"""Market data via yfinance (NSE symbols get a .NS suffix) plus indicator math.

Resilience layers (cloud IPs get 429-throttled by Yahoo):
1. the Yahoo chart endpoint over plain requests (standard TLS, proxy-aware) —
   yfinance's own transport impersonates a browser's TLS fingerprint, which a
   MITM egress proxy resets (curl error 35), so the plain client goes first;
2. yfinance itself, for hosts where its cookie/crumb path is the one that works;
3. NSE's own bhavcopy archive — a SECOND daily-bar source, independent of Yahoo,
   so a Yahoo 429 is no longer a total bar outage (tags source "nse_bhav");
4. on-disk daily-bar cache in state/cache/ohlcv/ (committed to git, so cloud
   runs inherit history and only need the incremental bar);
5. Groww live LTP fallback (data-only; needs GROWW_API_KEY/SECRET in env) to
   patch a live price onto cached history when Yahoo is down.
Layers 1 and 2 are both genuinely live Yahoo data and both tag source "yf".
Every snapshot carries a "source" field so agents can see what they're
standing on: "yf" | "nse_bhav" | "cache+groww_ltp" | "cache_stale".
"""
import os
import pathlib
import re
import sys
import time

import pandas as pd
import yfinance as yf

from engine import common

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "state" / "cache" / "ohlcv"
CACHE_ROWS = 420          # ~20 months of daily bars
CACHE_MAX_AGE_BARS = 5    # refuse cache whose last bar is older than this many trading days

# Yahoo's chart endpoint answers HTTP 200 for a `range` outside this vocabulary,
# serving one still-forming bar instead of an error (issue 20260810-1335). So a
# typo — `45`, `--days 30`, `banana` — used to come back shaped exactly like a
# successful fetch: same header, same columns, tagged source="yf". The desk
# checks the word itself rather than trusting the feed to refuse it.
VALID_PERIODS = ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")

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


def _drop_carried_bars(df: pd.DataFrame) -> pd.DataFrame:
    """Drop bars that repeat the prior bar's close AND its nonzero volume.

    Yahoo's continuous-futures series can carry an expiring contract's numbers
    forward onto the next date while giving that date its own open, producing a
    bar that reconciles with neither neighbour. Two real sessions never agree on
    both the close and a nonzero volume to the last float bit, so such a bar is a
    carry: drop it and leave a gap rather than feed a fake move downstream.

    Zero-volume series (FX, indices) are exempt — there an unchanged close is a
    real quiet session, and dropping it would invent gaps in a clean feed.

    Narrow on purpose. A bar that carries only its volume, under a genuine close,
    is a different defect wanting a different remedy (blank the volume, keep the
    price) — see state/issues OPEN-20260808-1653-data.
    """
    if len(df) < 2 or not {"Close", "Volume"} <= set(df.columns):
        return df
    carried = ((df["Close"] == df["Close"].shift())
               & (df["Volume"] == df["Volume"].shift())
               & (df["Volume"] > 0))
    keep = ~carried
    # A frame that is MOSTLY "carried" is not a frame with a few carried bars —
    # it is one this heuristic does not understand. Distrust the guard, not the
    # data: stripping a frame to nothing would turn the module's careful
    # degradation into an IndexError two callers down.
    if not carried.any() or carried.sum() > len(df) / 2 or int(keep.sum()) < 2:
        return df
    return df[keep]


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


BHAV_URL = ("https://nsearchives.nseindia.com/content/cm/"
            "BhavCopy_NSE_CM_0_0_0_{d}_F_0000.csv.zip")
BHAV_UA = "Mozilla/5.0"
BHAV_LOOKBACK_DAYS = 12   # calendar days — must outrun CACHE_MAX_AGE_BARS + a holiday weekend
_bhav_cache: dict[str, dict] = {}   # yyyymmdd -> {ticker: row}, per process


def _bhav_day(day: pd.Timestamp) -> dict:
    """One NSE bhavcopy date -> {ticker: OHLCV row}, cash equities only.

    Returns {} — never raises — when NSE has no file for that date: weekends,
    holidays, and today before the ~18:00 IST publication all look the same.
    One zip carries the whole market, so a 15-symbol scan costs one fetch per
    date, not per symbol; the process cache keeps it that way.
    """
    key = day.strftime("%Y%m%d")
    if key in _bhav_cache:
        return _bhav_cache[key]
    rows: dict[str, dict] = {}
    try:
        import io
        import zipfile

        import requests
        r = requests.get(BHAV_URL.format(d=key), headers={"User-Agent": BHAV_UA}, timeout=25)
        if getattr(r, "status_code", 200) == 200:
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                df = pd.read_csv(z.open(z.namelist()[0]))
            eq = df[(df["FinInstrmTp"].astype(str).str.strip() == "STK")
                    & (df["SctySrs"].astype(str).str.strip() == "EQ")]
            for t, o, h, l, c, v in zip(eq["TckrSymb"], eq["OpnPric"], eq["HghPric"],
                                        eq["LwPric"], eq["ClsPric"], eq["TtlTradgVol"]):
                rows[str(t).strip().upper()] = {
                    "Open": float(o), "High": float(h), "Low": float(l),
                    "Close": float(c), "Volume": float(v)}
    except Exception:
        rows = {}
    _bhav_cache[key] = rows
    return rows


def bhav_fetch(symbol: str, days: int = BHAV_LOOKBACK_DAYS) -> pd.DataFrame:
    """Recent daily bars for one NSE equity from the exchange's own archive.

    This is the desk's second bar source. Groww's fallback is an LTP — a price,
    not a bar — so it can only ever defend a position, never open one; these are
    real OHLCV bars with real full-day volume, settled by the exchange itself.

    Prices are exchange-raw (unadjusted) while the yfinance history is
    auto-adjusted, so these bars are only ever appended to close a freshness
    gap in an existing series — never used to rebuild history across a
    corporate action. Indices and FX are not in the CM segment; they raise.
    """
    s = symbol.upper()
    s = s[:-3] if s.endswith(".NS") else s
    if s in INDEX_MAP or s.startswith("^") or "=" in s:
        raise RuntimeError(f"bhavcopy covers NSE cash equities only, not {symbol}")
    today = pd.Timestamp.now(tz="Asia/Kolkata").normalize().tz_localize(None)
    bars = {}
    for back in range(days):
        day = today - pd.Timedelta(days=back)
        if day.weekday() >= 5:            # NSE is shut; no file exists to fetch
            continue
        row = _bhav_day(day).get(s)
        if row:
            bars[day] = row
    if not bars:
        raise RuntimeError(f"bhavcopy has no recent bars for {symbol}")
    df = pd.DataFrame.from_dict(bars, orient="index").sort_index()
    df.index.name = "Date"
    return df


def _groww_sdk():
    """The Groww SDK class, or None when the package isn't installed."""
    try:
        from growwapi import GrowwAPI
        return GrowwAPI
    except Exception:
        return None


def groww_status(symbol: str = "RELIANCE") -> dict:
    """Whether the live-LTP fallback actually works, and if not, why.

    groww_ltp() collapses every failure into None; preflight needs to tell a
    missing SDK from absent creds from a dead call, because a DEGRADED verdict
    whose stated remedy is "exits on live LTP" must prove live LTP exists.
    """
    if _groww_sdk() is None:
        return {"live_ltp": "dead", "why": "sdk_missing", "ltp": None}
    if not (os.environ.get("GROWW_API_KEY") and os.environ.get("GROWW_API_SECRET")):
        return {"live_ltp": "dead", "why": "no_creds", "ltp": None}
    ltp = groww_ltp(symbol)
    if ltp:
        return {"live_ltp": "ok", "why": None, "ltp": ltp}
    return {"live_ltp": "dead", "why": "auth_or_call_failed", "ltp": None}


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
            GrowwAPI = _groww_sdk()
            if GrowwAPI is None:
                return None
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


def _check_period(period: str) -> str:
    """Refuse a period Yahoo will not honour, before any request leaves the desk.

    Raises ValueError, deliberately not RuntimeError: the fallback ladder below
    catches RuntimeError, and a typo must not degrade into cached bars. An
    outage is answerable from cache; a nonsense question is not.
    """
    if period not in VALID_PERIODS:
        raise ValueError(f"invalid period {period!r} — valid: {', '.join(VALID_PERIODS)}")
    return period


def get_ohlcv(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    _check_period(period)
    if interval != "1d":
        return _yf_fetch(symbol, period, interval)
    try:
        df = _drop_carried_bars(_yf_fetch(symbol, period, interval))
        _save_cache(symbol, df)
        df.attrs["source"] = "yf"
        return df
    except RuntimeError:
        cached = _load_cache(symbol)
        # Yahoo is down. Before reaching for a patched or stale price, try the
        # exchange's own archive: it closes the freshness gap with genuine bars.
        # It appends to cached history rather than replacing it, so a symbol we
        # have never cached still degrades the old way.
        if cached is not None:
            try:
                merged = pd.concat([cached, bhav_fetch(symbol)])
                merged = merged[~merged.index.duplicated(keep="last")].sort_index()
                if _cache_age_bars(merged) <= CACHE_MAX_AGE_BARS:
                    merged.attrs["source"] = "nse_bhav"
                    return merged
            except Exception:
                pass
        if cached is None or _cache_age_bars(cached) > CACHE_MAX_AGE_BARS:
            raise
        ltp = groww_ltp(symbol)
        if ltp:
            patched = cached.copy()
            # The LTP is the newest price there is, so it must land on the
            # newest bar. If the cache already holds a bar dated at or after
            # today (clock skew, a bar stamped by exchange date), a row stamped
            # "now" would sort BEHIND it and iloc[-1] would hand back a stale
            # close while source still claims a live patch.
            ts = max(pd.Timestamp.now(tz="Asia/Kolkata").normalize().tz_localize(None),
                     patched.index.max())
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
        df = _drop_carried_bars(_yf_fetch(symbol, "5d", "1d"))
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


ROLL_GAP_PCT = 3.0      # an open this far off the prior close, ...
ROLL_VOL_STEP = 5.0     # ... on a volume step this large, is a contract handover


def _roll_suspected(symbol: str, df: pd.DataFrame) -> bool:
    """Does the newest bar look like a futures roll rather than a price move?

    A continuous-futures proxy splices contracts, so the new front month's first
    bar opens at a different price level entirely and arrives carrying that
    contract's much larger volume. The resulting "gap" is a contract change, not
    a price move (observed on CRUDE 2026-08-06: open +3.92% off the prior close
    on a 42.6x volume step). Crude and gold are 1.0 each of the macro-sentinel's
    5.5 vote weight and the regime sets the gross exposure cap, so a fabricated
    print here resizes the whole book.

    Both arms must fire, so an ordinary overnight gap on ordinary volume still
    reports normally. It errs toward withholding: on a hit the desk loses one
    day's change_pct but still gets `last`, which beats voting a fabricated
    percentage into a cap-setting score.

    Pinned to "=F" symbols deliberately: a cash equity gapping hard on heavy
    volume is an earnings reaction — the most informative print the desk gets —
    and suppressing that would be the worse bug.
    """
    if not yf_symbol(symbol).endswith("=F") or len(df) < 2:
        return False
    o, prev_close = float(df["Open"].iloc[-1]), float(df["Close"].iloc[-2])
    v, prev_vol = float(df["Volume"].iloc[-1]), float(df["Volume"].iloc[-2])
    if prev_close <= 0 or v <= 0 or prev_vol <= 0:
        return False
    return (abs(o / prev_close - 1) * 100 > ROLL_GAP_PCT
            and max(v / prev_vol, prev_vol / v) > ROLL_VOL_STEP)


def _partial_session(df: pd.DataFrame) -> bool:
    """Is the newest bar today's session, still in progress?

    A daily bar fetched mid-session is a running total, not a session. Dividing
    it by a 20-day FULL-day average understates participation by roughly the
    fraction of the session still to come (observed 2026-08-06: TATASTEEL read
    vol_ratio_20d 1.04 on the completed bar at 08:16 IST and 0.04 at 09:16, one
    minute after the open, on no market event).

    Only the volume is affected — a running high/low/close is the real level so
    far, but a running volume compared against completed days is not comparable
    to anything. So this suppresses vol_ratio_20d alone, which already has a
    documented "unmeasurable" value (None) that the score and the
    volume_unconfirmed flag both honour.
    """
    if df.empty or not common.market_status()["is_open"]:
        return False       # after 15:30 the same bar is a true full-day total
    return pd.Timestamp(df.index[-1]).normalize() == pd.Timestamp(common.now_ist().date())


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
    partial = _partial_session(df)
    vol_ratio = None
    if source in ("yf", "nse_bhav") and not partial:   # both carry true full-day volume
        vol_ratio = round(float(vol.iloc[-1] / max(vol.rolling(20).mean().iloc[-1], 1)), 2)
    roll = _roll_suspected(symbol, df)
    return {
        "symbol": symbol.upper(),
        "source": source,  # yf | nse_bhav | cache+groww_ltp | cache_stale — agents must treat non-live as degraded
        "last": round(last, 2),
        "change_pct": None if roll else round((last / prev - 1) * 100, 2),
        # True ⇒ change_pct withheld: the last bar is a contract handover, not a move
        "roll_suspected": roll,
        "rsi14": round(float(rsi(c).iloc[-1]), 1),
        "sma20": round(float(sma20.iloc[-1]), 2),
        "sma50": round(float(sma50.iloc[-1]), 2),
        "sma200": round(float(sma200.iloc[-1]), 2) if not pd.isna(sma200.iloc[-1]) else None,
        "macd_hist": round(float((macd - macd_sig).iloc[-1]), 2),
        "macd_cross": "bullish" if macd.iloc[-1] > macd_sig.iloc[-1] else "bearish",
        "atr14": round(float(a.iloc[-1]), 2),
        "vol_ratio_20d": vol_ratio,
        # True ⇒ vol_ratio_20d withheld: today's bar is still forming, so its
        # volume is a partial total and not comparable to a full-day average
        "vol_partial_session": partial,
        "pos_52w_pct": round((last - low52) / max(high52 - low52, 1e-9) * 100, 1),
        "high_52w": round(high52, 2),
        "low_52w": round(low52, 2),
        "trend": ("up" if last > sma50.iloc[-1] > (sma200.iloc[-1] if not pd.isna(sma200.iloc[-1]) else 0)
                  else "down" if last < sma50.iloc[-1] else "sideways"),
    }


def ohlcv_text(symbol: str, period: str = "3mo") -> str:
    """The CLI's OHLCV view: the whole requested window, with its extent stated.

    Issue 20260806-1026: this branch printed `.tail(60)` regardless of period, so
    a seat asking for 2y built support/resistance from ~3 months of candles and
    had no way to see the cut — the series simply appeared to end. A window an
    agent reasons over is never silently narrower than the one it asked for, and
    when the feed genuinely holds less than the period covers the header says so
    rather than leaving it to be inferred from a row that isn't there.
    """
    df = get_ohlcv(symbol, period=period)
    span = f"{df.index[0].date()}..{df.index[-1].date()}" if len(df) else "empty"
    return (f"# {symbol} period={period} rows={len(df)} span={span} "
            f"source={df.attrs.get('source', 'unknown')}\n{df.to_string()}")


if __name__ == "__main__":
    import json
    cmd = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    sym = sys.argv[2] if len(sys.argv) > 2 else "NIFTY"
    if cmd == "quote":
        print(json.dumps({"symbol": sym, "last": last_price(sym)}))
    elif cmd == "snapshot":
        print(json.dumps(snapshot(sym), indent=2))
    elif cmd == "ohlcv":
        try:
            print(ohlcv_text(sym, sys.argv[3] if len(sys.argv) > 3 else "3mo"))
        except ValueError as e:
            sys.exit(f"usage: python3 -m engine.data ohlcv <SYMBOL> [period] — {e}")
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
