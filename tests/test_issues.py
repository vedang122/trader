"""The issue channel's gating axis: which OPEN defects actually bar new entries.

An S1 halts entries because a safety defect can mis-place, mis-size or strand
an order. These tests pin the two halves of that reasoning: it must hold for
every area the order path runs through (and for areas nobody has invented yet),
and it must NOT hold for pure infrastructure, which cannot reach an order.
"""
import datetime as dt
import json
import re
import subprocess
import sys

import pytest

from engine import common, issues

REPO = __import__("pathlib").Path(__file__).resolve().parent.parent


def _file(area, sev="S1", title="a defect"):
    r = issues.file_issue(sev, area, f"{title} in {area}", "evidence: cmd + output")
    assert r["status"] == "filed", r
    return r["file"]


def _backdate(desk, name, hours):
    """Rewrite an issue's `filed:` stamp so age-based rules can be exercised."""
    p = desk / "issues" / name
    stamp = (common.now_ist() - dt.timedelta(hours=hours)).isoformat(timespec="seconds")
    p.write_text(re.sub(r"filed: .+", f"filed: {stamp}", p.read_text(), count=1))


def _row(name):
    return next(i for i in issues.list_issues() if i["file"] == name)


# --- the area axis -----------------------------------------------------------

@pytest.mark.parametrize("area", ["risk", "execute", "broker", "portfolio",
                                  "amend", "common", "data", "scan", "regime"])
def test_s1_on_the_order_path_blocks_entries(desk, area):
    name = _file(area)
    assert _row(name)["blocks_entries"] is True
    assert issues.gate()["entries_allowed"] is False


@pytest.mark.parametrize("area", ["ops", "ci", "issues"])
def test_infrastructure_s1_does_not_block_entries(desk, area):
    """The live defect: an Actions/CI S1 halted the desk for a whole session."""
    name = _file(area)
    assert _row(name)["blocks_entries"] is False
    g = issues.gate()
    assert g["entries_allowed"] is True
    assert g["blocking"] == []


def test_unknown_area_blocks_fail_closed(desk):
    """An area nobody classified must halt entries, not sail through."""
    name = _file("some-new-subsystem")
    assert _row(name)["blocks_entries"] is True
    assert issues.gate()["entries_allowed"] is False


def test_area_matching_is_case_and_space_insensitive(desk):
    name = _file("  OPS  ")
    assert _row(name)["blocks_entries"] is False


@pytest.mark.parametrize("sev", ["S2", "S3"])
def test_sub_s1_never_blocks(desk, sev):
    name = _file("execute", sev=sev)
    assert _row(name)["blocks_entries"] is False
    assert issues.gate()["entries_allowed"] is True


def test_one_order_path_s1_blocks_despite_many_infra_s1s(desk):
    for a in ("ops", "ci", "issues"):
        _file(a)
    blocker = _file("execute")
    g = issues.gate()
    assert g["entries_allowed"] is False
    assert g["blocking"] == [blocker]


# --- the escalation axis -----------------------------------------------------

def test_stale_s1_escalates_to_the_human(desk):
    """No expiry today: a stuck S1 repeats the same silent stand-down forever."""
    name = _file("execute")
    _backdate(desk, name, issues.ESCALATE_AFTER_H + 1)
    assert _row(name)["escalate"] is True
    assert issues.gate()["escalate"] == [name]


def test_stale_infra_s1_escalates_even_though_it_does_not_block(desk):
    name = _file("ops")
    _backdate(desk, name, issues.ESCALATE_AFTER_H + 1)
    row = _row(name)
    assert row["blocks_entries"] is False
    assert row["escalate"] is True


def test_fresh_s1_does_not_escalate(desk):
    name = _file("execute")
    assert _row(name)["escalate"] is False
    assert issues.gate()["escalate"] == []


def test_stale_s2_does_not_escalate(desk):
    name = _file("execute", sev="S2")
    _backdate(desk, name, issues.ESCALATE_AFTER_H * 10)
    assert _row(name)["escalate"] is False


def test_unparseable_filed_stamp_does_not_crash(desk):
    """A hand-edited issue must degrade to 'no age', never take the module down."""
    name = _file("execute")
    p = desk / "issues" / name
    p.write_text(re.sub(r"filed: .+", "filed: sometime last week", p.read_text(), count=1))
    row = _row(name)
    assert row["age_hours"] is None
    assert row["escalate"] is False
    assert row["blocks_entries"] is True  # severity/area still gate it


# --- shape + wiring ----------------------------------------------------------

def test_list_reports_area_and_blockers_sort_first(desk):
    _file("ops")
    blocker = _file("risk")
    rows = issues.list_issues()
    assert rows[0]["file"] == blocker
    assert {r["area"] for r in rows} == {"ops", "risk"}


def test_gate_counts_every_open_issue(desk):
    _file("ops")
    _file("execute", sev="S2")
    _file("data", sev="S3")
    assert issues.gate()["counts"] == {"S1": 1, "S2": 1, "S3": 1}


def test_gate_is_clean_when_nothing_is_open(desk):
    g = issues.gate()
    assert g == {"entries_allowed": True, "blocking": [], "escalate": [],
                 "counts": {}}


def test_gate_cli_runs_against_the_real_desk(desk):
    """Read-only smoke test: the desk invokes this through the CLI, not the API."""
    r = subprocess.run([sys.executable, "-m", "engine.issues", "gate"],
                       cwd=REPO, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    g = json.loads(r.stdout)
    assert isinstance(g["entries_allowed"], bool)
    assert isinstance(g["blocking"], list)
