"""Portfolio state: cash, positions, mark-to-market, realized/unrealized P&L."""
from engine import common


def load() -> dict:
    pf = common.load_json(common.STATE / "portfolio.json")
    if pf is None:
        raise RuntimeError("state/portfolio.json missing — desk not initialized")
    return pf


def save(pf: dict) -> None:
    common.save_json(common.STATE / "portfolio.json", pf)


def gross_exposure(pf: dict, quotes: dict[str, float]) -> float:
    return sum(abs(p["qty"]) * quotes.get(s, p["avg_price"])
               for s, p in pf["positions"].items())


def mark_to_market(pf: dict, quotes: dict[str, float]) -> dict:
    rows, unrealized = [], 0.0
    for sym, p in pf["positions"].items():
        ltp = quotes.get(sym, p["avg_price"])
        upl = (ltp - p["avg_price"]) * p["qty"]
        unrealized += upl
        rows.append({**p, "symbol": sym, "ltp": round(ltp, 2), "unrealized": round(upl, 2),
                     "unrealized_pct": round(upl / (abs(p["qty"]) * p["avg_price"]) * 100, 2)})
    equity = pf["cash"] + sum(abs(p["qty"]) * quotes.get(s, p["avg_price"])
                              for s, p in pf["positions"].items())
    return {
        "cash": round(pf["cash"], 2),
        "equity": round(equity, 2),
        "unrealized": round(unrealized, 2),
        "realized_today": round(pf.get("realized_today", {}).get("pnl", 0.0), 2),
        "positions": rows,
    }


def apply_fill(pf: dict, symbol: str, side: str, qty: int, price: float,
               stop: float | None, target: float | None, meta: dict) -> dict:
    """Apply a fill to the portfolio. Long-only for equity CNC; a SELL reduces/closes."""
    today = common.now_ist().date().isoformat()
    rt = pf.setdefault("realized_today", {"date": today, "pnl": 0.0})
    if rt["date"] != today:
        pf["realized_today"] = rt = {"date": today, "pnl": 0.0}

    pos = pf["positions"].get(symbol)
    notional = qty * price
    if side == "BUY":
        pf["cash"] -= notional
        if pos:
            total = pos["qty"] + qty
            pos["avg_price"] = (pos["avg_price"] * pos["qty"] + notional) / total
            pos["qty"] = total
        else:
            pf["positions"][symbol] = pos = {"qty": qty, "avg_price": price}
        pos.update({k: v for k, v in {"stop": stop, "target": target}.items() if v})
        pos.setdefault("opened", common.now_ist().date().isoformat())
        pos["thesis"] = meta.get("thesis", pos.get("thesis", ""))
    else:  # SELL
        if not pos or pos["qty"] < qty:
            raise ValueError(f"cannot sell {qty} {symbol}: position is {pos['qty'] if pos else 0}")
        pf["cash"] += notional
        realized = (price - pos["avg_price"]) * qty
        rt["pnl"] += realized
        pos["qty"] -= qty
        if pos["qty"] == 0:
            del pf["positions"][symbol]
    return pf
