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
    if s["vol_ratio_20d"] >= 1.3:
        score += 1.5        # participation
    if s["pos_52w_pct"] >= 80:
        score += 1          # strength near highs
    return round(score, 2)


def run(top: int = 5) -> dict:
    wl = common.load_yaml(common.STATE / "watchlist.yaml", {"symbols": []})
    rows, errors = [], []
    for item in wl["symbols"]:
        sym = item["symbol"] if isinstance(item, dict) else item
        try:
            s = data.snapshot(sym)
            s["score"] = setup_score(s)
            rows.append(s)
        except Exception as e:
            errors.append(f"{sym}: {e}")
    rows.sort(key=lambda r: r["score"], reverse=True)
    out = {"ts": common.now_ist().isoformat(timespec="seconds"),
           "candidates": rows[:top], "all": rows, "errors": errors}
    common.save_json(common.STATE / "scans" / "latest.json", out)
    return out


if __name__ == "__main__":
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 5
    out = run(top)
    print(json.dumps({"ts": out["ts"], "errors": out["errors"],
                      "candidates": out["candidates"]}, indent=2))
    print(f"\nfull table: state/scans/latest.json ({len(out['all'])} symbols)",
          file=sys.stderr)
