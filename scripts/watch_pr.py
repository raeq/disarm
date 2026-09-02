#!/usr/bin/env python3
"""Watch a pull request to merge, stopping the moment a human needs to act.

Every shepherding loop written by hand in this repo has had at least one of the four
bugs below, and each cost a real wait or a wrong report:

1. **A reviewer comment waited on CI.** A loop that acts on checks before it looks at
   review threads will sit through a whole CI run before noticing the PR is blocked on
   a comment. Here every cycle fetches threads and checks into one `Snapshot`, and
   `decide()` ranks unresolved threads above check state and above merging. The order
   of the two network calls in `fetch()` is irrelevant; the priority is in `decide()`,
   which is where it can be tested.

2. **`conclusion` is `""` for a running check, not `null`.** A loop that waits for
   `conclusion == null` to clear exits while checks are still in flight and then reports
   the running ones as failures. Pending is `status != "COMPLETED"`.

3. **`BLOCKED` with nothing pending and nothing unresolved span forever.** That state
   means something structural — a required review, a branch-protection rule — and no
   amount of waiting fixes it. It is a stop condition, not a sleep.

4. **Waiting for every check to finish never merges.** `UNSTABLE` and `HAS_HOOKS` are
   mergeable; a non-required check still running is not a reason to hold. Merge on any
   mergeable state and let the required set gate it.

The decision is a pure function of a `Snapshot`, so it is unit-tested in
`tests/test_watch_pr.py` without touching the network. The I/O layer around it is thin
on purpose.

Exit codes:
    0  merged (re-read from GitHub to confirm, not trusted from the loop)
    1  closed without merging, or reported merged but not confirmed
    2  a human is needed: an unresolved review thread, a failed check, a structural
       block, a stale branch, or a thread listing too long to read in one page
    3  gave up after --max-polls

Usage:
    python scripts/watch_pr.py 912
    python scripts/watch_pr.py 912 --repo raeq/disarm --interval 20 --max-polls 200
    python scripts/watch_pr.py 912 --no-merge      # report only, never merge
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum

DEFAULT_REPO = "raeq/disarm"

#: `gh pr view --json mergeStateStatus` values from which a squash merge is accepted.
#: `UNSTABLE` = a non-required check failed or is running; `HAS_HOOKS` = merge hooks.
#: Excluding these is what makes a loop wait for checks that never gate the merge.
MERGEABLE = frozenset({"CLEAN", "UNSTABLE", "HAS_HOOKS"})

#: States where the branch needs a rebase before anything else can happen.
NEEDS_REBASE = frozenset({"DIRTY", "BEHIND"})

#: GitHub's maximum page size for `reviewThreads`. Past this the listing silently
#: truncates, so `Snapshot.threads_truncated` records it rather than letting an unseen
#: thread read as an absent one.
THREAD_PAGE_SIZE = 100

#: How many consecutive polls must show the stuck shape before it is reported. One is
#: not enough: for a few seconds after a push GitHub reports BLOCKED with the previous
#: run's checks COMPLETED and the new ones not yet created, which is indistinguishable
#: from a structural block in a single snapshot.
STUCK_POLLS = 3

#: Conclusions that mean a check will not go green on its own. `CANCELLED` belongs
#: here — a cancelled required check blocks exactly like a failed one.
BAD_CONCLUSIONS = frozenset({"FAILURE", "TIMED_OUT", "CANCELLED", "STARTUP_FAILURE"})


class Action(Enum):
    MERGE = "merge"
    REBASE = "rebase"
    WAIT = "wait"
    STOP_MERGED = "merged"
    STOP_CLOSED = "closed"
    STOP_THREADS = "threads"
    STOP_FAILED = "failed"
    STOP_STUCK = "stuck"


@dataclass(frozen=True)
class Thread:
    id: str
    resolved: bool
    path: str = ""
    line: int | None = None
    body: str = ""


@dataclass(frozen=True)
class Check:
    name: str
    status: str = ""
    conclusion: str = ""

    @property
    def pending(self) -> bool:
        """Running or queued.

        Keyed on `status`, never on `conclusion`: GitHub reports a running check with
        `conclusion == ""`, which is indistinguishable from a missing field and is bug
        2 in this module's docstring.
        """
        return self.status != "COMPLETED"

    @property
    def broken(self) -> bool:
        return self.conclusion in BAD_CONCLUSIONS


@dataclass(frozen=True)
class Snapshot:
    state: str
    merge_state: str
    threads: tuple[Thread, ...] = ()
    checks: tuple[Check, ...] = ()
    #: True when the thread listing hit the page size, so `threads` is incomplete.
    threads_truncated: bool = False

    @property
    def unresolved(self) -> tuple[Thread, ...]:
        return tuple(t for t in self.threads if not t.resolved)

    @property
    def pending(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.pending)

    @property
    def broken(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.broken)


@dataclass
class Decision:
    action: Action
    detail: str = ""
    threads: tuple[Thread, ...] = field(default_factory=tuple)
    checks: tuple[Check, ...] = field(default_factory=tuple)
    #: True when this poll saw the stuck shape but has not seen it enough times yet.
    stuck: bool = False


def decide(snap: Snapshot, *, allow_merge: bool = True, stuck_polls: int = 0) -> Decision:
    """What to do about `snap`, in priority order.

    The order is the whole point. Threads outrank checks because a human is waiting;
    checks outrank merging because a red PR must not be merged; and a stuck PR is
    reported rather than slept on.
    """
    if snap.state == "MERGED":
        return Decision(Action.STOP_MERGED)
    if snap.state == "CLOSED":
        return Decision(Action.STOP_CLOSED)

    # 1. A reviewer is waiting. This is checked before CI, always.
    if snap.unresolved:
        return Decision(
            Action.STOP_THREADS,
            f"{len(snap.unresolved)} unresolved review thread(s)",
            threads=snap.unresolved,
        )

    # An incomplete thread listing cannot support "nothing unresolved". Stop rather
    # than merge on a view that may be missing the one thread that matters.
    if snap.threads_truncated:
        return Decision(
            Action.STOP_STUCK,
            f"review-thread listing truncated at {THREAD_PAGE_SIZE}; cannot confirm "
            "there are no unresolved threads",
        )

    # 2. Something is red and will not fix itself.
    if snap.broken:
        return Decision(
            Action.STOP_FAILED,
            ", ".join(c.name for c in snap.broken),
            checks=snap.broken,
        )

    if snap.merge_state in NEEDS_REBASE:
        return Decision(Action.REBASE, snap.merge_state)

    if snap.merge_state in MERGEABLE:
        if not allow_merge:
            return Decision(Action.STOP_STUCK, f"mergeable ({snap.merge_state}), --no-merge set")
        return Decision(Action.MERGE, snap.merge_state)

    # 3. BLOCKED with nothing running and nothing unresolved is structural: a required
    #    review, a branch-protection rule, a required check that never reported. No
    #    amount of waiting changes it — but it is also what a PR looks like for a few
    #    seconds after a push, while the previous run's checks read COMPLETED and the new
    #    ones do not exist yet. So it is reported only once it has held for
    #    `STUCK_POLLS` consecutive polls; the caller passes the running count.
    if not snap.pending:
        if stuck_polls + 1 < STUCK_POLLS:
            return Decision(
                Action.WAIT,
                f"{snap.merge_state} with nothing pending "
                f"({stuck_polls + 1}/{STUCK_POLLS} before calling it stuck)",
                stuck=True,
            )
        return Decision(
            Action.STOP_STUCK,
            f"{snap.merge_state} with no pending checks and no unresolved threads, "
            f"for {STUCK_POLLS} consecutive polls",
        )

    return Decision(Action.WAIT, f"{len(snap.pending)} check(s) pending")


# ---------------------------------------------------------------------------
# I/O — deliberately thin, so the logic above stays testable without a network.


def _gh(args: list[str]) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False).stdout.strip()


def fetch(pr: int, repo: str) -> Snapshot | None:
    """One snapshot, or None if the PR could not be read this cycle."""
    raw = _gh(
        [
            "pr",
            "view",
            str(pr),
            "--repo",
            repo,
            "--json",
            "state,mergeStateStatus,statusCheckRollup",
        ]
    )
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    checks = tuple(
        Check(
            name=c.get("name") or c.get("context") or "?",
            status=c.get("status") or "",
            conclusion=c.get("conclusion") or "",
        )
        for c in data.get("statusCheckRollup") or []
        if isinstance(c, dict)
    )

    owner, name = repo.split("/", 1)
    # 100 is GitHub's max page size. `pageInfo` comes back too: a PR with more threads
    # than one page would otherwise let this report "no unresolved threads" for threads
    # it never saw, which is the exact failure this script exists to prevent.
    query = (
        f'{{repository(owner:"{owner}",name:"{name}")'
        f"{{pullRequest(number:{pr}){{reviewThreads(last:{THREAD_PAGE_SIZE}){{"
        "pageInfo{hasPreviousPage} nodes{"
        "id isResolved comments(first:1){nodes{body path line}}}}}}}"
    )
    raw_threads = _gh(["api", "graphql", "-f", f"query={query}"])
    threads: tuple[Thread, ...] = ()
    truncated = False
    if raw_threads:
        try:
            nodes = json.loads(raw_threads)["data"]["repository"]["pullRequest"]["reviewThreads"][
                "nodes"
            ]
        except (json.JSONDecodeError, KeyError, TypeError):
            nodes = []
        threads = tuple(
            Thread(
                id=n["id"],
                resolved=n["isResolved"],
                path=(n["comments"]["nodes"] or [{}])[0].get("path") or "",
                line=(n["comments"]["nodes"] or [{}])[0].get("line"),
                body=(n["comments"]["nodes"] or [{}])[0].get("body") or "",
            )
            for n in nodes
        )

    return Snapshot(
        state=data.get("state") or "",
        merge_state=data.get("mergeStateStatus") or "",
        threads=threads,
        checks=checks,
        threads_truncated=truncated,
    )


def verify_merged(pr: int, repo: str) -> bool:
    """Confirm the merge landed, by asking GitHub rather than trusting the loop.

    A monitor event is not evidence. Squash merges also defeat ancestry checks, so
    this reads `state` back rather than comparing commits.
    """
    return (
        _gh(["pr", "view", str(pr), "--repo", repo, "--json", "state", "--jq", ".state"])
        == "MERGED"
    )


def _report(decision: Decision, pr: int) -> None:
    if decision.action is Action.STOP_THREADS:
        print(f"\n=== PR #{pr}: {decision.detail}\n")
        for t in decision.threads:
            where = f"{t.path}:{t.line}" if t.path else "(PR-level)"
            print(f"THREAD {t.id}\n  {where}\n  {t.body[:800]}\n")
    elif decision.action is Action.STOP_FAILED:
        print(f"\n=== PR #{pr}: checks failed: {decision.detail}")
    elif decision.action is Action.STOP_STUCK:
        print(f"\n=== PR #{pr}: {decision.detail}")


def watch(pr: int, repo: str, interval: int, max_polls: int, allow_merge: bool) -> int:
    stuck_polls = 0
    for poll in range(1, max_polls + 1):
        snap = fetch(pr, repo)
        if snap is None:
            time.sleep(interval)
            continue

        decision = decide(snap, allow_merge=allow_merge, stuck_polls=stuck_polls)
        stuck_polls = stuck_polls + 1 if decision.stuck else 0

        if decision.action is Action.STOP_MERGED:
            ok = verify_merged(pr, repo)
            print(f"PR #{pr} MERGED after {poll} poll(s)" + ("" if ok else " (UNVERIFIED)"))
            return 0 if ok else 1
        if decision.action is Action.STOP_CLOSED:
            print(f"PR #{pr} CLOSED without merging")
            return 1
        if decision.action in (Action.STOP_THREADS, Action.STOP_FAILED, Action.STOP_STUCK):
            _report(decision, pr)
            return 2
        if decision.action is Action.REBASE:
            print(f"PR #{pr} {decision.detail} — rebase needed; not done automatically")
            return 2
        if decision.action is Action.MERGE:
            print(f"PR #{pr} mergeable ({decision.detail}) — squashing")
            _gh(["pr", "merge", str(pr), "--repo", repo, "--squash"])
            time.sleep(min(interval, 10))
            continue

        time.sleep(interval)

    print(f"PR #{pr}: gave up after {max_polls} polls")
    return 3


def _repo_arg(value: str) -> str:
    """`OWNER/REPO`, validated here so a typo is an argparse error, not a traceback."""
    owner, _, name = value.partition("/")
    if not owner or not name or "/" in name:
        raise argparse.ArgumentTypeError(f"expected OWNER/REPO, got {value!r}")
    return value


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("pr", type=int)
    ap.add_argument("--repo", default=DEFAULT_REPO, type=_repo_arg)
    ap.add_argument("--interval", type=int, default=20, help="seconds between polls")
    ap.add_argument("--max-polls", type=int, default=200)
    ap.add_argument("--no-merge", action="store_true", help="report only, never merge")
    args = ap.parse_args()
    return watch(args.pr, args.repo, args.interval, args.max_polls, not args.no_merge)


if __name__ == "__main__":
    sys.exit(main())
