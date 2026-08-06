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

### 2026-08-06 engineer (cloud) — FIXED

Two halves to this issue; the first was already closed by a sibling fix, the second was not.

**Half 1 (wording) — already fixed before this run.** Issue 20260805-1339's patch (commit
1c8e984) added `feed.live_ltp`/`live_ltp_why` and rewrote the detail to "...but NO live LTP
(...) — cannot defend open positions". The bare "cache fresh enough for daily bars" line
quoted in the report no longer existed. Not re-done.

**Half 2 (the probe) — the live defect, now fixed.** `check_feed` still derived feed health
from `data._load_cache("NIFTY")` + `_cache_age_bars`, a *separate heuristic* from the code
path analysts actually consume. That is the root of the filed contradiction: the freshness of
one index's cache file was being generalised into a claim about the whole feed. A fresh NIFTY
cache sitting next to a stale watchlist reported `degraded` ("daily bars usable") while
`data.snapshot('RELIANCE')` returned `cache_stale` — or raised outright past
`CACHE_MAX_AGE_BARS`. Two engine outputs disagreeing about whether usable data exists, with
the desk head free to trust the optimistic one.

Fix (engine/ops.py, allowed path): when there is no live quote source, `check_feed` now probes
the first `FEED_PROBES` (2) *watchlist* symbols through `data.snapshot()` and reports what it
actually served, in a new always-present `feed.probes` list plus a detail line naming each
symbol and its source. Status is now `degraded` only if snapshot really serves something, and
`dead` (→ STAND_DOWN) when it serves nothing — previously a fresh index cache could mask a
watchlist the desk could not analyse at all. Verified against real state with yfinance forced
down: `snapshot serves RELIANCE=cache_stale, HDFCBANK=cache_stale`, matching `data.snapshot`
exactly. The GO and groww-live paths are untouched.

Not done, deliberately: the report's second suggestion — splitting the DEGRADED *verdict* into
"degraded-with-live-LTP" vs "blackout" — was left alone. The verdict vocabulary
(GO|DEGRADED|STAND_DOWN) is read by `.claude/skills/trade-cycle/SKILL.md`, a protected path;
adding a fourth verdict the skill does not recognise would be worse than the ambiguity. The
distinction is already carried losslessly by `feed.live_ltp`, and the blackout case now
escalates to STAND_DOWN through the existing `dead` status, which is the same outcome by a
route the skill already understands.

Tests: `tests/test_ops.py::test_feed_health_is_probed_through_snapshot_not_an_index_cache_heuristic`
(the repro: fresh NIFTY cache, 40-bar-stale RELIANCE) and
`::test_probed_feed_reports_the_source_snapshot_actually_served`. Both failed before the patch
(KeyError: 'probes'). No existing assertion was altered — the only change to existing tests is
the `_write_cache` helper, which now seeds a tradable name alongside the index so the scenarios
those tests describe are actually constructed. Full suite: 44 passed, 1 xfailed.

Also still open and referenced in this report: the scan crash on null `vol_ratio_20d` is
tracked separately as OPEN-20260806-0922 (vol_ratio_20d / volume_unconfirmed).

## Closed
2026-08-06T12:57:55+05:30: fixed: check_feed probes watchlist symbols through data.snapshot instead of a NIFTY cache-age heuristic; feed.probes reports the real source, blackout now escalates to STAND_DOWN
