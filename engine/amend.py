"""Constitutional amendment engine for risk_limits.yaml.

The desk tunes its own limits INSIDE the human-owned envelope
(state/risk_bounds.yaml). Asymmetry is the core invention:
  - tighten:  instant, any agent may request, no cooling. Reducing risk never
              waits for permission.
  - loosen:   requires evidence (>=N closed trades, positive expectancy_R),
              step-capped, rate-limited, then sits pending for a cooling period
              during which a human may `reject`. Applied automatically after.
  - guardian: drawdown-triggered auto-tightening + applies ripe pending
              amendments. Run once per trade cycle.

Usage:
  python3 -m engine.amend propose --param risk_per_trade_pct --to 1.25 --evidence "..."
  python3 -m engine.amend tighten --param risk_per_trade_pct --to 0.5 --note "..."
  python3 -m engine.amend guardian
  python3 -m engine.amend reject --note "human veto"
  python3 -m engine.amend show
"""
import json
import re
import sys
from datetime import datetime, timedelta

from engine import common, risk, stats

# +1: higher value = more risk (loosening raises it). -1: inverted (min_risk_reward).
RISK_DIRECTION = {"risk_per_trade_pct": 1, "max_daily_loss_pct": 1,
                  "max_open_positions": 1, "max_position_notional_pct": 1,
                  "max_gross_exposure_pct": 1, "min_risk_reward": -1}

PENDING = common.STATE / "amendments" / "pending.json"
HISTORY = common.STATE / "amendments" / "history.jsonl"


def bounds() -> dict:
    b = common.load_yaml(common.STATE / "risk_bounds.yaml")
    if b is None:
        raise RuntimeError("state/risk_bounds.yaml missing — envelope undefined")
    return b


def _history(entry: dict) -> None:
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY.open("a") as f:
        f.write(json.dumps({"ts": common.now_ist().isoformat(timespec="seconds"),
                            **entry}, default=str) + "\n")


def _write_limit(param: str, value: float) -> None:
    """Targeted edit that preserves the yaml's comments."""
    path = common.STATE / "risk_limits.yaml"
    text = path.read_text()
    new, n = re.subn(rf"(?m)^({param}:\s*)[0-9.]+", rf"\g<1>{value}", text)
    if n != 1:
        raise RuntimeError(f"could not rewrite {param} (matched {n} lines)")
    path.write_text(new)


def _is_loosening(param: str, current: float, to: float) -> bool:
    return (to - current) * RISK_DIRECTION[param] > 0


def _validate(param: str, to: float) -> tuple[float, dict]:
    if param not in RISK_DIRECTION:
        raise SystemExit(f"'{param}' is not amendable")
    b = bounds()["bounds"][param]
    if not b["min"] <= to <= b["max"]:
        raise SystemExit(f"{to} outside envelope [{b['min']}, {b['max']}] — a human "
                         f"must widen state/risk_bounds.yaml for that")
    current = risk.limits()[param]
    return current, b


def tighten(param: str, to: float, note: str) -> dict:
    current, _ = _validate(param, to)
    if _is_loosening(param, current, to):
        raise SystemExit(f"{param}: {current} -> {to} is a LOOSENING — use propose")
    _write_limit(param, to)
    entry = {"action": "tightened", "param": param, "from": current, "to": to, "note": note}
    _history(entry)
    common.journal({"type": "limit_tightened", **entry})
    return entry


def propose(param: str, to: float, evidence: str) -> dict:
    current, _ = _validate(param, to)
    if not _is_loosening(param, current, to):
        raise SystemExit("that is a tightening — use tighten, it applies instantly")
    rules = bounds()["amendment_rules"]
    step = abs(to - current) / abs(current)
    if step > rules["max_step_relative"] + 1e-9:
        raise SystemExit(f"step {step:.0%} exceeds max {rules['max_step_relative']:.0%}")
    sc = stats.scorecard()
    if (sc["closed_trades"] or 0) < rules["min_closed_trades_for_loosening"]:
        raise SystemExit(f"only {sc['closed_trades']} closed trades; loosening needs "
                         f">={rules['min_closed_trades_for_loosening']}")
    if sc["expectancy_R"] is None or sc["expectancy_R"] < rules["min_expectancy_R_for_loosening"]:
        raise SystemExit(f"expectancy_R {sc['expectancy_R']} below required "
                         f"{rules['min_expectancy_R_for_loosening']} — no loosening without edge")
    if HISTORY.exists():
        cutoff = common.now_ist() - timedelta(days=rules["min_days_between_loosenings"])
        for line in HISTORY.read_text().splitlines():
            e = json.loads(line)
            if e.get("action") == "loosened" and datetime.fromisoformat(e["ts"]) > cutoff:
                raise SystemExit(f"last loosening {e['ts']} is within "
                                 f"{rules['min_days_between_loosenings']} days")
    if common.load_json(PENDING):
        raise SystemExit("an amendment is already pending — one at a time")
    pending = {"param": param, "from": current, "to": to, "evidence": evidence,
               "proposed": common.now_ist().isoformat(timespec="seconds"),
               "ripe_after": (common.now_ist()
                              + timedelta(hours=rules["cooling_hours"])).isoformat(timespec="seconds"),
               "scorecard_at_proposal": {k: sc[k] for k in
                                         ("closed_trades", "expectancy_R", "win_rate")}}
    common.save_json(PENDING, pending)
    _history({"action": "proposed", **pending})
    common.journal({"type": "amendment_proposed", **pending})
    return pending


def reject(note: str) -> dict:
    p = common.load_json(PENDING)
    if not p:
        raise SystemExit("nothing pending")
    PENDING.unlink()
    entry = {"action": "rejected", "note": note, **p}
    _history(entry)
    common.journal({"type": "amendment_rejected", "note": note, "param": p["param"]})
    return entry


def guardian() -> dict:
    """Drawdown watchdog + pending-amendment applier. Idempotent; run every cycle."""
    report = {"drawdown": None, "actions": []}
    eq_path = common.STATE / "equity.jsonl"
    if eq_path.exists():
        rows = [json.loads(l) for l in eq_path.read_text().splitlines() if l.strip()]
        if rows:
            peak = max(r["equity"] for r in rows)
            current = rows[-1]["equity"]
            dd = (peak - current) / peak * 100
            report["drawdown"] = {"peak": peak, "current": current, "dd_pct": round(dd, 2)}
            at = bounds()["auto_tighten"]
            lm = risk.limits()
            floor = bounds()["bounds"]["risk_per_trade_pct"]["min"]
            if dd >= 10 and "drawdown_pct_10" in at:
                if lm["risk_per_trade_pct"] > floor:
                    tighten("risk_per_trade_pct", floor,
                            f"GUARDIAN: drawdown {dd:.1f}% >= 10% — risk to envelope floor")
                    report["actions"].append(f"risk_per_trade_pct -> {floor}")
                if at["drawdown_pct_10"].get("force_regime"):
                    import subprocess
                    subprocess.run([sys.executable, "-m", "engine.regime", "set", "risk_off",
                                    "--note", f"GUARDIAN: drawdown {dd:.1f}%"],
                                   cwd=common.ROOT, capture_output=True)
                    report["actions"].append("regime -> risk_off")
            elif dd >= 5 and "drawdown_pct_5" in at:
                target = max(floor, round(lm["risk_per_trade_pct"]
                                          * at["drawdown_pct_5"]["risk_per_trade_pct_factor"], 2))
                if lm["risk_per_trade_pct"] > target:
                    tighten("risk_per_trade_pct", target,
                            f"GUARDIAN: drawdown {dd:.1f}% >= 5% — halving per-trade risk")
                    report["actions"].append(f"risk_per_trade_pct -> {target}")
    p = common.load_json(PENDING)
    if p and common.now_ist() >= datetime.fromisoformat(p["ripe_after"]):
        _write_limit(p["param"], p["to"])
        PENDING.unlink()
        entry = {"action": "loosened", **p}
        _history(entry)
        common.journal({"type": "amendment_applied", **entry})
        report["actions"].append(f"applied pending: {p['param']} {p['from']} -> {p['to']}")
    elif p:
        report["pending"] = {"param": p["param"], "to": p["to"], "ripe_after": p["ripe_after"]}
    return report


if __name__ == "__main__":
    args = sys.argv[1:]
    get = lambda flag, default=None: (args[args.index(flag) + 1]
                                      if flag in args else default)
    cmd = args[0] if args else "show"
    if cmd == "propose":
        out = propose(get("--param"), float(get("--to")), get("--evidence", ""))
    elif cmd == "tighten":
        out = tighten(get("--param"), float(get("--to")), get("--note", ""))
    elif cmd == "guardian":
        out = guardian()
    elif cmd == "reject":
        out = reject(get("--note", "human veto"))
    else:
        out = {"pending": common.load_json(PENDING),
               "limits": risk.limits(), "bounds": bounds()["bounds"]}
    print(json.dumps(out, indent=2))
