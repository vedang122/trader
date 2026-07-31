"""Deterministic transaction-cost model. At small capital, friction is the
first adversary — every paper fill pays these charges so P&L is cost-true,
and the risk gate rejects trades whose expected edge is eaten by costs.
Usage: python3 -m engine.charges 1300 1380 2   # entry target qty -> round-trip cost
"""
import sys

from engine import common


def model() -> dict:
    return common.load_yaml(common.STATE / "charges.yaml", {})


def order_charges(price: float, qty: int, side: str) -> float:
    m = model()
    turnover = price * qty
    brokerage = min(m["brokerage_cap"], max(m["brokerage_min"],
                                            turnover * m["brokerage_pct"] / 100))
    stt = turnover * m["stt_pct"] / 100
    exch = turnover * m["exchange_txn_pct"] / 100
    sebi = turnover * m["sebi_pct"] / 100
    stamp = turnover * m["stamp_duty_buy_pct"] / 100 if side == "BUY" else 0.0
    gst = (brokerage + exch + sebi) * m["gst_pct"] / 100
    dp = m["dp_charge_sell"] if side == "SELL" else 0.0
    return round(brokerage + stt + exch + sebi + stamp + gst + dp, 2)


def round_trip(entry: float, exit_px: float, qty: int) -> float:
    return round(order_charges(entry, qty, "BUY") + order_charges(exit_px, qty, "SELL"), 2)


if __name__ == "__main__":
    entry, target, qty = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
    rt = round_trip(entry, target, qty)
    gross = (target - entry) * qty
    print(f"round-trip charges: {rt:.2f} | gross gain to target: {gross:.2f} "
          f"| cost drag: {rt / gross * 100 if gross > 0 else float('inf'):.1f}%")
