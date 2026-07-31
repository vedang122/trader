# Lesson memory — the desk's evolution layer

One file per agent (`technical-analyst.md`, `risk-officer.md`, …) plus `desk.md`
for cross-cutting patterns. Written ONLY by the trade-coach during /debrief.
Every specialist reads its own file at the start of a session — nothing else.

## Format (hard rules — the caps ARE the design)
- Max **12 active lessons** per file. At the cap, the coach must merge or retire
  before adding. Retired lessons move to `archive.md` (never loaded by agents).
- One lesson = max 3 lines:
  `- [YYYY-MM-DD | status] RULE (falsifiable, specific) — evidence: <journal refs / stats numbers>`
- `status`: `trial` (new) → `validated` (held up over ≥5 subsequent relevant
  trades, checked via engine.stats) → retired (contradicted or superseded).
- A lesson must change behavior in a checkable way. "Be more careful with
  momentum names" is not a lesson; "No entries with RSI > 72 unless volume
  ratio > 1.5 — 4 of 5 such entries stopped out (see stats by_strategy
  swing-momentum)" is.

## Why caps
Uncapped memory is context rot: after 200 trades an agent would drown in its
own history. Compression under a cap forces the coach to keep only rules that
still earn their lines. The raw history never disappears — it lives in
journal.jsonl and is queried through engine/stats.py, not loaded into context.
