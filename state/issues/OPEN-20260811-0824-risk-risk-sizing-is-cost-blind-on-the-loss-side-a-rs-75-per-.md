---
severity: S2
area: risk
filed: 2026-08-11T08:24:26+05:30
title: risk sizing is cost-blind on the loss side: a Rs 75 per-trade budget sizes a position whose actual loss through the stop is Rs 100
---

## Observed
OBSERVED (pre-open cycle 2026-08-11)

engine.risk size computes quantity from the gross stop distance only. It
neither subtracts nor reports the round-trip transaction charges that are
realised when the stop is actually hit, so the desk's stated per-trade risk
budget is systematically understated at this capital.

EVIDENCE

risk_limits.yaml: capital_base 10000, risk_per_trade_pct 0.75  ->  budget Rs 75.

  python3 -m engine.risk size 192.50 187.40
    {"suggested_qty": 14, "risk_amount": 71.4}

  true worst case for that exact structure, using engine.charges:
    dist = 192.50 - 187.40 = 5.10 ; qty 14
    gross loss at stop          = 5.10 * 14                       =  71.40
    charges.round_trip(192.50, 187.40, 14)                        =  28.69
    ACTUAL loss through the stop                                  = 100.09

  Rs 100.09 realised vs Rs 71.40 reported vs a Rs 75 constitutional budget:
  a 40% overshoot of the reported figure and 33% over the budget.

Reproduced on a second structure the same cycle:
    entry 192.50 stop 186.75 qty 13 -> reported risk 74.75, actual 102.55.

ASYMMETRY THAT MAKES THIS A REAL GAP, NOT A ROUNDING NIT

The desk already models charges - but only on the winning side. The
cost-viability gate applies charges.round_trip to the entry->target leg and
rejects a trade whose costs exceed 25% of the expected gain. The identical
charge model is never applied to the entry->stop leg. So the desk is precise
about what a win costs and blind to what a loss costs, in a repo whose own
CLAUDE.md states "at this capital, transaction costs are the first adversary."

At Rs 10,000 with ~Rs 28-30 of round-trip friction per trade, this is not
noise: charges are ~40% of the entire per-trade risk budget.

CONSEQUENCE

Every position the desk opens risks materially more than the constitution
says. Three concurrent positions sized this way risk ~Rs 300 through their
stops against a stated ~Rs 225, and the max_daily_loss_pct 3.0 breaker
(Rs 300) can therefore be breached by three stop-outs that each individually
looked compliant. The drawdown guardian then reacts to a drawdown the sizing
math never predicted.

SUPPORTING DOC INCONSISTENCY (same confusion, worth fixing together)

state/risk_limits.yaml line comment reads:
    risk_per_trade_pct: 0.75        # Rs 100 max loss to stop per trade (Module 9)
0.75% of 10,000 is Rs 75, not Rs 100. A human reading the risk constitution is
told Rs 100 while the enforced number is Rs 75 - and, by coincidence, Rs 100 is
roughly the true cost-inclusive loss. The comment should state the enforced
figure and say explicitly whether the budget is meant to be pre- or post-cost.

SUGGESTED FIX (engine owns the implementation)

Decide and document which the budget means, then make the code agree:
either size so that gross_loss + round_trip_charges <= budget, or keep gross
sizing but have engine.risk size return both numbers, e.g.
    {"suggested_qty": 13, "risk_amount": 66.3, "risk_amount_after_costs": 94.6}
so the risk-officer sees the real number at approval time. The second is the
smaller change and preserves the current gate semantics.

NOT A DUPLICATE of the open S3 "engine.risk size ignores notional/cash/gross
caps" - that one is about position-size caps; this is about the loss side of
the risk budget being cost-blind. They can be fixed independently.

## Engineer notes (append below)

### 2026-08-11 engineer(cloud) — reproduced exactly; fix is in protected engine/risk.py

Both evidence structures reproduce to the paisa against the live charge model,
so nothing here rests on the filer's arithmetic:

    entry 192.50 stop 187.40 -> qty 14, gross 71.40, round_trip 28.69, realised 100.09
    entry 192.50 stop 186.75 -> qty 13, gross 74.75, round_trip 27.80, realised 102.55

Budget is Rs 75 (capital_base 10000 x risk_per_trade_pct 0.75). Confirmed the
asymmetry is real and not incidental: `validate()` imports `charges.round_trip`
for the entry->target cost-drag gate at engine/risk.py:70-71, and the identical
model is never applied to entry->stop. `suggest_qty` is a pure
`budget // per_share` divide.

**What landed this commit**: `tests/test_risk_sizing_costs.py` only. Three tests
reproduce the gap and guard the two keys the risk-officer reads today
(`suggested_qty`, `risk_amount`) so the fix cannot silently drop them; two are
strict-xfail tripwires asserting the fixed behaviour. Applying the patch below
turns those two green, which turns the suite RED (strict xfail) — that is
deliberate. Delete both `@pytest.mark.xfail` markers in the same change that
applies the patch.

**Recommended fix is DISCLOSURE, not resizing** — this is the issue's own
second option, and the reason matters. Sizing to `gross + charges <= budget`
cuts every position by roughly a third:

| structure | qty today | qty if cost-inclusive | realised loss at new qty |
|---|---|---|---|
| 192.50 / 187.40 | 14 | 9 | 70.93 |
| 192.50 / 186.75 | 13 | 8 | 70.60 |
| 100.00 / 98.00  | 37 | 23 | 72.94 |

A ~35% cut in position size across the book is a constitutional change to how
much the desk trades, not a defect repair, and it interacts with the cost-drag
gate (smaller qty raises cost drag as a share of gain, so some trades that pass
today would newly fail). That decision belongs to the human. The patch below
therefore leaves enforcement semantics **exactly** as they are — no verdict
changes for any order — and only makes the true number visible: `size` gains
`risk_amount_after_costs` and `suggested_qty_after_costs`, and `validate()`
gains one note, `"risk after costs N vs budget M"`, so the risk-officer sees it
at approval time. `suggest_qty_after_costs` is supplied ready to use if the
human later decides to enforce it.

**Verified**: patch applies clean to current main (`git apply --check`); with
both xfail markers deleted the full suite is **161 passed, 8 xfailed**. No
existing assertion was altered, and no order's PASS/REJECT verdict changes —
the only diff in gate output is one added note.

Not addressed here (separate open issue, correctly filed as its own):
`OPEN-20260811-1129-risk`, the risk_limits.yaml comment claiming Rs 100 against
an enforced Rs 75. It is the same confusion but lives in `state/`, which an
engineer run must not touch.

## Proposed patch (needs human)

```diff
diff --git a/engine/risk.py b/engine/risk.py
index c27324d..de2d544 100644
--- a/engine/risk.py
+++ b/engine/risk.py
@@ -23,6 +23,24 @@ def suggest_qty(capital: float, entry: float, stop: float, risk_pct: float) -> i
     return int((capital * risk_pct / 100) // per_share)
 
 
+def realised_loss(entry: float, stop: float, qty: int) -> float:
+    """What a stop-out actually costs: the gross distance plus the round trip.
+    Sizing that ignores the second term understates the loss by ~40% at this
+    capital, where charges are a large fraction of the per-trade budget."""
+    from engine import charges as ch
+    return round(qty * abs(entry - stop) + ch.round_trip(entry, stop, qty), 2)
+
+
+def suggest_qty_after_costs(capital: float, entry: float, stop: float,
+                            risk_pct: float) -> int:
+    """Largest qty whose cost-inclusive loss still fits the per-trade budget."""
+    budget = capital * risk_pct / 100
+    q = suggest_qty(capital, entry, stop, risk_pct)
+    while q > 0 and realised_loss(entry, stop, q) > budget:
+        q -= 1
+    return q
+
+
 def validate(order: dict, pf: dict, quotes: dict[str, float]) -> dict:
     """Return {'verdict': 'PASS'|'REJECT', 'violations': [...], 'notes': [...]}"""
     lm, rg = limits(), regime()
@@ -61,6 +79,8 @@ def validate(order: dict, pf: dict, quotes: dict[str, float]) -> dict:
                 if risk_amt > max_risk * 1.02:  # 2% rounding tolerance
                     v.append(f"risk to stop {risk_amt:.0f} exceeds per-trade limit {max_risk:.0f} "
                              f"(suggest qty <= {suggest_qty(capital, entry, stop, lm['risk_per_trade_pct'])})")
+                notes.append(f"risk after costs {realised_loss(entry, stop, qty):.0f} "
+                             f"vs budget {max_risk:.0f}")
                 if target:
                     rr = (target - entry) / (entry - stop)
                     if rr < lm["min_risk_reward"]:
@@ -99,8 +119,12 @@ if __name__ == "__main__":
     if len(sys.argv) > 1 and sys.argv[1] == "size":
         _, _, entry, stop = sys.argv
         lm = limits()
-        q = suggest_qty(lm["capital_base"], float(entry), float(stop), lm["risk_per_trade_pct"])
+        entry, stop = float(entry), float(stop)
+        q = suggest_qty(lm["capital_base"], entry, stop, lm["risk_per_trade_pct"])
         print(json.dumps({"suggested_qty": q,
-                          "risk_amount": round(q * abs(float(entry) - float(stop)), 2)}))
+                          "risk_amount": round(q * abs(entry - stop), 2),
+                          "risk_amount_after_costs": realised_loss(entry, stop, q),
+                          "suggested_qty_after_costs": suggest_qty_after_costs(
+                              lm["capital_base"], entry, stop, lm["risk_per_trade_pct"])}))
     else:
         print(json.dumps({"limits": limits(), "regime": regime()}, indent=2))
```

Issue left **OPEN**: the defect is live in `engine/risk.py` until a human
applies the diff above and deletes the two xfail markers.
