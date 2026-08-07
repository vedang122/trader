---
severity: S2
area: ops
filed: 2026-08-07T08:53:06+05:30
title: a cancelled or timed-out merge job strands a run branch silently: neither the merge nor the PR fallback runs, and nothing reports it
---

## Observed
Carried forward from the CORRECTION section of
CLOSED-20260807-0825-ops-preflight-... so it is not lost with that issue.
The preflight half of that issue is FIXED (stray branches are now classified;
audit/code-only parks no longer STAND_DOWN the desk). This half is NOT, and it
lives in a protected path no engineer run may edit: .github/workflows/.

## Observed
Run 31117366902 (merge-cloud-state.yml, branch
claude/engineer-stop-lowering-enforcement, sha 0af5709, job 92670237013):
started 2026-08-06T15:46:47Z, ended 2026-08-06T16:01:48Z, conclusion CANCELLED
after ~15 minutes.

The workflow assumes exactly one of two terminal steps always runs: "Merge into
main" or "Open PR instead". A cancellation (or a timeout, or a runner reap)
between them satisfies NEITHER. Result: the branch was never merged, never
deleted, and no PR was opened -- list_pull_requests(state=open) -> []. Nothing
anywhere reported the failure. The desk discovered it a day later, as an
unexplained permanent STAND_DOWN it could not clear from inside.

For contrast, this run's own merge job (31144110893, same engine class, same
pytest step) completed in 39 SECONDS. So the ~15 minutes that preceded the
cancellation was not normal cost -- something hung, and the concurrency group
(merge-cloud-state, cancel-in-progress: false) serialises every cloud push
behind it, so a hang there is a lock on all state merges.

## Why it still matters after the preflight fix
The preflight fix downgrades an audit/code-only stray branch to a notice, so a
cancelled ENGINEER merge no longer bars trading. But a cancelled CYCLE merge
strands real desk state (portfolio/regime/limits) -- which correctly still
stands the desk down, still cannot be cleared from inside the desk, and still
arrives with no notification. The blast radius is reduced, not removed. Main's
journal.jsonl also carries a genuine audit-trail gap for any stranded branch.

## Suggested direction (needs human -- .github/** is protected)
- an `if: always()` (or `if: cancelled() || failure()`) final step that opens
  the PR, or at minimum files a desk issue, whenever the job ends without
  having merged -- so no path through the workflow is silent;
- an explicit `timeout-minutes` on the pytest step, so a hang fails loudly
  instead of hanging until something reaps it;
- investigate what made that pytest step take 15+ minutes when the same step
  now runs in ~30s (network-dependent test with no timeout is the first guess).

## Engineer notes (append below)
