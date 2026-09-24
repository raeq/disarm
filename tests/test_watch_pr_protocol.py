"""The merge protocol of `scripts/watch_pr.py`, against a fake GitHub (WatchPR model).

A TLA+ model of the watcher and GitHub (`formal/tla/WatchPR`) found these by model
checking; each test replays one of its counterexample traces through the real `fetch()`,
`decide()` and `watch()`, with a fake `gh` at the `subprocess.run` boundary. The fake is a
small GitHub: it answers only the `--json` fields asked for, keeps a PR state that events
can change between two calls, and applies GitHub's merge rules server-side
(`required_checks`, `protect_threads`, `--match-head-commit`), so a test can tell a merge
GitHub would refuse from one it would land.

`tests/test_watch_pr.py` tests `decide()` on snapshots; this file tests the I/O around it,
which is where every finding here lived. A review of an earlier head still counting after
a push (the model's F6) is documented in the script rather than changed.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "watch_pr.py"
_spec = importlib.util.spec_from_file_location("watch_pr_protocol", SCRIPT)
assert _spec and _spec.loader
watch_pr = importlib.util.module_from_spec(_spec)
sys.modules["watch_pr_protocol"] = watch_pr
_spec.loader.exec_module(watch_pr)


def run_check(
    name: str,
    conclusion: str = "SUCCESS",
    status: str = "COMPLETED",
    started: str = "2026-09-23T10:00:00Z",
) -> dict[str, Any]:
    return {
        "__typename": "CheckRun",
        "name": name,
        "status": status,
        "conclusion": conclusion if status == "COMPLETED" else "",
        "startedAt": started,
        "completedAt": started if status == "COMPLETED" else "0001-01-01T00:00:00Z",
    }


GREEN_X = run_check("All checks passed")
COPILOT_REVIEW = {"author": {"login": "copilot-pull-request-reviewer"}, "state": "COMMENTED"}


class FakeGitHub:
    """Just enough of GitHub and `gh` for `watch_pr.py`, with server-side merge rules."""

    def __init__(
        self,
        *,
        head: str = "aaa",
        checks: list[dict[str, Any]] | None = None,
        reviews: list[dict[str, Any]] | None = None,
        requests: list[dict[str, Any]] | None = None,
        threads: list[dict[str, Any]] | None = None,
        thread_reply: tuple[int, str] | None = None,
        required_checks: bool = False,
        protect_threads: bool = False,
        reject_merge: str | None = None,
    ) -> None:
        self.state = "OPEN"
        self.head = head
        self.checks = {head: list(checks if checks is not None else [GREEN_X])}
        self.reviews = list(reviews or [])
        self.requests = list(requests or [])
        self.threads = list(threads or [])
        self.thread_reply = thread_reply
        self.required_checks = required_checks
        self.protect_threads = protect_threads
        self.reject_merge = reject_merge
        self.calls: list[list[str]] = []
        self.hooks: list[tuple[Callable[[list[str], int], bool], Callable[[], None]]] = []
        self.merges: list[dict[str, Any]] = []  # every merge GitHub ACCEPTED
        self.merge_attempts = 0

    # --- GitHub's view of the PR ------------------------------------------------
    def _latest(self) -> dict[str, dict[str, Any]]:
        """The latest run per check name: what branch protection evaluates."""
        latest: dict[str, dict[str, Any]] = {}
        for c in sorted(self.checks.get(self.head, []), key=lambda c: c["startedAt"]):
            latest[c["name"]] = c
        return latest

    def _green(self) -> bool:
        latest = self._latest()
        return bool(latest) and all(
            c["status"] == "COMPLETED" and c["conclusion"] in ("SUCCESS", "SKIPPED")
            for c in latest.values()
        )

    def unresolved(self) -> int:
        return sum(1 for t in self.threads if not t["isResolved"])

    def merge_state(self) -> str:
        if self.required_checks and not self._green():
            return "BLOCKED"
        if self.protect_threads and self.unresolved():
            return "BLOCKED"
        return "CLEAN" if self._green() else "UNSTABLE"

    def _view(self, fields: list[str]) -> dict[str, Any]:
        full = {
            "state": self.state,
            "mergeStateStatus": self.merge_state(),
            "statusCheckRollup": self.checks.get(self.head, []),
            "author": {"login": "raeq"},
            "reviewRequests": self.requests,
            "reviews": self.reviews,
            "headRefOid": self.head,
        }
        return {k: full[k] for k in fields if k in full}

    def _graphql(self) -> tuple[int, str]:
        if self.thread_reply is not None:
            return self.thread_reply
        nodes = [
            {
                "id": t["id"],
                "isResolved": t["isResolved"],
                "comments": {"nodes": [{"body": "b", "path": "f.py", "line": 1}]},
            }
            for t in self.threads
        ]
        rt = {"pageInfo": {"hasPreviousPage": False}, "nodes": nodes}
        return 0, json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": rt}}}})

    def _merge(self, args: list[str]) -> tuple[int, str, str]:
        self.merge_attempts += 1
        match = (
            args[args.index("--match-head-commit") + 1] if "--match-head-commit" in args else None
        )
        if self.state != "OPEN":
            return 1, "", f"X Pull request #1 was already {self.state.lower()}\n"
        if self.reject_merge:
            return 1, "", self.reject_merge
        if match is not None and match != self.head:
            return 1, "", "X Head branch was modified. Review and try the merge again.\n"
        if self.required_checks and not self._green():
            return (
                1,
                "",
                "X Pull request #1 is not mergeable: the base branch policy prohibits the merge.\n",
            )
        if self.protect_threads and self.unresolved():
            return (
                1,
                "",
                "X Pull request #1 is not mergeable: the base branch policy prohibits the merge.\n",
            )
        self.state = "MERGED"
        self.merges.append(
            {
                "head": self.head,
                "unresolved": self.unresolved(),
                "latest": {n: c["conclusion"] for n, c in self._latest().items()},
            }
        )
        return 0, "", ""

    # --- the `subprocess.run` replacement -----------------------------------------
    def __call__(self, argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        assert argv[0] == "gh", argv
        args = list(argv[1:])
        self.calls.append(args)
        rc, out, err = 0, "", ""
        if args[:2] == ["pr", "view"] and "--jq" in args:
            out = self.state  # verify_merged(): --jq .state
        elif args[:2] == ["pr", "view"]:
            fields = args[args.index("--json") + 1].split(",")
            out = json.dumps(self._view(fields))
        elif args[:2] == ["api", "graphql"]:
            rc, out = self._graphql()
            err = "gh: GraphQL error\n" if rc else ""
        elif args[:2] == ["pr", "merge"]:
            rc, out, err = self._merge(args)
        else:  # pragma: no cover - a call this fake does not know is a test bug
            raise AssertionError(f"unexpected gh call {args}")
        n = len(self.calls)
        for when, what in list(self.hooks):
            if when(args, n):
                what()
        return subprocess.CompletedProcess(argv, rc, out + "\n", err)

    def after_first(self, prefix: list[str], what: Callable[[], None]) -> None:
        """Run `what` once, right after the first call starting with `prefix`."""
        fired = {"done": False}

        def when(args: list[str], _n: int) -> bool:
            if not fired["done"] and args[: len(prefix)] == prefix:
                fired["done"] = True
                return True
            return False

        self.hooks.append((when, what))


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> Callable[..., FakeGitHub]:
    def make(**kw: Any) -> FakeGitHub:
        fake = FakeGitHub(**kw)
        monkeypatch.setattr(watch_pr.subprocess, "run", fake)
        monkeypatch.setattr(watch_pr.time, "sleep", lambda _s: None)
        return fake

    return make


def watch(max_polls: int = 3, await_review: bool = False) -> int:
    return watch_pr.watch(
        1, "o/r", interval=0, max_polls=max_polls, allow_merge=True, await_review=await_review
    )


# =============================================================================
# F1  ThreadGateSound / MergedNoUnresolved: a FAILED thread query reads as "no threads"
# =============================================================================

THREAD_FAILURES = {
    "empty stdout (network error, gh auth hiccup)": (1, ""),
    "GraphQL error body (rate limit)": (
        1,
        json.dumps(
            {
                "data": None,
                "errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}],
            }
        ),
    ),
    "non-JSON body (502 from the proxy)": (1, "<html>502 Bad Gateway</html>"),
    "pullRequest null (transient resolver error)": (
        1,
        json.dumps(
            {
                "data": {"repository": {"pullRequest": None}},
                "errors": [{"message": "Something went wrong"}],
            }
        ),
    ),
}


@pytest.mark.parametrize("reply", THREAD_FAILURES.values(), ids=THREAD_FAILURES.keys())
def test_f1_a_failed_thread_query_never_reads_as_no_threads(gh, reply) -> None:
    """F1: a failed thread query is a failed read, not "no threads".

    A --await-review repo, which does not require conversation resolution. Copilot has
    reviewed and left an unresolved thread, CI is green, and the thread query fails
    once. `_gh` drops the exit status, so `fetch()` used to fall through to no threads,
    `decide()` saw nothing unresolved, and GitHub accepted the merge: the #987 failure,
    through the I/O layer instead of `decide()`.
    """
    fake = gh(
        reviews=[COPILOT_REVIEW], threads=[{"id": "T1", "isResolved": False}], thread_reply=reply
    )
    snap = watch_pr.fetch(1, "o/r")
    # The safe outcomes: a failed read (None), or a snapshot that cannot merge.
    assert (
        snap is None or watch_pr.decide(snap, await_review=True).action is not watch_pr.Action.MERGE
    )
    watch(max_polls=1, await_review=True)
    assert fake.merges == [], f"merged with an unresolved thread: {fake.merges}"


def test_f1b_a_failed_thread_read_does_not_count_towards_the_stuck_streak(gh) -> None:
    """F1b: the contributor docs say a failed read does not count towards the streak.

    The rule is in `docs/contributing/pull-requests.md`, "Watching a PR to merge". That
    held for the PR view and not for the thread query, whose failure still yielded a
    snapshot. Five polls show the stuck shape and every second thread read fails, so
    there are never two good sightings in a row, which must not stop as stuck.
    """
    fake = gh(required_checks=True, protect_threads=True, checks=[])  # BLOCKED, nothing pending
    good = None
    bad = (1, "")
    fake.thread_reply = good

    def flip() -> None:
        fake.thread_reply = bad if fake.thread_reply is None else good

    fake.hooks.append((lambda args, _n: args[:2] == ["api", "graphql"], flip))
    assert watch(max_polls=5) == 3


# =============================================================================
# F2  IssueEvaluatedHead / MergedEvaluatedHead: the merge names no head SHA
# =============================================================================


def _push_red_commit(fake: FakeGitHub) -> Callable[[], None]:
    def push() -> None:
        fake.head = "bbb"  # a new commit lands ...
        fake.checks["bbb"] = [run_check("All checks passed", "FAILURE")]  # ... and fails fast

    return push


def test_f2_a_head_pushed_after_the_read_is_not_merged(gh) -> None:
    """F2: the merge names the head the watcher evaluated.

    No required checks, as on a small --await-review repo. The watcher reads `aaa`:
    green, reviewed, no threads. Before `gh pr merge` a push moves the head to `bbb`,
    whose check has already failed. A merge naming no SHA let GitHub land `bbb`, a head
    the watcher never evaluated, and red; `--match-head-commit` makes GitHub refuse it.
    """
    fake = gh(reviews=[COPILOT_REVIEW])
    fake.after_first(["api", "graphql"], _push_red_commit(fake))  # after the last read
    watch(max_polls=2, await_review=True)
    merged = [m["head"] for m in fake.merges]
    assert merged in ([], ["aaa"]), f"merged {merged}, but only 'aaa' was evaluated"


def test_f2_server_side_mitigation_in_this_repo(gh) -> None:
    """The same race in this repo's configuration: GitHub refuses, and the watcher recovers.

    With a required check `bbb` is not green, so the merge is refused server-side,
    whatever the client sends. The next poll reads `bbb`, sees it red, and reports it
    after FAILURE_POLLS. This is why F2 was low severity here.
    """
    fake = gh(required_checks=True, protect_threads=True)
    fake.after_first(["api", "graphql"], _push_red_commit(fake))
    assert watch(max_polls=4) == 2
    assert fake.merges == []
    assert fake.merge_attempts == 1


# =============================================================================
# F3  EventuallyStops: a rejected merge is invisible, so the watcher retries it blind
# =============================================================================


def test_f3_a_rejected_merge_is_reported_not_retried_blind(gh, capsys) -> None:
    """F3: a refused merge is reported, and stops the watcher.

    GitHub refuses the squash every time (squash disabled, a merge queue required, a
    ruleset `gh`'s preflight cannot see). Its reason used to vanish with the exit status;
    the loop retried until --max-polls, printed "gave up" and exited 3, the code for
    "timed out", with the reason nowhere.
    """
    reason = "X Squash merges are not allowed on this repository.\n"
    fake = gh(reject_merge=reason)
    rc = watch(max_polls=5)
    out = capsys.readouterr().out
    assert fake.merges == []
    assert "Squash merges are not allowed" in out, (
        f"rc={rc}, {fake.merge_attempts} blind merge attempts; the refusal was never shown:\n{out}"
    )
    assert rc != 3


# =============================================================================
# F4  NoStaleFailStop: a superseded CANCELLED run on the same head reads as a failure
# =============================================================================


def test_f4_a_superseded_cancelled_run_does_not_stop_a_green_pr(gh) -> None:
    """F4: only the latest run of a check counts, as it does for branch protection.

    Two runs of the same workflow on the same head (a reopen, a re-trigger); the
    concurrency group cancels the first. If the rollup lists both, `All checks passed:
    CANCELLED` sits beside `SUCCESS`, and the cancelled one read as broken on a PR GitHub
    calls CLEAN. Conditional on GitHub listing the superseded run; harmless if it does not.
    """
    fake = gh(
        required_checks=True,
        protect_threads=True,
        checks=[
            run_check("All checks passed", "CANCELLED", started="2026-09-23T10:00:00Z"),
            run_check("All checks passed", "SUCCESS", started="2026-09-23T10:01:00Z"),
        ],
    )
    assert fake.merge_state() == "CLEAN"
    rc = watch(max_polls=3)
    assert rc == 0 and len(fake.merges) == 1, f"rc={rc}: stopped on a superseded run"


# =============================================================================
# F5  --await-review: a standing change request holds the gate (AwaitNoChangesRequested)
# =============================================================================


def test_f5_changes_requested_does_not_release_the_await_gate(gh) -> None:
    """F5: a change request with no inline thread used to open the gate, and the PR merged.

    The documented contract said only "until someone other than the author has
    reviewed", which this satisfied to the letter. A reviewer whose latest review
    requests changes now stops the watcher: a human has to act.
    """
    fake = gh(
        reviews=[
            {"author": {"login": "bob"}, "state": "CHANGES_REQUESTED", "commit": {"oid": "aaa"}}
        ]
    )
    watch(max_polls=2, await_review=True)
    assert fake.merges == [], "merged over a standing CHANGES_REQUESTED review"


def test_f5_a_later_approval_clears_the_request(gh) -> None:
    """The latest review per reviewer decides, as it does on GitHub."""
    fake = gh(
        reviews=[
            {"author": {"login": "bob"}, "state": "CHANGES_REQUESTED"},
            {"author": {"login": "bob"}, "state": "APPROVED"},
        ]
    )
    assert watch(max_polls=2, await_review=True) == 0
    assert [m["head"] for m in fake.merges] == ["aaa"]


def test_f4_a_job_name_shared_by_two_workflows_is_not_deduplicated(gh) -> None:
    """Latest per workflow and name, not per name: a newer `build` must not hide an older one.

    Deduplicating by name alone would let one workflow's passing job hide another
    workflow's failing job of the same name.
    """
    lint = {**run_check("build", "FAILURE", started="2026-09-23T10:00:00Z"), "workflowName": "A"}
    test = {**run_check("build", "SUCCESS", started="2026-09-23T10:01:00Z"), "workflowName": "B"}
    gh(checks=[lint, test])
    snap = watch_pr.fetch(1, "o/r")
    assert snap is not None
    assert sorted(c.conclusion for c in snap.checks) == ["FAILURE", "SUCCESS"]


# =============================================================================
# Pinned: behaviour the model shows is load-bearing
# =============================================================================


def test_pin_the_view_is_read_before_the_threads(gh) -> None:
    """`await_threadsfirst_tailquiet__MergedNoUnresolved` is VIOLATED, the view-first
    twin HOLDS: read threads first and a review that lands between the two reads, with
    its inline comment, is seen as "reviewed, no threads". The module docstring
    calls the order of the two calls irrelevant; under
    --await-review it is not.
    """
    fake = gh(requests=[{"login": "Copilot"}])

    def copilot_reviews() -> None:  # request cleared, review + thread appear
        fake.requests.clear()
        fake.reviews.append(COPILOT_REVIEW)
        fake.threads.append({"id": "T1", "isResolved": False})

    fake.after_first(["pr", "view"], copilot_reviews)
    snap = watch_pr.fetch(1, "o/r")
    kinds = [c[:2] for c in fake.calls]
    assert kinds.index(["pr", "view"]) < kinds.index(["api", "graphql"])
    assert snap is not None
    assert watch_pr.decide(snap, await_review=True).action is not watch_pr.Action.MERGE


def test_pin_truncation_never_reads_as_no_threads(gh) -> None:
    """ThreadGateSound restricted to the `trunc` outcome HOLDS: `hasPreviousPage` is read."""
    fake = gh(reviews=[COPILOT_REVIEW])
    rt = {"pageInfo": {"hasPreviousPage": True}, "nodes": []}
    fake.thread_reply = (
        0,
        json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": rt}}}}),
    )
    assert watch(max_polls=1, await_review=True) == 2
    assert fake.merges == []
