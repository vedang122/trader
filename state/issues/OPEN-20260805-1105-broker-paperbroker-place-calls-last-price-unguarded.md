---
severity: S2
area: broker
filed: 2026-08-05T11:05:54+05:30
title: PaperBroker.place calls last_price unguarded
---

## Observed
engine/broker.py:20 — PaperBroker.place() calls data.last_price(sym) outside try/except. execute.py now pre-checks the quote path, but a quote source dying between execute's check and place() still crashes mid-order instead of returning a clean failure. Protected path (broker.py) — needs human-reviewed fix. Evidence: 2026-08-04 execution-blindness incident, journal 11:50 IST entry.

## Engineer notes (append below)

### 2026-08-06 engineer (cloud) — REPRODUCED, patch proposed, NOT applied

Confirmed exactly as filed. Repro: make `data.last_price` succeed on its first call
(execute.py's pre-check, execute.py:19) and raise on the second (broker.py:20). The
`RuntimeError` propagates straight out of `execute.run` — no journal entry, no verdict,
no `order_rejected`. The caller sees a traceback where the constitution promises a clean
stand-down. The book is not corrupted (nothing is mutated before the fetch), so the damage
is blindness, not a ghost fill.

Regression test committed with this note: `tests/test_execute.py::
test_quote_dying_between_gate_and_fill_rejects_not_crashes`. It asserts the correct
end-state (result != EXECUTED, portfolio untouched, failure journaled) and is marked
`@pytest.mark.xfail(strict=True)` so the suite stays green while the defect is open AND
turns loud the moment the patch below lands (strict xfail fails if the test starts passing
— remove the marker in the same commit as the fix). Verify with `pytest --runxfail`, which
shows it failing against today's code. No existing assertion was touched.

Scope note: `KiteBroker.place` (broker.py:69) and `GrowwBroker.place` (broker.py:132) call
`data.last_price` through the same unguarded path. Left out of this patch deliberately —
they are live-mode-only and mirror a *placed* order, so a clean-failure return there would
be wrong (the order is already at the exchange; the right answer is a reconcile, not a
FAILED). That needs its own design pass; not filed as a new issue because it is the same
line of code under different semantics.

## Proposed patch (needs human)

Both files are protected paths, so nothing here has been applied. Verified locally: with
this diff the full suite is 43 passed under `pytest --runxfail` (0 failures), and the
xfail marker on the new test must be deleted as part of applying it.

```diff
diff --git a/engine/broker.py b/engine/broker.py
index 398ebf9..105e396 100644
--- a/engine/broker.py
+++ b/engine/broker.py
@@ -17,7 +17,13 @@ class PaperBroker:
     def place(self, order: dict) -> dict:
         from engine import charges, risk
         sym, side, qty = order["symbol"].upper(), order["side"].upper(), int(order["qty"])
-        ltp = data.last_price(sym)
+        try:
+            ltp = data.last_price(sym)
+        except Exception as e:
+            # A source can die between execute.py's pre-check and this fetch.
+            # Nothing has been mutated yet, so fail clean rather than crash.
+            return {"status": "FAILED", "broker": "paper", "symbol": sym, "side": side,
+                    "qty": qty, "error": f"no quote at fill time: {type(e).__name__}: {e}"[:160]}
         slip = risk.limits().get("slippage_bps", 5) / 10_000
         px = ltp * (1 + slip) if side == "BUY" else ltp * (1 - slip)
         px = round(px, 2)
diff --git a/engine/execute.py b/engine/execute.py
index 9965b21..c375df5 100644
--- a/engine/execute.py
+++ b/engine/execute.py
@@ -44,6 +44,11 @@ def run(ticket_path: str, check_only: bool = False) -> dict:
                 "violations": [f"market is {market['phase']} — live orders only during session"]}
 
     fill = broker.get_broker().place(order)
+    if fill.get("status") == "FAILED":
+        common.journal({"type": "order_failed", "ticket": ticket_path,
+                        "order": order, "fill": fill})
+        return {"result": "FAILED", "fill": fill,
+                "violations": [fill.get("error", "broker could not fill the order")]}
     common.journal({"type": "fill", "ticket": ticket_path, "order": order, "fill": fill,
                     "conviction": order.get("conviction"),
                     "thesis": order.get("thesis"), "strategy_tag": order.get("strategy_tag")})
```

Why the change spans two files: guarding broker.py alone is not enough. If `place()`
returned a `FAILED` dict and `execute.run` kept its current path, the desk would journal a
`fill` and report `EXECUTED` for an order that never happened — a worse failure than the
crash. The `execute.py` half is what makes the guard honest. `__main__` already exits 2 for
any result outside `(EXECUTED, WOULD_PASS)`, so `FAILED` gets the correct exit code with no
further change.

Issue left OPEN pending human review of the diff above.
