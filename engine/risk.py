"""Deterministic risk gate. Every order passes through validate() — the LLM layer
cannot waive these checks. Limits live in state/risk_limits.yaml (human-owned)."""
from engine import common, portfolio as pf_mod


def limits() -> dict:
    lm = common.load_yaml(common.STATE / "risk_limits.yaml")
    if lm is None:
        raise RuntimeError("state/risk_limits.yaml missing")
    return lm


def regime() -> dict:
    return common.load_json(common.STATE / "regime.json",
                            {"regime": "neutral", "gross_multiplier": 0.7})


def suggest_qty(capital: float, entry: float, stop: float, risk_pct: float) -> int:
    """Module 9 sizing: risk a fixed % of capital between entry and stop."""
    per_share = abs(entry - stop)
    if per_share <= 0:
        return 0
    return int((capital * risk_pct / 100) // per_share)


def validate(order: dict, pf: dict, quotes: dict[str, float]) -> dict:
    """Return {'verdict': 'PASS'|'REJECT', 'violations': [...], 'notes': [...]}"""
    lm, rg = limits(), regime()
    v, notes = [], []
    side, sym = order["side"].upper(), order["symbol"].upper()
    qty = int(order["qty"])
    ltp = quotes.get(sym) or order.get("limit_price")
    if not ltp:
        return {"verdict": "REJECT", "violations": [f"no price available for {sym}"], "notes": []}
    entry = order.get("limit_price") or ltp
    capital = lm["capital_base"]
    is_exit = side == "SELL" and sym in pf["positions"]

    if qty <= 0:
        v.append("qty must be positive")

    # Circuit breaker: exits always allowed, new risk is not.
    day_loss_limit = capital * lm["max_daily_loss_pct"] / 100
    realized = pf.get("realized_today", {}).get("pnl", 0.0)
    if not is_exit and realized <= -day_loss_limit:
        v.append(f"daily-loss circuit breaker tripped (realized today {realized:.0f} "
                 f"<= -{day_loss_limit:.0f}); entries blocked until tomorrow")

    if not is_exit:
        if side == "SELL":
            v.append("short selling equities is not enabled on this desk")
        stop, target = order.get("stop"), order.get("target")
        if lm.get("stop_required", True) and not stop:
            v.append("no stop/invalidation on ticket — a trade without an exit is not a trade")
        if stop:
            if stop >= entry:
                v.append(f"stop {stop} must be below entry {entry} for a long")
            else:
                risk_amt = qty * (entry - stop)
                max_risk = capital * lm["risk_per_trade_pct"] / 100
                if risk_amt > max_risk * 1.02:  # 2% rounding tolerance
                    v.append(f"risk to stop {risk_amt:.0f} exceeds per-trade limit {max_risk:.0f} "
                             f"(suggest qty <= {suggest_qty(capital, entry, stop, lm['risk_per_trade_pct'])})")
                if target:
                    rr = (target - entry) / (entry - stop)
                    if rr < lm["min_risk_reward"]:
                        v.append(f"risk:reward {rr:.2f} below minimum {lm['min_risk_reward']}")
                    else:
                        notes.append(f"R:R {rr:.2f}")
                    from engine import charges as ch
                    rt = ch.round_trip(entry, target, qty)
                    gross_gain = (target - entry) * qty
                    if gross_gain > 0 and rt > 0.25 * gross_gain:
                        v.append(f"cost drag: round-trip charges {rt:.0f} eat "
                                 f"{rt / gross_gain * 100:.0f}% of gain to target "
                                 f"(max 25%) — trade is too small or target too near")
                    elif gross_gain > 0:
                        notes.append(f"cost drag {rt / gross_gain * 100:.0f}%")
        notional = qty * entry
        if notional > capital * lm["max_position_notional_pct"] / 100:
            v.append(f"notional {notional:.0f} exceeds {lm['max_position_notional_pct']}% of capital")
        if notional > pf["cash"]:
            v.append(f"insufficient cash {pf['cash']:.0f} for notional {notional:.0f}")
        if sym not in pf["positions"] and len(pf["positions"]) >= lm["max_open_positions"]:
            v.append(f"already at max open positions ({lm['max_open_positions']})")
        gross = pf_mod.gross_exposure(pf, quotes) + notional
        max_gross = capital * lm["max_gross_exposure_pct"] / 100 * rg["gross_multiplier"]
        if gross > max_gross:
            v.append(f"gross exposure {gross:.0f} would exceed regime-scaled cap {max_gross:.0f} "
                     f"(regime={rg['regime']}, multiplier={rg['gross_multiplier']})")
        if not order.get("risk_officer_approval"):
            v.append("ticket lacks risk_officer_approval=true — committee protocol not followed")

    return {"verdict": "REJECT" if v else "PASS", "violations": v, "notes": notes}


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) > 1 and sys.argv[1] == "size":
        _, _, entry, stop = sys.argv
        lm = limits()
        q = suggest_qty(lm["capital_base"], float(entry), float(stop), lm["risk_per_trade_pct"])
        print(json.dumps({"suggested_qty": q,
                          "risk_amount": round(q * abs(float(entry) - float(stop)), 2)}))
    else:
        print(json.dumps({"limits": limits(), "regime": regime()}, indent=2))
