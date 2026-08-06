---
severity: S3
area: data
filed: 2026-08-06T10:26:40+05:30
title: OHLCV disk cache keys on the raw input string, not the normalized symbol, creating duplicate divergent cache files per instrument
---

## Observed
OBSERVED 2026-08-06 during the 10:16 IST cycle: an untracked file state/cache/ohlcv/RELIANCE.NS.csv appeared alongside the existing state/cache/ohlcv/RELIANCE.csv -- two cache files for the SAME instrument.

REPRODUCE:
  $ python3 -c "from engine import data; print(data.yf_symbol('RELIANCE'), data.yf_symbol('RELIANCE.NS'))"
  RELIANCE.NS RELIANCE.NS
yf_symbol() is correctly idempotent, so both inputs denote one instrument. But the cache filename is derived from the RAW caller-supplied string, so get_ohlcv('RELIANCE') writes RELIANCE.csv while get_ohlcv('RELIANCE.NS') writes RELIANCE.NS.csv.

WHY IT MATTERS (why this is S3 and not cosmetic): the two files refresh independently. A caller using the '.NS' spelling can be served a cache entry that the normal watchlist path (which uses the bare symbol) never refreshes, so staleness is per-spelling rather than per-instrument. state/cache/ohlcv is committed to git precisely so cloud clones start warm, so a stale duplicate persists across sessions and grows the repo with redundant copies. Agents are free to call either spelling -- the fundamental-analyst used the '.NS' form this cycle, which is how this surfaced.

SUGGESTED FIX (for the engineer, not applied here): key the cache path on yf_symbol(symbol) (or a canonical bare form) rather than the raw argument, and clean up any existing duplicate *.NS.csv entries in state/cache/ohlcv/.

## Engineer notes (append below)
