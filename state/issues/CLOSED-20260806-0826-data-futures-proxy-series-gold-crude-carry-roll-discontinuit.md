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

### 2026-08-08 engineer(cloud) — (a) and (b) landed in engine/data.py; one correction to the filed evidence

`engine/data.py` is an allowed path, so this is a real fix, not a proposed patch.
Two deterministic guards, four tests (`tests/test_data.py`), suite 95 passed /
5 xfailed. No existing assertion touched.

**(a) Roll discontinuity — landed.** `_roll_suspected(symbol, df)` fires when the
newest bar's open gaps >3% off the prior close AND volume steps by more than 5x
(either direction). On a hit, `snapshot()` returns `change_pct: None` and
`roll_suspected: true` instead of the fabricated percentage; `last` is still
reported, since the level is the best level we have. Pinned to `=F` symbols on
purpose — an equity gapping hard on 5x volume is an earnings reaction, the most
informative print the desk gets, and suppressing that would be the worse bug.
There is a test asserting exactly that (`test_earnings_gap_on_an_equity_is_not_a_roll`).

Verified against the live cache, not just fixtures: CRUDE's 2026-08-06 bar
(open 78.17 vs prior close 75.22 = +3.92%, volume 8,495 vs 362,270 = 42.6x)
**flags true today**, so the fake print this issue was filed about is now
withheld rather than voted into the regime score. GOLD's 08-06 bar does not flag
(open gap +1.24% fails the 3% arm even though volume stepped 31.8x) — that is
the AND semantics ask (a) specified, and a 1.24% gap is not a fabricated move.

**(b) Carried bars — landed as specified.** `_drop_carried_bars()` refuses, at
fetch ingest, any bar whose close AND nonzero volume both exactly equal the prior
bar's, so it can never reach the cache. Zero-volume series (FX, indices) are
exempt: there an unchanged close is a real quiet session, and dropping it would
invent gaps in the one part of the feed this issue notes is clean
(`test_flat_zero_volume_session_survives_ingest` pins that).

**Correction to the filed evidence for (B).** The repro script in this issue reads
`d,o,c,v = r[0], float(r[1]), float(r[4]), float(r[5])`, but the cache CSV header
is `Date,Close,High,Low,Open,Volume`. So `r[1]` is **Close**, not Open, and `r[4]`
is **Open**, not Close — the printed columns are swapped, and "IDENTICAL close" was
actually an identical *open*. Reading the file with its real header:

| date | Open | Close | Volume |
|---|---|---|---|
| 2026-08-03 | 80.099998 | 80.339996 | 294,823 |
| 2026-08-04 | 80.099998 | 75.769997 | 362,270 |
| 2026-08-05 | 75.169998 | 75.220001 | 362,270 |
| 2026-08-06 | 78.169998 | 78.180000 | 8,495 |

Every close is distinct. What actually repeats byte-identically is **Open** on
08-03/08-04 and **Volume** on 08-04/08-05. The bars are still corrupt — the
mechanism is just not the one filed. So guard (b) is correct as written (a bar
agreeing with its predecessor on both close and a nonzero volume is never a real
second session) but does **not** fire on today's file, and this issue's (B)
evidence should not be cited as proof that it does.

The residual — a carried *volume* under a genuine close — is a different defect
needing a different remedy (suppress volume-derived outputs for that bar rather
than drop a real price), so per the one-issue-per-run rule it is filed separately
rather than fixed here. It also explains a conservative false positive worth
naming: because 08-05's volume is stale, the roll detector's 42.6x step on 08-06
is measured against a carried number. That errs toward withholding `change_pct`,
which is the safe direction under "no data ≥ bad data", but it is not a clean read.

**(c) and (d) not taken.** (c) swaps the desk's macro inputs to spot proxies
(XAUUSD=X for GC=F). That changes what the desk looks at, not whether the code is
correct — a desk/data-source decision above an engineer's remit, and Yahoo has no
true Brent *spot* series (BZ=F rolls too), so it is only half available anyway.
(d) needs contract identity that Yahoo's continuous series does not expose;
`roll_suspected` delivers the actionable half of that ask. Both remain open
questions for the human, not defects in the code as it now stands.

Closing: the S2 harm this issue names — a fabricated `change_pct` reaching the
weighted regime score and mechanically resizing the gross cap — is now gated by
Python rather than by an agent's skepticism.

## Closed
2026-08-08T16:54:06+05:30: fixed: engine/data.py gates futures-proxy roll artifacts in Python — _roll_suspected() withholds change_pct and emits roll_suspected on a >3% open gap plus >5x volume step (pinned to =F so equity earnings gaps survive), and _drop_carried_bars() refuses at ingest any bar repeating the prior close AND nonzero volume. Verified firing on the live CRUDE 08-06 bar. 4 tests added; suite 95 passed. Filed OPEN-20260808-1653-data for the residual carried-volume case; asks (c)/(d) are desk data-source decisions left to the human.

**Addendum — one bound added after a self-check caught a regression I introduced.**
The first cut of `_drop_carried_bars` collapsed a fully flat nonzero-volume frame to
a single bar, and `snapshot()` then raised `IndexError` on `c.iloc[-2]` — trading a
stale-volume problem for a crash in the one module whose job is graceful
degradation. The guard now returns the frame untouched if the carried bars are a
majority or fewer than 2 would survive: a mostly-carried frame is one the heuristic
does not understand, so distrust the guard, not the data.
`test_carry_guard_never_strips_a_frame_to_nothing` pins it. Final suite: 96 passed,
5 xfailed (baseline was 91/5); 5 tests added.

Live-cache behaviour after the bound, for the record:

| symbol | yf | rows before/after guard | roll_suspected |
|---|---|---|---|
| GOLD | GC=F | 420 / 420 | false |
| CRUDE | CL=F | 420 / 420 | **true** |
| NIFTY | ^NSEI | 420 / 420 | false |
| USDINR | USDINR=X | 420 / 420 | false (=X is not =F — FX is not a rolling contract) |
