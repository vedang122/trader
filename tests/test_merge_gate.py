"""OPEN-20260807-1305-ops: the merge gate silently discards engineer branches.

The self-repair loop only works if a green engineer branch actually reaches
main. It does not: `merge-cloud-state.yml`'s test step overlays the branch with
`git checkout origin/<branch> -- .` (which writes the INDEX as well as the
worktree) and then "cleans up" with `git checkout -- .`, which restores the
worktree *from that same polluted index* and so undoes nothing. The merge step
then aborts with exit 2, and the Open-PR fallback is gated on the tests having
failed — they passed — so nothing merges, no PR opens, and no one is told.

The first two tests prove the mechanism against real git and are permanently
true of git itself. The last two read the live workflow and are the tripwire:
strict xfail, so the suite turns RED the moment the patch in the issue file is
applied and the markers are due for deletion.
"""
import re
import pathlib
import subprocess

import pytest
import yaml

WORKFLOW = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows" / "merge-cloud-state.yml"
NEEDS_HUMAN = ("OPEN-20260807-1305-ops: fix lives in the protected "
               ".github/workflows/merge-cloud-state.yml — proposed patch is in "
               "the issue file, needs human review")


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _gate_repo(tmp_path, drift: bool):
    """A miniature of the gate's checkout: main, a forked run branch, and the
    overlay the test step performs. `drift` replays a cycle push landing on main
    after the branch forked — the condition that loses the race."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "state").mkdir()
    (r / "tests").mkdir()
    (r / "state" / "journal.jsonl").write_text("line0\n")
    _git(r, "add", "-A"), _git(r, "commit", "-qm", "base")

    _git(r, "checkout", "-qb", "feat")
    (r / "tests" / "test_fix.py").write_text("def test_fix(): assert True\n")
    (r / "state" / "journal.jsonl").write_text("line0\nbranch entry\n")
    _git(r, "add", "-A"), _git(r, "commit", "-qm", "engineer fix")

    _git(r, "checkout", "-q", "main")
    if drift:
        (r / "state" / "journal.jsonl").write_text("line0\ncycle entry\n")
        _git(r, "add", "-A"), _git(r, "commit", "-qm", "cycle push")

    _git(r, "checkout", "feat", "--", ".")  # the step's overlay: stages every file
    assert _staged(r), "precondition: the overlay stages the branch's files"
    return r


def _staged(r):
    return _git(r, "diff", "--cached", "--name-only").stdout.split()


def test_checkout_dash_dot_cannot_undo_the_overlay(tmp_path):
    """`git checkout -- .` reads from the index it is meant to be undoing, so the
    overlay stays staged and the merge aborts. This is the stranding."""
    r = _gate_repo(tmp_path, drift=True)

    _git(r, "checkout", "--", ".")  # the workflow's cleanup, verbatim
    assert _staged(r) == ["state/journal.jsonl", "tests/test_fix.py"], \
        "the cleanup is a no-op against a staged overlay"

    merge = _git(r, "merge", "feat", "-X", "theirs", "--no-edit")
    assert merge.returncode == 2, merge.stderr
    assert "would be overwritten by merge" in merge.stderr


def test_reset_hard_undoes_the_overlay_and_the_merge_lands(tmp_path):
    """The proposed one-line fix: `git reset --hard HEAD` clears index and
    worktree together, and the same merge that aborted now succeeds."""
    r = _gate_repo(tmp_path, drift=True)
    _git(r, "reset", "-q", "--hard", "HEAD")
    assert _staged(r) == []

    merge = _git(r, "merge", "feat", "-X", "theirs", "--no-edit")
    assert merge.returncode == 0, merge.stderr


def test_the_stranding_is_a_race_not_a_constant(tmp_path):
    """Why it looked random: with no cycle push between fork and merge the
    overlay matches HEAD, so the broken cleanup is harmless and the branch
    lands. Only branches slower than the ~30min cycle cadence are discarded."""
    r = _gate_repo(tmp_path, drift=False)
    _git(r, "checkout", "--", ".")
    assert _git(r, "merge", "feat", "-X", "theirs", "--no-edit").returncode == 0


def _steps():
    wf = yaml.safe_load(WORKFLOW.read_text())
    return wf["jobs"]["merge"]["steps"]


def _step(name):
    for s in _steps():
        if s.get("name", "").startswith(name):
            return s
    raise AssertionError(f"no step named {name!r} in {WORKFLOW.name}")


@pytest.mark.xfail(strict=True, reason=NEEDS_HUMAN)
def test_test_step_leaves_a_clean_index_for_the_merge():
    """The overlay must be undone with a real reset (or run somewhere that is
    not the merge checkout at all), never with `git checkout -- .`."""
    run = _step("Run tests")["run"]
    assert not re.search(r"^\s*git checkout\s+--\s+\.\s*$", run, re.M), \
        "git checkout -- . restores from the polluted index; it cannot undo an overlay"
    assert re.search(r"git reset\s+(-q\s+)?--hard", run) or "git worktree" in run, \
        "the test step must hard-reset the overlay or test it outside the merge checkout"


@pytest.mark.xfail(strict=True, reason=NEEDS_HUMAN)
def test_a_job_that_neither_merges_nor_opens_a_pr_cannot_end_silently():
    """`tests.outcome != 'success'` is not the same condition as `the merge did
    not happen`. Any path that ends without merging must still open the PR or
    raise, or the next unanticipated failure is silent too."""
    steps = _steps()
    merge = _step("Merge into main")
    assert merge.get("id"), "the merge step needs an id so later steps can test its outcome"

    fallback = [s for s in steps
                if "always()" in str(s.get("if", "")) or merge["id"] in str(s.get("if", ""))]
    assert fallback, "no terminal step reports a job that ended without merging"
