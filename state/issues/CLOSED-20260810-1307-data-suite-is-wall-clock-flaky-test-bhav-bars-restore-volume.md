---
severity: S2
area: data
filed: 2026-08-10T13:07:20+05:30
title: suite is wall-clock flaky: test_bhav_bars_restore_volume_confirmation fails whenever pytest runs during NSE hours, so the CI merge gate strands every branch 09:15-15:30 IST
---

## Observed
REPRO: on a clean clone at 13:03 IST, python3 -m pytest tests/ -q gives 1 failed, 122 passed - tests/test_data.py::test_bhav_bars_restore_volume_confirmation, assert None is not None on snap[vol_ratio_20d]. The same clone is green after 15:30.

MECHANISM: the test fake _serve_bhav answered EVERY archive date with the same canned zip, including todays. The real archive never does that - _bhav_day documents it: NSE publishes a session only after it settles (~18:00 IST), so today before publication reads as a missing file. Serving it dated a bhav bar to a session still in progress, so _partial_session (added later, in c83df7e) saw newest bar == today AND market open, judged the bar still forming, and withheld vol_ratio_20d. Probe confirms: market pinned closed gives vol_ratio 1.92 / vol_partial_session False; pinned open gives None / True, last bar stamped todays date.

NOT a production defect: mid-session the real _bhav_day(today) 404s, so a nse_bhav frame is never dated today while the session is open. The fault is fixture fidelity, and the cost is real - the merge gate reruns this suite, so during market hours every engineer branch fails to merge.

FIX: _serve_bhav now 404s todays date, matching the exchange publication schedule. Added test_bhav_vol_confirmation_survives_an_open_session, which pins market_status to open so the claim is asserted at any hour instead of only after the close. No existing assertion changed.

## Engineer notes (append below)

## Closed
2026-08-10T13:07:31+05:30: fixed: _serve_bhav now 404s todays archive date to match NSEs post-settlement publication, so a bhav bar is never stamped to a live session; added a clock-pinned regression test. Suite 124 passed, 8 xfailed, green during market hours.
