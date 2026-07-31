"""Regime flag maintained by the macro-sentinel agent. Auditable via the journal.
Usage: python3 -m engine.regime set risk_on|neutral|risk_off --note "why"
       python3 -m engine.regime show
"""
import json
import sys

from engine import common

MULTIPLIERS = {"risk_on": 1.0, "neutral": 0.7, "risk_off": 0.4}

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "set":
        name = sys.argv[2]
        if name not in MULTIPLIERS:
            sys.exit(f"regime must be one of {list(MULTIPLIERS)}")
        note = sys.argv[sys.argv.index("--note") + 1] if "--note" in sys.argv else ""
        rg = {"regime": name, "gross_multiplier": MULTIPLIERS[name],
              "as_of": common.now_ist().isoformat(timespec="seconds"), "note": note}
        common.save_json(common.STATE / "regime.json", rg)
        common.journal({"type": "regime_change", **rg})
        print(json.dumps(rg, indent=2))
    else:
        print(json.dumps(common.load_json(common.STATE / "regime.json",
                                          {"regime": "neutral", "gross_multiplier": 0.7}), indent=2))
