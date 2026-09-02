"""`scripts/watch_pr.py` — one test per shepherding bug that actually cost us time.

These are regression tests, not coverage. Each names the loop that had the bug and the
symptom it produced, because the same four keep being rewritten by hand:

- a reviewer comment sat behind a full CI run
- running checks were reported as failures
- a structurally blocked PR was slept on indefinitely
- a mergeable PR was held because some non-required check was still going

The decision is a pure function of a snapshot, so none of this touches the network.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("watch_pr", ROOT / "scripts" / "watch_pr.py")
assert _spec and _spec.loader
watch_pr = importlib.util.module_from_spec(_spec)
sys.modules["watch_pr"] = watch_pr
_spec.loader.exec_module(watch_pr)

Action = watch_pr.Action
Check = watch_pr.Check
Snapshot = watch_pr.Snapshot
Thread = watch_pr.Thread
decide = watch_pr.decide

RUNNING = Check("Ruby binding", status="IN_PROGRESS", conclusion="")
GREEN = Check("Lint & format", status="COMPLETED", conclusion="SUCCESS")
RED = Check("Doc tests", status="COMPLETED", conclusion="FAILURE")
SKIPPED = Check("auto-merge", status="COMPLETED", conclusion="SKIPPED")

OPEN_THREAD = Thread("PRRT_x", resolved=False, path="src/lib.rs", line=42, body="please fix")
DONE_THREAD = Thread("PRRT_y", resolved=True)


# --- bug 1: a reviewer comment must never wait on CI -------------------------


def test_an_unresolved_thread_stops_the_loop_even_while_checks_run() -> None:
    """The bug: threads polled after checks, so a comment waited out the whole run."""
    snap = Snapshot("OPEN", "BLOCKED", threads=(OPEN_THREAD,), checks=(RUNNING, GREEN))
    assert decide(snap).action is Action.STOP_THREADS


def test_an_unresolved_thread_outranks_a_mergeable_state() -> None:
    """Both halves: the thread must also beat a PR that is otherwise ready to merge."""
    ready = Snapshot("OPEN", "CLEAN", threads=(DONE_THREAD,), checks=(GREEN,))
    assert decide(ready).action is Action.MERGE
    blocked = Snapshot("OPEN", "CLEAN", threads=(DONE_THREAD, OPEN_THREAD), checks=(GREEN,))
    assert decide(blocked).action is Action.STOP_THREADS


def test_an_unresolved_thread_outranks_a_failed_check() -> None:
    """A human waiting beats a red check: the comment may be *about* the failure."""
    snap = Snapshot("OPEN", "BLOCKED", threads=(OPEN_THREAD,), checks=(RED,))
    assert decide(snap).action is Action.STOP_THREADS


# --- bug 2: a running check reports conclusion "", not null ------------------


def test_a_running_check_is_pending_not_failed() -> None:
    """The bug: `conclusion == null` was the pending test, so `""` read as finished.

    That exited the wait early and then printed the still-running checks as failures.
    """
    assert RUNNING.pending is True
    assert RUNNING.broken is False
    snap = Snapshot("OPEN", "BLOCKED", checks=(RUNNING, GREEN))
    assert decide(snap).action is Action.WAIT


def test_a_skipped_check_is_neither_pending_nor_broken() -> None:
    assert SKIPPED.pending is False
    assert SKIPPED.broken is False


@pytest.mark.parametrize("conclusion", sorted(watch_pr.BAD_CONCLUSIONS))
def test_every_bad_conclusion_stops_the_loop(conclusion: str) -> None:
    """`CANCELLED` included: a cancelled required check blocks like a failed one."""
    snap = Snapshot("OPEN", "BLOCKED", checks=(Check("x", "COMPLETED", conclusion),))
    assert decide(snap).action is Action.STOP_FAILED


# --- bug 3: BLOCKED with nothing pending is structural, not slow -------------


def test_blocked_with_nothing_pending_stops_rather_than_sleeping() -> None:
    """The bug: the loop slept through a required-review block until it ran out."""
    snap = Snapshot("OPEN", "BLOCKED", threads=(DONE_THREAD,), checks=(GREEN, SKIPPED))
    d = decide(snap)
    assert d.action is Action.STOP_STUCK
    assert "BLOCKED" in d.detail


def test_blocked_with_something_pending_keeps_waiting() -> None:
    """The other half: don't cry stuck while CI is legitimately still going."""
    snap = Snapshot("OPEN", "BLOCKED", checks=(GREEN, RUNNING))
    assert decide(snap).action is Action.WAIT


# --- bug 4: don't wait for every check before merging ------------------------


@pytest.mark.parametrize("state", sorted(watch_pr.MERGEABLE))
def test_every_mergeable_state_merges_even_with_a_check_still_running(state: str) -> None:
    """The bug: waiting for all checks COMPLETED, so a non-required job held the merge.

    #912 merged on poll 9 with one check still in flight. A loop gated on "everything
    finished" would still have been waiting.
    """
    snap = Snapshot("OPEN", state, checks=(GREEN, RUNNING))
    assert decide(snap).action is Action.MERGE


def test_unstable_is_treated_as_mergeable() -> None:
    """Named explicitly: `UNSTABLE` looks alarming and is the common green-PR state."""
    assert "UNSTABLE" in watch_pr.MERGEABLE


# --- terminal and rebase states ---------------------------------------------


@pytest.mark.parametrize(
    ("state", "expected"),
    [("MERGED", Action.STOP_MERGED), ("CLOSED", Action.STOP_CLOSED)],
)
def test_terminal_states(state: str, expected: Action) -> None:
    assert decide(Snapshot(state, "UNKNOWN")).action is expected


def test_merged_wins_even_with_an_unresolved_thread() -> None:
    """A thread left open on a merged PR is not a reason to keep watching."""
    snap = Snapshot("MERGED", "UNKNOWN", threads=(OPEN_THREAD,))
    assert decide(snap).action is Action.STOP_MERGED


@pytest.mark.parametrize("state", sorted(watch_pr.NEEDS_REBASE))
def test_stale_branches_ask_for_a_rebase(state: str) -> None:
    assert decide(Snapshot("OPEN", state, checks=(GREEN,))).action is Action.REBASE


def test_no_merge_mode_reports_instead_of_merging() -> None:
    snap = Snapshot("OPEN", "CLEAN", checks=(GREEN,))
    assert decide(snap, allow_merge=False).action is Action.STOP_STUCK


def test_the_state_sets_do_not_overlap() -> None:
    """A state in two sets would make the priority order depend on branch order."""
    assert not (watch_pr.MERGEABLE & watch_pr.NEEDS_REBASE)
