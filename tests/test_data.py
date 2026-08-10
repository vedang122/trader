"""Data fallback ladder: yf -> cache+groww LTP -> stale cache -> honest failure."""
import subprocess
import sys

import pandas as pd
import pytest
import requests

from engine import common, data


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


def test_ltp_patch_lands_on_the_newest_bar(desk, monkeypatch):
    """A cache bar dated ahead of today must not strand the LTP behind it.

    `cache+groww_ltp` is a promise that the last close IS the live price; a
    patch filed before a newer cached bar quotes a stale close as a live one.
    """
    idx = pd.bdate_range(end=pd.Timestamp.now(tz="Asia/Kolkata").normalize().tz_localize(None)
                         + pd.tseries.offsets.BDay(3), periods=60)
    df = pd.DataFrame({"Open": 100.0, "High": 101.0, "Low": 99.0,
                       "Close": 100.0, "Volume": 1000}, index=idx)
    data.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(data._cache_path("TESTCO"))
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_ltp", lambda s: 105.0)
    out = data.get_ohlcv("TESTCO")
    assert out.attrs["source"] == "cache+groww_ltp"
    assert float(out["Close"].iloc[-1]) == 105.0


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
    """Every SETTLED archive date answers with the same canned zip.

    Today's file is a 404, because the exchange publishes a session only after
    it settles (~18:00 IST) — the same case _bhav_day documents as "today
    before publication looks like a missing file". Serving it would date a
    bhav bar to a session still in progress, which the real archive never
    does, and would make anything downstream of _partial_session read
    differently depending on the hour the suite happened to run.
    """
    data._bhav_cache.clear()
    seen = {"urls": []}
    today = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y%m%d")

    def fake_get(url, **kw):
        seen["urls"].append(url)
        seen["headers"] = kw.get("headers") or {}
        if today in url:
            return _BinResp(b"", 404)
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


def test_bhav_vol_confirmation_survives_an_open_session(desk, monkeypatch):
    """The same claim, with the clock pinned to a live session.

    Repro for the wall-clock flake: the archive publishes a session only once it
    has settled, so a bhav-sourced frame is never today's still-forming bar and
    _partial_session must not withhold its volume. Left to the real clock this
    passed after 15:30 and failed during the session.
    """
    monkeypatch.setattr(common, "market_status",
                        lambda: {"ist": "pinned", "phase": "open", "is_open": True})
    _write_cache("TESTCO", last_day_offset=4)
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_ltp", lambda s: None)
    _serve_bhav(monkeypatch, [{"sym": "TESTCO", "o": 100.0, "h": 104.0,
                               "l": 99.0, "c": 103.0, "v": 5000}])

    snap = data.snapshot("TESTCO")
    assert snap["source"] == "nse_bhav"
    assert snap["vol_partial_session"] is False
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


# --- futures-proxy hygiene: roll discontinuities and carried bars -------------
# Repro for OPEN-20260806-0826-data. GOLD (GC=F) and CRUDE (CL=F) are 1.0 of the
# macro-sentinel's 5.5 vote weight each, and the regime deterministically sets
# the gross exposure cap — so a fabricated change_pct resizes the whole book.


def _fetched(bars):
    """A freshly-fetched daily frame: bars = [(day, o, h, l, c, v), ...]."""
    idx = pd.DatetimeIndex([pd.Timestamp(b[0]) for b in bars])
    return pd.DataFrame({"Open": [b[1] for b in bars], "High": [b[2] for b in bars],
                         "Low": [b[3] for b in bars], "Close": [b[4] for b in bars],
                         "Volume": [b[5] for b in bars]}, index=idx)


def test_carried_bar_is_rejected_at_ingest(desk, monkeypatch):
    """CRUDE 2026-08-04 repeated 08-03's close to the last float bit AND its exact
    volume, while carrying its own open — an incoherent bar (O=75.77, C=80.10)
    that reconciles with neither neighbour. Two real sessions never agree on both
    close and a nonzero volume, so the bar is a carry and must not be stored."""
    df = _fetched([("2026-08-03", 80.34, 80.50, 79.90, 80.0999984741211, 294823),
                   ("2026-08-04", 75.77, 80.60, 75.60, 80.0999984741211, 294823),
                   ("2026-08-05", 75.56, 75.90, 74.80, 75.14, 11257)])
    monkeypatch.setattr(data, "_yf_fetch", lambda s, p, i: df)

    out = data.get_ohlcv("CRUDE")
    assert [str(d.date()) for d in out.index] == ["2026-08-03", "2026-08-05"], \
        "the carried 08-04 bar must be dropped, leaving a gap"
    assert data._load_cache("CRUDE") is None or \
        "2026-08-04" not in [str(d.date()) for d in data._load_cache("CRUDE").index], \
        "a carried bar must never reach the on-disk cache"


def test_flat_zero_volume_session_survives_ingest(desk, monkeypatch):
    """The carry guard keys on a repeated NONZERO volume. FX and index proxies
    (USDINR=X, ^INDIAVIX) carry Volume=0 every bar, so a quiet unchanged close
    there is a real session — dropping it would invent gaps in a clean feed."""
    df = _fetched([("2026-08-03", 88.10, 88.30, 88.00, 88.20, 0),
                   ("2026-08-04", 88.20, 88.25, 88.05, 88.20, 0),
                   ("2026-08-05", 88.20, 88.40, 88.15, 88.35, 0)])
    monkeypatch.setattr(data, "_yf_fetch", lambda s, p, i: df)

    out = data.get_ohlcv("USDINR")
    assert len(out) == 3, "a zero-volume flat session is real data, not a carry"


def test_roll_gap_suppresses_change_pct_on_a_futures_proxy(desk, monkeypatch):
    """GOLD 2026-08-05: open gapped +7.18% off the prior close while volume went
    698 -> 33,963. That is an expiring contract handing over to the new front
    month, not a gold move. The snapshot must say so rather than print the gap:
    an honest `roll_suspected` beats a fake percentage in a weighted input."""
    bars = [("2026-07-31", 4049.10, 4110.0, 4040.0, 4102.40, 1166),
            ("2026-08-03", 4033.70, 4090.0, 4020.0, 4083.40, 698),
            ("2026-08-04", 4095.40, 4100.0, 4040.0, 4050.50, 702),
            ("2026-08-05", 4341.40, 4350.0, 4300.0, 4307.00, 33963)]
    df = _fetched(bars)
    monkeypatch.setattr(data, "_yf_fetch", lambda s, p, i: df)

    snap = data.snapshot("GOLD")
    assert snap["roll_suspected"] is True
    assert snap["change_pct"] is None, "a contract change is not a price change"
    assert snap["last"] == 4307.00, "the level itself is still the best level we have"


def test_earnings_gap_on_an_equity_is_not_a_roll(desk, monkeypatch):
    """The guard must stay pinned to continuous-futures proxies. A cash equity
    gapping hard on 5x volume is an earnings reaction — the single most
    informative print there is. Suppressing THAT would be the worse bug."""
    bars = [("2026-07-31", 100.0, 101.0, 99.0, 100.0, 1000),
            ("2026-08-03", 100.0, 101.0, 99.0, 100.5, 1100),
            ("2026-08-04", 100.5, 101.5, 99.5, 101.0, 1050),
            ("2026-08-05", 112.0, 118.0, 111.0, 116.0, 9000)]
    df = _fetched(bars)
    monkeypatch.setattr(data, "_yf_fetch", lambda s, p, i: df)

    snap = data.snapshot("TESTCO")
    assert snap["roll_suspected"] is False
    assert snap["change_pct"] == 14.85, "a real equity gap must survive intact"


def test_carry_guard_never_strips_a_frame_to_nothing(desk, monkeypatch):
    """A frame that is MOSTLY carried is one the heuristic does not understand,
    not proof the feed is fake. The guard must hand it back whole: stripping it
    would turn this module's careful degradation into an IndexError two callers
    down, which is a worse failure than the stale volume it was hunting."""
    idx = pd.bdate_range(end=pd.Timestamp("2026-08-06"), periods=250)
    flat = pd.DataFrame({"Open": 100.0, "High": 101.0, "Low": 99.0,
                         "Close": 100.0, "Volume": 1000}, index=idx)
    monkeypatch.setattr(data, "_yf_fetch", lambda s, p, i: flat)

    assert len(data._drop_carried_bars(flat)) == 250
    snap = data.snapshot("TESTCO")          # must not raise
    assert snap["change_pct"] == 0.0
    assert snap["roll_suspected"] is False


# --- the in-progress session bar ---------------------------------------------
# Repro for OPEN-20260806-0922-scan. Intraday, the newest daily row is a running
# total, not a session: dividing it by a 20-day FULL-day average understates
# participation by roughly the fraction of the session still to come.


def _at(monkeypatch, iso):
    """Freeze the desk clock (data.py reads the session state through common)."""
    from engine import common
    monkeypatch.setattr(common, "now_ist",
                        lambda: pd.Timestamp(iso, tz=common.IST).to_pydatetime())


def _session_bars(last_day, last_vol):
    """20 settled sessions of steady volume, then `last_day` carrying last_vol."""
    days = pd.bdate_range(end=pd.Timestamp(last_day), periods=21)
    vols = [1000] * 20 + [last_vol]
    return _fetched([(d.strftime("%Y-%m-%d"), 100.0, 101.0, 99.0, 100.0, v)
                     for d, v in zip(days, vols)])


def test_partial_session_bar_withholds_vol_ratio(desk, monkeypatch):
    """TATASTEEL 2026-08-06: vol_ratio_20d read 1.04 on the completed bar at
    08:16 IST and 0.04 at 09:16 — one minute into the next session, on no market
    event. The 0.04 is one minute of trading over a full-day average. A ratio
    that moves 26x with the wall clock is unmeasured, not measured low, and the
    contract for unmeasured volume is already `None`."""
    monkeypatch.setattr(data, "_yf_fetch",
                        lambda s, p, i: _session_bars("2026-08-06", 40))
    _at(monkeypatch, "2026-08-06 09:16:00")     # Thursday, one minute after open

    snap = data.snapshot("TATASTEEL")
    assert snap["vol_partial_session"] is True
    assert snap["vol_ratio_20d"] is None, "0.04 of a day is not 0.04 of the volume"


def test_completed_session_bar_still_confirms_volume(desk, monkeypatch):
    """The guard must cost nothing once the session is over: after 15:30 the same
    bar is a true full-day total and participation is confirmable again.
    Suppressing volume on completed bars would break every volume-gated setup."""
    monkeypatch.setattr(data, "_yf_fetch",
                        lambda s, p, i: _session_bars("2026-08-06", 1400))
    _at(monkeypatch, "2026-08-06 16:00:00")     # same bar, session closed

    snap = data.snapshot("TATASTEEL")
    assert snap["vol_partial_session"] is False
    assert snap["vol_ratio_20d"] == 1.37


def test_yesterdays_bar_is_complete_even_mid_session(desk, monkeypatch):
    """Only TODAY's bar is in progress. Pre-open, or on a feed that has not yet
    printed today, the newest bar is a settled session — reading it as partial
    would blind the desk to volume for the whole morning."""
    monkeypatch.setattr(data, "_yf_fetch",
                        lambda s, p, i: _session_bars("2026-08-05", 1400))
    _at(monkeypatch, "2026-08-06 09:16:00")     # mid-session, but the bar is 08-05

    snap = data.snapshot("TATASTEEL")
    assert snap["vol_partial_session"] is False
    assert snap["vol_ratio_20d"] == 1.37


# --- the ohlcv CLI view: the window an analyst asks for is the window it gets ---

def _n_sessions(n, end="2026-08-07"):
    """n settled daily bars ending at `end`, closes walking up so rows differ."""
    days = pd.bdate_range(end=pd.Timestamp(end), periods=n)
    return _fetched([(d.strftime("%Y-%m-%d"), 100.0 + i, 101.0 + i, 99.0 + i,
                      100.0 + i, 1000) for i, d in enumerate(days)])


def test_ohlcv_view_honours_the_requested_period(desk, monkeypatch):
    """Issue 20260806-1026: the CLI printed `.tail(60)` whatever the period, so a
    seat asking for 2y built support/resistance from ~3 months and could not see
    the cut. The SUNPHARMA seat inferred 'no validated resistance exists above
    price' from a window a quarter the size it believed it had."""
    monkeypatch.setattr(data, "_yf_fetch", lambda s, p, i: _n_sessions(300))

    text = data.ohlcv_text("SUNPHARMA", "2y")

    assert len(text.splitlines()) == 302, "300 bars + header line + column line"
    assert "2025-06-16" in text, "the oldest bar of the requested window is present"


def test_ohlcv_view_states_its_own_size(desk, monkeypatch):
    """A window an agent reasons over always names its own extent: whatever the
    feed could serve, the caller can compare it against what it asked for."""
    monkeypatch.setattr(data, "_yf_fetch", lambda s, p, i: _n_sessions(40))

    head = data.ohlcv_text("SUNPHARMA", "2y").splitlines()[0]

    assert "rows=40" in head and "period=2y" in head, head
    assert "2026-08-07" in head, "the span is stated, so a short window is visible"


def test_ohlcv_cli_never_truncates_behind_the_caller(desk):
    """Tripwire on the CLI branch itself — the defect was one `.tail(60)` in
    `__main__`, not in any function a unit test would otherwise reach."""
    src = (data.ROOT / "engine" / "data.py").read_text()
    branch = src.split('elif cmd == "ohlcv":')[1].split("elif cmd ==")[0]

    assert "ohlcv_text" in branch, "the CLI prints the audited view"
    assert ".tail(" not in branch, f"fixed-row truncation is back in the CLI: {branch}"


# --- the period vocabulary: a window Yahoo will not honour is an error, not a bar ---
# Repro: OPEN-20260810-1335 — `ohlcv INFY 45` and `ohlcv INFY banana` both returned
# a ONE-ROW frame of today's still-forming session, exit 0, tagged source=yf. The
# chart endpoint answers 200 for a garbage `range`, so the failure arrives shaped
# exactly like a success: same header, same columns, plausible numbers. An analyst
# asking for 45 days to site support/resistance got one bar and no signal at all.

def _spy_fetch(monkeypatch):
    """Records whether the live fetch was reached. Validation must precede it."""
    seen = {"called": False}

    def fetch(symbol, period, interval):
        seen["called"] = True
        return _n_sessions(5)

    monkeypatch.setattr(data, "_yf_fetch", fetch)
    return seen


@pytest.mark.parametrize("period", ["banana", "45", "--days 30", "3M", "", "1 mo"])
def test_ohlcv_refuses_a_period_yahoo_will_not_honour(desk, monkeypatch, period):
    """The whole hazard is that these come back looking fine. They must not come
    back at all — and must be refused before any request leaves the desk."""
    seen = _spy_fetch(monkeypatch)

    with pytest.raises(ValueError):
        data.get_ohlcv("INFY", period=period)

    assert seen["called"] is False, f"{period!r} reached the network before validation"


def test_the_refusal_names_the_vocabulary_it_wants(desk, monkeypatch):
    """A bare day-count is the plausible typo (the desk head typed `45`). The
    error has to be actionable, so it names what would have worked."""
    _spy_fetch(monkeypatch)

    with pytest.raises(ValueError) as e:
        data.get_ohlcv("INFY", period="45")

    msg = str(e.value)
    assert "45" in msg, f"the rejected value is quoted back: {msg}"
    assert "3mo" in msg and "2y" in msg, f"the valid vocabulary is listed: {msg}"


@pytest.mark.parametrize("period", ["1d", "5d", "1mo", "3mo", "6mo",
                                    "1y", "2y", "5y", "10y", "ytd", "max"])
def test_every_valid_period_still_fetches(desk, monkeypatch, period):
    """Regression guard on the fix: the vocabulary the desk actually uses
    (`1y` in snapshot, `2y` in warm, `5d` in last_price, `6mo` in the
    technical-analyst's charter) must survive validation untouched."""
    seen = _spy_fetch(monkeypatch)

    df = data.get_ohlcv("INFY", period=period)

    assert seen["called"] is True and len(df) == 5


def test_a_bad_period_does_not_degrade_into_the_cache_ladder(desk, monkeypatch):
    """A typo is not an outage. The fallback ladder exists for a dead feed; if a
    bad period slid down it, the desk would answer a nonsense question with real
    cached bars and tag them `cache_stale` — a second silent success shape."""
    _write_cache("TESTCO")
    _kill_yf(monkeypatch)

    with pytest.raises(ValueError):
        data.get_ohlcv("TESTCO", period="banana")


def test_ohlcv_cli_exits_nonzero_on_a_bad_period():
    """The filed repro verbatim, through the real CLI. No network: the refusal
    lands before the fetch, so this test is offline by construction."""
    r = subprocess.run([sys.executable, "-m", "engine.data", "ohlcv", "INFY", "banana"],
                       cwd=data.ROOT, capture_output=True, text=True)

    assert r.returncode != 0, f"exit 0 on garbage period; stdout={r.stdout[:200]!r}"
    assert "source=yf" not in r.stdout, "a success-shaped frame was printed anyway"
    assert "banana" in r.stderr and "3mo" in r.stderr, r.stderr
