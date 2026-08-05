"""Deterministic journal aggregation. Agents NEVER read the raw journal for
analytics — they read this compact scorecard. FIFO-pairs fills into closed
trades, computes expectancy, calibration, and per-strategy edge.
Usage: python3 -m engine.stats            # scorecard JSON (also saved to state/stats.json)
"""
import json
from collections import defaultdict

from engine import common


def closed_trades() -> list[dict]:
    lots = defaultdict(list)  # symbol -> FIFO open lots
    closed = []
    path = common.STATE / "journal.jsonl"
    if not path.exists():
        return []
    for line in path.read_text().splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") != "fill":
            continue
        o, f = e.get("order", {}), e.get("fill", {})
        sym, side = f.get("symbol"), f.get("side")
        qty, px = f.get("qty", 0), f.get("price") or f.get("price_assumed", 0)
        chg_ps = (f.get("charges") or 0) / qty if qty else 0  # charges per share
        if side == "BUY":
            lots[sym].append({"qty": qty, "px": px, "chg_ps": chg_ps, "stop": o.get("stop"),
                              "target": o.get("target"), "conviction": o.get("conviction"),
                              "tag": o.get("strategy_tag", "untagged"), "ts": e.get("ts")})
        elif side == "SELL":
            remaining = qty
            while remaining > 0 and lots[sym]:
                lot = lots[sym][0]
                take = min(remaining, lot["qty"])
                gross = (px - lot["px"]) * take
                costs = (lot.get("chg_ps", 0) + chg_ps) * take
                pnl = gross - costs  # NET of all charges — costs are the first adversary
                risk = (lot["px"] - lot["stop"]) * take if lot.get("stop") else None
                closed.append({
                    "symbol": sym, "qty": take, "entry": lot["px"], "exit": px,
                    "pnl": round(pnl, 2), "gross_pnl": round(gross, 2),
                    "charges": round(costs, 2),
                    "R": round(pnl / risk, 2) if risk else None,
                    "conviction": lot.get("conviction"), "tag": lot["tag"],
                    "opened": lot["ts"], "closed": e.get("ts"),
                })
                lot["qty"] -= take
                remaining -= take
                if lot["qty"] == 0:
                    lots[sym].pop(0)
    return closed


def scorecard() -> dict:
    trades = closed_trades()
    n = len(trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    r_trades = [t for t in trades if t["R"] is not None]

    by_tag = defaultdict(lambda: {"n": 0, "pnl": 0.0, "wins": 0})
    for t in trades:
        b = by_tag[t["tag"]]
        b["n"] += 1
        b["pnl"] = round(b["pnl"] + t["pnl"], 2)
        b["wins"] += t["pnl"] > 0

    buckets = {"lt55": [], "55-70": [], "gt70": []}
    for t in trades:
        c = t.get("conviction")
        if c is None:
            continue
        key = "lt55" if c < 55 else "55-70" if c <= 70 else "gt70"
        buckets[key].append(t["pnl"] > 0)
    calibration = {k: {"n": len(v), "hit_rate": round(sum(v) / len(v), 2) if v else None}
                   for k, v in buckets.items()}

    sc = {
        "as_of": common.now_ist().isoformat(timespec="seconds"),
        "closed_trades": n,
        "win_rate": round(len(wins) / n, 2) if n else None,
        "avg_win": round(sum(t["pnl"] for t in wins) / len(wins), 2) if wins else None,
        "avg_loss": round(sum(t["pnl"] for t in losses) / len(losses), 2) if losses else None,
        "expectancy_inr": round(sum(t["pnl"] for t in trades) / n, 2) if n else None,
        "expectancy_R": round(sum(t["R"] for t in r_trades) / len(r_trades), 2) if r_trades else None,
        "total_pnl": round(sum(t["pnl"] for t in trades), 2),
        "by_strategy": dict(by_tag),
        "calibration": calibration,
        "last_10": trades[-10:],
    }
    common.save_json(common.STATE / "stats.json", {**sc, "all_trades": trades})
    return sc


if __name__ == "__main__":
    print(json.dumps(scorecard(), indent=2))
