---
severity: S2
area: data
filed: 2026-08-06T08:26:46+05:30
title: futures-proxy series (GOLD/CRUDE) carry roll discontinuities and duplicated bars; change_pct reports fake moves into the regime score
---

## Observed
OBSERVED 2026-08-06 pre-open cycle, while auditing the macro-sentinel's inputs.

The macro-sentinel reported gold "+6.0% 1-day" and flagged it itself as
"possibly a futures-roll artifact." It was right. Auditing the cached bars
shows the futures-backed proxies are structurally unreliable in two ways, and
BOTH feed the weighted regime score.

Reproduce:
  python3 -c "
  import csv
  for sym in ['GOLD','CRUDE']:
      rows=[r for r in csv.reader(open(f'state/cache/ohlcv/{sym}.csv')) if r and r[0][:2]=='20'][-5:]
      prev=None
      for r in rows:
          d,o,c,v=r[0],float(r[1]),float(r[4]),float(r[5])
          g='' if prev is None else f' gap={(o-prev)/prev*100:+.2f}%'
          print(sym,d,f'O={o:9.2f} C={c:9.2f} vol={v:>9.0f}{g}')
          prev=c"

--------------------------------------------------------------------
(A) ROLL DISCONTINUITY -- GOLD (GC=F)
--------------------------------------------------------------------
  2026-07-31 O= 4049.10 C= 4102.40 vol=     1166
  2026-08-03 O= 4033.70 C= 4083.40 vol=      698
  2026-08-04 O= 4095.40 C= 4050.50 vol=      698
  2026-08-05 O= 4341.40 C= 4307.00 vol=    33963  gap=+7.18%

The volume signature is the tell: 1166 -> 698 -> 698 is an expiring contract
bleeding liquidity, then 33,963 is the new front month. The +7.18% overnight
"gap" is a CONTRACT CHANGE, not a gold move. Independent check (WebSearch, spot
XAU): ~4132 two days ago -> ~4268 today, i.e. roughly +3.3% over two sessions --
real, but nothing like a +6-7% single-day print.

--------------------------------------------------------------------
(B) DUPLICATED / CARRIED BARS -- CRUDE (CL=F)
--------------------------------------------------------------------
  2026-08-03 O=   80.34 C=   80.0999984741211 vol=   294823
  2026-08-04 O=   75.77 C=   80.0999984741211 vol=   294823   <-- IDENTICAL close AND volume
  2026-08-05 O=   75.56 C=   75.14 vol=    11257

The 2026-08-04 bar repeats 08-03's close to the last float bit AND its exact
volume, while carrying its own open of 75.77. The result is an incoherent bar
(O=75.77, C=80.10, +5.7% intrabar) that reconciles with neither neighbour --
08-05 opens at 75.56, right where 08-04 OPENED, not where it "closed."
GOLD shows the same duplicate-volume signature on 08-03/08-04 (698, 698).

--------------------------------------------------------------------
WHY S2
--------------------------------------------------------------------
Per the macro-sentinel's published vote table, crude and gold are each weighted
1.0 of a 5.5 total -- together **36% of the regime score**. The regime is not
advisory: it deterministically sets gross_multiplier (0.4x / 0.7x / 1.0x), which
engine/risk.py:87-90 enforces as the gross exposure cap on every order.

So a fabricated ±6-7% print in a weighted input can move the score across a band
boundary and mechanically resize the desk's entire risk envelope. Today's score
was +0.55 -- already sitting on the +0.5 risk-on line. A single bad input at
1.0 weight is ~0.18 of score, i.e. more than enough to cross it.

It did not go wrong today for one reason only: the macro-sentinel distrusted the
number and spent a WebSearch cross-checking spot gold. That is the second time
this cycle (see OPEN-20260806-0820-news, stale-headline filter) that an agent's
skepticism substituted for an absent Python guard. CLAUDE.md's rule is that
these are "always capped by Python, never by promise."

Note the clean contrast: DXY, USDINR, INDIAVIX and NIFTY show no gaps, no
duplicate closes, no volume anomalies over the same window. This is specific to
the CME futures proxies, not a general feed problem -- the feed restoration from
last night is working.

ASKS:
  (a) Detect roll discontinuities: flag/suppress change_pct when an open gaps
      >3% from the prior close AND volume changes by more than ~5x. Emit
      `roll_suspected: true` on the snapshot rather than a fake percentage.
  (b) Reject duplicate bars at ingest: if a new bar's close AND volume both
      exactly equal the prior bar's, do not store it -- carry a gap instead.
      An exact float-identical close is never a real second session.
  (c) Prefer non-rolling proxies for the regime inputs where one exists --
      e.g. spot gold (XAUUSD=X) over GC=F, and Brent spot over CL=F. The desk
      only needs direction and magnitude, and never trades these instruments,
      so continuous-contract fidelity buys nothing while costing correctness.
  (d) If (c) is not taken, surface `contract` / roll date on the snapshot so a
      consumer can see which contract a level belongs to.

## Engineer notes (append below)
