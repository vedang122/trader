---
severity: S3
area: scan
filed: 2026-08-10T15:20:19+05:30
title: scan score is blind to the cost gate: SUNPHARMA ties for top board score while its minimum cost-viable target sits above its own 52-week high
---

## Observed
Cycle 2026-08-10 15:16 IST. SUNPHARMA scored 6.0, tied for the top of the board, and passes the notional cap (1 share = Rs 1949.30, 19.5 pct of capital, under the Rs 3500 cap). But it cannot clear the 25 pct cost-drag ceiling at any feasible share count. Evidence, all via python3 -m engine.charges: 1 share 1949.30 to 2000 = drag 50.5 pct; to 2025 = 33.9 pct; to 2052 = 25.0 pct. So the minimum cost-viable target is 2052, which is ABOVE the name 52-week high of 2046.90, in a stock that has been range-bound 1930-1990 for seven sessions with a bearish MACD cross and price under sma20. The trade is arithmetically impossible before any chart opinion is formed, yet the scan surfaces it at the top of the board and the desk head must recompute charges by hand every cycle to discover this. This is a DIFFERENT axis from the existing open S3 about LT and the notional cap: SUNPHARMA passes the notional cap and still cannot be traded. Same cycle, SBIN also failed: 3 shares 1071 to 1093 = 47.5 pct drag, to 1110 = 26.9 pct, still over ceiling. Ask: have scan emit a cost_viable flag or a min_viable_target per candidate, computed from charges.py against the 25 pct ceiling and the notional cap, so un-takeable names are ranked down or marked rather than topping the board. Third consecutive cycle where cost drag, not the chart, was the binding constraint.

## Engineer notes (append below)
