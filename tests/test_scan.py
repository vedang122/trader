"""Scanner triage: a degraded feed must narrow the scan, never zero it."""
import pandas as pd

from engine import common, data, scan


def _snap(**over):
    s = {"symbol": "TESTCO", "source": "yf", "last": 100.0, "change_pct": 0.5,
         "rsi14": 55.0, "sma20": 98.0, "sma50": 95.0, "sma200": 90.0,
         "macd_hist": 0.4, "macd_cross": "bullish", "atr14": 2.0,
         "vol_ratio_20d": 1.5, "pos_52w_pct": 85.0, "high_52w": 110.0,
         "low_52w": 60.0, "trend": "up"}
    s.update(over)
    return s


def test_score_survives_null_vol_ratio():
    """cache_stale snapshots carry vol_ratio_20d=None by contract — not an error."""
    # trend 2 + above sma200 1 + macd 1 + rsi in band 2 + near highs 1, volume 0
    assert scan.setup_score(_snap(source="cache_stale", vol_ratio_20d=None)) == 7.0


def test_null_vol_ratio_scores_as_no_confirmation():
    """Unverifiable volume wins no participation points, and costs none either."""
    unknown = scan.setup_score(_snap(vol_ratio_20d=None))
    quiet = scan.setup_score(_snap(vol_ratio_20d=0.8))
    loud = scan.setup_score(_snap(vol_ratio_20d=1.5))
    assert unknown == quiet == loud - 1.5


def test_degraded_scan_returns_candidates_not_errors(desk, monkeypatch):
    """The cached-bar fallback exists to keep the desk seeing the market."""
    (desk / "watchlist.yaml").write_text("symbols:\n  - AAA\n  - BBB\n")
    monkeypatch.setattr(data, "snapshot",
                        lambda sym: _snap(symbol=sym, source="cache_stale",
                                          vol_ratio_20d=None))
    out = scan.run(top=5)
    assert out["errors"] == []
    assert [c["symbol"] for c in out["candidates"]] == ["AAA", "BBB"]


def test_degraded_candidates_flag_unconfirmed_volume(desk, monkeypatch):
    """Downstream volume-gated setups need to see that volume is unverifiable."""
    (desk / "watchlist.yaml").write_text("symbols:\n  - AAA\n  - BBB\n")
    snaps = {"AAA": _snap(symbol="AAA", source="cache_stale", vol_ratio_20d=None),
             "BBB": _snap(symbol="BBB")}
    monkeypatch.setattr(data, "snapshot", lambda sym: snaps[sym])
    out = scan.run(top=5)
    flags = {c["symbol"]: c["volume_unconfirmed"] for c in out["all"]}
    assert flags == {"AAA": True, "BBB": False}


def test_scan_still_reports_real_errors(desk, monkeypatch):
    """Guarding None must not swallow genuine per-symbol failures."""
    (desk / "watchlist.yaml").write_text("symbols:\n  - AAA\n  - BBB\n")

    def flaky(sym):
        if sym == "AAA":
            raise RuntimeError("yfinance failed for AAA: empty response")
        return _snap(symbol=sym)

    monkeypatch.setattr(data, "snapshot", flaky)
    out = scan.run(top=5)
    assert out["errors"] == ["AAA: yfinance failed for AAA: empty response"]
    assert [c["symbol"] for c in out["candidates"]] == ["BBB"]


def test_partial_session_scan_flags_volume_unconfirmed(desk, monkeypatch):
    """The filed defect end to end (OPEN-20260806-0922). At 09:16 IST the board
    read vol_ratio_20d 0.01-0.13 with volume_unconfirmed=False on every symbol —
    'participation is confirmed to be 1% of normal' — when the honest reading was
    'not measurable yet'. Suppressing the ratio must flip the flag and cost the
    row its participation points, or the ranking still moves with the clock."""
    (desk / "watchlist.yaml").write_text("symbols:\n  - TATASTEEL\n")
    idx = pd.bdate_range(end=pd.Timestamp("2026-08-06"), periods=21)
    vols = [1000] * 20 + [40]                    # one minute of a session
    frame = pd.DataFrame({"Open": 100.0, "High": 101.0, "Low": 99.0,
                          "Close": 100.0, "Volume": vols}, index=idx)
    monkeypatch.setattr(data, "_yf_fetch", lambda s, p, i: frame)
    monkeypatch.setattr(common, "now_ist",
                        lambda: pd.Timestamp("2026-08-06 09:16:00",
                                             tz=common.IST).to_pydatetime())

    row = scan.run(top=5)["all"][0]
    assert row["vol_ratio_20d"] is None
    assert row["volume_unconfirmed"] is True, "0.04 of a day is not a confirmed reading"
    assert row["score"] == scan.setup_score({**row, "vol_ratio_20d": 2.0}) - 1.5
