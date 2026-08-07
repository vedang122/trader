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
