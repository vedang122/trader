---
severity: S2
area: portfolio
filed: 2026-08-05T11:05:54+05:30
title: stop-lowering not engine-enforced
---

## Observed
Non-negotiable 'stops never move down' is enforced only by agent convention. Nothing in portfolio.apply_fill or execute.py rejects a ticket/state change that lowers an existing position's stop. An agent bug could silently widen risk. Proposed: apply_fill (or a dedicated update path) must reject stop < current stop for longs. Protected paths (portfolio.py/execute.py) — needs human-reviewed fix.

## Engineer notes (append below)

### 2026-08-06 engineer (cloud) — REPRODUCED, patch proposed, NOT applied

Confirmed exactly as filed, and the hole is wider than "an agent bug could widen risk":
nothing at *either* layer looks at the stop already guarding an open position.

- `portfolio.apply_fill` (portfolio.py:58) blind-writes the ticket's stop over the
  existing one: `pos.update({... "stop": stop ...})`. Add-on BUY into a held name →
  the old stop is gone.
- `risk.validate` (risk.py:59) sizes risk as `qty * (entry - stop)` on the *new* qty
  alone. It never reads `pf["positions"][sym]["stop"]`, so a looser stop on an add-on
  is invisible to the gate and the ticket PASSES.

Measured repro (10 shares @100 stop 98, then 10 more @101 stop 90): position ends at
qty 20, stop 90. Intended risk on the book was Rs.40; actual risk is now Rs.200 — a 5x
widening, unjournaled and unvetoed. `engine.status` then reports the loosened stop as
if it were the real one, so the desk's own risk display corroborates the error.

Regression tests committed with this note, in `tests/test_portfolio.py`:
`test_add_on_fill_cannot_lower_an_existing_stop` (unit, portfolio layer) and
`test_gate_rejects_a_ticket_that_lowers_an_open_position_stop` (end-to-end through
`execute.run`). Both are `@pytest.mark.xfail(strict=True)` so the suite stays green
while the defect is open AND turns loud the moment the patch lands — strict xfail
fails if the test starts passing, so **delete both markers in the same commit as the
fix**. Verify they fail against today's code with `pytest --runxfail`.

Two non-xfail control tests ship alongside them and pass today and after the patch:
`test_add_on_fill_may_raise_a_stop` (the rule is one-directional — tightening is
always legal) and `test_gate_still_passes_an_add_on_that_holds_the_stop` (guards
against over-tightening the gate into rejecting legitimate pyramiding). No existing
assertion was touched.

Design note on *where* to enforce. The issue proposes rejecting in `apply_fill`, but
`apply_fill` runs **after** `broker.place` has already filled (broker.py:29). Raising
there would abort a fill that really happened and desynchronise the book from the
broker — in live mode, catastrophically. So enforcement belongs at the gate, before
the order goes out, with `apply_fill` clamping defensively as a backstop rather than
raising. That is what the diff below does: `risk.validate` REJECTs (journaled as
`order_rejected` by the existing execute.py path, no change needed there), and
`apply_fill` keeps the tighter stop and journals `stop_lower_blocked` if anything ever
bypasses the gate.

Scope note: this covers stop-lowering on **entry tickets**. A hand-edit of
`state/portfolio.json` still bypasses everything — the engine cannot defend against
direct state edits, and that is a separate concern, not filed as an issue.

## Proposed patch (needs human)

Both files are protected paths, so nothing here has been applied. Verified locally:
with this diff the full suite is 53 passed / 1 failed under `pytest --runxfail`, and
the single failure is the unrelated, still-open
`OPEN-20260805-1105-broker-paperbroker-place-calls-last-price-unguarded` xfail. Both
xfail markers in `tests/test_portfolio.py` must be deleted as part of applying it.

```diff
diff --git a/engine/portfolio.py b/engine/portfolio.py
index 1102f1f..af18005 100644
--- a/engine/portfolio.py
+++ b/engine/portfolio.py
@@ -55,6 +55,13 @@ def apply_fill(pf: dict, symbol: str, side: str, qty: int, price: float,
             pos["qty"] = total
         else:
             pf["positions"][symbol] = pos = {"qty": qty, "avg_price": price}
+        if stop and pos.get("stop") and stop < pos["stop"]:
+            # Non-negotiable #2: stops never move down. The gate should have
+            # rejected this ticket; if one reaches here anyway, keep the tighter
+            # stop and leave a trace rather than silently widening risk.
+            common.journal({"type": "stop_lower_blocked", "symbol": symbol,
+                            "kept": pos["stop"], "rejected": stop})
+            stop = pos["stop"]
         pos.update({k: v for k, v in {"stop": stop, "target": target}.items() if v})
         pos.setdefault("opened", common.now_ist().date().isoformat())
         pos["thesis"] = meta.get("thesis", pos.get("thesis", ""))
diff --git a/engine/risk.py b/engine/risk.py
index c27324d..0f30049 100644
--- a/engine/risk.py
+++ b/engine/risk.py
@@ -53,6 +53,10 @@ def validate(order: dict, pf: dict, quotes: dict[str, float]) -> dict:
         if lm.get("stop_required", True) and not stop:
             v.append("no stop/invalidation on ticket — a trade without an exit is not a trade")
         if stop:
+            held = pf["positions"].get(sym)
+            if held and held.get("stop") and stop < held["stop"]:
+                v.append(f"stop {stop} is looser than the {held['stop']} already guarding "
+                         f"the open {sym} position — stops never move down")
             if stop >= entry:
                 v.append(f"stop {stop} must be below entry {entry} for a long")
             else:
```

Both halves are needed. The `risk.py` half is the real enforcement — it stops the order
before it reaches a broker, at the layer the constitution says is final. The
`portfolio.py` half is the backstop for any future caller that reaches `apply_fill`
without passing through `validate` (today `broker.place` is the only one, but nothing
in the code enforces that). Neither half changes behaviour for a first entry, an exit,
or an add-on that holds or tightens its stop.

Issue left OPEN pending human review of the diff above.
