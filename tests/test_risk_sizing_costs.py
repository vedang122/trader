"""OPEN-20260811-0824-risk: sizing is cost-blind on the loss side.

`suggest_qty` divides the per-trade budget by the gross stop distance and stops
there, and the `size` CLI reports that gross figure as `risk_amount`. Neither
subtracts the round-trip charges that are actually paid when the stop is hit.
At this capital those charges are ~40% of the whole per-trade budget, so every
position risks materially more than the constitution says: a Rs 75 budget sizes
a structure whose realised loss through the stop is Rs 100.

The asymmetry is what makes it a defect rather than a rounding nit. `validate()`
already runs `charges.round_trip` over the entry->target leg for the cost-drag
gate, so the desk is precise about what a *win* costs and blind to what a *loss*
costs — in a repo whose CLAUDE.md calls transaction costs "the first adversary".

The first three tests reproduce the gap and guard the keys the fix must not
take away; they are true of the charge model itself and stay true after the
fix. The last two are the tripwire: strict xfail, so the suite turns RED the
moment the patch in the issue file is applied and the markers are due for
deletion.
"""
import json
import pathlib
import subprocess
import sys

import pytest

from engine import charges as ch, risk

REPO = pathlib.Path(__file__).resolve().parent.parent
NEEDS_HUMAN = ("OPEN-20260811-0824-risk: fix lives in protected engine/risk.py — "
               "proposed patch is in the issue file, needs human review")

# The two structures the desk filed as evidence, pre-open 2026-08-11.
EVIDENCE = [(192.50, 187.40), (192.50, 186.75)]


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "engine.risk", *args],
                          cwd=REPO, capture_output=True, text=True)


def _budget(lm):
    return lm["capital_base"] * lm["risk_per_trade_pct"] / 100


def test_reported_risk_omits_the_charges_paid_through_the_stop():
    """The core arithmetic: what `size` calls `risk_amount` is the gross stop
    distance, and the loss actually realised is that plus the round trip."""
    lm = risk.limits()
    budget = _budget(lm)
    for entry, stop in EVIDENCE:
        qty = risk.suggest_qty(lm["capital_base"], entry, stop, lm["risk_per_trade_pct"])
        gross = qty * (entry - stop)
        realised = gross + ch.round_trip(entry, stop, qty)
        assert gross <= budget, "gross sizing is within budget — that is the illusion"
        assert realised > budget, (
            f"entry {entry} stop {stop} qty {qty}: realised loss {realised:.2f} "
            f"should overshoot the Rs {budget:.0f} budget while gross {gross:.2f} fits")
        # Not a rounding nit: the overshoot is a third of the budget again.
        assert realised >= budget * 1.30


def test_the_win_leg_is_costed_while_the_sizing_math_is_not(desk):
    """The asymmetry, stated as arithmetic rather than as the absence of a
    string: `validate()` runs the charge model over entry->target for its
    cost-drag gate, while `suggest_qty` divides the budget by the raw stop
    distance and never consults that model at all."""
    pf = {"cash": 10000.0, "positions": {}, "realized_today": {"pnl": 0.0}}
    order = {"symbol": "TESTCO", "side": "BUY", "qty": 30, "limit_price": 100.0,
             "stop": 98.0, "target": 106.0, "risk_officer_approval": True}
    out = risk.validate(order, pf, {"TESTCO": 100.0})
    assert any("cost drag" in n for n in out["notes"]), "the win side is costed"

    # The loss side: qty is exactly budget // per-share, charges nowhere in it.
    qty = risk.suggest_qty(10000, 100.0, 98.0, 1.0)
    assert qty == int((10000 * 1.0 / 100) // 2.0) == 50
    assert qty * 2.0 + ch.round_trip(100.0, 98.0, qty) > 100.0, \
        "the same round trip the win side already models blows the loss budget"


def test_size_cli_still_reports_gross_qty_and_risk_amount():
    """Regression guard: whatever the fix adds, these two keys are what the
    risk-officer reads today and must survive."""
    r = _cli("size", "192.50", "187.40")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["suggested_qty"] == 14
    assert out["risk_amount"] == pytest.approx(71.40, abs=0.01)


@pytest.mark.xfail(strict=True, reason=NEEDS_HUMAN)
def test_size_reports_the_loss_actually_realised_through_the_stop():
    """The risk-officer approves against this number, so it has to be the true
    one. Reporting it is the smaller fix and leaves gate semantics untouched."""
    r = _cli("size", "192.50", "187.40")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert "risk_amount_after_costs" in out, \
        "size must report the cost-inclusive loss, not only the gross distance"
    qty = out["suggested_qty"]
    expected = qty * (192.50 - 187.40) + ch.round_trip(192.50, 187.40, qty)
    assert out["risk_amount_after_costs"] == pytest.approx(expected, abs=0.01)
    assert out["risk_amount_after_costs"] > out["risk_amount"]


@pytest.mark.xfail(strict=True, reason=NEEDS_HUMAN)
def test_the_gate_states_cost_inclusive_risk_at_approval_time(desk):
    """A veto needs the real number in front of it. Whether breaching the budget
    after costs becomes a VIOLATION is the human's call (it cuts size ~35%);
    surfacing it as a note is not."""
    pf = {"cash": 10000.0, "positions": {}, "realized_today": {"pnl": 0.0}}
    order = {"symbol": "TESTCO", "side": "BUY", "qty": 30, "limit_price": 100.0,
             "stop": 98.0, "target": 106.0, "risk_officer_approval": True}
    out = risk.validate(order, pf, {"TESTCO": 100.0})
    blob = " ".join(out["notes"] + out["violations"]).lower()
    assert "after cost" in blob or "cost-inclusive" in blob, \
        "the gate must state what the loss through the stop really costs"
