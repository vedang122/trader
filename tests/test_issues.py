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


# --- the needs-human axis ----------------------------------------------------
# A protected-path fix cannot be landed by the engineer, so it is written into
# the issue as a patch and the issue stays OPEN. That commit touches only
# allowed paths, so CI classifies it `engine`, merges it, and no PR is ever
# opened — the patch reaches nobody. Detection has to key off the marker in the
# issue body, not off the file list in the diff.

def _append(desk, name, text):
    (desk / "issues" / name).open("a").write(text)


@pytest.mark.parametrize("heading", [
    "## Proposed patch (needs human)",
    "## Suggested direction (needs human -- .github/** is protected)",
    "## proposed patch (Needs Human)",
])
def test_a_patch_marker_flags_the_issue_as_needing_a_human(desk, heading):
    """Both headings the desk actually writes, and case does not decide it."""
    name = _file("broker", sev="S2")
    assert _row(name)["needs_human"] is False
    _append(desk, name, f"\n{heading}\n```diff\n-old\n+new\n```\n")
    assert _row(name)["needs_human"] is True
    assert issues.gate()["needs_human"] == [name]


def test_front_matter_key_also_flags_it(desk):
    """An explicit `needs_human: true` stands even with no patch section."""
    name = _file("portfolio", sev="S2")
    p = desk / "issues" / name
    p.write_text(p.read_text().replace("area: ", "needs_human: true\narea: ", 1))
    assert _row(name)["needs_human"] is True


def test_prose_about_a_human_is_not_a_marker(desk):
    """'needs human review' in the body is narration, not a pending patch."""
    name = _file("data", sev="S2")
    _append(desk, name, "\nProtected path — needs human-reviewed fix.\n")
    assert _row(name)["needs_human"] is False
    assert issues.gate()["needs_human"] == []


def test_closed_issues_are_not_pending(desk):
    name = _file("broker", sev="S2")
    _append(desk, name, "\n## Proposed patch (needs human)\n```diff\n+x\n```\n")
    issues.close(name.replace("OPEN-", "").replace(".md", ""), "landed by hand")
    assert issues.gate()["needs_human"] == []


def test_pending_human_cli_reports_the_stranded_patches(desk):
    """The routine reads this to know what to put in front of the human."""
    name = _file("broker", sev="S2")
    _append(desk, name, "\n## Proposed patch (needs human)\n```diff\n+x\n```\n")
    rows = issues.pending_human()
    assert [r["file"] for r in rows] == [name]
    assert rows[0]["severity"] == "S2" and rows[0]["area"] == "broker"


def test_pending_human_cli_runs_against_the_real_desk():
    r = subprocess.run([sys.executable, "-m", "engine.issues", "pending-human"],
                       cwd=REPO, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert isinstance(json.loads(r.stdout), list)


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
                 "needs_human": [], "counts": {}}


def test_gate_cli_runs_against_the_real_desk(desk):
    """Read-only smoke test: the desk invokes this through the CLI, not the API."""
    r = subprocess.run([sys.executable, "-m", "engine.issues", "gate"],
                       cwd=REPO, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    g = json.loads(r.stdout)
    assert isinstance(g["entries_allowed"], bool)
    assert isinstance(g["blocking"], list)


# --- delivery ----------------------------------------------------------------
# Detection (above) is not delivery. The routine's own draft PR cannot carry a
# stranded patch: the merge gate's last act is `git push origin --delete
# "$GITHUB_REF_NAME"`, and deleting a PR's head branch closes the PR. Measured
# on the real repo — PR #11 opened 2026-08-09T11:22:50Z, closed 11:23:03Z by
# its own workflow run (#10 and #9 the same). So the digest has to exist as a
# branch-independent artifact the routine can post somewhere deletion can't
# reach; `handoff` renders exactly that, and nothing else in the engine does.

def test_handoff_carries_each_stranded_patch_to_one_artifact(desk):
    name = _file("broker", sev="S2", title="last_price unguarded")
    _append(desk, name, "\n## Proposed patch (needs human)\n"
                        "```diff\n-old_line\n+new_line\n```\n")
    out = issues.handoff()
    assert name in out                      # which issue file to open
    assert "S2" in out and "broker" in out  # severity + area at a glance
    assert "+new_line" in out               # the patch itself, not a pointer


def test_handoff_omits_issues_that_are_not_waiting_on_anyone(desk):
    _file("scan", sev="S3", title="a paper cut")
    stranded = _file("risk", sev="S2", title="cli eats subcommands")
    _append(desk, stranded, "\n## Proposed patch (needs human)\n```diff\n+fix\n```\n")
    out = issues.handoff()
    assert stranded in out
    assert "a paper cut" not in out


def test_handoff_says_so_when_nothing_is_stranded(desk):
    out = issues.handoff()
    assert "no patches" in out.lower()
    assert "```" not in out  # nothing to apply, so nothing that looks applicable


def test_handoff_cli_runs_against_the_real_desk():
    r = subprocess.run([sys.executable, "-m", "engine.issues", "handoff"],
                       cwd=REPO, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip()
