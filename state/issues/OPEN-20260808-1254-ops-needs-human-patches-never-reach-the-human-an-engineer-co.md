---
severity: S2
area: ops
filed: 2026-08-08T12:54:34+05:30
title: needs-human patches never reach the human: an engineer commit touching only allowed paths classifies as engine, auto-merges, and no PR is ever opened
---

## Observed
## Observed
Two protected-path fixes are fully written, tested and sitting in issue files
that nobody is being shown:

- OPEN-20260807-1305-ops (S1, merge gate): unified diff for
  .github/workflows/merge-cloud-state.yml, appended 2026-08-07.
- OPEN-20260807-1518-issues (S2, this run): unified diff for
  .claude/skills/trade-cycle/SKILL.md.

`gh pr list --state open` on 2026-08-08 returns **empty**. Neither patch has
ever been surfaced. The S1 has been waiting a full day.

## Mechanism
The engineer routine is instructed, correctly, that when a fix lives in a
protected file it must NOT edit that file — it appends a "Proposed patch
(needs human)" section to the issue and commits "only the issue file + test".

But that commit then touches only `state/issues/`, `tests/` and `engine/` —
all ALLOWED paths. So merge-cloud-state.yml's classifier returns
`class=engine`, not `protected`. Tests pass, the merge step runs, main
advances, the branch is deleted, and the "Open PR instead" step is skipped
because it is gated on `class == 'protected' || tests != success`.

The result: the *description* of a protected-path change is silently merged as
an ordinary engine change. The protected file is never in the diff, so nothing
in the pipeline ever classifies the work as needing review. The routine
correctly reports "needs the human's PR review" — and no PR exists.

## Why this is not the already-filed stranding bug
OPEN-20260807-0853-ops and OPEN-20260807-1305-ops both describe a branch that
fails to merge and is silently dropped. This is the inverse: the branch merges
perfectly. Nothing fails. The gap is that a successful merge is the WRONG
outcome for a commit whose payload is a request for human action, and no
signal distinguishes the two.

## Impact
The desk's escape hatch for protected code is a no-op. Every protected-path
defect the engineer diagnoses accumulates as prose in state/issues/ that only
another engineer run will ever read. Both currently-blocked fixes — including
the S1 that broke the self-repair loop itself — are stuck behind this.

## Suggested direction
The proposed-patch marker, not the file list, should drive classification.
Options, cheapest first:
1. Engineer routine opens the PR itself (it has GH tooling) instead of relying
   on the workflow's fallback — no protected file changes.
2. Classifier greps the diff for a new `## Proposed patch (needs human)`
   heading under state/issues/ and forces `class=protected`.
3. A `needs-human:` front-matter key on the issue, set by engine.issues, that
   the workflow reads. This is the only option that stays testable in Python.

Option 1 needs no protected-path edit at all and could land immediately.
Filed by the engineer routine, 2026-08-08, while handling
OPEN-20260807-1518-issues.

## Engineer notes (append below)
