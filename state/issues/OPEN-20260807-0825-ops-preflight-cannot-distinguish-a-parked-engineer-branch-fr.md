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

---

## CORRECTION appended by desk head, same cycle (2026-08-07 ~08:35 IST)

The premise above ("that branch is not a broken merge, it is a deliberate park")
is **incomplete and partly wrong**. Checked the Actions history afterwards and
found the real cause. Both facts are true, but the second is the operative one:

- Workflow run **31142779344** (`merge-cloud-state.yml`, this cycle's own state
  push) -> `completed / success`. The auto-merge workflow is **healthy**.
- Workflow run **31117366902**, head branch
  `claude/engineer-stop-lowering-enforcement`, head sha `0af5709`, job `merge`
  (id 92670237013): started 2026-08-06T15:46:47Z, completed 2026-08-06T16:01:48Z,
  conclusion **`cancelled`** — after ~15 minutes.

So the branch was NOT left stranded by design and NOT by a policy decision. Its
merge job was cancelled mid-run, which means **neither** the "Merge into main"
step **nor** the "Open PR instead" fallback ever executed. That is exactly why
`list_pull_requests(state=open)` returns `[]` AND why the branch was never
merged or deleted: the job died in between the two outcomes, in the one window
where the workflow produces no artifact and no notification at all.

Its diff is `state/issues/...md`, `state/journal.jsonl`, `tests/test_portfolio.py`.
Per the classifier that is CLASS=**engine** (the `tests/` path is allowlisted but
is not `^state/`), so it runs the pytest step — which is where the ~15 minutes
went before the cancellation.

WHAT THIS CHANGES:
1. The preflight conflation described above is still a genuine defect worth
   fixing — a STAND_DOWN that no in-desk action can clear will keep disabling
   trading — but its trigger here was an infrastructure cancellation, not a
   deliberate park. Fix the classifier reasoning accordingly.
2. There is a second, likely more urgent defect: **a cancelled merge job is a
   silent hole.** The workflow has a merge path and a PR path, and assumes one
   of them always runs. Cancellation (or a timeout) satisfies neither, and
   nothing anywhere reports it. The desk then discovers the consequence a day
   later, as an unexplained permanent STAND_DOWN. Consider an
   `if: always()`/`if: cancelled()` step that opens the PR (or at minimum files
   a desk issue) whenever the job ends without having merged, plus an explicit
   `timeout-minutes` on the pytest step so a hang fails loudly instead of
   hanging until something reaps it.
3. Note also `concurrency: {group: merge-cloud-state, cancel-in-progress: false}`
   serialises every cloud push through one group. A ~15-minute pytest step
   inside that group is a long lock, and queued runs can be cancelled while
   pending. Worth checking whether the test step is genuinely that slow or
   whether it hangs.

IMMEDIATE HUMAN ACTION that unblocks the trading desk (cheapest first): simply
**re-run workflow run 31117366902**. The engineer reported its suite green
locally ("49 passed, 1 xfailed"), so a completed run should either auto-merge
the branch and delete it, or open the review PR — either outcome clears the
stray branch and ends the desk's STAND_DOWN. If it is instead intended to stay
parked pending human review, opening the PR for it also clears preflight,
because preflight's complaint is the unmerged branch, not the unfixed bug.

Log content for job 92670237013 is no longer downloadable (HTTP 404, expired),
so the precise cancellation reason could not be recovered; the conclusion field
and timings above are from the Actions API and are exact.
