"""OPEN-20260806-1123-risk: the risk CLI answers questions it never evaluated.

`engine/risk.py`'s __main__ dispatches on `sys.argv[1] == "size"` and sends
everything else to an else-branch that prints `{limits, regime}` and exits 0.
So `python3 -m engine.risk check --symbol LT ...` — a pre-check an agent might
plausibly type — returns JSON that contains the limits, names no violations and
exits clean, for an order that was never passed to validate(). The order that
prompted the filing (LT, 1 share @ 4063.40) breaches max_position_notional_pct;
the CLI said nothing.

The first two tests are the regression guard: the two invocations that work
today must keep working across the fix. The rest are strict-xfail tripwires
asserting the fixed behaviour — they turn the suite RED the moment the patch in
the issue file is applied, which is when the markers are due for deletion.

The gate itself is not in question here: engine/execute.py still calls
validate() on every order, so nothing reaches a broker unchecked. What is
broken is the pre-check surface at the judgment layer.
"""
import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
NEEDS_HUMAN = ("OPEN-20260806-1123-risk: fix lives in protected engine/risk.py — "
               "proposed patch is in the issue file, needs human review")


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "engine.risk", *args],
                          cwd=REPO, capture_output=True, text=True)


def test_bare_invocation_still_prints_limits_and_regime():
    """The no-argument form is the desk's way of reading its own constitution.
    The fix must not take it away."""
    r = _cli()
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert "limits" in out and "regime" in out
    assert "capital_base" in out["limits"]


def test_size_subcommand_still_works():
    """Shape only — the numbers move with risk_limits.yaml amendments."""
    r = _cli("size", "100", "98")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert isinstance(out["suggested_qty"], int)
    assert out["suggested_qty"] > 0
    assert "risk_amount" in out


@pytest.mark.xfail(strict=True, reason=NEEDS_HUMAN)
def test_unknown_subcommand_exits_nonzero():
    """A subcommand the CLI does not implement is an error, not a default print."""
    assert _cli("florble").returncode != 0


@pytest.mark.xfail(strict=True, reason=NEEDS_HUMAN)
def test_unknown_subcommand_does_not_emit_a_success_shaped_blob():
    """The specific hazard: output that looks like a clean verdict. An agent
    reading stdout must not find limits-and-no-violations for an order the gate
    never saw."""
    r = _cli("check", "--symbol", "LT", "--qty", "1",
             "--price", "4063.4", "--stop", "3995")
    assert "limits" not in r.stdout, \
        "an unevaluated pre-check must not print the limits blob"
    assert "florble" in _cli("florble").stderr or "unknown" in _cli("florble").stderr.lower(), \
        "the error must name what was not understood"


@pytest.mark.xfail(strict=True, reason=NEEDS_HUMAN)
def test_size_with_wrong_arity_fails_without_a_traceback():
    """`size` with the wrong number of operands currently dies in an argv
    unpack. Usage, not a stack trace."""
    r = _cli("size", "100")
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
