---
severity: S1
area: ops
filed: 2026-08-07T13:05:07+05:30
title: merge gate strands any engine-class branch whose base drifted: the test step leaves the index staged, so git merge aborts and the PR fallback never fires
---

## Observed
Root cause of the stranding described in
OPEN-20260807-0853-ops (which guessed cancellation/timeout/network hang).
The real mechanism is deterministic and reproducible; the cancellation was a
separate, earlier symptom on the same branch.

## Mechanism
merge-cloud-state.yml, "Run tests (engine-class diffs)" step:

    git checkout origin/${GITHUB_REF_NAME} -- .   # writes index AND worktree
    pip install -q -r requirements.txt pytest
    python -m pytest tests/ -q
    git checkout -- .                             # restores worktree FROM THE INDEX

`git checkout <ref> -- .` stages every overlaid file. The cleanup
`git checkout -- .` restores the worktree from that same polluted index, so it
un-does nothing: the index is still staged over HEAD when the merge step runs.
`git merge` then refuses with

    error: Your local changes to the following files would be overwritten by merge
    Merge with strategy ort failed.        (exit 2)

Reproduced locally against origin/main and origin/claude/engineer-stop-lowering-enforcement:
33 files staged after the "cleanup", merge aborts.

## Why it is intermittent (this is a race, not a constant)
The staged overlay only differs from HEAD for files where the BRANCH and MAIN
disagree. So:

- branch forked at main's tip -> overlay == HEAD for everything except the
  branch's own new files, and the merge brings those with identical content,
  so git allows it. Verified: MERGE SUCCESS.
- main advanced since the branch forked -> the overlay REVERTS main's newer
  files in the index, and the merge wants to touch them. Verified: MERGE FAILS.

Cycle runs push state/ every ~30 minutes, so any engineer branch whose merge
job starts more than about one cycle after it forked loses the race. Fast
pushes merge (31144110893, 31144196282, 31097664570, 31081077389 all succeeded);
the slow one stranded. This is why the failure looked random.

## Why it is silent
Step 5 "Merge into main" fails with exit 2. Step 6 "Open PR instead" is
gated on

    class == 'protected' || (class == 'engine' && tests.outcome != 'success')

Tests PASSED (51 passed, 3 xfailed in 8.6s) and the class is engine, so the
fallback is SKIPPED. The job ends "failure" having neither merged nor opened a
PR, and nothing notifies anyone -- the same silent hole
OPEN-20260807-0853-ops describes, reached by a third path that issue did not
identify.

## Evidence
Run 31117366902 attempt 2 (2026-08-07T07:30Z), job 92801353508:
step 4 "Run tests" success (27s), step 5 "Merge into main" FAILURE,
step 6 "Open PR instead" SKIPPED. Log excerpt above. Attempt 1 of the same run
(job 92670237013, 2026-08-06) was the ~15-minute CANCELLED job already filed.

## Impact
Every engineer fix that does not win the race against the next cycle push is
silently discarded. The desk's self-repair loop looks like it works and does
not. state-only cycle pushes are unaffected (class=state skips the test step,
so the index is never polluted) -- which is why trading kept working while
engineering quietly did not.

## Suggested direction (needs human -- .github/** is protected)
One-line fix, replace the cleanup with a real reset:

```diff
       - name: Run tests (engine-class diffs)
         if: steps.classify.outputs.class == 'engine'
         id: tests
         continue-on-error: true
+        timeout-minutes: 10
         run: |
           git checkout origin/${GITHUB_REF_NAME} -- .
           pip install -q -r requirements.txt pytest
           python -m pytest tests/ -q
-          git checkout -- .
+          git reset -q --hard HEAD
```

`git reset --hard HEAD` clears index and worktree together; `git checkout -- .`
cannot, because it reads from the index it is meant to be undoing. Testing the
overlay in a `git worktree` (or a separate clone) would be cleaner still, since
it never touches the merge checkout at all.

Independently, and per OPEN-20260807-0853-ops, the job needs a terminal
`if: always()` step that opens the PR / files an issue whenever it ends without
having merged -- otherwise the next unanticipated path is silent too. Note the
current fallback would ALSO have to widen its condition: "merge step failed" is
not "tests failed".

## Verified safe to land
The stranded branch's merge result is green: `git merge -X theirs` of
claude/engineer-stop-lowering-enforcement into current main touches exactly 3
files (+168 lines, 0 deletions -- main's journal entries are preserved) and the
suite passes 54 passed, 3 xfailed. It needs a human merge because this bug
blocks the gate from doing it.

## Engineer notes (append below)
