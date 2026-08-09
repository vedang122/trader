---
severity: S2
area: data
filed: 2026-08-06T10:26:24+05:30
title: engine.data ohlcv CLI hardcodes .tail(60), silently discarding the period argument analysts pass
---

## Observed
IMPACT: the technical-analyst is the desk's primary trade filter and builds support/resistance via the CLI. Its S&R rule requires >=3 well-spaced touches, so levels older than ~3 months are INVISIBLE to it -- while the analyst believes it requested 1-2 years. It has no way to detect the truncation; the series just appears to end.

REPRODUCE (2026-08-06 10:40 IST):
  $ for p in 6mo 1y 2y; do python3 -m engine.data ohlcv SUNPHARMA $p | wc -l; done
  62
  62
  62
Identical row count for every period. Meanwhile the library path is NOT truncated:
  $ python3 -c "from engine import data; print(len(data.get_ohlcv('SUNPHARMA')))"
  250
So the CLI and library disagree by 4x on the same default period ('1y').

CAUSE: engine/data.py:341
  print(get_ohlcv(sym, period=sys.argv[3] if len(sys.argv) > 3 else "3mo").tail(60).to_string())
The period arg is correctly passed to get_ohlcv, then .tail(60) discards the result. CACHE_ROWS=420, so the data is present on disk -- this is purely a display-layer truncation being consumed as if it were the dataset.

EVIDENCE THIS CHANGED A DECISION TODAY: the SUNPHARMA technical-analyst reported verbatim: 'the 1y/2y args returned the same ~60-row window as 6mo -- the tool appears capped at that history for this symbol, so my S&R is built on ~3 months of daily candles only'. It then concluded 'no validated (>=3-touch) resistance exists above price', which is a statement about a 3-month window being presented as a statement about the name. That conclusion fed the Phase 3 drop.

SUGGESTED FIX (for the engineer, not applied here): make the CLI print a window consistent with the requested period, or emit an explicit truncation notice naming the rows shown vs rows available. Do not silently truncate a series an agent will reason over.

## Engineer notes (append below)

## Closed
2026-08-09T08:50:56+05:30: fixed: ohlcv CLI now prints the full requested period via ohlcv_text(), header states rows/period/span/source; SUNPHARMA 6mo/1y/2y were 62/62/62 rows, now 128/253/503
