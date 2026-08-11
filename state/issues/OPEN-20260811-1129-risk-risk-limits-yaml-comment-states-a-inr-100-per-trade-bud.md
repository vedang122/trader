---
severity: S3
area: risk
filed: 2026-08-11T11:29:18+05:30
title: risk_limits.yaml comment states a INR 100 per-trade budget while the file's own 0.75% enforces INR 75 - agents reading the constitution size 33% oversized
---

## Observed
## Observed
`state/risk_limits.yaml` line 9 reads:

    risk_per_trade_pct: 0.75        # INR 100 max loss to stop per trade (Module 9)

0.75% of the INR 10,000 capital_base is **INR 75**, not INR 100. The inline
comment is stale — it dates from when the limit was 1.0%, before the
2026-08-04 tightening (journal ts 2026-08-04T09:31:52, M&M cost-loaded-risk
overrun) took it 1.0 -> 0.75.

## Evidence
Enforced value, straight from the engine:

    $ python3 -m engine.risk size 188.29 184.50
    {"suggested_qty": 19, "risk_amount": 72.01}      # budget is 75, not 100

    $ python3 -c "from engine import risk; l=risk.limits(); \
      print(l['capital_base']*l['risk_per_trade_pct']/100)"
    75.0

`engine/risk.py` computes `max_risk = capital * risk_per_trade_pct / 100` = 75.0
and rejects above it. So the file's own comment contradicts the value the same
file enforces, by 33%.

## Why it matters (severity rationale)
This is the risk constitution, and agents read it directly — the risk-officer
and both analysts open this file for the per-trade budget rather than shelling
out to `engine.risk`. An agent trusting the comment sizes to a INR 100 budget
and produces tickets 33% oversized. The engine would REJECT them at the
enforcement layer, so this is **not** a safety hole (hence S3, not S1/S2) — the
two-brain rule holds and no bad order reaches a broker. The cost is wasted
committee/risk-gate cycles on tickets that were never admissible, plus an
agent-visible inconsistency in the one file the desk treats as law.

## Suggested fix
Correct the comment to `# INR 75 max loss to stop per trade (Module 9)`, or
better, drop the hardcoded rupee figure from the comment entirely so it cannot
drift again when the guardian auto-tightens `risk_per_trade_pct` (the guardian
halves this value on a 5% drawdown, which would falsify any literal figure
written there).

## Not fixed by the desk head
Per the desk charter I do not edit engine code or risk files; `risk_limits.yaml`
is amendable only through `engine.amend`, and this is a comment change, not a
limit change, so it needs the engineer, not an amendment.


## Engineer notes (append below)
