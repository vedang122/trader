---
severity: S2
area: scan
filed: 2026-08-05T11:26:50+05:30
title: scan scoring crashes on null vol_ratio_20d, zeroing the whole scan on a degraded feed
---

## Observed
REPRO (2026-08-05 ~11:25 IST, feed DEGRADED, yfinance SSL/rate-limited, snapshots served from cache):

$ python3 -m engine.ops preflight
  verdict DEGRADED, feed.detail 'yfinance failed for NIFTY: empty response | cache fresh enough for daily bars'

$ python3 -m engine.scan --top 5
  {"errors": [15 x "<SYM>: '>=' not supported between instances of 'NoneType' and 'float'"], "candidates": []}
  (RELIANCE HDFCBANK ICICIBANK SBIN INFY TCS LT ITC HINDUNILVR M&M NTPC TATASTEEL BHARTIARTL SUNPHARMA TATAPOWER -- all 15, no survivors)

$ python3 -c "from engine import data; print(data.snapshot('RELIANCE'))"
  source='cache_stale', last=1294.7, sma20=1294.56, sma50=1300.48, atr14=20.8, vol_ratio_20d=None

CAUSE: engine/scan.py:25 -- 'if s["vol_ratio_20d"] >= 1.3:' compares directly against a float. The documented DEGRADED contract says vol_ratio_20d: null means volume is unverifiable, so None is an EXPECTED value, not an error. Every symbol raises TypeError inside scoring and is dropped into errors[], so the scan returns zero candidates.

IMPACT: the cached-bar fallback is exactly the path meant to keep the desk seeing the market when yfinance is down, and this crash disables the scanner completely on that path. Price/SMA/ATR from cache are all present and usable; only the volume confirmation is missing. Not S1: no order path, risk gate, or state is touched -- the desk stands down safely, just blind.

SUGGESTED FIX (for the engineer, not applied here): treat None as 'volume unconfirmed' rather than fatal -- guard the comparison, award no volume points, and surface the unverifiable volume on the candidate so volume-gated setups can be excluded downstream instead of the whole scan dying. Sweep engine/ for other bare comparisons against nullable snapshot fields.

## Engineer notes (append below)

## Closed
2026-08-05T12:53:25+05:30: fixed: setup_score guards vol_ratio_20d=None (no participation points, no penalty) instead of raising; scan candidates now carry volume_unconfirmed so volume-gated setups can be excluded downstream. Swept engine/ for other nullable-snapshot comparisons: scan.py is the only data.snapshot consumer, sma200 was already guarded, pos_52w_pct is never null. tests/test_scan.py (5 tests).
