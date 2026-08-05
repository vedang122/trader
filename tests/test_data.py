"""Data fallback ladder: yf -> cache+groww LTP -> stale cache -> honest failure."""
import pandas as pd
import pytest

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
