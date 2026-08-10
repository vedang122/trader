"""Engineering feedback channel — how the trading desk reports engine defects.

Trading sessions NEVER edit engine code (separation of duties: a trader must
not be able to rewrite the risk gate). Instead they file a structured issue
here; the kautilya-engineer routine picks it up, reproduces it with a failing
test, fixes it on a branch, and CI gates the merge.

Usage:
  python3 -m engine.issues file --sev S1 --area execute --title "..." --body "..."
  python3 -m engine.issues list
  python3 -m engine.issues pending-human
  python3 -m engine.issues handoff
  python3 -m engine.issues close <issue-file-stem> --note "fixed in <sha>"

Severity: S1 = safety (cannot exit / gate bypassed / state corruption) — the
desk must also stand down from NEW entries until it is closed, but only when
the defect can reach an order: see INFRA_AREAS and `gate` below.
S2 = degraded correctness (bad marks, wrong stats, feed fallback misbehavior).
S3 = paper cut. Duplicate filing is prevented by a slug on (area, title).
"""
import argparse
import datetime as dt
import json
import re
import sys

from engine import common

# An S1 bars new entries because a safety defect can mis-place, mis-size or
# strand an order. That reasoning only holds for code the order path runs
# through. These areas sit entirely outside it — ops/ci are branch hygiene and
# CI plumbing, issues is this feedback channel itself — so an S1 there is loud
# but is not a trading blockade. Fail closed, exactly like ops.NOTICE_ONLY:
# anything not listed here blocks, including an area invented tomorrow.
INFRA_AREAS = ("ops", "ci", "issues")
# A blocking S1 that outlives this is a decision for the human, not a routine
# stand-down the desk repeats silently every cycle until someone notices.
ESCALATE_AFTER_H = 24
# When a fix lives in a protected file the engineer may not land it: it writes
# the patch into the issue and leaves the issue OPEN. That commit touches only
# ALLOWED paths, so CI classifies it `engine` and merges it like any other fix
# — the request for human action is invisible in the diff. The marker in the
# body is the only durable signal, so detection reads the body. A section
# HEADING, not prose: "needs human-reviewed fix" in an Observed paragraph is
# narration, not a patch waiting on someone.
NEEDS_HUMAN_RE = re.compile(r"^#{2,3} .*\(needs human", re.M | re.I)

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


def blocks_entries(sev: str, area: str) -> bool:
    """Does an OPEN issue of this (severity, area) bar NEW entries?"""
    return sev == "S1" and area.strip().lower() not in INFRA_AREAS


def _age_hours(head: str) -> float | None:
    """Hours since the `filed:` stamp; None if it is missing or hand-mangled."""
    m = re.search(r"filed: (.+)", head)
    try:
        return (common.now_ist() - dt.datetime.fromisoformat(m.group(1).strip())
                ).total_seconds() / 3600
    except Exception:
        return None


def needs_human(text: str) -> bool:
    """Is this issue carrying a patch that only the human can land?"""
    return bool(NEEDS_HUMAN_RE.search(text)
                or re.search(r"^needs_human: true", text[:400], re.M | re.I))


def list_issues() -> list[dict]:
    out = []
    for p in sorted(_dir().glob("OPEN-*.md")):
        body = p.read_text()
        head = body[:400]
        sev = re.search(r"severity: (\S+)", head)
        area = re.search(r"area: (.+)", head)
        title = re.search(r"title: (.+)", head)
        sev = sev.group(1) if sev else "?"
        area = area.group(1).strip() if area else "?"
        age = _age_hours(head)
        out.append({"file": p.name, "severity": sev, "area": area,
                    "title": title.group(1) if title else "?",
                    "blocks_entries": blocks_entries(sev, area),
                    "needs_human": needs_human(body),
                    "age_hours": None if age is None else round(age, 1),
                    "escalate": sev == "S1" and age is not None and age >= ESCALATE_AFTER_H})
    # Blockers first within a severity — the desk reads the top of this list.
    return sorted(out, key=lambda x: (x["severity"], not x["blocks_entries"]))


def gate() -> dict:
    """Deterministic answer to 'may the desk open new positions?'.

    The trader reads this instead of eyeballing severities: judgment stays in
    the agents, the classification stays in Python.
    """
    rows = list_issues()
    counts = {}
    for r in rows:
        counts[r["severity"]] = counts.get(r["severity"], 0) + 1
    return {"entries_allowed": not any(r["blocks_entries"] for r in rows),
            "blocking": [r["file"] for r in rows if r["blocks_entries"]],
            "escalate": [r["file"] for r in rows if r["escalate"]],
            "needs_human": [r["file"] for r in rows if r["needs_human"]],
            "counts": counts}


def pending_human() -> list[dict]:
    """OPEN issues whose fix is written but waits on a human to land it.

    The engineer routine reads this at the end of a run and puts the result in
    front of the human itself (a PR), rather than trusting CI to notice — CI
    classifies these commits by the paths they touch, and the protected file
    is by definition NOT one of them.
    """
    return [r for r in list_issues() if r["needs_human"]]


def _stranded_patches(text: str) -> list[str]:
    """The needs-human sections of one issue, verbatim.

    From each marker heading to the next heading of the same level or higher,
    so a patch travels with its fences and its caveats — the human is being
    asked to apply it, not to reconstruct it from a pointer.
    """
    out = []
    for m in NEEDS_HUMAN_RE.finditer(text):
        rest = text[m.start():]
        level = len(rest) - len(rest.lstrip("#"))
        # Search below the marker's own heading line, or it terminates itself.
        body = rest.find("\n") + 1 or len(rest)
        nxt = re.search(rf"^#{{1,{level}}} ", rest[body:], re.M)
        out.append((rest[:body + nxt.start()] if nxt else rest).strip())
    return out


def handoff() -> str:
    """Every stranded patch as ONE markdown artifact, for a durable channel.

    Detection (`pending_human`) is not delivery, and the routine's own draft PR
    cannot deliver: the merge gate's last act is `git push origin --delete
    "$GITHUB_REF_NAME"`, and deleting a PR's head branch closes the PR. On the
    real repo PR #11 opened 2026-08-09T11:22:50Z and closed 11:23:03Z — 13s —
    killed by its own workflow run; #10 and #9 the same. So this renders an
    artifact that carries no branch: post it as a GitHub Issue (branch deletion
    cannot reach one) or send it in the routine's notification.
    """
    rows = pending_human()
    if not rows:
        return "No patches are waiting on a human.\n"
    parts = [f"{len(rows)} patch(es) waiting on a human, oldest first. Each is "
             "written and tested; each lives in a protected path the engineer "
             "routine may not edit.\n"]
    for r in sorted(rows, key=lambda x: -(x["age_hours"] or 0)):
        age = "unknown age" if r["age_hours"] is None else f"open {r['age_hours']:.0f}h"
        parts.append(f"\n---\n\n## {r['severity']} · {r['area']} · {age}\n"
                     f"{r['title']}\n\n`state/issues/{r['file']}`\n")
        parts.extend(f"\n{s}\n" for s in _stranded_patches(
            (_dir() / r["file"]).read_text()))
    return "".join(parts)


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
    ap.add_argument("cmd", choices=["file", "list", "close", "gate", "pending-human",
                                    "handoff"])
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
    elif a.cmd == "gate":
        print(json.dumps(gate(), indent=2))
    elif a.cmd == "pending-human":
        print(json.dumps(pending_human(), indent=2))
    elif a.cmd == "handoff":
        print(handoff())
    else:
        print(json.dumps(close(a.stem or "", a.note), indent=2))
