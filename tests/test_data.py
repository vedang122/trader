"""Data fallback ladder: yf -> cache+groww LTP -> stale cache -> honest failure."""
import pandas as pd
import pytest
import requests

from engine import data


def _write_cache(sym, last_day_offset=0, monkeypatch=None):
    idx = pd.bdate_range(end=pd.Timestamp.now(tz="Asia/Kolkata").normalize().tz_localize(None)
                         - pd.tseries.offsets.BDay(last_day_offset), periods=60)
    df = pd.DataFrame({"Open": 100.0, "High": 101.0, "Low": 99.0,
                       "Close": 100.0, "Volume": 1000}, index=idx)
    data.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(data._cache_path(sym))
    return df


def _kill_yf(monkeypatch):
    def dead(symbol, period, interval):
        raise RuntimeError("429")
    monkeypatch.setattr(data, "_yf_fetch", dead)


def test_fresh_cache_plus_groww_ltp(desk, monkeypatch):
    _write_cache("TESTCO")
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_ltp", lambda s: 105.0)
    df = data.get_ohlcv("TESTCO")
    assert df.attrs["source"] == "cache+groww_ltp"
    assert float(df["Close"].iloc[-1]) == 105.0


def test_fresh_cache_no_groww_is_stale(desk, monkeypatch):
    _write_cache("TESTCO")
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_ltp", lambda s: None)
    df = data.get_ohlcv("TESTCO")
    assert df.attrs["source"] == "cache_stale"


def test_old_cache_refuses(desk, monkeypatch):
    _write_cache("TESTCO", last_day_offset=10)  # 10 business days stale
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_ltp", lambda s: 105.0)
    with pytest.raises(RuntimeError):
        data.get_ohlcv("TESTCO")


def test_last_price_groww_fallback(desk, monkeypatch):
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_ltp", lambda s: 99.5)
    assert data.last_price("TESTCO") == 99.5


def test_last_price_raises_when_all_dead(desk, monkeypatch):
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_ltp", lambda s: None)
    with pytest.raises(RuntimeError):
        data.last_price("TESTCO")


def test_indices_never_hit_groww(desk):
    assert data.groww_ltp("NIFTY") is None
    assert data.groww_ltp("USDINR") is None


# --- direct Yahoo chart transport (S1: curl_cffi impersonation reset by proxy) ---

def _chart_payload(closes=(101.0, 102.0, 103.0), adj=None, tz="Asia/Kolkata"):
    """Minimal replica of query1.finance.yahoo.com/v8/finance/chart/<sym>."""
    n = len(closes)
    ts = [1785901500 - (n - 1 - i) * 86400 for i in range(n)]   # last bar = 2026-08-05 IST
    quote = {"open": [c - 1 for c in closes], "high": [c + 2 for c in closes],
             "low": [c - 2 for c in closes], "close": list(closes),
             "volume": [1000 * (i + 1) for i in range(n)]}
    indicators = {"quote": [quote]}
    if adj is not None:
        indicators["adjclose"] = [{"adjclose": list(adj)}]
    return {"chart": {"result": [{"meta": {"exchangeTimezoneName": tz,
                                           "regularMarketPrice": closes[-1]},
                                  "timestamp": ts, "indicators": indicators}],
                      "error": None}}


class _Resp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload


def _serve_chart(monkeypatch, payload, status=200):
    """Pin the plain-requests transport to a canned chart response."""
    seen = {}

    def fake_get(url, **kw):
        seen["url"], seen["headers"] = url, kw.get("headers") or {}
        return _Resp(payload, status)

    monkeypatch.setattr(requests, "get", fake_get)
    return seen


def _kill_yfinance_transport(monkeypatch):
    """yfinance's impersonated TLS is reset by the egress proxy (curl error 35)."""
    import yfinance as yf

    def reset(*a, **kw):
        raise OSError("Failed to perform, curl: (35) Recv failure: Connection reset by peer")

    monkeypatch.setattr(yf, "download", reset)


def test_chart_frame_parses_ohlcv(desk):
    df = data._chart_frame(_chart_payload())
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 3
    assert float(df["Close"].iloc[-1]) == 103.0
    assert float(df["Open"].iloc[-1]) == 102.0
    assert df.index.tz is None                     # daily bars are tz-naive, like yfinance
    assert str(df.index[-1].date()) == "2026-08-05"


def test_chart_frame_auto_adjusts_like_yfinance(desk):
    """Close becomes adjclose; O/H/L scale by the same ratio; Volume is untouched."""
    df = data._chart_frame(_chart_payload(closes=(100.0,), adj=(50.0,)))
    assert float(df["Close"].iloc[-1]) == 50.0
    assert float(df["Open"].iloc[-1]) == pytest.approx(49.5)   # 99 * 0.5
    assert float(df["Volume"].iloc[-1]) == 1000


def test_chart_frame_rejects_empty_result(desk):
    with pytest.raises(RuntimeError):
        data._chart_frame({"chart": {"result": None,
                                     "error": {"code": "Not Found"}}})


def test_live_when_yfinance_transport_is_reset(desk, monkeypatch):
    """The S1 repro: yfinance's transport is dead, but the plain-requests chart
    endpoint answers 200 — the desk must stay LIVE, not degrade to cache_stale."""
    _write_cache("TESTCO")                     # fresh cache exists and is WRONG
    _kill_yfinance_transport(monkeypatch)
    monkeypatch.setattr(data, "groww_ltp", lambda s: None)
    seen = _serve_chart(monkeypatch, _chart_payload(closes=(101.0, 102.0, 103.0)))

    df = data.get_ohlcv("TESTCO", period="5d")
    assert df.attrs["source"] == "yf"          # a real source tag — entries stay unblocked
    assert float(df["Close"].iloc[-1]) == 103.0   # live, not the cache's 100.0
    assert "TESTCO.NS" in seen["url"] and "User-Agent" in seen["headers"]


def test_chart_ua_stays_generic():
    """Yahoo 429s a UA that claims a browser our TLS fingerprint can't back up.
    Measured: 'Mozilla/5.0' -> 200, full Chrome UA -> 429, requests default -> 429."""
    assert data.CHART_UA == "Mozilla/5.0"
    assert "Chrome" not in data.CHART_UA and "Safari" not in data.CHART_UA


def test_last_price_uses_chart_before_degrading(desk, monkeypatch):
    _kill_yfinance_transport(monkeypatch)
    monkeypatch.setattr(data, "groww_ltp", lambda s: 99.5)
    _serve_chart(monkeypatch, _chart_payload(closes=(103.0,)))
    assert data.last_price("TESTCO") == 103.0  # Yahoo beats the broker LTP patch


def test_chart_failure_still_degrades_to_cache(desk, monkeypatch):
    """Both live paths dead ⇒ the old ladder still applies. No silent live claim."""
    _write_cache("TESTCO")
    _kill_yfinance_transport(monkeypatch)
    monkeypatch.setattr(data, "groww_ltp", lambda s: None)
    _serve_chart(monkeypatch, {"chart": {"result": None, "error": {"code": "429"}}}, status=429)

    df = data.get_ohlcv("TESTCO", period="5d")
    assert df.attrs["source"] == "cache_stale"


# --- second daily-bar source: the exchange's own bhavcopy archive (S2 outage) ---
# Repro: OPEN-20260805-1436 — Yahoo 429s this egress, and yfinance was the ONLY
# source of daily bars, so every watchlist symbol served cache_stale and entries
# were foreclosed for five consecutive cycles. Groww's LTP is a price, not a bar,
# so it can never unlock an entry. NSE's own archive can.

_real_bhav_day = data._bhav_day      # captured before conftest's offline stub


def _bhav_csv(rows):
    """Minimal replica of BhavCopy_NSE_CM_0_0_0_<date>_F_0000.csv."""
    head = ("TradDt,FinInstrmTp,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,"
            "TtlTradgVol\n")
    return head + "".join(
        f"2026-08-05,{r.get('tp', 'STK')},{r['sym']},{r.get('srs', 'EQ')},"
        f"{r['o']},{r['h']},{r['l']},{r['c']},{r['v']}\n" for r in rows)


def _bhav_zip(rows):
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("BhavCopy.csv", _bhav_csv(rows))
    return buf.getvalue()


class _BinResp:
    def __init__(self, content, status=200):
        self.content, self.status_code = content, status


def _serve_bhav(monkeypatch, rows, status=200):
    """Every archive date answers with the same canned zip."""
    data._bhav_cache.clear()
    seen = {"urls": []}

    def fake_get(url, **kw):
        seen["urls"].append(url)
        seen["headers"] = kw.get("headers") or {}
        return _BinResp(_bhav_zip(rows), status)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(data, "_bhav_day", _real_bhav_day)   # undo conftest's offline stub
    return seen


def test_bhav_day_parses_exchange_archive(desk, monkeypatch):
    """The archive is a zipped CSV; only cash-equity series are bars we can use."""
    _serve_bhav(monkeypatch, [
        {"sym": "TESTCO", "o": 100.0, "h": 104.0, "l": 99.0, "c": 103.0, "v": 5000},
        {"sym": "SGBJUN28", "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v": 1, "srs": "GB"},
    ])
    day = data._bhav_day(pd.Timestamp("2026-08-05"))
    assert day["TESTCO"] == {"Open": 100.0, "High": 104.0, "Low": 99.0,
                             "Close": 103.0, "Volume": 5000.0}
    assert "SGBJUN28" not in day          # gold bonds are not equity bars


def test_yahoo_dead_still_yields_live_bars_from_the_exchange(desk, monkeypatch):
    """THE REPRO: Yahoo is 429 and Groww is absent. Before the fix this returned
    cache_stale with no volume and the desk could not initiate. The exchange's
    own archive is a genuine second bar source — bars, not just a last price."""
    _write_cache("TESTCO", last_day_offset=4)      # history exists but is stale
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_ltp", lambda s: None)
    _serve_bhav(monkeypatch, [{"sym": "TESTCO", "o": 100.0, "h": 104.0,
                               "l": 99.0, "c": 103.0, "v": 5000}])

    df = data.get_ohlcv("TESTCO")
    assert df.attrs["source"] == "nse_bhav"        # not cache_stale, not a patch
    assert float(df["Close"].iloc[-1]) == 103.0    # a real settled close
    assert float(df["Volume"].iloc[-1]) == 5000.0  # a real full-day volume
    assert len(df) > 50                            # cached history is preserved


def test_bhav_bars_restore_volume_confirmation(desk, monkeypatch):
    """Groww's LTP patch writes Volume=0, so vol_ratio is suppressed. Exchange
    bars carry true volume, so the snapshot may confirm participation again."""
    _write_cache("TESTCO", last_day_offset=4)
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_ltp", lambda s: None)
    _serve_bhav(monkeypatch, [{"sym": "TESTCO", "o": 100.0, "h": 104.0,
                               "l": 99.0, "c": 103.0, "v": 5000}])

    snap = data.snapshot("TESTCO")
    assert snap["source"] == "nse_bhav"
    assert snap["vol_ratio_20d"] is not None


def test_bhav_declines_non_equities(desk, monkeypatch):
    """The CM bhavcopy has no indices or FX — it must say so, not invent a bar."""
    for sym in ("NIFTY", "USDINR", "^NSEI"):
        with pytest.raises(RuntimeError):
            data.bhav_fetch(sym)


def test_dead_exchange_archive_keeps_the_old_ladder(desk, monkeypatch):
    """A second source must not become a second way to fail: archive down ⇒ the
    cache/groww ladder still applies exactly as before."""
    _write_cache("TESTCO")
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_ltp", lambda s: None)
    _serve_bhav(monkeypatch, [], status=503)

    df = data.get_ohlcv("TESTCO")
    assert df.attrs["source"] == "cache_stale"
