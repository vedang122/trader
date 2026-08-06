---
severity: S3
area: issues
filed: 2026-08-06T12:58:06+05:30
title: engine.issues close rejects the exact filename that list prints
---

## Observed
`engine.issues list` emits {"file": "OPEN-20260805-1226-ops-...md"}, but close() globs `OPEN-*{stem}*.md`, so passing that filename (or its stem) back produces `OPEN-*OPEN-...*` and returns {"status": "not_found"} with exit 0. The caller must hand-strip the OPEN- prefix and the .md suffix, and a silent not_found reads like a no-op rather than an error. Found 2026-08-06 while closing 20260805-1226. Fix direction: strip a leading OPEN-/CLOSED- and a trailing .md from stem before globbing, and exit non-zero on not_found so a scripted close cannot fail quietly. engine/issues.py is an allowed path.

## Engineer notes (append below)
