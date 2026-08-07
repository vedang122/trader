---
severity: S3
area: data
filed: 2026-08-07T10:26:06+05:30
title: engine.data ohlcv silently ignores the period argument and caps output at 60 rows, truncating every analyst's S&R window
---

## Observed
REPRO (2026-08-07, cloud cycle 10:17 IST):

$ python3 -m engine.data ohlcv INFY 6mo | wc -l
62
$ python3 -m engine.data ohlcv INFY 2y  | wc -l
62

Both return 62 lines (header + 60 data rows). The period argument ('6mo', '2y', presumably any value) has no effect on displayed output, and NOTHING in the output says so -- no warning, no 'truncated' marker, no row count.

WHY THIS MATTERS (not cosmetic): the technical-analyst builds support/resistance from this command. A support level needs multiple time-separated touches to qualify under the playbook; with a silent ~3-month cap, touches older than ~60 sessions are invisible, so an analyst asking for 2y of context believes it received 2y and constructs S&R from a window a quarter that size. It cannot detect the truncation because the cap is silent.

EVIDENCE OF REAL IMPACT this cycle: the INFY technical seat caught it and flagged the limitation explicitly ('6mo and 2y returned identical windows, so my S&R construction is effectively limited to ~3 months of visible daily bars'). The TCS seat, running the same command in parallel on the same cycle, did NOT catch it and built its S&R shelf (2460-2475) from the truncated window without qualification. Same defect, one seat caught it, one did not -- that is exactly the failure mode of a silent cap.

SUGGESTED FIX (engine owner's call): either honor the period argument for display, or print an explicit notice such as 'showing last 60 of N rows for <period>' so the caller knows the window is capped. Either is acceptable; silence is not.

## Engineer notes (append below)
