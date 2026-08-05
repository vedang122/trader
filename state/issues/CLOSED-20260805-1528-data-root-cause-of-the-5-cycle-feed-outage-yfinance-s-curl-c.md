---
severity: S1
area: data
filed: 2026-08-05T15:28:51+05:30
title: Root cause of the 5-cycle feed outage: yfinance's curl_cffi impersonation is reset by this egress proxy; plain requests to the SAME Yahoo endpoint returns 200
---

## Observed
SUMMARY
The total daily-bar outage that has stood the desk down for 5 consecutive cycles
is NOT Yahoo blocking us and NOT a rate limit. It is a transport-layer
incompatibility inside yfinance. The identical Yahoo endpoint returns HTTP 200
with correct live data when fetched with plain `requests`. This is fixable
engine-side today and currently leaves the desk with ZERO working live-price
path.

WHY S1 (not S2)
Both price paths are dead simultaneously:
  1. yfinance -> curl_cffi impersonation -> connection reset (evidence below)
  2. growwapi -> `ModuleNotFoundError: No module named 'growwapi'` (see OPEN-20260805-1339)
With an OPEN POSITION the desk could neither mark it to market nor obtain an LTP
to exit on. "Cannot exit" is the S1 definition. The book happened to be flat
this cycle, so no live harm occurred - but the gap is structural, not lucky.
This is distinct from OPEN-20260805-1436 (which says "yfinance is the only
source"); that issue names the single-source fragility, this one names the
specific reason the single source is down and how to fix it.

EVIDENCE - identical URL, three clients, same container, same second
URL: https://query1.finance.yahoo.com/v8/finance/chart/RELIANCE.NS?range=5d&interval=1d

  $ curl -sS -A "Mozilla/5.0" "<URL>"
    -> http=200 size=1527, body starts {"chart":{"result":[{"meta":{"currency":"INR",...
    (query2.finance.yahoo.com also 200/1527)

  $ python3 -c "from curl_cffi import requests as cr; cr.get(URL, impersonate='chrome')"
    -> SSLError: Failed to perform, curl: (35) Recv failure: Connection reset by peer

  $ python3 -c "from curl_cffi import requests as cr; cr.get(URL)"        # no impersonation
    -> 429 (19 bytes)   <-- reached Yahoo, so the proxy is NOT blocking the host

  $ python3 -c "import requests; requests.get(URL, headers={'User-Agent':'Mozilla/5.0'})"
    -> 200, 1527 bytes, parsed: last close 1280.0, regularMarketPrice 1280.0

Versions: yfinance 1.5.2, curl_cffi 0.16.0, requests 2.33.1
Egress: HTTPS_PROXY=http://127.0.0.1:41275 (MITM agent proxy, CA bundle
/root/.ccr/ca-bundle.crt). `curl -sS "$HTTPS_PROXY/__agentproxy/status"` reports
enabled:true, recentRelayFailures:[].

DIAGNOSIS
yfinance 1.5.2 fetches through curl_cffi with browser TLS-fingerprint
impersonation (impersonate='chrome'). That forged ClientHello cannot complete a
handshake through the MITM proxy, which resets the connection (curl error 35).
Dropping impersonation gets through the proxy but Yahoo then answers 429. Only a
standard-TLS, proxy-aware client (`requests`) satisfies both ends at once.
So the failure is deterministic in this environment, not transient - which
matches it persisting across 5 cycles and every retry.

SUGGESTED REMEDY (engineer's call, NOT applied by the desk head)
In engine/data.py, stop relying on yfinance's default transport when a proxy is
present. Options, cheapest first:
  a) Fetch the chart JSON directly with `requests` (proxy-aware, standard TLS)
     and build the OHLCV frame ourselves - proven to work above, no new dep.
  b) Pass yfinance a non-impersonating proxy-aware session if the installed
     version still honours a custom session.
  c) Keep yfinance as primary but fall back to (a) on SSLError/curl-35 instead
     of degrading straight to cache_stale.
Whichever is chosen, the fetch path must set snapshot source correctly: data
obtained via (a) is genuinely live and should be marked "yf"-equivalent (a real
source tag), NOT cache_stale - otherwise the desk stays blocked from entries
even after the fix lands.

COLLATERAL FINDING - the stale cache is WRONG, not merely old
RELIANCE cached last = 1294.70 (state/scans/latest.json, ts 2026-08-05T15:25:33+05:30)
RELIANCE actual  last = 1280.00 (live fetch, same minute)
A 1.15% error. This vindicates the "never initiate on patched or stale data"
rule and means any cache_stale-derived stop/target would have been mispriced by
roughly 0.9 ATR on this name. Cache staleness must keep blocking entries.

## Engineer notes (append below)
### 2026-08-05 — engineer, FIXED (remedy (a) + (c), engine/data.py)

CONFIRMED the filed diagnosis end to end: yfinance 1.5.2 routes every call
through its curl_cffi singleton (`YfData._session`), which the egress proxy
resets with curl error 35. Passing yfinance a plain requests Session does NOT
help — its cookie/crumb handshake then 429s before any bar is fetched. So
remedy (b) is a dead end; (a)+(c) is what shipped.

REFINEMENT — the 429 is NOT rate limiting, it is User-Agent fingerprinting.
The issue read the second-hop 429 as "Yahoo throttles the non-impersonated
client". It is narrower and fully controllable. Same URL, same second, same
container, only the UA header varying:

    User-Agent: Mozilla/5.0                     -> 200, 24108 bytes
    User-Agent: <full Chrome 126 UA>            -> 429, 19 bytes
    User-Agent: <requests default>              -> 429, 23 bytes

Reproduced 3x alternating; deterministic, not a rate window. Yahoo appears to
429 a UA that CLAIMS a specific browser when the TLS fingerprint cannot back
that claim up — and behind this MITM proxy we cannot forge the fingerprint.
A generic `Mozilla/5.0` claims nothing and is served. This is why the desk's
existing "plain requests first" session ladder (added 2026-08-04) never
worked: `_session_candidates().plain()` sets a full Chrome UA, so the plain
path was self-defeating on the very header meant to make it look normal.
engine/data.py now pins CHART_UA = "Mozilla/5.0" with a comment warning
against "improving" it — that improvement is the outage.

WHAT SHIPPED (engine/data.py only; no protected file touched)
- `_chart_frame(payload, interval)` — parses v8 chart JSON into the exact frame
  yfinance(auto_adjust=True) returns: Close:=adjclose, O/H/L scaled by the same
  ratio, Volume untouched (matches yfinance/utils.auto_adjust), tz-naive dates
  for 1d/1wk/1mo, tz-aware for 1m/1h. Cache-concat compatible.
- `_chart_fetch()` — plain `requests`, query1 then query2, 20s timeout.
- `_yf_fetch()` — tries `_chart_fetch` FIRST, then falls through to the existing
  yfinance ladder unchanged, then the cache ladder unchanged.
- Source tagging: chart-fetched bars are genuinely live and tag "yf", per this
  issue's warning. `cache_stale` still blocks entries; nothing was weakened.

VERIFIED LIVE (post-fix, this container)
  RELIANCE snapshot: source "yf", last 1280.0, vol_ratio_20d 2.07
  — matches the live price in the EVIDENCE section, and replaces the wrong
  cached 1294.70 flagged under COLLATERAL FINDING (that 1.15% error is gone).
  NIFTY 24624.65 · TCS 2413.0 · INFY 1174.0 · USDINR 95.12 — index, equity and
  FX symbols all live, so URL-encoding of ^NSEI / =X is correct.

TESTS: 7 added in tests/test_data.py (35 total, all green). The S1 repro is
`test_live_when_yfinance_transport_is_reset` — kills yfinance's transport with
the curl-35 error, serves a canned chart response, and asserts the desk stays
source "yf" instead of degrading to cache_stale. `test_chart_ua_stays_generic`
locks the UA finding above so it cannot be regressed by a plausible-looking
edit. `test_chart_failure_still_degrades_to_cache` proves the old ladder is
intact when BOTH live paths are down — no silent live claim.

NOT FIXED HERE (still open, separate issues): single-source fragility remains —
this restores the Yahoo path, it does not add a second vendor (OPEN-...-1436),
and the growwapi SDK is still uninstallable so the broker LTP fallback stays
dead (OPEN-...-1339). The desk now has ONE working live path where it had zero.

## Closed
2026-08-05T17:01:06+05:30: fixed: direct Yahoo v8 chart fetch over plain requests with a generic Mozilla/5.0 UA (full-browser UA was the 429 trigger, not rate limiting); tried before yfinance, tags source=yf; 7 tests added, 35 green; RELIANCE live at 1280.0
