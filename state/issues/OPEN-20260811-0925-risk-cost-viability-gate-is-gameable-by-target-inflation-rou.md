---
severity: S2
area: risk
filed: 2026-08-11T09:25:09+05:30
title: cost-viability gate is gameable by target inflation: round-trip cost is invariant to the target while the gate denominator scales with it, so +Rs 1.00 on the target flips FAIL to PASS
---

## Observed
## Observed
OBSERVED (cycle 2026-08-11 09:20 IST, market open)

The 25% cost-viability gate is trivially satisfiable by inflating the TARGET,
because round-trip charges are almost completely INVARIANT to the target while
the gate's denominator (expected gain) scales linearly with it. The gate
therefore does not measure what it claims to measure, and it actively rewards
the one input the desk has full discretion over and never verifies.

EVIDENCE (TATASTEEL, entry 192.60 / stop 187.40, qty 14, notional Rs 2,696)

  target    R:R    gross gain   round-trip cost   drag     gate
  200.50    1.52       110.6         29.10        26.3%    FAIL
  201.50    1.71       124.6         29.13        23.4%    PASS
  202.00    1.81       131.6         29.15        22.2%    PASS
  203.00    2.00       145.6         29.18        20.0%    PASS

Reproduce:
  python3 - <<EOF
  from engine import charges
  entry, stop, qty = 192.60, 187.40, 14
  for tgt in (200.50, 201.50, 202.00, 203.00):
      gain = (tgt - entry) * qty
      rt = charges.round_trip(entry, tgt, qty)
      print(tgt, round(gain,1), round(rt,2), round(100*rt/gain,1))
  EOF

Moving the target UP by Rs 1.00 changes the modelled cost by 3 paise (29.10 ->
29.13) but moves the drag 26.3% -> 23.4% and flips the verdict FAIL -> PASS.
Cost varies 0.3% across the entire target range while drag varies 31%.

WHY THIS IS A SAFETY ISSUE, NOT A MODELLING NIT

The technical-analyst independently identified this on today's board WITHOUT
being told the gate mechanics. Its verdict, verbatim: the honest nearest
resistance shelf is the mid-June consolidation at ~199.9-200.95; a target of
200.50 there gives R:R 1.52 and FAILS the cost gate at 26%; the 203.00 target
that PASSES at 20.0% is "the maximum defensible number, not the central one",
and it is "suspicious that it lands just inside the gate boundary while the
honest shelf fails it."

So the gate's incentive gradient points AWAY from the chart: the analyst that
reports the honest target gets its trade rejected, and the analyst that
stretches the target to the outer edge of the S&R padding tolerance gets its
trade approved. The desk's own lesson file already names this failure mode
(state/lessons/desk.md, 2026-08-08, trial): "possible systematic tendency to
engineer TO the gate rather than THROUGH it with margin", evidence TATASTEEL
veto 2026-08-04T15:28:25. That lesson treated it as an agent behavioural
tendency. This issue shows the gate's own arithmetic is what produces the
incentive - it is a mechanism defect, not only a discipline problem.

Compounding: min_risk_reward is 2.0 and the cost gate is 25%. At this capital
those two constraints are near-collinear - for typical Rs 190-1,100 names the
target that satisfies R:R 2.0 lands at drag ~20-21%, just inside the gate. So
almost every structure the desk can legally build arrives at BOTH gates
simultaneously and at their boundary, which is precisely the "boundary-fit
ticket" pattern the desk lesson says to treat as failing.

CONSEQUENCE

The gate cannot distinguish a genuinely cost-viable trade from one whose
target was stretched to clear it. Every approval it grants is conditional on a
target nobody validates against the chart, so the desk's headline protection
against transaction costs at Rs 10,000 capital is, as implemented, an
unenforced honour system.

SUGGESTED FIX (engine owns the implementation; do NOT let a trader pick)

Options, smallest first:
1. Report, do not just gate: have the risk path emit the target-sensitivity,
   e.g. the minimum target that clears the gate ("gate clears at target >=
   201.35") so the risk-officer can see how much of the pass is target-stretch
   and compare it against the analyst's stated structural level.
2. Gate on a target the desk did not choose freely: measure drag against an
   ATR-anchored or S&R-anchored reference target rather than the ticket's own
   target.
3. Require the ticket to carry the structural basis for its target (a named
   S&R level or ATR multiple) and have the gate reject targets that exceed
   that level by more than the playbook's padding tolerance.

NOT A DUPLICATE of the open S3 "scan score is blind to the cost gate" (that is
about board ranking) nor of the open S2 "risk sizing is cost-blind on the loss
side" (that is the loss leg). This is the gain leg's denominator being
attacker-controlled. All three are independent.

## Engineer notes (append below)


## Engineer notes (append below)
