"""Non-negotiable #2: every entry has a stop, and stops never move down."""
import json

import pytest

from engine import data, execute, portfolio, risk
from tests.conftest import make_ticket


def _buy(pf, **over):
    a = {"symbol": "TESTCO", "side": "BUY", "qty": 10, "price": 100.0,
         "stop": 98.0, "target": 106.0, "meta": {}}
    a.update(over)
    return portfolio.apply_fill(pf, a["symbol"], a["side"], a["qty"], a["price"],
                                a["stop"], a["target"], a["meta"])


@pytest.mark.xfail(strict=True, reason="OPEN-20260805-1105-portfolio: fix lives in the "
                                       "protected engine/portfolio.py + engine/risk.py — "
                                       "proposed patch is in the issue file, needs human review")
def test_add_on_fill_cannot_lower_an_existing_stop(desk):
    """apply_fill blindly pos.update()s the ticket's stop, so an add-on carrying a
    looser stop silently widens risk on shares that were already sized against a
    tighter one. 98 -> 90 on 20 shares is Rs.40 of intended risk becoming Rs.200."""
    pf = json.loads((desk / "portfolio.json").read_text())
    _buy(pf)
    assert pf["positions"]["TESTCO"]["stop"] == 98.0
    _buy(pf, price=101.0, stop=90.0, target=112.0)
    assert pf["positions"]["TESTCO"]["qty"] == 20
    assert pf["positions"]["TESTCO"]["stop"] == 98.0, "stops never move down"


def test_add_on_fill_may_raise_a_stop(desk):
    """The rule is one-directional: tightening is always allowed."""
    pf = json.loads((desk / "portfolio.json").read_text())
    _buy(pf)
    _buy(pf, price=104.0, stop=102.0, target=118.0)
    assert pf["positions"]["TESTCO"]["stop"] == 102.0


@pytest.mark.xfail(strict=True, reason="OPEN-20260805-1105-portfolio: fix lives in the "
                                       "protected engine/portfolio.py + engine/risk.py — "
                                       "proposed patch is in the issue file, needs human review")
def test_gate_rejects_a_ticket_that_lowers_an_open_position_stop(desk, monkeypatch):
    """risk.validate sizes risk on the new qty alone, so it never notices that the
    ticket's stop is looser than the one guarding the shares already held. The
    ticket passes the gate and reaches the broker."""
    monkeypatch.setattr(data, "last_price", lambda sym: 100.0)
    assert execute.run(str(make_ticket(desk)))["result"] == "EXECUTED"

    out = execute.run(str(make_ticket(desk, qty=10, stop=90.0, target=120.0)))
    assert out["result"] == "REJECTED", out
    assert any("never move down" in x for x in out["violations"]), out

    pf = json.loads((desk / "portfolio.json").read_text())
    assert pf["positions"]["TESTCO"]["stop"] == 98.0
    entries = [json.loads(l) for l in (desk / "journal.jsonl").read_text().splitlines()]
    assert entries[-1]["type"] == "order_rejected"


def test_gate_still_passes_an_add_on_that_holds_the_stop(desk, monkeypatch):
    """Guard against over-tightening: adding to a winner at the same stop is legal."""
    monkeypatch.setattr(data, "last_price", lambda sym: 100.0)
    assert execute.run(str(make_ticket(desk)))["result"] == "EXECUTED"
    pf = json.loads((desk / "portfolio.json").read_text())
    verdict = risk.validate(
        json.loads(make_ticket(desk, qty=10, stop=98.0, target=115.0).read_text()),
        pf, {"TESTCO": 100.0})
    assert verdict["verdict"] == "PASS", verdict
