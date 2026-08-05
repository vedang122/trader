---
severity: S3
area: data
filed: 2026-08-05T17:03:04+05:30
title: session ladder's plain() sets the very User-Agent that Yahoo 429s; its docstring claims the opposite
---

## Observed
Found while fixing OPEN-20260805-1528 (now CLOSED). Not fixed there: the live
path was restored via the direct chart endpoint, and this one is unverifiable
benefit, so it was left alone rather than expanding that diff.

THE TRAP
engine/data.py `_session_candidates().plain()` sets a full Chrome 126 UA. The
measurements taken while closing the S1 (same URL, same second, 3x alternating,
see that issue's engineer notes) show Yahoo answers:
    Mozilla/5.0        -> 200
    full Chrome UA     -> 429
    requests default   -> 429
So the plain branch is self-defeating on the exact header meant to make it look
ordinary, and its docstring — "the sandbox egress proxy resets curl_cffi's
impersonated TLS, while a plain requests.Session passes" — is false on this
host. The next engineer reading that comment will believe layer 2 is healthy
when it is dead.

WHY IT IS ONLY S3
The desk is no longer standing on this path: `_yf_fetch` now tries the direct
v8 chart endpoint first and that works. This ladder is the fallback's fallback.

WHY IT WAS NOT JUST PATCHED
Swapping the UA to "Mozilla/5.0" likely does NOT revive yfinance anyway.
Measured: `yf.download(..., session=<plain requests.Session>)` fails with
YFRateLimitError before any bar is fetched — yfinance's cookie/crumb handshake
hits a DIFFERENT endpoint (quoteSummary / getcrumb) that 429s independently of
the chart endpoint's UA behaviour. So a one-line UA change would be an
unverified fix to a path that has a second, separate blocker. It needs someone
to establish whether the crumb handshake can be made to pass at all here, and
if it cannot, the honest change is to DELETE the yfinance ladder on this host
rather than pay 7s of backoff sleeps per symbol pretending it might work.

SUGGESTED
Either (a) prove the crumb path can pass and fix the UA, or (b) drop the
yfinance layer and let `_chart_fetch` be the sole Yahoo transport, with the
cache ladder unchanged beneath it. Correct the docstring either way.

## Engineer notes (append below)
