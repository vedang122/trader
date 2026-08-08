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

### 2026-08-08 engineer(cloud) — area axis landed in the engine; one prose line still needs a human

The classification half of this issue is **fixed and merged**: `engine/issues.py`
now decides blocking deterministically instead of leaving it to a severity
glance. `list` rows gain `area`, `blocks_entries`, `age_hours` and `escalate`,
and a new `gate` subcommand answers the only question Phase 0 actually asks:

    $ python3 -m engine.issues gate      # against live state, this cycle
    {"entries_allowed": true, "blocking": [], "escalate": [],
     "counts": {"S1": 1, "S2": 10, "S3": 9}}

That `true` is the fix: the lone S1 is `area: ops`, which cannot reach an order.

**Design, and why it is the safe direction.** The rule is an allowlist of
*non*-blocking areas, not a list of blocking ones — `INFRA_AREAS = ("ops",
"ci", "issues")`, everything else blocks, mirroring `ops.NOTICE_ONLY`. So the
change can only ever un-block those three named areas; a new area invented
later, or a typo'd one, halts entries as before. This is deliberately narrower
than the direction suggested above: `scan`, `regime`, `news` and `data` all
feed marks, sizing or the exposure cap, so their S1s keep blocking. Tests pin
that (`test_s1_on_the_order_path_blocks_entries` covers nine order-path areas,
`test_unknown_area_blocks_fail_closed` covers the invented one).

**Escalation.** Any S1 open longer than `ESCALATE_AFTER_H = 24` is flagged
`escalate`, blocking or not — that is the "stuck across sessions" axis this
issue asked for, and it fires for infra S1s too, so a non-blocking S1 can no
longer sit unnoticed forever. The ops S1 above is at 23.8h and will surface on
the next cycle.

**Verified**: 26 new tests in `tests/test_issues.py`; full suite 91 passed,
5 xfailed. No existing assertion was altered.

## Proposed patch (needs human)

`.claude/skills/trade-cycle/SKILL.md` is protected, so Phase 0 still instructs
the desk to halt on *any* OPEN S1. Until this one line lands, a literal reading
of the skill still stands the desk down against the engine's verdict — the
engine says GO and the prose says NO. Applying it is what actually ends the
blockade:

```diff
--- a/.claude/skills/trade-cycle/SKILL.md
+++ b/.claude/skills/trade-cycle/SKILL.md
@@ -26,9 +26,12 @@
 - Stray `claude/*` branches in the preflight = the state auto-merge workflow
   is broken; flag it to the user in your final message every cycle until clean.
-- Also check `python3 -m engine.issues list`: any OPEN **S1** (safety) issue →
-  no new entries until it is closed. S2/S3 don't block, but repeat them in
-  your final message so they stay visible.
+- Also run `python3 -m engine.issues gate`: `entries_allowed: false` → no new
+  entries until every file it lists under `blocking` is closed. It gates on
+  area as well as severity, so an S1 in ops/ci/issues warns without barring the
+  book while every other area fails closed — do not second-guess it either way.
+  Name anything under `escalate` in your final message: that is a stuck S1 the
+  human must decide on. S2/S3 don't block, but repeat them so they stay visible.
```

No test can pin this half — it is agent-facing prose, not code. The engine-side
guarantees it depends on are already covered by `tests/test_issues.py`.

Issue left **OPEN** until that line lands.
