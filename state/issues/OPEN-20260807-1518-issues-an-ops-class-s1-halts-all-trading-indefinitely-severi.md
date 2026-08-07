---
severity: S2
area: issues
filed: 2026-08-07T15:18:13+05:30
title: an ops-class S1 halts all trading indefinitely: severity gating has no area axis and no escalation path, desk lost a full session
---

## Observed
## Observed
The desk has now stood down for FIVE consecutive cycles across an entire NSE
session (2026-08-07: ~11:30, 13:18, 14:18, 15:17 + earlier) with zero entries
considered, because trade-cycle Phase 0 says:

    "any OPEN S1 (safety) issue -> no new entries until it is closed"

and the only OPEN S1 is
OPEN-20260807-1305-ops-merge-gate-strands-any-engine-class-branch-whose-base-dr.md

That S1 is a GitHub Actions defect in the state-merge workflow. It cannot
place, mis-size, or fail to exit an order. It is entirely outside the order
path: engine/risk.py, engine/execute.py and engine/broker.py are untouched by
it, and preflight this cycle returned GO with feed ok, 0 stray branches,
0 behind main.

## The gap
The Phase 0 rule treats severity as a single axis, so an ops/CI-class S1
produces exactly the same total trading blockade as "the desk cannot exit a
position" or "the risk gate can be bypassed" would. There is:
  - no distinction between order-path S1 and infrastructure S1;
  - no expiry, escalation, or human-notification path when a blocking S1 stays
    open across sessions -- the desk simply goes quiet indefinitely and each
    cycle reports the same stand-down;
  - no bound on how long the blockade can run.

The failure mode is silent-by-construction: every cycle looks disciplined and
correct in isolation, and only the journal across cycles shows the desk has
not evaluated a single candidate all day.

## Evidence (this cycle, 2026-08-07T15:17 IST)
    $ python3 -m engine.ops preflight
    {"verdict": "GO", "reasons": [], "notices": [], ...
     "feed": {"status": "ok", "detail": "yfinance live"}}

    $ python3 -m engine.issues list   # -> Counter({'S2': 10, 'S3': 8, 'S1': 1})
    S1 | merge gate strands any engine-class branch whose base drifted ...

    $ grep -n checkout .github/workflows/merge-cloud-state.yml
    54:  git checkout origin/${GITHUB_REF_NAME} -- .
    57:  git checkout -- .          # still unfixed; last workflow commit b776ad0

    Book: flat, 0/3 positions, cash 9991.98, no alerts.
    Scan: 15/15 symbols source=yf, errors []. Data was fine all session.

## Suggested direction (engineer's call, not the desk's)
Classify blocking severity by AREA as well as level -- e.g. only S1 in
{risk, execute, broker, portfolio, amend, common} halts entries, while S1 in
{ops, ci, news, regime, scan} loudly warns and escalates but does not gate the
book. Alternatively keep the blanket rule but add a hard escalation: if a
blocking S1 survives N cycles, the desk must surface it to the human as a
decision item rather than silently repeating the stand-down.

Filed by the desk head, NOT acted upon: entries stayed barred this cycle per
the rule as written. This issue only asks that the rule be reviewed.

## Engineer notes (append below)
