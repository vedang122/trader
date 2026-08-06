"""Deterministic ops health checks — the desk's own plumbing inspector.

`python3 -m engine.ops preflight` runs at Phase 0 of every trade cycle and
answers three questions no agent should be trusted to answer from vibes:
1. STATE: is this clone current with origin/main, and are there unmerged
   claude/* run branches (= the auto-merge workflow failed)?
2. CONTINUITY: when did the desk last journal anything?
3. FEED: is the price feed live, degraded (cache/Groww fallback), or dead?
   Degraded is not one state: feed.live_ltp says whether the Groww fallback
   actually answers, because "exits allowed on live LTP" is a lie without it.
   feed.probes says what data.snapshot() really served for the names the desk
   trades — feed health is never inferred from an index's cache age, because a
   fresh NIFTY cache next to a stale watchlist reads as usable data and isn't.

Verdict: GO | DEGRADED | STAND_DOWN. STAND_DOWN and stray-branch findings are
auto-journaled as ops_alert so the weekly debrief audits infrastructure, not
just trades.
"""
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
STRAY_BRANCH_AGE_S = 1800  # unmerged claude/* older than this = merge workflow broken
FEED_PROBES = 2            # watchlist names snapshot-probed when yfinance is down


def _git(*args, timeout=45) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def check_state() -> dict:
    out = {"fetch_ok": False, "behind_main": None, "ahead_main": None, "stray_branches": []}
    code, _ = _git("fetch", "origin", "--prune")
    out["fetch_ok"] = code == 0
    if out["fetch_ok"]:
        code, counts = _git("rev-list", "--left-right", "--count", "HEAD...origin/main")
        if code == 0 and counts:
            ahead, behind = (counts.split() + ["0", "0"])[:2]
            out["ahead_main"], out["behind_main"] = int(ahead), int(behind)
        code, refs = _git("for-each-ref", "refs/remotes/origin/claude",
                          "--format=%(refname:short) %(committerdate:unix)")
        if code == 0 and refs:
            now = time.time()
            for line in refs.splitlines():
                name, _, ts = line.rpartition(" ")
                if ts.isdigit() and now - int(ts) > STRAY_BRANCH_AGE_S:
                    out["stray_branches"].append(name)
    return out


def check_continuity() -> dict:
    p = ROOT / "state" / "journal.jsonl"
    try:
        last = json.loads(p.read_text().strip().splitlines()[-1])
        return {"last_journal_ts": last.get("ts"), "last_journal_type": last.get("type")}
    except Exception:
        return {"last_journal_ts": None, "last_journal_type": None}


def _probe_symbols() -> list[str]:
    """The names preflight asks about: what the desk trades, not an index."""
    from engine import common
    wl = common.load_yaml(common.STATE / "watchlist.yaml", {}) or {}
    raw = wl.get("symbols", []) if isinstance(wl, dict) else wl
    syms = [s["symbol"] if isinstance(s, dict) else s for s in raw]
    return syms[:FEED_PROBES] or ["RELIANCE"]


def _probe(sym: str) -> dict:
    """What data.snapshot() actually serves for sym right now — source or error."""
    from engine import data
    try:
        return {"symbol": sym, "source": data.snapshot(sym)["source"], "error": None}
    except Exception as e:
        return {"symbol": sym, "source": None, "error": f"{type(e).__name__}: {e}"[:120]}


def check_feed() -> dict:
    from engine import data
    canary = {"status": "dead", "detail": None, "live_ltp": "unprobed",
              "live_ltp_why": None, "probes": []}
    try:
        data._yf_fetch("NIFTY", "5d", "1d")
        canary.update(status="ok", detail="yfinance live")
        return canary
    except Exception as e:
        canary["detail"] = f"yfinance: {str(e)[:120]}"
    gw = data.groww_status("RELIANCE")
    canary.update(live_ltp=gw["live_ltp"], live_ltp_why=gw["why"])
    if gw["live_ltp"] == "ok":
        canary.update(status="degraded", detail=canary["detail"] + " | groww LTP live")
        return canary
    # No live quote source. Whether daily-bar work is still possible is a claim
    # about the watchlist, so ask snapshot rather than an index's cache mtime.
    canary["probes"] = [_probe(s) for s in _probe_symbols()]
    served = ", ".join(f"{p['symbol']}={p['source']}" for p in canary["probes"] if p["source"])
    if served:
        canary.update(status="degraded", detail=canary["detail"]
                      + f" | snapshot serves {served} — daily bars only, NO live LTP"
                      + f" ({gw['why']}); cannot defend open positions")
    else:
        canary["detail"] += " | snapshot serves nothing: " + "; ".join(
            f"{p['symbol']}: {p['error']}" for p in canary["probes"])
    return canary


def preflight() -> dict:
    state, cont, feed = check_state(), check_continuity(), check_feed()
    reasons = []
    if state["behind_main"]:
        reasons.append(f"clone is {state['behind_main']} commit(s) behind origin/main — pull before trading")
    if state["stray_branches"]:
        reasons.append(f"unmerged run branches (merge workflow broken?): {state['stray_branches']}")
    if not state["fetch_ok"]:
        reasons.append("git fetch failed — state sync unverifiable")
    if feed["status"] == "dead":
        reasons.append("price feed dead (yfinance + groww + cache all unusable)")
    verdict = "STAND_DOWN" if reasons else ("DEGRADED" if feed["status"] == "degraded" else "GO")
    result = {"verdict": verdict, "reasons": reasons, "state": state, "continuity": cont, "feed": feed}
    if verdict == "STAND_DOWN" or state["stray_branches"]:
        try:
            from engine.common import journal
            journal({"type": "ops_alert", "verdict": verdict, "reasons": reasons,
                     "feed": feed["status"], "state": {k: state[k] for k in
                     ("behind_main", "stray_branches", "fetch_ok")}})
        except Exception:
            pass
    return result


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "preflight"
    if cmd == "preflight":
        print(json.dumps(preflight(), indent=2))
    else:
        print(json.dumps({"error": f"unknown command {cmd}"}))
