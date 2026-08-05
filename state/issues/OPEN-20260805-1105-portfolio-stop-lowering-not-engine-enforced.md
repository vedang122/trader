---
severity: S2
area: portfolio
filed: 2026-08-05T11:05:54+05:30
title: stop-lowering not engine-enforced
---

## Observed
Non-negotiable 'stops never move down' is enforced only by agent convention. Nothing in portfolio.apply_fill or execute.py rejects a ticket/state change that lowers an existing position's stop. An agent bug could silently widen risk. Proposed: apply_fill (or a dedicated update path) must reject stop < current stop for longs. Protected paths (portfolio.py/execute.py) — needs human-reviewed fix.

## Engineer notes (append below)
