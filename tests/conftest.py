"""Isolated desk fixture: every test runs against a throwaway state/ dir."""
import json
import shutil
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """Tmp state dir with known limits; engine modules pointed at it."""
    state = tmp_path / "state"
    state.mkdir()
    (state / "tickets").mkdir()
    (state / "issues").mkdir()
    (state / "risk_limits.yaml").write_text(
        "capital_base: 10000\nrisk_per_trade_pct: 1.0\nmax_daily_loss_pct: 3.0\n"
        "max_open_positions: 3\nmax_position_notional_pct: 35\nmax_gross_exposure_pct: 100\n"
        "min_risk_reward: 2.0\nstop_required: true\nslippage_bps: 5\n")
    (state / "regime.json").write_text(json.dumps(
        {"regime": "risk_on", "gross_multiplier": 1.0, "as_of": "2026-01-01T09:00:00+05:30"}))
    (state / "portfolio.json").write_text(json.dumps(
        {"cash": 10000.0, "positions": {}, "realized_today": {"date": "2026-01-01", "pnl": 0.0}}))
    (state / "broker.yaml").write_text("mode: paper\n")
    shutil.copy(REPO / "state" / "charges.yaml", state / "charges.yaml")

    from engine import common
    monkeypatch.setattr(common, "STATE", state)
    from engine import data
    monkeypatch.setattr(data, "CACHE_DIR", state / "cache" / "ohlcv")
    # The NSE archive is a network source: offline by default so no test can
    # reach the exchange by accident. Bhavcopy tests re-patch it explicitly.
    monkeypatch.setattr(data, "_bhav_day", lambda day: {})
    return state


def make_ticket(state, **over):
    """A ticket that passes every gate unless overridden."""
    t = {"symbol": "TESTCO", "side": "BUY", "qty": 30, "type": "LIMIT",
         "limit_price": 100.0, "product": "CNC", "stop": 98.0, "target": 106.0,
         "thesis": "test", "conviction": 60, "strategy_tag": "test",
         "risk_officer_approval": True}
    t.update(over)
    p = state / "tickets" / "T-test.json"
    p.write_text(json.dumps(t))
    return p
