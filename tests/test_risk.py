"""The risk gate is the desk's constitution — every clause gets a test."""
import json

from engine import risk


PF = {"cash": 10000.0, "positions": {}, "realized_today": {"date": "2026-01-01", "pnl": 0.0}}


def order(**over):
    o = {"symbol": "TESTCO", "side": "BUY", "qty": 30, "limit_price": 100.0,
         "stop": 98.0, "target": 106.0, "risk_officer_approval": True}
    o.update(over)
    return o


def test_valid_order_passes(desk):
    v = risk.validate(order(), PF, {"TESTCO": 100.0})
    assert v["verdict"] == "PASS", v["violations"]


def test_no_stop_rejected(desk):
    o = order()
    del o["stop"]
    v = risk.validate(o, PF, {"TESTCO": 100.0})
    assert v["verdict"] == "REJECT"
    assert any("stop" in x for x in v["violations"])


def test_stop_above_entry_rejected(desk):
    v = risk.validate(order(stop=101.0), PF, {"TESTCO": 100.0})
    assert v["verdict"] == "REJECT"


def test_oversized_risk_rejected(desk):
    # 200 shares x Rs2 risk = Rs400 >> Rs100 (1% of 10k)
    v = risk.validate(order(qty=200), PF, {"TESTCO": 100.0})
    assert any("per-trade limit" in x for x in v["violations"])


def test_rrr_below_min_rejected(desk):
    v = risk.validate(order(target=102.0), PF, {"TESTCO": 100.0})  # RRR 1.0 < 2.0
    assert any("risk:reward" in x for x in v["violations"])


def test_notional_cap_rejected(desk):
    v = risk.validate(order(qty=40, limit_price=100.0, stop=99.0, target=110.0),
                      PF, {"TESTCO": 100.0})  # 4000 > 3500
    assert any("notional" in x for x in v["violations"])


def test_missing_officer_approval_rejected(desk):
    v = risk.validate(order(risk_officer_approval=False), PF, {"TESTCO": 100.0})
    assert any("risk_officer_approval" in x for x in v["violations"])


def test_circuit_breaker_blocks_entries_not_exits(desk):
    pf = {"cash": 5000.0, "positions": {"HELDCO": {"qty": 10, "avg_price": 100.0}},
          "realized_today": {"date": "2026-01-01", "pnl": -301.0}}
    entry = risk.validate(order(), pf, {"TESTCO": 100.0})
    assert any("circuit breaker" in x for x in entry["violations"])
    exit_v = risk.validate({"symbol": "HELDCO", "side": "SELL", "qty": 10},
                           pf, {"HELDCO": 95.0})
    assert exit_v["verdict"] == "PASS", exit_v["violations"]


def test_cost_viability_gate(desk):
    # RRR fine (2.5) but absolute gain so small charges eat >25% of it
    v = risk.validate(order(qty=30, limit_price=100.0, stop=99.8, target=100.5),
                      PF, {"TESTCO": 100.0})
    assert any("cost drag" in x for x in v["violations"])


def test_short_selling_rejected(desk):
    v = risk.validate({"symbol": "TESTCO", "side": "SELL", "qty": 10,
                       "risk_officer_approval": True}, PF, {"TESTCO": 100.0})
    assert any("short selling" in x for x in v["violations"])
