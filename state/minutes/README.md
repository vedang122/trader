# Desk minutes — the reasoning record

One file per decision-bearing trade cycle: `<YYYY-MM-DD-HHMM>.md`, ≤80 lines.
Written by the desk head in Phase 6 of /trade-cycle; read by the trade-coach
at /debrief to score the quality of the desk's *arguments*, not just outcomes.

Write minutes ONLY when the committee convened, the risk gate ruled, or a
position decision was made. No-op ticks (market closed, no candidates) get no
minutes — the journal's cycle_summary already covers them.

## Required sections
1. **Committee** — each analyst consulted, compressed to 3-5 lines: bias,
   levels, confidence, their strongest argument, and the strongest
   counter-argument they acknowledged. Compress; never paste raw reports.
2. **Synthesis** — why each candidate advanced or dropped; what the desk head
   weighed most; what was close.
3. **Risk gate** — the officer's grounds and bias flags, if consulted.
4. **Falsifiable self-prediction** — one line: "this read is wrong if X
   happens by <date>". The coach checks these at the next debrief.

## Lifecycle
- Journal (`state/journal.jsonl`) = permanent audit trail of WHAT happened.
- Minutes = bounded working memory of WHY. The coach prunes files older than
  30 days at /debrief.
