"""Preflight must PROVE the live-LTP fallback, never assume it.

Issue 20260805-1339: preflight returned DEGRADED with feed detail "cache fresh
enough for daily bars" while the Groww SDK was not even installed. The DEGRADED
contract promises "position defense and exits allowed on live LTP" — so a
DEGRADED verdict with a dead fallback and one with a live one must not look
identical to the desk head.
"""
import pathlib
import time

import pandas as pd

from engine import data, ops

REPO = pathlib.Path(__file__).resolve().parent.parent


def _write_cache(*syms, age_bars=0):
    """Cache 60 daily bars per symbol; age_bars pushes the last bar into the past.

    Defaults to the index AND a tradable name, because feed health is a claim
    about what the desk can actually analyse, not about one index's cache file.
    """
    end = pd.Timestamp.now(tz="Asia/Kolkata").normalize().tz_localize(None)
    if age_bars:
        end -= pd.tseries.offsets.BDay(age_bars)
    idx = pd.bdate_range(end=end, periods=60)
    df = pd.DataFrame({"Open": 100.0, "High": 101.0, "Low": 99.0,
                       "Close": 100.0, "Volume": 1000}, index=idx)
    data.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for sym in (syms or ("NIFTY", "RELIANCE")):
        df.to_csv(data._cache_path(sym))


def _kill_yf(monkeypatch):
    def dead(symbol, period, interval):
        raise RuntimeError("429")
    monkeypatch.setattr(data, "_yf_fetch", dead)


def test_groww_status_names_a_missing_sdk(desk, monkeypatch):
    monkeypatch.setattr(data, "_groww_sdk", lambda: None)
    assert data.groww_status() == {"live_ltp": "dead", "why": "sdk_missing", "ltp": None}


def test_groww_status_names_absent_creds(desk, monkeypatch):
    monkeypatch.setattr(data, "_groww_sdk", lambda: object())
    monkeypatch.delenv("GROWW_API_KEY", raising=False)
    monkeypatch.delenv("GROWW_API_SECRET", raising=False)
    assert data.groww_status()["why"] == "no_creds"


def test_groww_status_ok_carries_the_price(desk, monkeypatch):
    monkeypatch.setattr(data, "_groww_sdk", lambda: object())
    monkeypatch.setenv("GROWW_API_KEY", "k")
    monkeypatch.setenv("GROWW_API_SECRET", "s")
    monkeypatch.setattr(data, "groww_ltp", lambda s: 1285.5)
    assert data.groww_status() == {"live_ltp": "ok", "why": None, "ltp": 1285.5}


def test_stale_cache_degraded_admits_it_has_no_live_ltp(desk, monkeypatch):
    _write_cache()
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_status",
                        lambda *a: {"live_ltp": "dead", "why": "sdk_missing", "ltp": None})
    feed = ops.check_feed()
    assert feed["status"] == "degraded"
    assert feed["live_ltp"] == "dead"
    assert feed["live_ltp_why"] == "sdk_missing"
    assert "no live ltp" in feed["detail"].lower()


def test_groww_backed_degraded_reports_live_ltp_ok(desk, monkeypatch):
    _write_cache()
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_status",
                        lambda *a: {"live_ltp": "ok", "why": None, "ltp": 1285.5})
    feed = ops.check_feed()
    assert feed["status"] == "degraded"
    assert feed["live_ltp"] == "ok"


def test_preflight_feed_always_carries_live_ltp_key(desk, monkeypatch):
    _write_cache()
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_status",
                        lambda *a: {"live_ltp": "dead", "why": "no_creds", "ltp": None})
    monkeypatch.setattr(ops, "check_state", lambda: {
        "fetch_ok": True, "behind_main": 0, "ahead_main": 0, "stray_branches": []})
    out = ops.preflight()
    assert out["verdict"] == "DEGRADED"
    assert out["feed"]["live_ltp"] == "dead"


def test_feed_health_is_probed_through_snapshot_not_an_index_cache_heuristic(desk, monkeypatch):
    """Issue 20260805-1226: preflight reported feed "cache fresh enough for daily
    bars" — a claim read off NIFTY's cache file — while `data.snapshot()` on the
    names the desk actually trades returned cache_stale/raised. Two engine outputs
    contradicting each other about whether usable data exists is worse than either
    answer alone: the desk head trusts the optimistic one. Feed health must be
    derived from what snapshot really serves for the watchlist.
    """
    (desk / "watchlist.yaml").write_text("symbols:\n  - {symbol: RELIANCE, sector: energy}\n")
    _write_cache("NIFTY")                      # the index cache is fresh...
    _write_cache("RELIANCE", age_bars=40)      # ...the tradable name is long stale
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_status",
                        lambda *a: {"live_ltp": "dead", "why": "sdk_missing", "ltp": None})

    feed = ops.check_feed()
    probes = {p["symbol"]: p for p in feed["probes"]}
    assert set(probes) == {"RELIANCE"}, "preflight must probe what the desk trades"
    assert probes["RELIANCE"]["source"] is None, "snapshot cannot serve a 40-bar-stale cache"
    assert feed["status"] == "dead", "no analysable name and no live LTP is a blackout"
    assert "RELIANCE" in feed["detail"]
    assert "fresh enough" not in feed["detail"]


def test_probed_feed_reports_the_source_snapshot_actually_served(desk, monkeypatch):
    """The other half: when the cache DOES serve the watchlist, say so by name and
    source rather than asserting a generic freshness the analysts may not see."""
    (desk / "watchlist.yaml").write_text("symbols:\n  - {symbol: RELIANCE, sector: energy}\n")
    _write_cache()
    _kill_yf(monkeypatch)
    monkeypatch.setattr(data, "groww_status",
                        lambda *a: {"live_ltp": "dead", "why": "no_creds", "ltp": None})

    feed = ops.check_feed()
    assert feed["status"] == "degraded"
    assert feed["probes"] == [{"symbol": "RELIANCE", "source": "cache_stale", "error": None}]
    assert "RELIANCE=cache_stale" in feed["detail"]


def test_requirements_core_installs_without_growwapi():
    """growwapi -> clint -> args are sdist-only and fail to build in the cloud
    container; one unbuildable line fails the WHOLE file, so `pip install -r
    requirements.txt` left pandas/yfinance/pytest uninstalled too."""
    text = (REPO / "requirements.txt").read_text()
    reqs = [ln.split("#")[0].strip() for ln in text.splitlines()]
    reqs = [r for r in reqs if r]
    assert "growwapi" not in reqs, "bare growwapi takes the whole core install down with it"
    assert {"pandas", "yfinance", "pytest"} <= set(reqs)
    assert {"pyotp", "pynacl", "protobuf", "nkeys", "nats-py"} <= set(reqs), \
        "growwapi's runtime deps must still be installed for the --no-deps SDK to import"
    assert "--no-deps growwapi" in text, "the file must document how to get the SDK in"


# --- stray run branches: merge hygiene vs a real state divergence -------------
# Issue 20260807-0825: ANY unmerged claude/* branch older than 30min forced a
# STAND_DOWN, and Phase 0 reads STAND_DOWN as "no new entries, period". A branch
# parked for human review (or stranded by a cancelled merge job) carries only
# audit lines and code — nothing the desk reads to price or size a trade — yet
# no action available inside the desk can clear it. The desk was therefore
# foreclosed from trading indefinitely by a repo-hygiene condition.

def _fake_git(monkeypatch, diffs, *, diff_rc=0):
    """Drive check_state off a scripted git: one stray branch per diffs key."""
    old = int(time.time()) - 86400

    def fake(*args, timeout=45):
        if args[0] == "fetch":
            return 0, ""
        if args[0] == "rev-list":
            return 0, "0 0"
        if args[0] == "for-each-ref":
            return 0, "\n".join(f"{b} {old}" for b in diffs)
        if args[0] == "diff":
            branch = args[-1].split("...")[-1]
            return diff_rc, "\n".join(diffs.get(branch, []))
        return 1, f"unexpected git {args}"

    monkeypatch.setattr(ops, "_git", fake)


def _stub_health(monkeypatch):
    monkeypatch.setattr(ops, "check_feed", lambda: {
        "status": "ok", "detail": "yfinance live", "live_ltp": "unprobed",
        "live_ltp_why": None, "probes": []})
    monkeypatch.setattr(ops, "check_continuity", lambda: {
        "last_journal_ts": "2026-08-07T08:00:00+05:30", "last_journal_type": "cycle"})


def test_parked_engineer_branch_is_a_notice_not_a_stand_down(desk, monkeypatch):
    """Audit trail + code only: report it every cycle, but do not bar entries."""
    branch = "origin/claude/engineer-stop-lowering-enforcement"
    _fake_git(monkeypatch, {branch: ["state/issues/OPEN-20260805-1105-portfolio.md",
                                     "state/journal.jsonl",
                                     "tests/test_portfolio.py"]})
    _stub_health(monkeypatch)

    out = ops.preflight()
    assert out["verdict"] == "GO", f"parked branch must not foreclose trading: {out['reasons']}"
    assert out["reasons"] == []
    assert branch in out["state"]["stray_branches"], "the branch is still reported"
    assert out["state"]["blocking_branches"] == []
    assert any(branch in n for n in out["notices"]), "hygiene finding must stay visible"


def test_branch_carrying_desk_state_still_stands_the_desk_down(desk, monkeypatch):
    """The other half: unmerged portfolio/limits mean this clone's book is wrong."""
    branch = "origin/claude/cycle-20260807"
    _fake_git(monkeypatch, {branch: ["state/journal.jsonl", "state/portfolio.json"]})
    _stub_health(monkeypatch)

    out = ops.preflight()
    assert out["verdict"] == "STAND_DOWN"
    assert out["state"]["blocking_branches"] == [branch]
    assert any(branch in r for r in out["reasons"])
    assert any("state/portfolio.json" in r for r in out["reasons"]), \
        "say WHICH unmerged state bars the desk, not just the branch name"


def test_unreadable_branch_diff_is_treated_as_blocking(desk, monkeypatch):
    """No data >= bad data: if git cannot say what the branch carries, assume state."""
    branch = "origin/claude/mystery"
    _fake_git(monkeypatch, {branch: []}, diff_rc=1)
    _stub_health(monkeypatch)

    out = ops.preflight()
    assert out["verdict"] == "STAND_DOWN"
    assert out["state"]["blocking_branches"] == [branch]
