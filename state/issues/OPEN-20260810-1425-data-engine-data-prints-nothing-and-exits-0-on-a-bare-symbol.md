---
severity: S3
area: data
filed: 2026-08-10T14:25:27+05:30
title: engine.data prints nothing and exits 0 on a bare symbol argv, while a bare no-arg call returns a NIFTY quote
---

## Observed
Repro (2026-08-10 ~14:25 IST, cloud cycle):

  $ python3 -m engine.data TATASTEEL
  (no output)
  exit code: 0

  $ python3 -m engine.data
  {"symbol": "NIFTY", "source": "yf", "last": 24587.65, ...}

  $ python3 -m engine.data quote TATASTEEL
  {"symbol": "TATASTEEL", "last": 190.9199981689453}

Only the third form works. The trap: 'engine.data <SYMBOL>' is the most natural
invocation an agent will type, and it is silently a no-op with a SUCCESS exit
code -- indistinguishable from 'the feed returned nothing for this symbol'.
Meanwhile the no-arg form does NOT error either; it silently substitutes NIFTY,
so an agent that drops its argv gets an index quote where it expected a stock.

Same defect class as the already-open S2 'engine.risk CLI silently ignores
unrecognized subcommands' and S2 'engine.data ohlcv silently accepts an invalid
period string' -- unrecognized argv should exit non-zero with a usage line, never
succeed silently. Filed separately because it is a different module entry point
and the NIFTY-default fallback is an extra failure mode not covered by those two.

Impact this cycle: none on decisions (caught immediately because a JSON parse of
the empty output raised). Filed as S3, not S2, because the wrong-data path
requires argv to be dropped entirely rather than merely mistyped.

## Engineer notes (append below)
