---
severity: S3
area: data
filed: 2026-08-08T16:53:45+05:30
title: carried Volume under a genuine close: CRUDE 08-04/08-05 share vol=362270 exactly, so vol_ratio_20d and the roll detector's volume step both read a stale number
---

## Observed
## Observed
Found while fixing OPEN-20260806-0826-data (futures-proxy roll/carry). That issue's
guard (b) — drop a bar whose close AND nonzero volume both equal the prior bar's —
landed and is correct, but it does not fire here, because the close is genuine and
only the volume is carried.

state/cache/ohlcv/CRUDE.csv, read with its real header (Date,Close,High,Low,Open,Volume):

| date | Open | Close | Volume |
|---|---|---|---|
| 2026-08-03 | 80.099998 | 80.339996 | 294,823 |
| 2026-08-04 | 80.099998 | 75.769997 | 362,270 |
| 2026-08-05 | 75.169998 | 75.220001 | 362,270 |
| 2026-08-06 | 78.169998 | 78.180000 | 8,495 |

Volume is byte-identical across 08-04/08-05; Open is byte-identical across
08-03/08-04. All four closes are distinct. GOLD shows the same shape (426 repeated
on 08-04/08-05). Reproduce:

    python3 -c "
    import pandas as pd
    for s in ['CRUDE','GOLD']:
        df=pd.read_csv(f'state/cache/ohlcv/{s}.csv',index_col=0,parse_dates=True).tail(5)
        print(s, [str(d.date()) for d in df.index[df['Volume'].diff()==0]])"

## Why it matters
Two consumers read that volume as if it were real:

1. `snapshot()['vol_ratio_20d']` — participation confirmation. A carried volume
   makes a quiet session look as busy as the previous one, or vice versa.
2. `data._roll_suspected()` — its volume-step arm divides by the prior bar's
   volume. On CRUDE 08-06 the 42.6x step is measured against 08-05's *stale*
   362,270, not a real one. That errs toward withholding change_pct, which is the
   safe direction under "no data >= bad data", so the current behaviour is
   conservative rather than wrong — but the number driving it is not a clean read.

S3 not S2: unlike the fabricated change_pct in the parent issue, no fabricated
value currently reaches the regime score from this — the failure mode is a
degraded confirmation signal and an unclean input to a guard that already fails safe.

## Suggested direction
The remedy is NOT the parent issue's remedy. Dropping the bar would discard a
genuine close, which is the more valuable half of it. Instead treat the volume
field alone as unknown:

  (a) At ingest, when a bar's nonzero volume exactly equals the prior bar's while
      its close differs, blank that bar's Volume (NaN) rather than drop the row.
  (b) Have `vol_ratio_20d` return None for a bar with no trustworthy volume — the
      same contract it already honours for cache+groww_ltp bars (Volume=0).
  (c) Have `_roll_suspected` decline to judge (return False) when either bar's
      volume is untrustworthy, so the gap arm alone never trips it.

Also worth a look: whether the duplication is Yahoo's or ours. `_save_cache`
concats old+new and keeps `last` per index, which cannot duplicate a value across
*adjacent distinct dates*, so this most likely arrives from the feed — but the
repeated Open on 08-03/08-04 suggests a partial-bar overwrite path worth ruling out.

## Note for whoever reads the parent issue
OPEN-20260806-0826-data's repro script mis-indexes the CSV (`r[1]` is Close, not
Open; `r[4]` is Open, not Close), so its "IDENTICAL close AND volume" table is
column-swapped. The bars are genuinely corrupt; the stated mechanism was not the
real one. Details in that issue's 2026-08-08 engineer note.

## Engineer notes (append below)
