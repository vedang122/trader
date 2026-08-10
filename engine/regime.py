"""Regime flag maintained by the macro-sentinel agent. Auditable via the journal.

Usage: python3 -m engine.regime show
       python3 -m engine.regime set risk_on|neutral|risk_off --note - <<'EOF'
       crude holds $83.34; the digest's $83/deadlock line stands
       EOF
       python3 -m engine.regime set neutral --note "plain prose, no $ or backticks"

Pass the note on stdin (`--note -`, quoted heredoc delimiter) whenever it
carries a `$` amount, a backtick or any other shell metacharacter. A
double-quoted argv note is expanded by the shell before the engine sees it:
`$83.34` becomes `3.34` and `$83` becomes `3`, silently, exit 0
(OPEN-20260807-0825-regime). Nothing downstream can detect that, so the note
has to bypass the shell rather than be checked afterwards.
"""
import json
import sys

from engine import common

MULTIPLIERS = {"risk_on": 1.0, "neutral": 0.7, "risk_off": 0.4}
STDIN = "-"


def read_note(argv, stdin=None) -> str:
    """The note as the caller meant it. `--note -` reads stdin, where prose
    carrying $-amounts never passes through the shell's expander."""
    if "--note" not in argv:
        return ""
    i = argv.index("--note") + 1
    if i >= len(argv):
        sys.exit("--note needs a value ('-' reads the note from stdin)")
    if argv[i] != STDIN:
        return argv[i]
    stdin = sys.stdin if stdin is None else stdin
    if stdin.isatty():
        sys.exit("--note - reads the note from stdin; nothing was piped in")
    return stdin.read().rstrip("\n")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "set":
        name = sys.argv[2]
        if name not in MULTIPLIERS:
            sys.exit(f"regime must be one of {list(MULTIPLIERS)}")
        note = read_note(sys.argv)
        rg = {"regime": name, "gross_multiplier": MULTIPLIERS[name],
              "as_of": common.now_ist().isoformat(timespec="seconds"), "note": note}
        common.save_json(common.STATE / "regime.json", rg)
        common.journal({"type": "regime_change", **rg})
        print(json.dumps(rg, indent=2))
    else:
        print(json.dumps(common.load_json(common.STATE / "regime.json",
                                          {"regime": "neutral", "gross_multiplier": 0.7}), indent=2))
