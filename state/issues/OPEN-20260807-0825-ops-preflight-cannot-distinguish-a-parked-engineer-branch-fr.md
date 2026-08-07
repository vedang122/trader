---
severity: S2
area: ops
filed: 2026-08-07T08:25:13+05:30
title: preflight cannot distinguish a parked engineer branch from a broken state auto-merge; a deliberately-parked branch forecloses ALL new entries indefinitely
---

## Observed
Observed 2026-08-07 08:16 IST (cloud pre-open cycle).

python3 -m engine.ops preflight returns:
  verdict: STAND_DOWN
  reasons: ["unmerged run branches (merge workflow broken?): [origin/claude/engineer-stop-lowering-enforcement]"]
  state: {fetch_ok: true, behind_main: 0, ahead_main: 0}
  feed: {status: ok, detail: yfinance live}

Everything else is healthy: feed ok, not behind main, guardian clean, no OPEN S1.
The SOLE reason the desk is barred from entering is the existence of one remote
branch.

That branch is not a broken merge. It is a deliberate park:
  git log --oneline origin/main..origin/claude/engineer-stop-lowering-enforcement
  0af5709 engineer(cloud): stop-lowering-not-engine-enforced - reproducing tests + proposed patch (needs human)
and its own journal entry (2026-08-06T17:01:42, engineer_report) records
status "needs_human" with the issue left OPEN by design, because the fix
requires accepting a SKILL.md change a human must approve.

There is no open PR for it (github list_pull_requests state=open -> []), so
nothing will merge it on its own.

CONSEQUENCE: per .claude/skills/trade-cycle/SKILL.md Phase 0, STAND_DOWN means
"no new entries this cycle, period." Since the branch is parked pending a human
and nothing inside the desk may merge or delete it, EVERY future cycle trips the
same STAND_DOWN. The desk is now indefinitely foreclosed from trading by a
repo-hygiene condition, not by any market or risk judgment. The trading system
has been disabled as a side effect of the engineering system working as intended.

Note the check is not simply wrong -- there IS genuinely unmerged state on that
branch. Verified: its last journal line
  {"ts": "2026-08-06T21:15:50+05:30", "type": "engineer_report", ...}
is absent from main. So main journal.jsonl has a real audit-trail gap. The defect
is the conflation, not the detection.

SUGGESTED DIRECTION (not a patch -- desk head does not edit engine code):
distinguish the two cases. E.g. treat a branch whose head commit is an
engineer(cloud) park with a needs_human journal entry as a NOTICE (report it,
do not STAND_DOWN), and reserve STAND_DOWN for branches that carry unmerged
state with no parking record -- or gate on whether the unmerged content touches
state/ files the desk actually reads (portfolio, regime, limits) versus
journal/issue append-only lines. Alternatively give ops a way to acknowledge a
known-parked branch so it stops re-tripping.

## Engineer notes (append below)
