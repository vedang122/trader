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

### 2026-08-07 engineer(cloud) — reproduced against real git; patch below, still needs a human

`.github/**` is protected, so no workflow file is touched by this commit. What
landed is `tests/test_merge_gate.py`: three tests that prove the mechanism
against real git, and two strict-xfail tripwires that read the live workflow.
Applying the patch below turns those two green, which turns the suite RED
(strict xfail) — that is deliberate. Delete the two `@pytest.mark.xfail`
markers in the same change that applies the patch.

**Reproduction (deterministic, no GitHub needed).** A miniature repo: main,
a run branch forked from it, and one cycle push landing on main afterwards.

| cleanup used | cycle push after fork? | staged after cleanup | `git merge -X theirs` |
|---|---|---|---|
| `git checkout -- .` (current) | yes | 2 files | **exit 2**, "would be overwritten by merge" |
| `git checkout -- .` (current) | no  | 2 files | exit 0 — merges anyway |
| `git reset -q --hard HEAD` | yes | none | exit 0 |

Row 3 is the fix. Rows 1 and 2 together are the race: the same broken cleanup
strands a branch or does not, decided only by whether a ~30-minute cycle push
beat it to main. Nothing about the branch's own content decides it.

**One correction to the one-liner suggested above.** Actions runs `run:` blocks
under `bash --noprofile --norc -eo pipefail`. Appending `git reset -q --hard
HEAD` as the last line means it never executes on a red suite — `set -e` exits
at pytest. Verified: `false; rc=$?` exits 1 without reaching the next line,
while `false || rc=$?` continues. So the reset has to be reached through `||`
and the real exit code re-raised afterwards, or the gate leaves a polluted
index behind on exactly the runs that already went wrong.

**Fallback condition.** `steps.tests.outcome != 'success'` cannot express "the
merge did not happen" — this stranding had *green* tests, which is why nothing
opened. The merge step needs an `id` and `continue-on-error`, and the fallback
needs to key off `steps.merge.outcome` under `always()`. That also subsumes
OPEN-20260807-0853-ops's silent-cancellation path: a cancelled merge step is
likewise `outcome != 'success'`.

**Verified**: patched YAML still parses; both tripwire tests pass against it;
a red suite still propagates exit 1 (so `tests.outcome == 'failure'` → merge
skipped → PR opens) *and* leaves a clean index; the drifted merge then lands.

```diff
--- a/.github/workflows/merge-cloud-state.yml
+++ b/.github/workflows/merge-cloud-state.yml
@@ -50,14 +50,19 @@
         if: steps.classify.outputs.class == 'engine'
         id: tests
         continue-on-error: true
+        timeout-minutes: 10
         run: |
           git checkout origin/${GITHUB_REF_NAME} -- .
           pip install -q -r requirements.txt pytest
-          python -m pytest tests/ -q
-          git checkout -- .
+          rc=0
+          python -m pytest tests/ -q || rc=$?
+          git reset -q --hard HEAD
+          exit $rc
 
       - name: Merge into main
+        id: merge
         if: steps.classify.outputs.class == 'state' || (steps.classify.outputs.class == 'engine' && steps.tests.outcome == 'success')
+        continue-on-error: true
         run: |
           git config user.name "kautilya-state-bot"
           git config user.email "actions@github.com"
@@ -65,12 +70,12 @@
           git push origin main
           git push origin --delete "${GITHUB_REF_NAME}" || true
 
-      - name: Open PR instead (protected paths or red tests)
-        if: steps.classify.outputs.class == 'protected' || (steps.classify.outputs.class == 'engine' && steps.tests.outcome != 'success')
+      - name: Open PR instead (protected paths, red tests, or a failed merge)
+        if: always() && steps.merge.outcome != 'success'
         env:
           GH_TOKEN: ${{ github.token }}
         run: |
-          REASON="${{ steps.classify.outputs.class == 'protected' && 'touches protected paths (risk/amend/charges/execute/broker/portfolio/common/workflows/charters/bounds) — human review required' || 'test suite failed' }}"
+          REASON="${{ steps.classify.outputs.class == 'protected' && 'touches protected paths (risk/amend/charges/execute/broker/portfolio/common/workflows/charters/bounds) — human review required' || steps.tests.outcome == 'failure' && 'test suite failed' || 'the merge step did not succeed' }}"
           gh pr create --base main --head "${GITHUB_REF_NAME}" \
             --title "cloud change needs review: ${GITHUB_REF_NAME}" \
             --body "Auto-merge declined: ${REASON}. Review and merge manually, or close." || true
```

The new test is `tests/test_merge_gate.py` in this commit — it is not
reproduced inline here to keep one copy authoritative.

Issue left **OPEN**: the defect is still live in the workflow until a human
applies the diff above.

### 2026-08-09 engineer(cloud) — patch re-verified against today's main; still undelivered after 55.7h

No code changed this run. What changed is the confidence that the two-day-old
patch above is still the right one, and the confirmation that nobody has seen it.

**Patch is not stale.** `.github/workflows/merge-cloud-state.yml` is unchanged
since the patch was written: `git apply --check` of the diff above against
current main (1fffed0) succeeds with no fuzz. Applied in a scratch copy, the
YAML still parses and — with the two `@pytest.mark.xfail` markers in
`tests/test_merge_gate.py` deleted, as that section instructs — the full suite
is **115 passed / 6 xfailed**. The change is ready to land as written.

**It never reached the human.** `list_pull_requests(state=open)` on
vedang122/trader returns `[]`, and no `claude/*` branch survives on the remote.
The commit carrying this patch (a22453b) touched only allowed paths, so the gate
classified it `engine` and auto-merged it with no PR — the exact hole later filed
as OPEN-20260808-1254-ops and only *detected* by 7ebb815. `engine.issues
pending-human` now lists this issue first, but detection is not delivery: the
gate has no path that opens a PR for a patch that lives in an issue body.

**Nothing further is available to an engineer run.** The damage is already
mitigated as far as allowed paths reach — `engine.ops` flags unmerged `claude/*`
branches older than 30 minutes and journals an `ops_alert`, non-blocking per
20260807-0825 — and the defect itself is one `run:` block inside protected
`.github/**`. Every subsequent engineer run will re-derive this same conclusion
and re-append to this file until a human acts.

**The one human action**, in a single commit: apply the diff above to
`.github/workflows/merge-cloud-state.yml`, delete the two
`@pytest.mark.xfail(strict=True, reason=NEEDS_HUMAN)` lines in
`tests/test_merge_gate.py`, run the suite (expect 115/6), merge. Until then every
engineer fix that forks more than one cycle-push ahead of its merge job is still
being discarded silently.
