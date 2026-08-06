---
severity: S2
area: risk
filed: 2026-08-06T11:23:34+05:30
title: engine.risk CLI silently ignores unrecognized subcommands and prints a success-shaped limits blob with exit 0
---

## Observed
OBSERVED during cloud cycle 2026-08-06 11:20 IST while trying to pre-check a candidate order against the gate.

engine/risk.py:99 handles exactly one subcommand:
    if len(sys.argv) > 1 and sys.argv[1] == 'size':
Everything else falls through to the module's default path, which prints {limits: {...}, regime: {...}} and exits 0.

REPRO (all three produce identical output, exit 0):
  $ python3 -m engine.risk check --symbol LT --side BUY --qty 1 --price 4063.4 --stop 3995 --target 4200
  $ python3 -m engine.risk check --symbol FAKE --qty 999 --price 1 --stop 2
  $ python3 -m engine.risk florble
  -> {"limits": {"capital_base": 10000, ...}, "regime": {...}}  exit=0

WHY IT MATTERS (not a bypass, but a misleading-success hazard):
The output is JSON, contains the risk limits, mentions no violations, and exits 0. An agent that runs a pre-check this way gets something that looks exactly like a clean verdict for an order that was never evaluated. In this cycle the order in question (LT, 1 share @ 4063.40) actually VIOLATES max_position_notional_pct -- 4063 > 35%% of 10000 = 3500, which engine/risk.py:80 would reject -- yet the CLI returned the success-shaped blob. I only caught it because I did the arithmetic by hand.

Severity S2 not S1: the authoritative gate inside engine/execute.py still runs and would reject the order, so nothing can actually reach a broker unchecked. The defect is that the CLI invites a false clean read at the judgment layer.

SUGGESTED FIX: argparse with subcommands and a nonzero exit on unknown args; and/or an actual 'check' subcommand exposing the existing violation logic (engine/risk.py:79-86) so pre-checks are real. Related: OPEN-20260806-0824 (engine.risk size ignores notional/cash/gross caps) -- same surface, and this cycle produced a second concrete instance of it: 'engine.risk size 4063.4 3995' returned qty=1, a notional the gate forbids.

## Engineer notes (append below)
