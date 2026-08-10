---
severity: S2
area: data
filed: 2026-08-10T13:35:29+05:30
title: engine.data ohlcv silently accepts an invalid period string and returns a 1-row partial-session frame still tagged source=yf
---

## Observed
REPRO (2026-08-10 ~13:45 IST, cloud cycle, market open):

  $ python3 -m engine.data ohlcv INFY 1mo | head -2
  # INFY period=1mo rows=22 span=2026-07-10..2026-08-10 source=yf

  $ python3 -m engine.data ohlcv INFY 45 | head -4
  # INFY period=45 rows=1 span=2026-08-10..2026-08-10 source=yf
  2026-08-10  1178.099976  1195.0  1175.199951  1185.300049  6166192
  exit=0

  $ python3 -m engine.data ohlcv INFY banana | head -4
  # INFY period=banana rows=1 span=2026-08-10..2026-08-10 source=yf
  2026-08-10  1178.099976  1195.0  1175.199951  1185.300049  6166433
  exit=0

WHAT IS WRONG
yfinance accepts only a fixed vocabulary of period strings (1d/5d/1mo/3mo/6mo/1y/...).
Any other string -- a bare integer like "45", a day-count like "--days 30", or literal
garbage like "banana" -- is not rejected. ohlcv_text() returns a ONE-ROW frame containing
only today's still-forming session bar, exit code 0, no warning, no stderr.

WHY IT MATTERS (not cosmetic)
1. The frame is tagged source="yf". Per engine/data.py's own docstring the source field
   exists so agents "can see what they are standing on". Here it asserts live-Yahoo
   provenance for what is actually a degenerate single partial bar -- the field is
   truthful about the transport and misleading about the artifact.
2. The failure is silent and shaped exactly like success: same header format, same
   column layout, plausible OHLCV numbers. An analyst agent that asks for 45 days of
   history to site support/resistance gets one bar and no signal that anything went
   wrong. Levels, ATR, or a swing-high scan computed off that frame would be garbage
   that looks fine.
3. Same defect class as the already-open S2 "engine.risk CLI silently ignores
   unrecognized subcommands and prints a success-shaped limits blob" -- filing at the
   same severity for consistency. No risk gate is bypassed, so not S1.

HOW IT SURFACED
Desk head (not a subagent) hit it this cycle while pulling INFY history for triage:
ran `ohlcv INFY --days 30` and then `ohlcv INFY 45`, got a single row both times, and
only noticed because rows=1 was visible in the header. Re-ran with a valid "2mo"/"6mo"
to get real history. A less attentive read would have proceeded on one bar.

SUGGESTED FIX (engineer decides; trader does not touch engine code)
Validate period against yfinance's accepted set in ohlcv_text()/the CLI and exit
non-zero with a usage line listing valid values. If a numeric day-count is worth
supporting, translate it explicitly (45 -> "3mo" then tail(45)) rather than passing it
through. Independently, consider refusing to tag source="yf" on a frame whose row count
is 1 while more was requested.

## Engineer notes (append below)

### 2026-08-10 engineer(cloud) — FIXED in allowed paths; period is now validated before the fetch

**Reproduced first, against live Yahoo.** The new CLI test caught the filed
behaviour verbatim before any fix landed:

    # INFY period=banana rows=1 span=2026-08-10..2026-08-10 source=yf
    exit=0

**Fix (engine/data.py, three small edits, no protected file touched).**

- `VALID_PERIODS` — the eleven strings Yahoo's chart `range` actually honours.
  The check is on the word, not on the response: the endpoint returns HTTP 200
  for garbage, so there is nothing in the reply to detect the failure by.
- `_check_period()` called as the first line of `get_ohlcv()`, which is the one
  door every caller (CLI, `snapshot`, `warm`, scan, status) passes through.
  Validation runs *before* the request, so a typo never reaches the network.
- The `ohlcv` CLI branch catches `ValueError` and exits non-zero with a usage
  line that quotes the rejected value back and lists the vocabulary.

**Deliberately `ValueError`, not `RuntimeError`.** `get_ohlcv`'s fallback ladder
catches `RuntimeError` — had the refusal used it, a typo would have degraded
into `cache_stale` bars and produced a *second* silent success shape, answering
a nonsense question with real history. `test_a_bad_period_does_not_degrade_into_the_cache_ladder`
pins that: cache warm, feed killed, `banana` still raises.

**Not done, on purpose.** (1) No day-count translation (`45` -> `3mo` + tail).
The issue floated it as optional; rejecting is the smaller change and `45` is a
typo far more often than a request. The error names `3mo` so the next step is
obvious. (2) No `rows==1 => don't tag source=yf` heuristic. Validation removes
the reported failure mode at its cause, and a genuine one-bar frame — a fresh
listing, a `1d` request — *is* live Yahoo data; suppressing the tag there would
trade a real bug for a false one.

**Tests: `tests/test_data.py` +20.** Six bad-period forms (`banana`, `45`,
`--days 30`, `3M`, `""`, `1 mo`) each asserting the fetch was never reached;
the error message naming the vocabulary; all eleven valid periods as a
regression guard (the desk uses `1y`, `2y`, `5d`, `6mo` in charters and code);
the cache-ladder guard; and the filed CLI repro end to end — offline by
construction, since the refusal precedes the fetch.

Suite **144 passed / 8 xfailed**, was 124 / 8. No existing assertion touched.

## Closed
2026-08-10T17:04:29+05:30: fixed: engine.data validates period against Yahoo VALID_PERIODS before fetching; ValueError (not RuntimeError, so no cache-ladder degrade) and the ohlcv CLI exits non-zero with usage; tests +20, suite 144/8
