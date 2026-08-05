"""The only market door: crash-free under dead feeds, honest paper fills."""
import json

from engine import execute, data, common
from tests.conftest import make_ticket


def test_dead_quote_path_rejects_not_crashes(desk, monkeypatch):
    """Regression: 2026-08-04 execution blindness — with every quote source dead,
    execute.py crashed instead of rejecting, so the desk couldn't even exit."""
    def dead(sym):
        raise RuntimeError("yfinance failed / groww absent")
    monkeypatch.setattr(data, "last_price", dead)
    out = execute.run(str(make_ticket(desk)))
    assert out["result"] == "REJECTED"
    assert any("no live quote path" in x for x in out["violations"])
    entries = [json.loads(l) for l in (desk / "journal.jsonl").read_text().splitlines()]
    assert entries[-1]["type"] == "order_rejected"


def test_paper_round_trip_with_charges(desk, monkeypatch):
    monkeypatch.setattr(data, "last_price", lambda sym: 100.0)
    out = execute.run(str(make_ticket(desk)))
    assert out["result"] == "EXECUTED", out
    fill = out["fill"]
    assert fill["price"] == 100.05  # 5bps slippage on LTP 100
    assert fill["charges"] > 0
    pf = json.loads((desk / "portfolio.json").read_text())
    assert pf["positions"]["TESTCO"]["qty"] == 30
    assert pf["positions"]["TESTCO"]["stop"] == 98.0
    # cost basis bakes in buy charges
    assert pf["positions"]["TESTCO"]["avg_price"] > 100.05

    monkeypatch.setattr(data, "last_price", lambda sym: 106.0)
    sell = make_ticket(desk, side="SELL", qty=30)
    out2 = execute.run(str(sell))
    assert out2["result"] == "EXECUTED", out2
    pf2 = json.loads((desk / "portfolio.json").read_text())
    assert pf2["positions"] == {}
    assert pf2["cash"] > 10000  # profitable round trip net of charges


def test_check_only_places_nothing(desk, monkeypatch):
    monkeypatch.setattr(data, "last_price", lambda sym: 100.0)
    out = execute.run(str(make_ticket(desk)), check_only=True)
    assert out["result"] == "WOULD_PASS"
    pf = json.loads((desk / "portfolio.json").read_text())
    assert pf["positions"] == {}


def test_gate_reject_is_journaled(desk, monkeypatch):
    monkeypatch.setattr(data, "last_price", lambda sym: 100.0)
    out = execute.run(str(make_ticket(desk, stop=None)))
    assert out["result"] == "REJECTED"
    entries = [json.loads(l) for l in (desk / "journal.jsonl").read_text().splitlines()]
    assert entries[-1]["type"] == "order_rejected"
