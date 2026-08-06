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

### 2026-08-06 engineer (cloud): second bar source LANDED; one protected line still blocks entries

FIXED (engine/data.py, allowed path): NSE's own bhavcopy archive is now a real
second daily-bar source, tried after Yahoo fails and before any patched/stale
fallback. `data.bhav_fetch()` + `data._bhav_day()`; snapshots tag `source:
"nse_bhav"`. It appends genuine settled OHLCV — with true full-day volume, so
`vol_ratio_20d` is populated again — onto the cached history, closing the
freshness gap. One zip carries the whole market and is process-cached, so a
15-symbol scan costs ~1 fetch per date, not per symbol.

Verified live from this container while Yahoo was returning 429, with
`_yf_fetch` forced dead:
    SBIN      source=nse_bhav last=1085.0  vol_ratio=1.38
    RELIANCE  source=nse_bhav last=1325.0  vol_ratio=1.66
    ICICIBANK source=nse_bhav last=1457.5  vol_ratio=1.21
    LT        source=nse_bhav last=4061.8  vol_ratio=0.73
    NIFTY     source=cache_stale (CM bhavcopy has no indices — see limits)
Those closes match Yahoo's own values to the paisa in the same session.

Limits, stated plainly:
- Equities only. Indices/FX (NIFTY, USDINR, GOLD...) are not in the CM segment
  and still degrade to cache. The regime read is therefore NOT repaired by this.
- Needs an existing cached series to append to; a never-cached symbol degrades
  exactly as before. (state/cache/ohlcv/ is committed, so the cloud clone has it.)
- Bars are exchange-raw/unadjusted vs yfinance's auto-adjusted history, so they
  close a gap but must never rebuild history across a corporate action.
- NSE publishes after ~18:00 IST, so intraday the freshest bhav bar is the prior
  session's close — a true daily bar, but not an intraday price.

STILL OPEN — the last step is one line in a PROTECTED path and needs a human.

## Proposed patch (needs human)

Phase 0's DEGRADED rule names the *provider* rather than the *property* it
actually cares about ("not patched, not stale"). Exchange-settled bhavcopy bars
are, if anything, more authoritative than Yahoo's — but they are literally not
`source: "yf"`, so entries stay foreclosed until this line accepts them.

```diff
--- a/.claude/skills/trade-cycle/SKILL.md
+++ b/.claude/skills/trade-cycle/SKILL.md
@@
 - **DEGRADED** (cache/Groww fallback) → position defense and exits allowed on
-  live LTP; new entries only if the candidate's snapshot has `source: "yf"` —
-  never initiate on patched or stale data. Snapshots carry a `source` field;
+  live LTP; new entries only if the candidate's snapshot has `source: "yf"` or
+  `source: "nse_bhav"` (Yahoo live, or an exchange-settled daily bar) — never
+  initiate on patched or stale data. Snapshots carry a `source` field;
   `vol_ratio_20d: null` means volume is unverifiable — volume-gated setups
   cannot confirm.
```

Human's call, and it is a judgment call, not a defect: `nse_bhav` is settled
end-of-day truth, so an entry taken on it is an entry taken on yesterday's close
plus whatever the live LTP says now. If the desk would rather stand down than
initiate without an intraday bar, reject this hunk and the engine change still
stands on its own — it repairs volume confirmation and position defense.

Covering tests are already merged and green (tests/test_data.py):
`test_bhav_day_parses_exchange_archive`,
`test_yahoo_dead_still_yields_live_bars_from_the_exchange`,
`test_bhav_bars_restore_volume_confirmation`,
`test_bhav_declines_non_equities`,
`test_dead_exchange_archive_keeps_the_old_ladder`.

NOT addressed (deliberate): the issue's item (5), scan reporting `errors: []`
on an all-stale scan. `tests/test_scan.py::test_degraded_scan_returns_candidates_not_errors`
asserts that emptiness on purpose ("a degraded feed must narrow the scan, never
zero it"), so making it loud would mean weakening an existing assertion. If the
desk wants that loudness it needs its own issue and a decision on that test.
