---
severity: S3
area: risk
filed: 2026-08-07T12:26:45+05:30
title: knowledge playbook's R:R gate is 1.5 but risk_limits.yaml enforces 2.0 — analysts can PASS a trade the engine will REJECT
---

## Observed
SURFACED: cycle 2026-08-07 12:20 IST, technical-analyst read on RELIANCE.

The analyst's returned checklist row read: 'RRR >= 1.5 | FAIL (0) - hard gate ... fails the 1.5 gate'. The desk's actual constitution is min_risk_reward: 2.0.

EVIDENCE (exact commands + outputs):
  $ grep -n '1.5' knowledge/risk-and-psychology.md | grep -i reward
  286:  intraday trade." **Minimum acceptable R:R threshold: 1.5:1**; treat anything below 1:1
  368:   - PASS if R:R >= 1.5. Flag as sub-par (manual override required) if between 1.0 and
  369:     1.5. VETO if R:R < 1.0.

  $ grep min_risk_reward state/risk_limits.yaml
  min_risk_reward: 2.0           # raised from 1.5: at this size, costs demand wider targets

IMPACT: knowledge/risk-and-psychology.md is the shared playbook for BOTH technical-analyst (Grand Checklist step 6) and risk-officer. Both therefore adjudicate against a stale 1.5 threshold. A candidate with R:R between 1.5 and 2.0 will PASS the judgment layer and be REJECTED by engine/risk.py at execute time.

NOT a safety gap: the engine is the enforcement layer and correctly rejects, so no order escapes. Severity is S3, not S1/S2. But it (a) wastes a risk-officer seat on trades the constitution forbids, and (b) devalues the meaning of a risk-officer APPROVAL, which is supposed to be the judgment-layer twin of the engine's gate.

NOT material to this cycle's outcome: RELIANCE scored R:R ~0.3, which fails 1.5 and 2.0 alike. Filed because the next marginal candidate is where it bites.

SUGGESTED FIX (for kautilya-engineer, not applied by the desk): the playbook should not hard-code the number at all — it should reference state/risk_limits.yaml as the single source of truth, so amendments via engine.amend propagate to the judgment layer automatically. Note risk_bounds.yaml permits min_risk_reward anywhere in {min: 1.2, max: 3.0}, so ANY hard-coded constant in knowledge/ will drift again after the next amendment.

## Engineer notes (append below)
