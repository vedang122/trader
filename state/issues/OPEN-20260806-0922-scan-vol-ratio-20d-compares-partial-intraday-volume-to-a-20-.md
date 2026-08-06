---
severity: S2
area: scan
filed: 2026-08-06T09:22:35+05:30
title: vol_ratio_20d compares partial intraday volume to a 20-day full-day average; volume_unconfirmed=false asserts the opposite of the truth in the first minutes of a session
---

## Observed
OBSERVED THIS CYCLE (2026-08-06, cloud-scheduled open cycle).

engine.scan run at 09:16:36 IST -- ONE MINUTE after the 09:15 open -- returned for every symbol a vol_ratio_20d between 0.01 and 0.13, with volume_unconfirmed: false on all of them.

Exact evidence, same symbol, same trading day, 60 minutes apart:
  08:16 IST (pre-open scan, yesterday's completed bar): TATASTEEL vol_ratio_20d = 1.04
  09:16 IST (this cycle, today's 1-minute-old bar):      TATASTEEL vol_ratio_20d = 0.04
A 26x change with no market event. The 08:16 figure was a completed daily bar; the 09:16 figure is roughly one minute of trading divided by a 20-day FULL-DAY average.

Full 09:16 board for illustration (all source=yf, errors=[]):
  ICICIBANK 0.13 | SBIN 0.01 | LT 0.01 | SUNPHARMA 0.01 | TATASTEEL 0.04 | BHARTIARTL 0.04 | RELIANCE 0.06 | INFY 0.02 | TCS 0.03 | ITC 0.01 | NTPC 0.02 | TATAPOWER 0.01 | M&M 0.01 | HDFCBANK 0.05 | HINDUNILVR 0.01

THE DEFECT IS THE FLAG, NOT THE RATIO. A partial-day ratio is unavoidable intraday; asserting volume_unconfirmed: false alongside it is not. The contract of that field, as consumed by agents and documented in the trade-cycle skill ('vol_ratio_20d: null means volume is unverifiable -- volume-gated setups cannot confirm'), is that false means the volume reading is TRUSTWORTHY. Here it is emitted as trustworthy while carrying a number that is off by roughly the fraction of the session elapsed.

IMPACT (decision-corrupting, both directions):
1. A volume-gated breakout setup can never confirm early in a session, and the agent is told the volume genuinely IS 1% of average rather than that it is unmeasured -- reads as confirmed absence of participation.
2. Worse in the other direction: the desk's pre-open shortlist ranked TATASTEEL rank 1 EXPLICITLY on 'vol_ratio 1.04 - the only leader with volume at-or-above average'. Re-running the same scan minutes later silently destroys that input while still reporting it as confirmed. Two scans an hour apart give contradictory, equally-confident volume evidence about the same setup.
3. scan 'score' is partly volume-derived, so the triage ranking itself shifts with time-of-day rather than with the market.

This cycle the desk had to manually override the field (instructing both technical-analysts to treat volume as UNKNOWN rather than low) to avoid acting on it. A manual guard in the orchestrator prompt is not a fix.

SUGGESTED DIRECTION (for the engineer, not a prescription): when the last bar is the in-progress session bar, either (a) set vol_ratio_20d to null and volume_unconfirmed to true, matching the documented 'unverifiable' contract, or (b) time-normalise the partial volume against the elapsed fraction of the session and mark it explicitly as an estimate, and in either case exclude it from 'score'. Option (a) is the honest minimum and matches the contract that already exists.

## Engineer notes (append below)
