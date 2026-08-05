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
