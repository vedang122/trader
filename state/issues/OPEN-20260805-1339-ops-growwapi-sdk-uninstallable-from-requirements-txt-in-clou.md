---
severity: S2
area: ops
filed: 2026-08-05T13:39:20+05:30
title: growwapi SDK uninstallable from requirements.txt in cloud env - live-LTP fallback silently dead, preflight never probes it
---

## Observed
EVIDENCE (cloud cycle 2026-08-05 ~13:20 IST, fresh clone):

1. yfinance is hard-down on this egress - NOT an SSL/proxy fault, it is an upstream rate limit:
   $ curl -sS -o /dev/null -w '%{http_code}' 'https://query1.finance.yahoo.com/v8/finance/chart/RELIANCE.NS?range=5d&interval=1d'
   429
   $ curl -sS 'https://$HTTPS_PROXY/__agentproxy/status'  -> enabled, recentRelayFailures: []
   The 'SSLError / Recv failure: Connection reset by peer' that prior cycles reported is Yahoo dropping connections under 429, not a TLS problem. Prior cycle notes attributing it to SSL are misleading.

2. The Groww live-LTP fallback - the ONLY thing that makes a DEGRADED verdict survivable - was dead for a trivial reason:
   $ python3 -m engine.data growwcheck
   {"creds_present": true, "auth": "FAILED - No module named 'growwapi'", "ltp_reliance": null}

3. Root cause: 'pip install -r requirements.txt' FAILS to install growwapi in this container. growwapi -> clint -> args, and args/clint fail to build:
   AttributeError: install_layout. Did you mean: 'install_platlib'?
   ERROR: Could not build wheels for clint, args
   pip then exits 0 for the other packages, so the failure is easy to miss.

   WORKAROUND that worked (took 4 rounds - growwapi's runtime imports are not covered by --no-deps):
   pip install --no-deps growwapi && pip install pyotp pynacl protobuf websocket-client nkeys nats-py
   -> {"creds_present": true, "auth": "ok (TOTP flow)", "ltp_reliance": 1285.5}
   After this, snapshots returned source 'cache+groww_ltp' with live prices instead of 'cache_stale'.

WHY THIS IS A SAFETY GAP (not just an install annoyance):
engine.ops preflight returned verdict DEGRADED with feed detail 'cache fresh enough for daily bars' - while the live-LTP fallback was completely non-functional. The DEGRADED contract in trade-cycle SKILL.md is 'position defense and exits allowed on live LTP'. If the desk had held open positions, it would have believed it could defend the book and detect a stop breach when it had NO live price at all. This cycle the book was flat so nothing materialized. Filed S2 rather than S1 only because the book was flat and the engine degraded honestly rather than fabricating a price.

ASKS:
(a) requirements.txt should install growwapi in a way that actually works in the cloud container (pin/vendor around the clint/args build break, or drop to the minimal runtime dep set listed above). A silent install failure of the fallback feed is the real defect.
(b) engine.ops preflight should PROBE the live-LTP fallback (cheap growwcheck-style call) and surface it, e.g. feed.live_ltp: ok|dead. A DEGRADED verdict whose stated remedy is 'exits allowed on live LTP' must verify that live LTP actually exists. Right now DEGRADED-with-working-Groww and DEGRADED-with-dead-Groww are indistinguishable to the desk head, and only one of them is survivable with positions open.
(c) preflight's feed detail string 'cache fresh enough for daily bars' is reassuring in a way the state does not earn - see the related open issue OPEN-20260805-1226.

## Engineer notes (append below)
