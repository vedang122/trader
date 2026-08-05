"""Market data via yfinance (NSE symbols get a .NS suffix) plus indicator math.

Resilience layers (cloud IPs get 429-throttled by Yahoo):
1. the Yahoo chart endpoint over plain requests (standard TLS, proxy-aware) —
   yfinance's own transport impersonates a browser's TLS fingerprint, which a
   MITM egress proxy resets (curl error 35), so the plain client goes first;
2. yfinance itself, for hosts where its cookie/crumb path is the one that works;
3. on-disk daily-bar cache in state/cache/ohlcv/ (committed to git, so cloud
   runs inherit history and only need the incremental bar);
4. Groww live LTP fallback (data-only; needs GROWW_API_KEY/SECRET in env) to
   patch a live price onto cached history when Yahoo is down.
Layers 1 and 2 are both genuinely live Yahoo data and both tag source "yf".
Every snapshot carries a "source" field so agents can see what they're
standing on: "yf" | "cache+groww_ltp" | "cache_stale".
"""
import os
import pathlib
import re
import sys
import time

import pandas as pd
import yfinance as yf

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "state" / "cache" / "ohlcv"
CACHE_ROWS = 420          # ~20 months of daily bars
CACHE_MAX_AGE_BARS = 5    # refuse cache whose last bar is older than this many trading days

INDEX_MAP = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "INDIAVIX": "^INDIAVIX",
             "USDINR": "USDINR=X", "GOLD": "GC=F", "CRUDE": "CL=F", "DXY": "DX-Y.NYB"}

_session = None
_groww = None


def yf_symbol(symbol: str) -> str:
    s = symbol.upper()
    if s in INDEX_MAP:
        return INDEX_MAP[s]
    if s.startswith("^") or "=" in s or s.endswith(".NS"):
        return s
    return s + ".NS"


def _session_candidates():
    """Ordered quote-session strategies. Cloud finding (journal 2026-08-04): the
    sandbox egress proxy resets curl_cffi's impersonated TLS, while a plain
    requests.Session passes — so plain goes FIRST, impersonation is the retry."""
    def plain():
        import requests
        s = requests.Session()
        s.headers["User-Agent"] = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")
        return s
    def impersonated():
        from curl_cffi import requests as curl_requests
        return curl_requests.Session(impersonate="chrome")
    return [plain, impersonated, lambda: None]


CHART_URL = "https://query{host}.finance.yahoo.com/v8/finance/chart/{sym}"
# Deliberately generic. Measured 2026-08-05, same second, same container:
# "Mozilla/5.0" -> 200; a full Chrome UA -> 429; the requests default UA -> 429.
# Yahoo 429s a UA that claims a browser when the TLS fingerprint isn't that
# browser's — and we cannot forge the fingerprint through the egress proxy.
# Do not "improve" this into a realistic UA; that is what breaks the feed.
CHART_UA = "Mozilla/5.0"


def _chart_frame(payload: dict, interval: str = "1d") -> pd.DataFrame:
    """Yahoo chart JSON -> the same OHLCV frame yfinance(auto_adjust=True) returns."""
    chart = (payload or {}).get("chart") or {}
    results = chart.get("result")
    if not results:
        err = (chart.get("error") or {}).get("description") or chart.get("error") or "no result"
        raise RuntimeError(f"chart endpoint: {err}")
    res = results[0]
    ts, ind = res.get("timestamp") or [], res.get("indicators") or {}
    quote = (ind.get("quote") or [{}])[0]
    if not ts or not quote.get("close"):
        raise RuntimeError("chart endpoint: empty series")

    idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert(res["meta"]["exchangeTimezoneName"])
    df = pd.DataFrame({"Open": quote.get("open"), "High": quote.get("high"),
                       "Low": quote.get("low"), "Close": quote.get("close"),
                       "Volume": quote.get("volume")}, index=idx)
    adj = (ind.get("adjclose") or [{}])[0].get("adjclose")
    if adj is not None:
        ratio = pd.Series(adj, index=idx) / df["Close"]
        for col in ("Open", "High", "Low"):
            df[col] = df[col] * ratio
        df["Close"] = pd.Series(adj, index=idx)   # Volume is untouched, as yfinance does
    if interval[-1] not in "mh":   # 1m/1h keep their tz; 1d/1wk/1mo are naive dates (yfinance)
        df.index = df.index.normalize().tz_localize(None)
    df.index.name = "Date"
    return df.dropna(subset=["Close"])


def _chart_fetch(symbol: str, period: str, interval: str) -> pd.DataFrame:
    """Fetch daily bars straight from Yahoo over plain requests (standard TLS)."""
    import requests
    from urllib.parse import quote as urlquote

    last_err = None
    for host in (1, 2):
        try:
            r = requests.get(CHART_URL.format(host=host, sym=urlquote(yf_symbol(symbol))),
                             params={"range": period, "interval": interval,
                                     "events": "div,split"},
                             headers={"User-Agent": CHART_UA}, timeout=20)
            if getattr(r, "status_code", 200) != 200:
                last_err = RuntimeError(f"HTTP {r.status_code}")
                continue
            return _chart_frame(r.json(), interval)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"chart fetch failed for {symbol}: {last_err}")


def _yf_fetch(symbol: str, period: str, interval: str) -> pd.DataFrame:
    try:
        return _chart_fetch(symbol, period, interval)
    except Exception as e:
        last_err = e
    for delay, make_session in zip((0, 2, 5), _session_candidates()):
        if delay:
            time.sleep(delay)
        try:
            kwargs = dict(period=period, interval=interval, progress=False,
                          auto_adjust=True, multi_level_index=False)
            try:
                sess = make_session()
            except Exception:
                sess = None
            try:
                df = yf.download(yf_symbol(symbol), session=sess, **kwargs) if sess \
                    else yf.download(yf_symbol(symbol), **kwargs)
            except TypeError:  # older yfinance without session kwarg
                df = yf.download(yf_symbol(symbol), **kwargs)
            if df is not None and not df.empty:
                return df.dropna(subset=["Close"])
        except Exception as e:
            last_err = e
    raise RuntimeError(f"yfinance failed for {symbol}: {last_err or 'empty response'}")


def _cache_path(symbol: str) -> pathlib.Path:
    return CACHE_DIR / (re.sub(r"[^A-Za-z0-9._&-]", "_", symbol.upper()) + ".csv")


def _load_cache(symbol: str) -> pd.DataFrame | None:
    p = _cache_path(symbol)
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        return df if not df.empty else None
    except Exception:
        return None


def _save_cache(symbol: str, df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    old = _load_cache(symbol)
    if old is not None:
        df = pd.concat([old, df])
        df = df[~df.index.duplicated(keep="last")].sort_index()
    df.tail(CACHE_ROWS).to_csv(_cache_path(symbol))


def _cache_age_bars(df: pd.DataFrame) -> int:
    """Approximate trading days between the cache's last bar and now (IST)."""
    days = pd.bdate_range(df.index[-1].date(), pd.Timestamp.now(tz="Asia/Kolkata").date())
    return max(len(days) - 1, 0)


def groww_ltp(symbol: str) -> float | None:
    """Live LTP from Groww (data-only). None if creds/SDK absent or call fails."""
    global _groww
    s = symbol.upper()
    if s in INDEX_MAP or s.startswith("^") or "=" in s:
        return None
    if _groww is False:
        return None
    try:
        if _groww is None:
            from growwapi import GrowwAPI
            api_key, secret = os.environ.get("GROWW_API_KEY"), os.environ.get("GROWW_API_SECRET")
            if not api_key or not secret:
                _groww = False
                return None
            try:
                import pyotp
                resp = GrowwAPI.get_access_token(api_key=api_key, totp=pyotp.TOTP(secret).now())
            except Exception:
                resp = GrowwAPI.get_access_token(api_key=api_key, secret=secret)
            token = resp.get("token") if isinstance(resp, dict) else resp
            if not token:
                _groww = False
                return None
            _groww = GrowwAPI(token)
        out = _groww.get_ltp(exchange_trading_symbols=(f"NSE_{s}",), segment=_groww.SEGMENT_CASH)
        for v in (out or {}).values():
            return float(v)
        return None
    except Exception:
        return None


def get_ohlcv(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    if interval != "1d":
        return _yf_fetch(symbol, period, interval)
    try:
        df = _yf_fetch(symbol, period, interval)
        _save_cache(symbol, df)
        df.attrs["source"] = "yf"
        return df
    except RuntimeError:
        cached = _load_cache(symbol)
        if cached is None or _cache_age_bars(cached) > CACHE_MAX_AGE_BARS:
            raise
        ltp = groww_ltp(symbol)
        if ltp:
            patched = cached.copy()
            ts = pd.Timestamp.now(tz="Asia/Kolkata").normalize().tz_localize(None)
            row = {c: None for c in patched.columns}
            row.update({"Open": ltp, "High": ltp, "Low": ltp, "Close": ltp, "Volume": 0})
            patched.loc[ts] = row
            patched = patched[~patched.index.duplicated(keep="last")].sort_index()
            patched.attrs["source"] = "cache+groww_ltp"
            return patched
        cached.attrs["source"] = "cache_stale"
        return cached


def last_price(symbol: str) -> float:
    try:
        df = _yf_fetch(symbol, "5d", "1d")
        _save_cache(symbol, df) if "=" not in symbol and not symbol.startswith("^") else None
        return float(df["Close"].iloc[-1])
    except RuntimeError:
        ltp = groww_ltp(symbol)
        if ltp:
            return ltp
        raise


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - 100 / (1 + rs)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift()).abs(),
        (df["Low"] - df["Close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def snapshot(symbol: str) -> dict:
    """One-symbol technical snapshot: everything the desk needs to triage a chart."""
    df = get_ohlcv(symbol, period="1y", interval="1d")
    source = df.attrs.get("source", "yf")
    c = df["Close"]
    last, prev = float(c.iloc[-1]), float(c.iloc[-2])
    sma20, sma50 = c.rolling(20).mean(), c.rolling(50).mean()
    sma200 = c.rolling(200).mean()
    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_sig = macd.ewm(span=9, adjust=False).mean()
    vol = df["Volume"]
    a = atr(df)
    high52, low52 = float(df["High"].max()), float(df["Low"].min())
    vol_ratio = None
    if source == "yf":
        vol_ratio = round(float(vol.iloc[-1] / max(vol.rolling(20).mean().iloc[-1], 1)), 2)
    return {
        "symbol": symbol.upper(),
        "source": source,  # yf | cache+groww_ltp | cache_stale — agents must treat non-yf as degraded
        "last": round(last, 2),
        "change_pct": round((last / prev - 1) * 100, 2),
        "rsi14": round(float(rsi(c).iloc[-1]), 1),
        "sma20": round(float(sma20.iloc[-1]), 2),
        "sma50": round(float(sma50.iloc[-1]), 2),
        "sma200": round(float(sma200.iloc[-1]), 2) if not pd.isna(sma200.iloc[-1]) else None,
        "macd_hist": round(float((macd - macd_sig).iloc[-1]), 2),
        "macd_cross": "bullish" if macd.iloc[-1] > macd_sig.iloc[-1] else "bearish",
        "atr14": round(float(a.iloc[-1]), 2),
        "vol_ratio_20d": vol_ratio,
        "pos_52w_pct": round((last - low52) / max(high52 - low52, 1e-9) * 100, 1),
        "high_52w": round(high52, 2),
        "low_52w": round(low52, 2),
        "trend": ("up" if last > sma50.iloc[-1] > (sma200.iloc[-1] if not pd.isna(sma200.iloc[-1]) else 0)
                  else "down" if last < sma50.iloc[-1] else "sideways"),
    }


if __name__ == "__main__":
    import json
    cmd = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    sym = sys.argv[2] if len(sys.argv) > 2 else "NIFTY"
    if cmd == "quote":
        print(json.dumps({"symbol": sym, "last": last_price(sym)}))
    elif cmd == "snapshot":
        print(json.dumps(snapshot(sym), indent=2))
    elif cmd == "ohlcv":
        print(get_ohlcv(sym, period=sys.argv[3] if len(sys.argv) > 3 else "3mo").tail(60).to_string())
    elif cmd == "growwcheck":
        status = {"creds_present": bool(os.environ.get("GROWW_API_KEY") and os.environ.get("GROWW_API_SECRET")),
                  "auth": None, "ltp_reliance": None}
        try:
            from growwapi import GrowwAPI
            key, sec = os.environ.get("GROWW_API_KEY"), os.environ.get("GROWW_API_SECRET")
            try:
                import pyotp
                resp = GrowwAPI.get_access_token(api_key=key, totp=pyotp.TOTP(sec).now())
                status["auth"] = "ok (TOTP flow — self-refreshing, 6AM resets harmless)"
            except Exception as e1:
                try:
                    resp = GrowwAPI.get_access_token(api_key=key, secret=sec)
                    status["auth"] = "ok (approval flow — DIES at 6AM daily until re-approved in console; switch to a TOTP key)"
                except Exception as e2:
                    status["auth"] = f"FAILED — totp: {str(e1)[:80]} | secret: {str(e2)[:120]}"
                    resp = None
            if resp:
                token = resp.get("token") if isinstance(resp, dict) else resp
                g = GrowwAPI(token)
                out = g.get_ltp(exchange_trading_symbols=("NSE_RELIANCE",), segment=g.SEGMENT_CASH)
                status["ltp_reliance"] = list((out or {}).values())[0] if out else None
        except Exception as e:
            status["auth"] = status["auth"] or f"FAILED — {str(e)[:150]}"
        print(json.dumps(status, indent=2))
    elif cmd == "warm":
        from engine import common
        wl = common.load_yaml(ROOT / "state" / "watchlist.yaml", {}) or {}
        raw = wl.get("symbols", wl) if isinstance(wl, dict) else wl
        syms = [s["symbol"] if isinstance(s, dict) else s for s in raw]
        ok, fail = [], []
        for s in syms + list(INDEX_MAP):
            try:
                get_ohlcv(s, period="2y")
                ok.append(s)
            except Exception:
                fail.append(s)
            time.sleep(1)
        print(json.dumps({"cached": ok, "failed": fail}))
