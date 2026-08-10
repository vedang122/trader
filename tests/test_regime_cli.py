"""OPEN-20260807-0825-regime: the shell eats the numbers in a published note.

`engine.regime set` takes its note from argv, and the module's own usage line
told the macro-sentinel to pass it double-quoted. Bash expands `$83` (unset
positional `$8`, then a literal `3`) before the engine sees anything, so a note
reading "the digest's $83/deadlock line holds up" was published to
state/regime.json as "the digest's 3/deadlock line holds up" — silently, exit 0.
regime.json is T2 state the committee and the risk-officer read, and the token
destroyed is exactly the kind that carries the reasoning: a price.

No engine-side detector can recover this. By the time argv exists the `$83` is
gone and what remains is indistinguishable from a note that always said `3`.
The fix is to take the note off the shell's hands entirely: `--note -` reads it
from stdin, where a quoted heredoc delimiter means no expansion happens at all.

Every test here runs the CLI in a throwaway copy of the repo, because `set`
writes state/regime.json and appends to the journal — real desk state that a
test must never touch.
"""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

from engine import regime

REPO = pathlib.Path(__file__).resolve().parent.parent
NOTE = "crude holds $83.34/bbl; the digest's $83/deadlock line stands"


@pytest.fixture
def sandbox(tmp_path):
    """A copy of engine/ with an empty state/ beside it, so common.ROOT — which
    is derived from engine/common.py's location — lands inside tmp_path."""
    shutil.copytree(REPO / "engine", tmp_path / "engine",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (tmp_path / "state").mkdir()
    return tmp_path


def _sh(sandbox, script):
    """Run a shell line exactly as an agent would type it — the shell is the
    component under test as much as the engine is."""
    return subprocess.run(["bash", "-c", script], cwd=sandbox,
                          capture_output=True, text=True, timeout=60)


def _published(sandbox):
    return json.loads((sandbox / "state" / "regime.json").read_text())


# --- the defect --------------------------------------------------------------

def test_the_documented_argv_form_loses_the_dollar_amount(sandbox):
    """The reproduction, verbatim from the issue. This is what the shell does,
    not what the engine does — it is pinned here so the hazard stays visible
    and nobody re-documents the double-quoted form as safe."""
    r = _sh(sandbox, f'python3 -m engine.regime set neutral --note "{NOTE}"')
    assert r.returncode == 0, r.stderr
    assert _published(sandbox)["note"] == "crude holds 3.34/bbl; the digest's 3/deadlock line stands"
    # 83.34 -> 3.34 is the nastier half: still a plausible crude print, and
    # nothing downstream can tell it was ever anything else.


def test_note_from_stdin_is_published_verbatim(sandbox):
    """The fix, end to end: a quoted heredoc delimiter stops the shell from
    expanding anything, and `--note -` picks the note up off stdin intact."""
    r = _sh(sandbox, "python3 -m engine.regime set neutral --note - <<'EOF'\n"
                     f"{NOTE}\nEOF\n")
    assert r.returncode == 0, r.stderr
    assert _published(sandbox)["note"] == NOTE


def test_stdin_note_is_journaled_verbatim(sandbox):
    """regime.json is what agents read; the journal is what the coach audits
    later. The note has to survive into both."""
    _sh(sandbox, "python3 -m engine.regime set risk_off --note - <<'EOF'\n"
                 f"{NOTE}\nEOF\n")
    entries = [json.loads(l) for l in
               (sandbox / "state" / "journal.jsonl").read_text().splitlines() if l.strip()]
    assert entries[-1]["type"] == "regime_change"
    assert entries[-1]["note"] == NOTE


def test_multi_line_stdin_note_keeps_its_lines(sandbox):
    r = _sh(sandbox, "python3 -m engine.regime set neutral --note - <<'EOF'\n"
                     "line one: $83\nline two: still $83\nEOF\n")
    assert r.returncode == 0, r.stderr
    assert _published(sandbox)["note"] == "line one: $83\nline two: still $83"


def test_note_flag_without_a_value_is_usage_not_a_traceback(sandbox):
    """`--note` as the last token used to die in an argv index unpack."""
    r = _sh(sandbox, "python3 -m engine.regime set neutral --note")
    assert r.returncode != 0
    assert "Traceback" not in r.stderr


def test_read_note_takes_stdin_only_for_the_dash_sentinel():
    """Unit-level: ordinary prose is never diverted to stdin."""
    import io
    assert regime.read_note(["set", "neutral", "--note", "-"],
                            stdin=io.StringIO(NOTE + "\n")) == NOTE
    assert regime.read_note(["set", "neutral", "--note", NOTE],
                            stdin=io.StringIO("unused")) == NOTE
    assert regime.read_note(["set", "neutral"], stdin=io.StringIO("unused")) == ""


def test_usage_shows_the_stdin_form(sandbox):
    """Delivery half of the fix: the macro-sentinel copies its invocation from
    this docstring, so the safe form has to be the one written there."""
    assert "--note -" in regime.__doc__


# --- regression guards -------------------------------------------------------

def test_plain_argv_note_still_works(sandbox):
    """Notes without shell metacharacters keep the short form."""
    r = _sh(sandbox, 'python3 -m engine.regime set risk_on --note "breadth improving"')
    assert r.returncode == 0, r.stderr
    pub = _published(sandbox)
    assert pub["note"] == "breadth improving"
    assert pub["regime"] == "risk_on"
    assert pub["gross_multiplier"] == 1.0


def test_unknown_regime_still_rejected(sandbox):
    r = _sh(sandbox, "python3 -m engine.regime set florble --note x")
    assert r.returncode != 0
    assert not (sandbox / "state" / "regime.json").exists()


def test_show_still_reads_without_writing(sandbox):
    r = _sh(sandbox, "python3 -m engine.regime show")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["regime"] == "neutral"
    assert not (sandbox / "state" / "journal.jsonl").exists()
