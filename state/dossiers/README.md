# Symbol dossiers — the desk's entity memory

One file per watchlist symbol (`RELIANCE.md`, `NTPC.md`, …). The wiki-pattern
idea (compile once, compound forever) applied to the one knowledge type it fits
on a trading desk: slow-moving facts about companies. Everything fast-moving or
quantitative stays OUT — prices live in scans, trades in the journal, aggregates
in engine.stats.

## Hard format (cap: 80 lines/file — the cap IS the design)
```markdown
---
symbol: RELIANCE
sector: energy
updated: YYYY-MM-DD
quality_grade: A|B|C          # fundamental-analyst's latest
grade_date: YYYY-MM-DD
valuation: cheap|fair|expensive
earnings_next: YYYY-MM-DD     # if known, else omit
---
## Business (≤8 lines — stable facts only: what it earns from, moat, key risk)
## Grade history (≤8 lines, newest first: date | grade | valuation | one-line basis)
## Levels that mattered (≤8 lines: date | level | what price did there)
## Red flags & watch items (≤6 lines, each with the journal ts or source that raised it)
## Desk record in this name (≤4 lines: trades, net P&L, pointer: engine.stats)
```

## Ownership (who writes what)
- **fundamental-analyst** (at research time): frontmatter grades, Business,
  Grade history. Reads the dossier FIRST — refresh only what's stale instead of
  re-deriving the company from scratch.
- **trade-coach** (at /debrief): Levels that mattered, Red flags outcomes,
  Desk record, and cap enforcement — over 80 lines, compress oldest first.
- Everyone else: read-only. Committee briefs in trade-cycle include the
  candidate's dossier when it exists.

## Truth policy (differs from a wiki — this is the point)
A wiki validates claims by cross-source corroboration. A dossier line is
validated by what the MARKET subsequently did: a grade that preceded a losing
thesis gets its outcome noted, not silently rewritten. Contradictions are
resolved by date and P&L, and the coach retires lines that stopped earning
their space. Staleness rule: a grade older than 90 days is marked `(stale)` by
the coach and triggers a re-grade on next candidacy.
