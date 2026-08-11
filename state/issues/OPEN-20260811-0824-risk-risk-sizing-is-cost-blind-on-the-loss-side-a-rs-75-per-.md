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
