"""The ONLY door to the market. Reads an order ticket JSON, re-validates it
against the deterministic risk gate, routes to the configured broker, journals
everything. Usage:
    python3 -m engine.execute state/tickets/T123.json          # validate + place
    python3 -m engine.execute state/tickets/T123.json --check   # validate only
"""
import json
import sys

from engine import broker, common, data, portfolio as pf_mod, risk


def run(ticket_path: str, check_only: bool = False) -> dict:
    order = json.loads(common.ROOT.joinpath(ticket_path).read_text()
                       if not ticket_path.startswith("/") else open(ticket_path).read())
    sym = order["symbol"].upper()
    pf = pf_mod.load()
    try:
        quotes = {sym: data.last_price(sym)}
    except Exception as e:
        common.journal({"type": "order_rejected", "ticket": ticket_path, "order": order,
                        "violations": [f"no live quote path for {sym} — cannot price a fill ({str(e)[:80]})"]})
        return {"result": "REJECTED",
                "violations": [f"no live quote path for {sym} — cannot price a fill; "
                               "desk must stand down, not fly blind"]}
    for held in pf["positions"]:
        if held != sym:
            try:
                quotes[held] = data.last_price(held)
            except RuntimeError:
                pass

    verdict = risk.validate(order, pf, quotes)
    if verdict["verdict"] == "REJECT":
        common.journal({"type": "order_rejected", "ticket": ticket_path,
                        "order": order, "violations": verdict["violations"]})
        return {"result": "REJECTED", **verdict}
    if check_only:
        return {"result": "WOULD_PASS", **verdict}

    market = common.market_status()
    if not market["is_open"] and broker.config().get("mode") == "live":
        return {"result": "REJECTED",
                "violations": [f"market is {market['phase']} — live orders only during session"]}

    fill = broker.get_broker().place(order)
    common.journal({"type": "fill", "ticket": ticket_path, "order": order, "fill": fill,
                    "conviction": order.get("conviction"),
                    "thesis": order.get("thesis"), "strategy_tag": order.get("strategy_tag")})
    return {"result": "EXECUTED", "fill": fill, "risk_notes": verdict["notes"]}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    out = run(sys.argv[1], check_only="--check" in sys.argv)
    print(json.dumps(out, indent=2))
    sys.exit(0 if out["result"] in ("EXECUTED", "WOULD_PASS") else 2)
