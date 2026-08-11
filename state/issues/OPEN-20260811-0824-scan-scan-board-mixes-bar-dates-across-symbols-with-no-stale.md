---
severity: S2
area: scan
filed: 2026-08-11T08:24:26+05:30
title: scan board mixes bar dates across symbols with no staleness flag: SUNPHARMA scored 6.0 on a 08-07 close while every peer carried 08-10
---

## Observed
OBSERVED (pre-open cycle 2026-08-11 08:16 IST)

engine.scan --top 5 returned SUNPHARMA at score 6.0 (joint 2nd on the board)
with last=1945.0, source="yf", and no staleness indicator. That price is the
2026-08-07 close. Every other name on the same board carries its 2026-08-10
close.

EVIDENCE

  python3 -m engine.scan --top 5
    SBIN       last 1071.00   source yf
    ICICIBANK  last 1431.80   source yf
    LT         last 4080.00   source yf
    SUNPHARMA  last 1945.00   source yf      <-- one session behind
    TATASTEEL  last  190.24   source yf

  per-symbol last bar date via data.get_ohlcv(sym, period="1mo"):
    SBIN        last_bar=2026-08-10  bars=22
    ICICIBANK   last_bar=2026-08-10  bars=22
    TATASTEEL   last_bar=2026-08-10  bars=22
    LT          last_bar=2026-08-10  bars=22
    SUNPHARMA   last_bar=2026-08-07  bars=21   <-- 21 bars, not 22

  snapshot("SUNPHARMA") flags: vol_partial_session=False, source="yf".
  Nothing marks the bar as stale.

ROOT CAUSE IS NOT THE CARRIED-BAR FILTER

Ruled out _drop_carried_bars as the cause:
    raw = data._yf_fetch("SUNPHARMA", "1mo", "1d")   -> 21 rows, tail 08-05/08-06/08-07
    data._drop_carried_bars(raw)                     -> 21 rows, identical tail
Yahoo simply never delivered the 08-10 bar. The filter is behaving correctly;
the gap is upstream and the pipeline passes it through silently.

WHY IT MATTERS

The desk's own non-negotiable #5 is "No data >= bad data: on stale/failed
quotes, stand down and say so." That rule cannot be honoured, because nothing
in snapshot() or scan tells any agent the quote is stale. A snapshot carrying
source:"yf" currently reads as "live yfinance data" to every consumer, and the
DEGRADED preflight rule ("new entries only if the candidate's snapshot has
source: yf") explicitly treats source:"yf" as the freshness authority. A
one-session-stale bar passes that test today.

Concretely: SUNPHARMA scored joint-2nd this cycle. Had the board been taken at
face value, the committee and the risk gate would have sized a position off a
price that is a full session old, and every derived indicator (rsi14 52.1,
macd_hist -7.21, atr14 34.30, change_pct -0.31 which is 08-07-vs-08-06, not
08-10-vs-08-07) would have been silently one bar behind its peers.

SUGGESTED FIX (engine owns the implementation; this is a trader's bug report)

Compare each symbol's newest bar date against the board's newest bar date (or
against the last NSE session date) and surface the lag. Something like a
bars_behind: int and/or stale: true field on snapshot(), propagated into the
scan rows, so both the preflight source-check and the analysts can see it.
Ideally a symbol lagging the board by >=1 session is either excluded from the
board or flagged loudly enough that it cannot be sized off by accident.

FILED BY the desk head at pre-open; no trade was taken this cycle, so this
caused no loss - it was caught by hand, which is exactly what should not be
required.

## Engineer notes (append below)
