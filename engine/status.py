"""Desk status: clock, portfolio mark-to-market, risk utilization, position health.
The first command every trade cycle runs.
Usage: python3 -m engine.status [--clock]
"""
import json
import sys

from engine import common, data, portfolio as pf_mod, risk


def run() -> dict:
    market = common.market_status()
    pf = pf_mod.load()
    quotes = {}
    for sym in pf["positions"]:
        try:
            quotes[sym] = data.last_price(sym)
        except RuntimeError:
            pass
    mtm = pf_mod.mark_to_market(pf, quotes)
    lm, rg = risk.limits(), risk.regime()
    capital = lm["capital_base"]
    gross = sum(abs(p["qty"]) * p["ltp"] for p in mtm["positions"])
    alerts = []
    for p in mtm["positions"]:
        if p.get("stop") and p["ltp"] <= p["stop"]:
            alerts.append(f"{p['symbol']}: BELOW STOP {p['stop']} (ltp {p['ltp']}) — exit required")
        if p.get("target") and p["ltp"] >= p["target"]:
            alerts.append(f"{p['symbol']}: target {p['target']} reached (ltp {p['ltp']}) — review exit")
    day_loss_limit = capital * lm["max_daily_loss_pct"] / 100
    if mtm["realized_today"] <= -day_loss_limit:
        alerts.append("DAILY-LOSS CIRCUIT BREAKER TRIPPED — no new entries today")
    _track_equity(mtm["equity"])
    sentiment = common.load_json(common.STATE / "sentiment.json")
    return {
        "market": market,
        "broker_mode": (common.load_yaml(common.STATE / "broker.yaml", {}) or {}).get("mode", "paper"),
        "regime": rg,
        "sentiment": ({"tone": sentiment.get("tone"), "as_of": sentiment.get("as_of")}
                      if sentiment else None),
        "portfolio": mtm,
        "risk_utilization": {
            "open_positions": f"{len(mtm['positions'])}/{lm['max_open_positions']}",
            "gross_exposure": round(gross, 0),
            "gross_cap_regime_scaled": round(capital * lm["max_gross_exposure_pct"] / 100
                                             * rg["gross_multiplier"], 0),
            "daily_loss_used": f"{mtm['realized_today']:.0f} / -{day_loss_limit:.0f}",
        },
        "alerts": alerts,
    }


def _track_equity(equity: float) -> None:
    """Append to the equity curve (guardian's drawdown source), max once per 10 min."""
    import json as _json
    path = common.STATE / "equity.jsonl"
    now = common.now_ist()
    if path.exists():
        lines = path.read_text().splitlines()
        if lines:
            from datetime import datetime
            last = _json.loads(lines[-1])
            if (now - datetime.fromisoformat(last["ts"])).total_seconds() < 600:
                return
    with path.open("a") as f:
        f.write(_json.dumps({"ts": now.isoformat(timespec="seconds"),
                             "equity": round(equity, 2)}) + "\n")


if __name__ == "__main__":
    if "--clock" in sys.argv:
        print(json.dumps(common.market_status()))
    else:
        print(json.dumps(run(), indent=2))
