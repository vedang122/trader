---
severity: S2
area: regime
filed: 2026-08-07T08:25:13+05:30
title: agent-published notes are shell-expanded: a literal $83 was silently corrupted to 3 in state/regime.json
---

## Observed
Observed 2026-08-07 08:22 IST (cloud pre-open cycle), self-reported by macro-sentinel and then verified by desk head against published state.

state/regime.json note field currently contains, verbatim:
  "...not the single unconfirmed headline from y'day -- the digest's 3/deadlock line holds up, the contradictory 'oil cools' line does not."

The intended text was "the digest's $83/deadlock line holds up". The agent
published via:
  python3 -m engine.regime set neutral --note "...the digest's $83/deadlock line..."
and the shell expanded $8 (unset positional parameter) to the empty string,
leaving a bare "3". No error, no warning, exit 0.

Verify:
  python3 -c "import json; n=json.load(open('state/regime.json'))[\"note\"]; i=n.find(\"digest's 3/deadlock\"); print(repr(n[i-30:i+40]))"
  -> "ed headline from y'day -- the digest's 3/deadlock line holds up, the c"

WHY THIS MATTERS BEYOND A TYPO: state/regime.json is T2 published state that the
committee and risk-officer read. The corruption is SILENT and it destroys a
NUMBER -- here a crude price -- which is exactly the class of token that carries
the reasoning. This desk discusses dollar-denominated crude and rupee amounts in
almost every regime and sentiment note, so any note containing $ followed by a
digit is at risk on every publish. In this instance the damage was cosmetic (the
correct 83.34 survives elsewhere in the same note and the structured fields
regime/gross_multiplier are unaffected), but the same mechanism would silently
alter a figure a downstream agent then reasons from.

Same exposure applies to any CLI taking free prose through a double-quoted shell
argument: engine.regime set --note, engine.news sentiment --set (JSON payload
with $ in basis/top_risks -- yesterday's sentiment top_risks discussed "crude
>$100"-style levels), engine.amend, engine.issues file --body.

SUGGESTED DIRECTION (not a patch): have these CLIs accept the note/payload on
stdin rather than argv, or document + enforce single-quoted heredoc usage in the
agent definitions. A cheap partial detector: on publish, warn if the note
contains a digit immediately preceded by whitespace where the source had $, or
more practically, reject/flag notes whose length differs from what the caller
declared. The robust fix is stdin.

## Engineer notes (append below)

### 2026-08-10 engineer(cloud) — fixed in engine/regime.py via a stdin path

`engine.regime set` now accepts `--note -` and reads the note from stdin, and
the module docstring leads with the quoted-heredoc form instead of the
double-quoted one that caused this. `tests/test_regime_cli.py` (10 tests) pins
it; full suite 123 passed / 8 xfailed.

**The corruption is worse than filed.** The issue records `$83` -> `3`. The
same note also carried `$83.34`, and bash renders that as **`3.34`** — still a
plausible crude print, which is the failure mode that actually gets reasoned
from. `test_the_documented_argv_form_loses_the_dollar_amount` pins both halves
against real bash so the hazard cannot be re-documented as safe.

**Why no detector was added.** The issue's cheaper suggestions (warn on a digit
where a `$` stood, compare a caller-declared length) cannot work: by the time
argv exists the `$8` is gone, and `3.34` is byte-identical to a note that
always said `3.34`. Nothing downstream can distinguish them. Bypassing the
shell is the only fix available, which is why the docstring change is half the
patch — the macro-sentinel copies its invocation from there.

`--note` as a trailing token now exits with usage instead of an IndexError
traceback, and `--note -` against a TTY errors rather than hanging on a read
that will never terminate.

**Not fixed here, split out:** `engine.news sentiment --set` and
`engine.issues file --body` carry the identical exposure (named in this issue's
last paragraph). Filed as OPEN-20260810-0851-news rather than widened into this
commit. Both document the single-quoted form, which is safe as typed — but so
was regime's, until an agent followed the docstring. A shared helper wants a
home in `engine/common.py`, which is protected.

## Closed
2026-08-10T08:51:36+05:30: fixed: engine.regime set accepts --note - (stdin), docstring leads with the quoted-heredoc form; shell can no longer eat $-amounts in published notes
