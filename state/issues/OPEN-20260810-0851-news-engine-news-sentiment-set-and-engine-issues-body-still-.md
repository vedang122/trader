---
severity: S3
area: news
filed: 2026-08-10T08:51:07+05:30
title: engine.news sentiment --set and engine.issues --body still take shell-expanded prose through argv
---

## Observed
## Observed
Split out of OPEN-20260807-0825-regime, which fixed `engine.regime set` by
adding `--note -` (stdin) but named two further CLIs carrying the identical
hazard. Filing rather than widening that fix, per one-issue-per-run.

## Mechanism
Free prose reaching an engine CLI through argv has already been through the
shell. A double-quoted `$83` is expanded to `3` and `$83.34` to `3.34` before
Python starts - silently, exit 0, and undetectable afterwards. Still exposed:

  python3 -m engine.news sentiment --set '<json>'   engine/news.py:199
  python3 -m engine.issues file ... --body "..."    engine/issues.py:171

news is the sharper of the two: sentiment payloads routinely carry
"crude >$100"-style levels in basis/top_risks, and the published object is T2
state the committee reads. The documented usage single-quotes the JSON, which
is safe - but that is caller discipline, not enforcement, and the regime bug
was exactly a caller who used the double-quoted form the docstring showed.

## Suggested direction
Mirror the regime fix: accept `-` for the payload/body argument and read stdin,
then document the quoted-heredoc form as the primary usage. `engine/regime.py`
read_note() is the reference implementation (~14 lines). A shared helper would
be better than a third copy, but engine/common.py is protected and the engineer
charter allows no new engine/ modules, so a human is needed to give it a home.

## Verify
  cd /tmp && python3 -m engine.news sentiment --set "{\"tone\":\"crude $83\"}"


## Engineer notes (append below)
