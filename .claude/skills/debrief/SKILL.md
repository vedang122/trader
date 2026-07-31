---
name: debrief
description: Weekly (or on-demand) performance review of the trading desk — expectancy, conviction calibration, discipline audit, lessons. Use when the user says "debrief", "review the week", "how is the desk doing", or after any losing streak.
---

# Desk debrief

1. Launch the `trade-coach` agent with the review period (default: since the
   last file in `state/debriefs/`, else desk inception). It reads the
   deterministic scorecard (`engine.stats`), writes `state/debriefs/<date>.md`,
   routes lessons to `state/lessons/<agent>.md` (capped, lifecycle-managed),
   and files any limit amendments through `engine.amend`.
2. Read the debrief file it produced and relay to the user: the scorecard
   (expectancy, calibration table, discipline flags), the one most damaging
   pattern, lessons issued/promoted/retired, and any amendment it proposed or
   tightening it applied.
3. If a loosening is now PENDING (24h cooling), tell the user explicitly: what,
   why, when it takes effect, and that `python3 -m engine.amend reject` vetoes
   it. Watchlist diffs still need explicit user approval before you apply them.
4. If the desk has fewer than 5 closed trades, say the sample is too small for
   calibration claims and keep the review qualitative — process only.
