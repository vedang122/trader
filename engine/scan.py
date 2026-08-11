"""Watchlist scanner: computes a technical snapshot per symbol, ranks setups,
writes state/scans/latest.json. The committee only deep-dives what this surfaces.
Usage: python3 -m engine.scan [--top N]
"""
import json
import sys

from engine import common, data


def setup_score(s: dict) -> float:
    """Cheap deterministic triage — NOT a signal. Rewards trend alignment,
    momentum near (not past) extremes, and volume confirmation."""
    score = 0.0
    if s["trend"] == "up":
        score += 2
    if s["sma200"] and s["last"] > s["sma200"]:
        score += 1
    if s["macd_cross"] == "bullish":
        score += 1
    if 45 <= s["rsi14"] <= 65:
        score += 2          # room to run
    elif s["rsi14"] > 75 or s["rsi14"] < 25:
        score -= 1          # stretched
    if s["vol_ratio_20d"] is not None and s["vol_ratio_20d"] >= 1.3:
        score += 1.5        # participation (None = unverifiable on a degraded
                            # feed: no points, but no penalty either)
    if s["pos_52w_pct"] >= 80:
        score += 1          # strength near highs
    return round(score, 2)


def _mark_staleness(rows: list) -> str | None:
    """Date every row against the newest session the board actually printed.

    Issue 20260811-0824: SUNPHARMA ranked joint-2nd on a 08-07 close while every
    peer carried 08-10, and no field said so — `source` read "yf", which the
    DEGRADED preflight treats as the freshness authority. Each derived number on
    that row (rsi14, macd_hist, atr14, change_pct) was silently one bar behind
    its peers'.

    Lag is counted in sessions the board printed, not calendar days: 08-07 to
    08-10 is one missed session, not three, and no exchange-holiday calendar is
    needed to say so. The measure is relative, so it catches a symbol falling
    behind its peers — not a whole board frozen on the same old session, which
    is what `source` and the cache ladder already report. A row with no date
    cannot be proven current and is treated as behind rather than assumed fresh.
    """
    dates = sorted({r["bar_date"] for r in rows if r.get("bar_date")}, reverse=True)
    rank = {d: i for i, d in enumerate(dates)}
    for r in rows:
        r.setdefault("bar_date", None)
        if r["bar_date"] is None:      # unproven, not presumed current
            r["sessions_behind"], r["stale"] = len(dates), True
        else:
            r["sessions_behind"] = rank[r["bar_date"]]
            r["stale"] = r["sessions_behind"] > 0
    return dates[0] if dates else None


def run(top: int = 5) -> dict:
    wl = common.load_yaml(common.STATE / "watchlist.yaml", {"symbols": []})
    rows, errors = [], []
    for item in wl["symbols"]:
        sym = item["symbol"] if isinstance(item, dict) else item
        try:
            s = data.snapshot(sym)
            s["score"] = setup_score(s)
            # degraded feeds serve cached bars without volume — say so on the
            # candidate so volume-gated setups can be excluded downstream.
            s["volume_unconfirmed"] = s["vol_ratio_20d"] is None
            rows.append(s)
        except Exception as e:
            errors.append(f"{sym}: {e}")
    board_date = _mark_staleness(rows)
    rows.sort(key=lambda r: r["score"], reverse=True)
    # Non-negotiable #5 — stand down on a stale quote, and say so. A flag alone
    # would not do it: the stale row keeps its score, so it would still reach the
    # committee and the risk gate on the shortlist. It stays in `all` (excluded,
    # not hidden) and is named in `stale` so the omission is visible.
    fresh = [r for r in rows if not r["stale"]]
    stale = [{"symbol": r["symbol"], "bar_date": r["bar_date"],
              "sessions_behind": r["sessions_behind"], "score": r["score"]}
             for r in rows if r["stale"]]
    out = {"ts": common.now_ist().isoformat(timespec="seconds"),
           "board_bar_date": board_date, "candidates": fresh[:top],
           "stale": stale, "all": rows, "errors": errors}
    common.save_json(common.STATE / "scans" / "latest.json", out)
    return out


if __name__ == "__main__":
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 5
    out = run(top)
    print(json.dumps({"ts": out["ts"], "board_bar_date": out["board_bar_date"],
                      "errors": out["errors"], "stale": out["stale"],
                      "candidates": out["candidates"]}, indent=2))
    if out["stale"]:
        print(f"held back as stale: {', '.join(r['symbol'] for r in out['stale'])}",
              file=sys.stderr)
    print(f"\nfull table: state/scans/latest.json ({len(out['all'])} symbols)",
          file=sys.stderr)
