---
severity: S3
area: regime
filed: 2026-08-10T08:53:33+05:30
title: macro-sentinel charter still documents the shell-expanded --note form the engine fix replaced
---

## Observed
## Observed
Residual half of CLOSED-20260807-0825-regime. The engine side is fixed:
`engine.regime set --note -` now reads the note from stdin, where the shell
cannot expand it. But the macro-sentinel is not told to use it.

`.claude/agents/macro-sentinel.md:31` still reads:

  `python3 -m engine.regime set <risk_on|neutral|risk_off> --note "<one-line basis>"`

That is the exact double-quoted form that published "the digest's 3/deadlock"
instead of "the digest's $83/deadlock" on 2026-08-07, and it is the line the
agent copies from. A safe path nobody is pointed at fixes nothing: the next
macro note carrying a crude print will be corrupted the same way.

## Why this is a separate issue
`.claude/**` is protected — an engineer run may not edit agent charters. The
engine fix landed on its own (main @ 3bf27ee); this one line needs the human.

## Proposed patch (needs human)

```diff
--- a/.claude/agents/macro-sentinel.md
+++ b/.claude/agents/macro-sentinel.md
@@ -30,7 +30,12 @@
 Publish the verdict with:
-`python3 -m engine.regime set <risk_on|neutral|risk_off> --note "<one-line basis>"`
+```
+python3 -m engine.regime set <risk_on|neutral|risk_off> --note - <<'EOF'
+<one-line basis, $-amounts and backticks written verbatim>
+EOF
+```
+The heredoc form is not optional when the basis quotes a level. A double-quoted
+`--note` is expanded by the shell first: `$83` publishes as `3`, `$83.34` as
+`3.34`, silently and with exit 0 (CLOSED-20260807-0825-regime).
```

## Verify after applying
  python3 -m pytest tests/test_regime_cli.py -q     # 10 passed
  grep -n 'note -' .claude/agents/macro-sentinel.md  # the heredoc form is present

The engine-level guard is already regression-tested in tests/test_regime_cli.py;
nothing further is testable from an engineer run, because the charter is prose
the agent reads, not code the suite imports.


## Engineer notes (append below)
