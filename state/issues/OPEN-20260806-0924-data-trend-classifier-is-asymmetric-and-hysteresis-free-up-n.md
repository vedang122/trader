---
severity: S3
area: data
filed: 2026-08-06T09:24:54+05:30
title: trend classifier is asymmetric and hysteresis-free: 'up' needs two conditions, 'down' needs one, so a name with a bullish SMA50>SMA200 stack is labelled 'down' on a 0.3% SMA50 breach
---

## Observed
OBSERVED THIS CYCLE (2026-08-06, cloud-scheduled open cycle).

CODE (engine/data.py:327-328):
  "trend": ("up" if last > sma50 > (sma200 if not isna(sma200) else 0)
            else "down" if last < sma50 else "sideways")

TWO DISTINCT PROBLEMS, one line.

(1) ASYMMETRY. The 'up' branch requires TWO conditions (last > sma50 AND sma50 > sma200). The 'down' branch requires ONE (last < sma50) and never consults sma200 at all. So a name whose long-term structure is constructive -- sma50 above sma200, price above sma200 -- is labelled 'down' the moment it dips a fraction below sma50. A symmetric definition would return 'sideways'.

EXACT CASE, TATASTEEL at 09:16:36 IST today:
  last 191.64 | sma20 187.38 | sma50 192.29 | sma200 188.91
  'up'?   191.64 > 192.29 -> False. Not up.
  'down'? 191.64 < 192.29 -> True.  -> labelled "down"
Yet sma50 (192.29) > sma200 (188.91) -- the bullish stack the 'up' branch cares about -- AND last (191.64) > sma200 (188.91). The stock is above its 200-day average and its 50-day is above its 200-day, and the engine calls the trend 'down'.

(2) NO HYSTERESIS / DEADBAND. The breach that triggered the flip was 0.65 points, 0.34% of price, and under 20% of the symbol's own ATR14 (3.59). There is no deadband, no confirmation requirement, no ATR-relative tolerance.

DEMONSTRATED TRIAGE IMPACT THIS CYCLE (this is not hypothetical):
  08:16 IST pre-open scan: TATASTEEL last 192.99, trend "up",   score 6.0 -> ranked #1 candidate of 15, and written into the premarket_plan as the desk's lead idea for the open.
  09:16 IST open scan:     TATASTEEL last 191.64, trend "down", score 4.0 -> ranked #5, below three names it had outranked an hour earlier.
A 1.35-point move re-ordered the entire triage board. engine/scan.py:12-15 rewards trend alignment in 'score', so the label is not cosmetic -- it decides which candidates reach the analyst committee at all. The desk head had to manually restore TATASTEEL to the committee against its own score to avoid losing the pre-open lead candidate to a rounding-scale price move.

Independently corroborated by the technical-analyst this cycle, working from raw OHLCV rather than the label: it found 08-05's close (192.99) was the FIRST daily close above SMA50 in roughly 2.5 months -- i.e. a genuine reclaim attempt under live test. The binary label collapses 'contested reclaim of a major average' into the same bucket as 'established downtrend'.

NOTE ON SCOPE: this is a separate defect from OPEN-20260806-0922 (partial-intraday-volume). That one is about the last bar being incomplete; THIS one reproduces on fully completed daily bars too -- any close 0.1% under sma50 with sma50 > sma200 mislabels. Fixing the volume issue does not fix this.

SUGGESTED DIRECTION (not a prescription): make the branches symmetric (require last < sma50 < sma200 for 'down', else 'sideways'), and add an ATR- or percentage-scaled deadband around sma50 so a sub-noise breach returns 'sideways' rather than flipping the label. Consider also whether 'score' should consume a graded trend strength instead of a three-way label.

## Engineer notes (append below)
