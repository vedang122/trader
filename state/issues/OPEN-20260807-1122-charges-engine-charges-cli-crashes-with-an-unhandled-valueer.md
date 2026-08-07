---
severity: S3
area: charges
filed: 2026-08-07T11:22:24+05:30
title: engine.charges CLI crashes with an unhandled ValueError traceback on --help or any non-numeric arg instead of printing usage
---

## Observed
Discovered during the 2026-08-07 11:16 IST cloud cycle while probing the cost-viability gate.

COMMAND:
  python3 -m engine.charges --help

ACTUAL OUTPUT:
  Traceback (most recent call last):
    File "<frozen runpy>", line 198, in _run_module_as_main
    File "<frozen runpy>", line 88, in _run_code
    File "/home/user/trader/engine/charges.py", line 34, in <module>
      entry, target, qty = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
                           ^^^^^^^^^^^^^^^^^^
  ValueError: could not convert string to float: '--help'

EXPECTED: a usage line, e.g. 'usage: python3 -m engine.charges <entry> <target> <qty>', and a non-zero exit without a traceback.

WHY IT MATTERS: charges.py parses sys.argv positionally at module top level with no argc check and no try/except. Any agent that probes the CLI to learn its signature -- the natural first move -- gets an unhandled traceback rather than usage. Same crash for a missing arg (IndexError) or a typo'd number. Low severity (the gate itself computes correctly when called with three numerics: verified 'python3 -m engine.charges 1441.5 1544.5 1' -> 'round-trip charges: 24.53 | gross gain to target: 103.00 | cost drag: 23.8%'), but it is a real unhandled crash on the desk's cost-gate tool and cheap to fix with an argc guard.

RELATED: engine.risk CLI has the mirror-image defect already filed as S2 (silently ignores unrecognized subcommands and prints a success-shaped blob with exit 0). Both are argv-handling gaps in engine CLIs; a fixer may want to address them together.

## Engineer notes (append below)
