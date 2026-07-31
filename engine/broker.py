"""Broker adapters. Paper is the default; live routes to Groww (or legacy Kite)
and refuses to run unless state/broker.yaml is explicitly configured for it.
Live credentials come from the environment (GROWW_API_KEY / GROWW_API_SECRET
in ~/.zshrc) — never from repo files. Integration notes: knowledge/groww-api.md."""
import os

from engine import common, data, portfolio as pf_mod


def config() -> dict:
    return common.load_yaml(common.STATE / "broker.yaml", {"mode": "paper"})


class PaperBroker:
    """Fills at last traded price plus a slippage haircut, against real quotes."""

    def place(self, order: dict) -> dict:
        from engine import charges, risk
        sym, side, qty = order["symbol"].upper(), order["side"].upper(), int(order["qty"])
        ltp = data.last_price(sym)
        slip = risk.limits().get("slippage_bps", 5) / 10_000
        px = ltp * (1 + slip) if side == "BUY" else ltp * (1 - slip)
        px = round(px, 2)
        fees = charges.order_charges(px, qty, side)
        pf = pf_mod.load()
        if side == "BUY":
            # bake buy-side charges into cost basis — proper accounting
            eff_px = round(px + fees / qty, 4)
            pf_mod.apply_fill(pf, sym, side, qty, eff_px,
                              order.get("stop"), order.get("target"), order)
        else:
            pf_mod.apply_fill(pf, sym, side, qty, px,
                              order.get("stop"), order.get("target"), order)
            pf["cash"] -= fees          # sell-side charges reduce proceeds...
            pf["realized_today"]["pnl"] -= fees  # ...and realized P&L
        pf_mod.save(pf)
        return {"status": "FILLED", "broker": "paper", "symbol": sym, "side": side,
                "qty": qty, "price": px, "charges": fees, "ltp_at_fill": round(ltp, 2)}


class KiteBroker:
    """Zerodha Kite Connect. Requires api_key + access_token in state/broker.yaml
    (access token must be refreshed each trading day via the login flow)."""

    def __init__(self, cfg: dict):
        try:
            from kiteconnect import KiteConnect
        except ImportError as e:
            raise RuntimeError("kiteconnect not installed — run: pip install kiteconnect") from e
        kite_cfg = cfg.get("kite") or {}
        if not kite_cfg.get("api_key") or not kite_cfg.get("access_token"):
            raise RuntimeError("state/broker.yaml missing kite.api_key / kite.access_token — "
                               "run the /go-live checklist")
        self.kite = KiteConnect(api_key=kite_cfg["api_key"])
        self.kite.set_access_token(kite_cfg["access_token"])

    def place(self, order: dict) -> dict:
        sym, side, qty = order["symbol"].upper(), order["side"].upper(), int(order["qty"])
        kwargs = dict(
            variety="regular", exchange=order.get("exchange", "NSE"),
            tradingsymbol=sym, transaction_type=side, quantity=qty,
            product=order.get("product", "CNC"),
            order_type="LIMIT" if order.get("limit_price") else "MARKET",
        )
        if order.get("limit_price"):
            kwargs["price"] = float(order["limit_price"])
        order_id = self.kite.place_order(**kwargs)
        # Mirror the fill into local state so risk checks stay accurate.
        px = float(order.get("limit_price") or data.last_price(sym))
        pf = pf_mod.load()
        pf_mod.apply_fill(pf, sym, side, qty, px,
                          order.get("stop"), order.get("target"), order)
        pf_mod.save(pf)
        return {"status": "PLACED", "broker": "kite", "order_id": order_id,
                "symbol": sym, "side": side, "qty": qty, "price_assumed": px}


class GrowwBroker:
    """Groww Trade API. Auth: GrowwAPI.get_access_token with the env-provided
    key + TOTP seed (preferred) or approval secret, then GrowwAPI(token).
    After every protected BUY fill it parks an OCO smart order (stop + target)
    server-side so protection survives the desk sleeping."""

    def __init__(self, cfg: dict):
        try:
            from growwapi import GrowwAPI
        except ImportError as e:
            raise RuntimeError("growwapi not installed — run: pip install growwapi pyotp") from e
        api_key = os.environ.get("GROWW_API_KEY")
        secret = os.environ.get("GROWW_API_SECRET")
        if not api_key or not secret:
            raise RuntimeError("GROWW_API_KEY / GROWW_API_SECRET not set in the environment — "
                               "add them to ~/.zshrc per /go-live")
        token = None
        try:
            import pyotp
            resp = GrowwAPI.get_access_token(api_key=api_key, totp=pyotp.TOTP(secret).now())
            token = resp.get("token") if isinstance(resp, dict) else resp
        except Exception:
            resp = GrowwAPI.get_access_token(api_key=api_key, secret=secret)
            token = resp.get("token") if isinstance(resp, dict) else resp
        if not token:
            raise RuntimeError("Groww auth returned no token — desk stands down today")
        self.g = GrowwAPI(token)

    def _ltp(self, sym: str) -> float | None:
        try:
            out = self.g.get_ltp(exchange_trading_symbols=(f"NSE_{sym}",),
                                 segment=self.g.SEGMENT_CASH)
            for v in (out or {}).values():
                return float(v)
        except Exception:
            return None

    def place(self, order: dict) -> dict:
        from engine import charges
        g = self.g
        sym, side, qty = order["symbol"].upper(), order["side"].upper(), int(order["qty"])
        ref = f"KTLYA{common.now_ist().strftime('%m%d%H%M%S')}"
        resp = g.place_order(
            validity=g.VALIDITY_DAY, exchange=g.EXCHANGE_NSE,
            order_type=g.ORDER_TYPE_LIMIT if order.get("limit_price") else g.ORDER_TYPE_MARKET,
            product=g.PRODUCT_CNC, quantity=qty, segment=g.SEGMENT_CASH,
            trading_symbol=sym,
            transaction_type=g.TRANSACTION_TYPE_BUY if side == "BUY" else g.TRANSACTION_TYPE_SELL,
            price=float(order.get("limit_price") or 0.0),
            order_reference_id=ref)
        order_id = (resp or {}).get("groww_order_id")

        # Mirror into local state at limit price or live LTP (estimated charges
        # baked in, same accounting as paper, so local books track reality).
        px = float(order.get("limit_price") or self._ltp(sym) or data.last_price(sym))
        fees = charges.order_charges(px, qty, side)
        pf = pf_mod.load()
        if side == "BUY":
            pf_mod.apply_fill(pf, sym, side, qty, round(px + fees / qty, 4),
                              order.get("stop"), order.get("target"), order)
        else:
            pf_mod.apply_fill(pf, sym, side, qty, px,
                              order.get("stop"), order.get("target"), order)
            pf["cash"] -= fees
            pf["realized_today"]["pnl"] -= fees
        pf_mod.save(pf)

        result = {"status": "PLACED", "broker": "groww", "order_id": order_id,
                  "reference_id": ref, "symbol": sym, "side": side, "qty": qty,
                  "price_assumed": px, "charges_estimated": fees}

        # Server-side protection: OCO (stop-loss + target) after a protected entry.
        if side == "BUY" and order.get("stop") and order.get("target"):
            try:
                oco = g.create_smart_order(
                    smart_order_type=g.SMART_ORDER_TYPE_OCO, segment=g.SEGMENT_CASH,
                    trading_symbol=sym, quantity=qty, product_type=g.PRODUCT_CNC,
                    exchange=g.EXCHANGE_NSE, duration=g.VALIDITY_GTC,
                    transaction_type=g.TRANSACTION_TYPE_SELL,
                    stop_loss={"trigger_price": float(order["stop"])},
                    target={"trigger_price": float(order["target"])})
                result["oco"] = {"status": "PLACED",
                                 "id": (oco or {}).get("groww_order_id") or str(oco)[:120]}
            except Exception as e:
                result["oco"] = {"status": "FAILED", "error": f"{type(e).__name__}: {e}"[:200]}
                result["warning"] = ("server-side OCO protection FAILED — the trade-cycle "
                                     "MUST enforce this stop; do not slow the loop below "
                                     "30min while this position is open")
        return result

    def sync(self) -> dict:
        """Reconcile local portfolio positions against Groww holdings; local
        stops/targets/theses are preserved. Run each live morning."""
        raw = self.g.get_holdings_for_user()
        rows = raw.get("holdings", raw) if isinstance(raw, dict) else raw
        pf = pf_mod.load()
        drift = []
        remote = {}
        for h in rows or []:
            sym = (h.get("trading_symbol") or h.get("tradingSymbol") or "").upper()
            qty = int(h.get("quantity") or h.get("qty") or 0)
            avg = float(h.get("average_price") or h.get("avg_price") or 0)
            if sym and qty:
                remote[sym] = {"qty": qty, "avg_price": avg}
        for sym, r in remote.items():
            local = pf["positions"].get(sym)
            if not local or local["qty"] != r["qty"]:
                drift.append(f"{sym}: local {local['qty'] if local else 0} vs groww {r['qty']}")
                pf["positions"].setdefault(sym, {}).update(r)
        for sym in list(pf["positions"]):
            if sym not in remote:
                drift.append(f"{sym}: held locally, absent at groww — removed")
                del pf["positions"][sym]
        pf_mod.save(pf)
        common.journal({"type": "broker_sync", "drift": drift, "positions": list(remote)})
        return {"synced": len(remote), "drift": drift}


def get_broker():
    cfg = config()
    mode = cfg.get("mode", "paper")
    if mode == "live":
        if cfg.get("live_acknowledgement") != "I accept real-money order placement":
            raise RuntimeError("mode is 'live' but live_acknowledgement is missing in "
                               "state/broker.yaml — a human must set it verbatim")
        provider = cfg.get("provider", "groww")
        return GrowwBroker(cfg) if provider == "groww" else KiteBroker(cfg)
    return PaperBroker()


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) > 1 and sys.argv[1] == "sync":
        b = get_broker()
        if isinstance(b, PaperBroker):
            print(json.dumps({"note": "paper mode — nothing to sync"}))
        else:
            print(json.dumps(b.sync(), indent=2))
    else:
        print(json.dumps({"mode": config().get("mode", "paper"),
                          "provider": config().get("provider", "groww")}))
