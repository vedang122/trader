---
severity: S3
area: issues
filed: 2026-08-08T08:50:41+05:30
title: engine.issues close rejects the exact filename that engine.issues list prints
---

## Observed
`engine.issues list` emits each issue as `{"file": "OPEN-<ts>-<slug>.md"}` —
the only machine-readable handle the CLI hands out. Feeding that value
straight back to `close` fails:

    $ python3 -m engine.issues close OPEN-20260808-0850-data-groww-ltp-...
    {"status": "not_found", ...}

because `close()` globs `OPEN-*{stem}*.md`, so a stem that already carries the
`OPEN-` prefix searches for `OPEN-*OPEN-...` and matches nothing. The `.md`
suffix breaks it the same way. The caller must know to strip both ends, which
is not stated anywhere and is invisible from the `list` output.

Cost: a silent not_found. An agent that does not re-read the result would
believe it closed an issue that is still OPEN — the failure mode is a lie in
the audit trail, not a crash. Cost me one round-trip this run.

Fix (engine/issues.py, ALLOWED path): strip a leading `OPEN-`/`CLOSED-` and a
trailing `.md` from `stem` before globbing, and make an ambiguous match (more
than one file) report itself rather than closing the first hit.
Not fixed here: one issue per run, and this run's issue was the red suite.

## Engineer notes (append below)
