---
severity: S3
area: charges
filed: 2026-08-10T12:26:03+05:30
title: engine.charges crashes with a raw ValueError traceback on --help or any non-numeric argv instead of printing usage
---

## Observed
Every other engine module answers --help or bad args gracefully; engine.charges dies in argv parsing at module import time.

REPRO (this cycle, 2026-08-10 12:18 IST):
  $ python3 -m engine.charges --help
  Traceback (most recent call last):
    File "<frozen runpy>", line 198, in _run_module_as_main
    File "<frozen runpy>", line 88, in _run_code
    File "/home/user/trader/engine/charges.py", line 34, in <module>
      entry, target, qty = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
                           ^^^^^^^^^^^^^^^^^^
  ValueError: could not convert string to float: '--help'

Correct invocation works fine: 'python3 -m engine.charges 1079.8 1146.4 2' -> 'round-trip charges: 26.69 | gross gain to target: 133.20 | cost drag: 20.0%'.

IMPACT: cosmetic/usability only, NOT a trading-correctness or safety defect. The cost model itself computed correctly all cycle and its numbers were consistent with engine.risk.validate's independent 'cost drag' note (both said 20% for entry 1079.8 / target 1146.4 / qty 2). Filed for completeness because it is a genuine uncaught crash on a reasonable invocation, and a desk agent probing the charge model for the first time will hit it. Suggested fix: guard argv length and catch ValueError, print 'usage: python3 -m engine.charges <entry> <target> <qty>'.

## Engineer notes (append below)
