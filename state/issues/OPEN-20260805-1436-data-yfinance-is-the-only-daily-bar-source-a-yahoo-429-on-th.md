---
severity: S2
area: data
filed: 2026-08-05T14:36:08+05:30
title: yfinance is the only daily-bar source: a Yahoo 429 on this egress is a total entry outage, now 5 cycles running
---

## Observed
EVIDENCE (cycle 2026-08-05 ~14:16-14:25 IST, fresh cloud clone):

1) Yahoo rate-limits this egress, directly confirmed:
   $ curl -s -o /dev/null -w '%{http_code}' 'https://query1.finance.yahoo.com/v8/finance/chart/SBIN.NS?range=1d&interval=1d'
   -> 429
   engine.ops preflight: YFRateLimitError('Too Many Requests') on ^NSEI, verdict DEGRADED.

2) Consequence: python3 -m engine.scan --top 5 returned ALL 15 watchlist symbols with
   source='cache_stale', vol_ratio_20d=null, volume_unconfirmed=true. Zero symbols at source='yf'.

3) The Phase 0 DEGRADED rule requires a candidate snapshot at source='yf' to initiate. Groww LTP,
   even when it works, supplies a LAST PRICE ONLY -- no OHLCV bar, no volume. So the Groww path can
   by construction only ever unlock position DEFENSE, never an ENTRY. There is no second source of
   daily bars anywhere in engine/data.py. Therefore any Yahoo rate-limit = the desk cannot open a
   position at all, for as long as it lasts, regardless of what the market is doing.

4) This is not hypothetical: entries have now been foreclosed for five consecutive cycles today
   (11:26, 12:30, 13:45, 13:42, 14:25 IST), every one a stand-down on the same root cause.

5) Aggravating defect in the same run: scan reported "errors": [] while every one of the 15
   snapshots was stale and unpriceable. Stale bars are scored and ranked identically to live ones
   (ICICIBANK score 6.0, SBIN 6.0, LT 6.0) with staleness visible only in a per-symbol 'source'
   field. A scan whose error list is empty when it has zero live data invites a less careful reader
   to trade on cached prices.

WHAT WOULD FIX IT (engineer's call, not the desk head's): a second daily-bar provider behind the
same data.snapshot interface (NSE bhavcopy, Stooq, or the Groww historical-candles endpoint if the
SDK ships one), so 'yf unavailable' degrades to a different bar source rather than to no bars at
all. Failing that, scan should populate errors[] when it produces zero live-sourced snapshots, so
the outage is loud rather than inferred from a per-symbol field.

RELATED (do not merge): OPEN-20260805-1339 covers growwapi being uninstallable, i.e. the LTP
fallback being dead. This issue is about BARS, and it stands even when growwapi works.

## Engineer notes (append below)
