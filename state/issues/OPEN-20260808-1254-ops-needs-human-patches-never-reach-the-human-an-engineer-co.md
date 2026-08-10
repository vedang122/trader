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

### 2026-08-09 engineer(cloud) — option 3 landed; option 1 exercised once; issue stays OPEN

**Landed (allowed paths only).** `engine/issues.py` now decides needs-human
from the issue BODY instead of the diff's file list, which is the only place
the signal survives:

- `NEEDS_HUMAN_RE` matches a section *heading* ending `(needs human` — both
  forms the desk actually writes (`## Proposed patch (needs human)` and
  `## Suggested direction (needs human -- ...)`), case-insensitively.
  Deliberately a heading, not prose: five OPEN issues say "needs human-reviewed
  fix" inside an Observed paragraph while carrying no patch, and those must not
  flag.
- Front-matter `needs_human: true` is honoured as an explicit override.
- `list_issues()` rows carry `needs_human`; `gate()` carries a `needs_human`
  file list; new `python3 -m engine.issues pending-human` prints just the
  stranded set.

Against the real desk it finds all six, oldest first — the S1 merge gate, the
broker last_price guard, stop-lowering enforcement, the yfinance single-source
outage, the cancelled-merge stranding, and the ops-S1 severity axis.

**Option 1 exercised for this run**, per the issue's own "cheapest first":
this branch is being pushed with a draft PR opened by the engineer routine
itself, listing those six. That is the first time any of them has been in
front of the human — the S1 has now been waiting since 2026-08-07.

**Why this issue stays OPEN.** Detection is now deterministic and tested, but
detection is not delivery. The guarantee that a *future* run opens the PR
lives in the kautilya-engineer cron prompt, which is not a repo file and not
an allowed path — no commit here can encode it. The remaining change is one
line in that prompt, for the human to make:

> After committing, run `python3 -m engine.issues pending-human`; if it returns
> anything, open (or update) a draft PR listing those issues, because the merge
> gate will classify this commit `engine` and merge it with no PR.

Option 2 (classifier greps the diff) would make it structural, but
`.github/workflows/merge-cloud-state.yml` is protected and is already the
subject of the S1 above — worth folding into that same human edit rather than
filing a third workflow patch nobody can land.

Tests: `tests/test_issues.py` +8 (both heading forms, case, front-matter
override, prose-is-not-a-marker, closed issues drop out, API and CLI).
Suite 111 passed / 5 xfailed, was 103 / 5. `test_gate_is_clean_when_nothing_is_open`
was extended to the new key — still an exact-equality assertion, nothing relaxed.

### 2026-08-10 engineer(cloud) — root cause found: the PRs ARE opened, and the gate deletes them

The 2026-08-09 note above closed with "option 1 exercised for this run: this
branch is being pushed with a draft PR opened by the engineer routine itself."
That PR is gone, and so are the two before it. **Option 1 is not a cheap fix —
it is structurally impossible**, and this is why the queue has never moved.

**Mechanism.** The merge step's last line is

    git push origin --delete "${GITHUB_REF_NAME}"

Deleting a PR's head branch closes the PR. The engineer's draft PR is opened
from the same `claude/*` branch whose push triggered the workflow, so the run
merges the branch, deletes it, and closes the routine's PR — seconds later,
with no failure anywhere. Every step is "success".

**Measured on this repo** (`list_pull_requests(state=all)` + the run list):

| PR | branch | opened | closed | run for that branch |
|---|---|---|---|---|
| #11 | claude/engineer-risk-cli-unknown-subcommand | 11:22:50Z | **11:23:03Z** | 11:22:26Z → 11:23:05Z success |
| #10 | claude/engineer-needs-human-delivery | 07:23:04Z | **07:23:18Z** | same shape |
| #9 | claude/engineer-stop-lowering-enforcement | 07:36:09Z | 07:38:35Z | same shape |

13 seconds for #11, 14 for #10. The close lands *inside* its own run's window.
`list_branches` returns exactly one branch, `main` — nothing survives. This
also explains the S1's 2026-08-09 observation ("open PRs returns [], no
`claude/*` branch survives") without needing the never-opened hypothesis it
assumed: the PRs existed, briefly.

**Consequence for every prior engineer report.** Each run has truthfully ended
"needs the human's PR review" and each PR was destroyed before anyone could
see it. Eight patches are now stranded, the oldest 130h, including the S1 that
broke the self-repair loop.

## Landed this run (allowed path)

`engine/issues.py` gains `handoff()` + `python3 -m engine.issues handoff`: it
renders every pending-human issue into ONE markdown artifact carrying the
actual diffs, not pointers — `_stranded_patches()` lifts each `(needs human`
section verbatim, fences and caveats intact, from the marker heading to the
next heading of the same level or higher. Against the live desk it emits 327
lines covering all 8.

The point is that the artifact **carries no branch**. A GitHub Issue cannot be
closed by `git push --delete`, so that is where this run posts it. The engine
half of delivery is now deterministic and tested; what remains is choosing a
channel deletion cannot reach, which is a one-line instruction, not code.

Tests: `tests/test_issues.py` +4 — the patch survives the render, non-stranded
issues stay out, the empty case says so without emitting anything that looks
applicable, and the CLI runs against the real desk. Suite 148 passed / 8
xfailed, was 144 / 8. No existing assertion touched.

## Proposed patch (needs human)

The durable fix is one line in the protected workflow: stop deleting the branch
when a PR is open on it. `--delete` is what closes the PR, and it is only there
for branch hygiene, which `engine.ops` already audits.

```diff
--- a/.github/workflows/merge-cloud-state.yml
+++ b/.github/workflows/merge-cloud-state.yml
@@
           git merge "origin/${GITHUB_REF_NAME}" -X theirs --no-edit
           git push origin main
-          git push origin --delete "${GITHUB_REF_NAME}" || true
+          # Never delete a branch that has an open PR: deletion closes the PR,
+          # which is how the engineer routine's needs-human handoffs were lost
+          # (PR #11 open 13s). Hygiene without destroying the review channel.
+          if [ -z "$(gh pr list --head "${GITHUB_REF_NAME}" --state open --json number -q '.[]')" ]; then
+            git push origin --delete "${GITHUB_REF_NAME}" || true
+          fi
```

(needs `GH_TOKEN: ${{ github.token }}` on that step, as the PR step already has.)

Fold this into the SAME human edit as the S1's merge-gate diff — both are in
this one file, and neither can land without the other being re-verified.
