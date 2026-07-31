"""Shared paths, state I/O, and the IST market clock."""
import json
import pathlib
from datetime import datetime, time
from zoneinfo import ZoneInfo

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
IST = ZoneInfo("Asia/Kolkata")

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def now_ist() -> datetime:
    return datetime.now(IST)


def market_status(dt: datetime | None = None) -> dict:
    """NSE equity session status. Weekday + hours only; exchange holidays
    are not modelled — the trade-cycle skill sanity-checks those."""
    dt = dt or now_ist()
    is_weekday = dt.weekday() < 5
    in_hours = MARKET_OPEN <= dt.time() <= MARKET_CLOSE
    phase = "closed"
    if is_weekday:
        if in_hours:
            phase = "open"
        elif dt.time() < MARKET_OPEN:
            phase = "pre-open"
        else:
            phase = "post-close"
    return {
        "ist": dt.isoformat(timespec="seconds"),
        "phase": phase,
        "is_open": is_weekday and in_hours,
    }


def load_json(path: pathlib.Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def save_json(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str))
    tmp.replace(path)


def load_yaml(path: pathlib.Path, default=None):
    if not path.exists():
        return default
    return yaml.safe_load(path.read_text())


def journal(entry: dict) -> None:
    """Append-only trade journal. Every fill, veto, and regime change lands here."""
    entry = {"ts": now_ist().isoformat(timespec="seconds"), **entry}
    path = STATE / "journal.jsonl"
    with path.open("a") as f:
        f.write(json.dumps(entry, default=str) + "\n")
