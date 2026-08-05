---
severity: S2
area: ops
filed: 2026-08-05T12:26:53+05:30
title: preflight reports feed 'cache fresh enough for daily bars' while data.snapshot returns source=cache_stale with no LTP
---

## Observed
Cycle 2026-08-05 12:16-12:30 IST. Two engine outputs contradict each other about whether usable data exists.

`python3 -m engine.ops preflight` ->
  {"verdict": "DEGRADED", "feed": {"status": "degraded",
   "detail": "yfinance: yfinance failed for NIFTY: empty response | cache fresh enough for daily bars"}}

`python3 -c "from engine import data; print(data.snapshot('RELIANCE'))"` ->
  {"symbol": "RELIANCE", "source": "cache_stale", "sma20": 1294.56, "sma50": 1300.48,
   "atr14": 20.8, "vol_ratio_20d": null}   # note: NO ltp key at all

Why it matters (safety-adjacent, not just cosmetic): the trade-cycle skill treats DEGRADED as
'position defense and exits allowed on live LTP'. Preflight's wording ('cache fresh enough')
implies defense is viable. It is not - there is no LTP and the cache is self-labelled stale.
The book happened to be empty this cycle, so nothing was risked. With an open position and a
breached stop, a desk head trusting the preflight line would go looking for a live quote that
the data layer cannot produce.

Suggested direction (engineer's call, not the trader's): preflight's feed.detail should be
derived from what data.snapshot actually returns for a probe symbol (source + presence of ltp),
not from a separate cache-age heuristic; and the DEGRADED verdict should distinguish
'degraded-with-live-LTP' (defense possible) from 'blackout' (defense impossible, exits blind).

Related still-OPEN: scan scoring crash on null vol_ratio_20d - reproduced again this cycle,
15/15 watchlist symbols errored, 0 candidates.

## Engineer notes (append below)
