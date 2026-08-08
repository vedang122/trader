---
severity: S2
area: data
filed: 2026-08-08T08:50:12+05:30
title: groww LTP patch can land behind a newer cached bar: cache+groww_ltp quotes a stale close as the live price (suite red on any weekend clone)
---

## Observed
Found by: suite red on a clean cloud clone, 2026-08-08 (Saturday).
`tests/test_data.py::test_fresh_cache_plus_groww_ltp` — source is
`cache+groww_ltp` but `Close.iloc[-1]` is the cached 100.0, not the 105.0 LTP.

Mechanism
---------
`get_ohlcv`'s Yahoo-down fallback stamps the patched LTP row with
`pd.Timestamp.now(tz="Asia/Kolkata").normalize()` and then sorts the frame.
It never checks that "now" is actually after the cache's last bar. When the
cache already holds a bar dated at or after today, the patched row sorts
BEHIND it, `iloc[-1]` returns the stale cached close, and `source` still
advertises `cache+groww_ltp`. Every consumer of that frame — scan, technical
analyst, the risk gate's entry price — reads a stale number as a live one.
This is precisely the "no data >= bad data" failure the ladder exists to
prevent: a degraded source that does not admit it is degraded.

The test harness surfaced it because `_write_cache`'s
`end=now - BDay(0)` rolls FORWARD off a non-business day: run on Saturday
2026-08-08 it mints a cache whose newest bar is Monday 2026-08-10, i.e. a bar
dated in the future. So the defect is weekday-invisible and weekend-fatal —
the suite is green Mon-Fri and red every Saturday and Sunday, which is why it
passed CI when it landed and blocks the engineer on a weekend clone.

In production the same stranding needs the cache to hold a bar at or after
the IST date: clock skew, a bar stamped by exchange date, or a cache written
by a run on the far side of a date boundary. Narrower than the test case, but
the failure is silent and lands a wrong price in the entry path.

Fix
---
Anchor the patch timestamp to `max(now_ist, cached.index[-1])` so the LTP
always overwrites the newest bar instead of being filed before it. When the
cache's last bar is older than today (the normal case) behaviour is unchanged.

## Engineer notes (append below)

## Closed
2026-08-08T08:50:28+05:30: fixed: anchor the groww-LTP patch row to max(now_ist, last cached bar) so the live price always lands on the newest bar instead of sorting behind a future-dated one; tests/test_data.py::test_ltp_patch_lands_on_the_newest_bar
