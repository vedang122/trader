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

### 2026-08-09 engineer(cloud) — reproduced; patch written and verified, NOT applied

`engine/risk.py` is a protected file, so nothing in this commit touches it.
What landed is `tests/test_risk_cli.py`: two regression guards that pass today
and must keep passing across the fix, and three strict-xfail tripwires that
assert the fixed behaviour. Applying the diff below turns all three green,
which turns the suite RED (strict xfail) — that is deliberate. Delete the three
`@pytest.mark.xfail` markers in the same change that applies the patch.

**Reproduced verbatim against the live CLI**, all three exit 0 with an
identical `{limits, regime}` blob:

    python3 -m engine.risk florble
    python3 -m engine.risk check --symbol LT --qty 1 --price 4063.4 --stop 3995
    python3 -m engine.risk                        # the only one that is correct

One extra defect on the same surface, not in the original filing: `size` with
the wrong operand count dies inside `_, _, entry, stop = sys.argv` with a
`ValueError` traceback rather than a usage line. Same three-line dispatch, so
it is fixed here rather than filed separately.

**Scope deliberately kept to the misleading-success hazard.** The filing also
suggests a real `check` subcommand exposing `validate()`. That needs a
constructed ticket, the portfolio and a quotes dict — a much larger patch to a
protected file, and rejecting `check` as unknown already closes the hazard: no
invocation can return a clean-looking verdict for an unevaluated order. If the
desk wants a genuine pre-check it should be filed as its own issue.
`argparse` was considered and rejected as heavier than a three-branch dispatch
needs; the exit codes and stderr are what the tests pin, so a later argparse
rewrite satisfies them unchanged.

**Callers checked**: the only two invocations in the repo are
`.claude/skills/trade-cycle/SKILL.md:74` and `.claude/agents/risk-officer.md:19`,
both `engine.risk size <entry> <stop>` — three argv, unaffected. The bare
limits-reading form is preserved.

**Verified**: with the patch applied the full suite is 113 passed / 5 xfailed
with only the three tripwires XPASSing (i.e. the patch breaks nothing else);
reverted, it is 113 passed / 8 xfailed. No existing assertion was touched.

## Proposed patch (needs human)

```diff
--- a/engine/risk.py
+++ b/engine/risk.py
@@ -96,11 +96,18 @@ def validate(order: dict, pf: dict, quotes: dict[str, float]) -> dict:
 
 if __name__ == "__main__":
     import json, sys
-    if len(sys.argv) > 1 and sys.argv[1] == "size":
-        _, _, entry, stop = sys.argv
+    USAGE = "usage: python3 -m engine.risk [size <entry> <stop>]"
+    argv = sys.argv[1:]
+    if not argv:
+        print(json.dumps({"limits": limits(), "regime": regime()}, indent=2))
+    elif argv[0] == "size":
+        if len(argv) != 3:
+            sys.exit(f"engine.risk: size takes exactly <entry> <stop>\n{USAGE}")
+        entry, stop = argv[1], argv[2]
         lm = limits()
         q = suggest_qty(lm["capital_base"], float(entry), float(stop), lm["risk_per_trade_pct"])
         print(json.dumps({"suggested_qty": q,
                           "risk_amount": round(q * abs(float(entry) - float(stop)), 2)}))
     else:
-        print(json.dumps({"limits": limits(), "regime": regime()}, indent=2))
+        sys.exit(f"engine.risk: unknown subcommand {argv[0]!r} — this CLI does not "
+                 f"evaluate orders; the gate runs inside engine.execute\n{USAGE}")
```

`sys.exit(str)` writes the message to stderr and exits 1, which is what the
tripwires assert; the exact code is not pinned, so `argparse`'s 2 also passes.

The new test is `tests/test_risk_cli.py` in this commit — not reproduced inline
here, to keep one copy authoritative.

Issue left **OPEN**: the defect is live in `engine/risk.py` until a human
applies the diff above.
