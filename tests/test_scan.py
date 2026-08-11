"""Scanner triage: a degraded feed must narrow the scan, never zero it."""
import pandas as pd

from engine import common, data, scan


def _snap(**over):
    s = {"symbol": "TESTCO", "source": "yf", "bar_date": "2026-08-10",
         "last": 100.0, "change_pct": 0.5,
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


# --- bar-date staleness: the board must not mix sessions in silence ---

def _dated(sym, bar_date, **over):
    return _snap(symbol=sym, bar_date=bar_date, **over)


def test_stale_row_is_flagged_against_the_board(desk, monkeypatch):
    """The filed defect (OPEN-20260811-0824-scan). SUNPHARMA scored 6.0 at
    joint-2nd on a 08-07 close while every peer on the same board carried 08-10,
    and nothing in the row said so: source read 'yf', which the DEGRADED
    preflight treats as the freshness authority. A board that mixes sessions
    must say which rows are behind."""
    (desk / "watchlist.yaml").write_text(
        "symbols:\n  - SBIN\n  - LT\n  - SUNPHARMA\n")
    snaps = {"SBIN": _dated("SBIN", "2026-08-10"),
             "LT": _dated("LT", "2026-08-10"),
             "SUNPHARMA": _dated("SUNPHARMA", "2026-08-07")}
    monkeypatch.setattr(data, "snapshot", lambda sym: snaps[sym])

    out = scan.run(top=5)
    rows = {r["symbol"]: r for r in out["all"]}
    assert out["board_bar_date"] == "2026-08-10"
    assert rows["SUNPHARMA"]["stale"] is True
    assert rows["SUNPHARMA"]["sessions_behind"] == 1
    assert rows["SBIN"]["stale"] is False and rows["SBIN"]["sessions_behind"] == 0


def test_stale_row_is_kept_off_the_candidate_shortlist(desk, monkeypatch):
    """Non-negotiable #5: on stale quotes the desk stands down and says so. The
    stale name still scores top of the board here — flagging it is not enough if
    it stays on the shortlist the committee deep-dives and the risk gate sizes."""
    (desk / "watchlist.yaml").write_text("symbols:\n  - SBIN\n  - SUNPHARMA\n")
    snaps = {"SBIN": _dated("SBIN", "2026-08-10", rsi14=80.0, trend="down"),
             "SUNPHARMA": _dated("SUNPHARMA", "2026-08-07")}
    monkeypatch.setattr(data, "snapshot", lambda sym: snaps[sym])

    out = scan.run(top=5)
    assert [c["symbol"] for c in out["candidates"]] == ["SBIN"]
    assert [s["symbol"] for s in out["stale"]] == ["SUNPHARMA"]
    assert {r["symbol"] for r in out["all"]} == {"SBIN", "SUNPHARMA"}, \
        "the full table still carries the row — it is excluded, not hidden"


def test_aligned_board_flags_nothing(desk, monkeypatch):
    """No false positives: when every feed printed the same session, every row
    is current and the shortlist is untouched."""
    (desk / "watchlist.yaml").write_text("symbols:\n  - AAA\n  - BBB\n")
    monkeypatch.setattr(data, "snapshot",
                        lambda sym: _dated(sym, "2026-08-10"))

    out = scan.run(top=5)
    assert out["stale"] == []
    assert [c["symbol"] for c in out["candidates"]] == ["AAA", "BBB"]
    assert all(r["sessions_behind"] == 0 for r in out["all"])


def test_staleness_is_measured_in_printed_sessions_not_calendar_days(desk, monkeypatch):
    """08-07 to 08-10 is three calendar days but one session — a weekend is not
    a data gap. Counting days would flag every Monday board as three behind."""
    (desk / "watchlist.yaml").write_text(
        "symbols:\n  - AAA\n  - BBB\n  - CCC\n")
    snaps = {"AAA": _dated("AAA", "2026-08-10"),
             "BBB": _dated("BBB", "2026-08-07"),
             "CCC": _dated("CCC", "2026-08-06")}
    monkeypatch.setattr(data, "snapshot", lambda sym: snaps[sym])

    behind = {r["symbol"]: r["sessions_behind"] for r in scan.run(top=5)["all"]}
    assert behind == {"AAA": 0, "BBB": 1, "CCC": 2}


def test_scan_survives_a_snapshot_without_a_bar_date(desk, monkeypatch):
    """Degraded sources must not crash the board. An undated row cannot be
    proven current, so it is treated as stale rather than assumed fresh."""
    (desk / "watchlist.yaml").write_text("symbols:\n  - AAA\n  - BBB\n")
    snaps = {"AAA": _dated("AAA", "2026-08-10"), "BBB": _snap(symbol="BBB")}
    snaps["BBB"].pop("bar_date", None)
    monkeypatch.setattr(data, "snapshot", lambda sym: snaps[sym])

    out = scan.run(top=5)
    rows = {r["symbol"]: r for r in out["all"]}
    assert rows["BBB"]["stale"] is True
    assert rows["BBB"]["bar_date"] is None
    assert [c["symbol"] for c in out["candidates"]] == ["AAA"]


def test_an_entirely_undated_board_is_stale_not_silently_current(desk, monkeypatch):
    """With no dated row there is no peer to compare against, so the relative
    measure has nothing to say. It must not read that as 'everything current' —
    an undated row is unproven whether or not anything else on the board is
    dated. snapshot() always dates its bar, so this guards a future feed."""
    (desk / "watchlist.yaml").write_text("symbols:\n  - AAA\n  - BBB\n")

    def undated(sym):
        s = _snap(symbol=sym)
        s.pop("bar_date", None)
        return s

    monkeypatch.setattr(data, "snapshot", undated)
    out = scan.run(top=5)
    assert out["board_bar_date"] is None
    assert out["candidates"] == []
    assert all(r["stale"] for r in out["all"])
