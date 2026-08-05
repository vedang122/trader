"""Engineering feedback channel — how the trading desk reports engine defects.

Trading sessions NEVER edit engine code (separation of duties: a trader must
not be able to rewrite the risk gate). Instead they file a structured issue
here; the kautilya-engineer routine picks it up, reproduces it with a failing
test, fixes it on a branch, and CI gates the merge.

Usage:
  python3 -m engine.issues file --sev S1 --area execute --title "..." --body "..."
  python3 -m engine.issues list
  python3 -m engine.issues close <issue-file-stem> --note "fixed in <sha>"

Severity: S1 = safety (cannot exit / gate bypassed / state corruption) — the
desk must also stand down from NEW entries until it is closed.
S2 = degraded correctness (bad marks, wrong stats, feed fallback misbehavior).
S3 = paper cut. Duplicate filing is prevented by a slug on (area, title).
"""
import argparse
import json
import re
import sys

from engine import common

DIR = None  # resolved at call time so tests can monkeypatch common.STATE


def _dir():
    d = common.STATE / "issues"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(area: str, title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"{area}-{title}".lower()).strip("-")[:60]


def file_issue(sev: str, area: str, title: str, body: str) -> dict:
    slug = _slug(area, title)
    existing = list(_dir().glob(f"OPEN-*-{slug}.md"))
    if existing:
        return {"status": "duplicate", "of": existing[0].name}
    ts = common.now_ist().strftime("%Y%m%d-%H%M")
    p = _dir() / f"OPEN-{ts}-{slug}.md"
    p.write_text(f"""---
severity: {sev}
area: {area}
filed: {common.now_ist().isoformat(timespec='seconds')}
title: {title}
---

## Observed
{body}

## Engineer notes (append below)
""")
    common.journal({"type": "issue_filed", "severity": sev, "area": area,
                    "title": title, "file": p.name})
    return {"status": "filed", "file": p.name, "severity": sev}


def list_issues() -> list[dict]:
    out = []
    for p in sorted(_dir().glob("OPEN-*.md")):
        head = p.read_text()[:400]
        sev = re.search(r"severity: (\S+)", head)
        title = re.search(r"title: (.+)", head)
        out.append({"file": p.name, "severity": sev.group(1) if sev else "?",
                    "title": title.group(1) if title else "?"})
    return sorted(out, key=lambda x: x["severity"])


def close(stem: str, note: str) -> dict:
    for p in _dir().glob(f"OPEN-*{stem}*.md"):
        closed = p.with_name(p.name.replace("OPEN-", "CLOSED-", 1))
        p.rename(closed)
        with closed.open("a") as f:
            f.write(f"\n## Closed\n{common.now_ist().isoformat(timespec='seconds')}: {note}\n")
        common.journal({"type": "issue_closed", "file": closed.name, "note": note})
        return {"status": "closed", "file": closed.name}
    return {"status": "not_found", "stem": stem}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["file", "list", "close"])
    ap.add_argument("stem", nargs="?")
    ap.add_argument("--sev", default="S2", choices=["S1", "S2", "S3"])
    ap.add_argument("--area", default="engine")
    ap.add_argument("--title", default="")
    ap.add_argument("--body", default="")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.cmd == "file":
        if not a.title:
            sys.exit("--title required")
        print(json.dumps(file_issue(a.sev, a.area, a.title, a.body), indent=2))
    elif a.cmd == "list":
        print(json.dumps(list_issues(), indent=2))
    else:
        print(json.dumps(close(a.stem or "", a.note), indent=2))
