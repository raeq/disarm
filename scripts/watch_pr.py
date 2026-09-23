#!/usr/bin/env python3
"""Watch a pull request to merge, stopping the moment a human needs to act.

Every shepherding loop written by hand in this repo has had at least one of the four
bugs below, and each cost a real wait or a wrong report:

1. **A reviewer comment waited on CI.** A loop that acts on checks before it looks at
   review threads will sit through a whole CI run before noticing the PR is blocked on
   a comment. Here every cycle fetches threads and checks into one `Snapshot`, and
   `decide()` ranks unresolved threads above check state and above merging. The
   priority is in `decide()`, which is where it can be tested. The order of the two
   network calls in `fetch()` matters too, though this used to say it did not: the PR
   view is read before the threads, so a review that arrives between the two reads
   brings its threads with it. Read the other way round, `--await-review` can see the
   review and miss its thread (WatchPR model, `formal/tla/WatchPR`).

2. **`conclusion` is `""` for a running check, not `null`.** A loop that waits for
   `conclusion == null` to clear exits while checks are still in flight and then reports
   the running ones as failures. Pending is `status != "COMPLETED"`.

3. **`BLOCKED` with nothing pending and nothing unresolved span forever.** That state
   means something structural — a required review, a branch-protection rule — and no
   amount of waiting fixes it. It is a stop condition, not a sleep.

4. **Waiting for every check to finish never merges.** `UNSTABLE` and `HAS_HOOKS` are
   mergeable; a non-required check still running is not a reason to hold. Merge on any
   mergeable state and let the required set gate it.

On a repo whose branch protection does not require conversation resolution, a green PR
is mergeable before its reviewer has said anything, and a thread that has not been
written yet cannot be unresolved. `--await-review` emulates the rule (#987): no merge
while a review request is pending, nor before someone other than the author has
reviewed, and never while a reviewer's latest review requests changes. This repo
requires resolution, so the default leaves it to GitHub.

What no client can close, and the model shows: a review request, thread or
change request that arrives between the last read and the merge still gets through
`--await-review`; only requiring conversation resolution on the server closes that.
A review of an earlier head still counts after a push; to require one per head, turn on
"dismiss stale pull request approvals". And a check that is not *required* does not hold
the merge while it runs, by design (point 4), so the checks that matter must be required.

The merge names the head it evaluated (`--match-head-commit`), so a push after the read
is refused rather than merged unseen, and a refused merge is reported and stops the
watcher instead of being retried blind.

The decision is a pure function of a `Snapshot`, so it is unit-tested in
`tests/test_watch_pr.py` without touching the network. The I/O layer around it is thin
on purpose.

Exit codes:
    0  merged (re-read from GitHub to confirm, not trusted from the loop)
    1  closed without merging, or reported merged but not confirmed
    2  a human is needed: an unresolved review thread, a failed check, a structural
       block, a stale branch, a thread listing too long to read in one page, a merge
       GitHub refused twice (its reason is printed), or, with --await-review, a
       reviewer whose latest review requests changes
    3  gave up after --max-polls, including while awaiting a review that never came

Usage:
    python scripts/watch_pr.py 912
    python scripts/watch_pr.py 912 --repo raeq/disarm --interval 20 --max-polls 200
    python scripts/watch_pr.py 912 --no-merge      # report only, never merge
    python scripts/watch_pr.py 12 --repo raeq/ibook2epub --await-review
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

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

#: How many consecutive polls must show the SAME failing checks before they are reported.
#: One is not enough: for a few seconds after a push the rollup still carries the previous
#: run's conclusions, so a failure that has already been fixed reads as a live one. Seen
#: on #926, where the watcher stopped on a `Lint & format` failure belonging to the SHA
#: before the fix.
FAILURE_POLLS = 2

#: How many consecutive polls must show the stuck shape before it is reported. One is
#: not enough: for a few seconds after a push GitHub reports BLOCKED with the previous
#: run's checks COMPLETED and the new ones not yet created, which is indistinguishable
#: from a structural block in a single snapshot.
STUCK_POLLS = 3

#: Consecutive refused merges before the refusal is the stop reason (WatchPR model, F3).
MERGE_REJECTIONS = 2

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
    #: The PR's author, whose own reviews — a reply to a thread is one — do not count.
    author: str = ""
    #: Reviewers asked and not yet answered.
    requested: tuple[str, ...] = ()
    #: Who has submitted a review, the author included.
    reviewed_by: tuple[str, ...] = ()
    #: The head commit the rollup describes (`headRefOid`), "" when unknown.
    head: str = ""
    #: Non-authors whose latest submitted review requests changes.
    changes_requested: tuple[str, ...] = ()

    @property
    def unresolved(self) -> tuple[Thread, ...]:
        return tuple(t for t in self.threads if not t.resolved)

    @property
    def pending(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.pending)

    @property
    def broken(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.broken)

    @property
    def awaited(self) -> str:
        """Why a review is still outstanding, or "" when it is not.

        A pending request is the reviewer asked and not yet answered. No review at all
        covers the second after a PR opens, before the request exists.
        """
        if self.requested:
            return f"awaiting review from {', '.join(self.requested)}"
        if not any(login != self.author for login in self.reviewed_by):
            return "awaiting a first review from someone other than the author"
        return ""


@dataclass
class Decision:
    action: Action
    detail: str = ""
    threads: tuple[Thread, ...] = field(default_factory=tuple)
    checks: tuple[Check, ...] = field(default_factory=tuple)
    #: True when this poll saw the stuck shape but has not seen it enough times yet.
    stuck: bool = False
    #: The sorted failing check names this poll saw, "" when none.
    broken_names: str = ""
    #: How many consecutive polls have now shown `broken_names`, counting this one.
    failure_seen: int = 0


def decide(
    snap: Snapshot,
    *,
    allow_merge: bool = True,
    await_review: bool = False,
    stuck_polls: int = 0,
    failure_polls: int = 0,
    last_broken: str = "",
) -> Decision:
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

    # 2. Something is red and will not fix itself — once the same names have been red on
    #    consecutive polls. A single sighting can be the previous SHA's rollup.
    if snap.broken:
        names = ", ".join(sorted(c.name for c in snap.broken))
        # Count THIS sighting. Deriving the running total here rather than in the caller
        # is what fixes the off-by-one the #928 review found: the caller only incremented
        # once the current names matched the previous ones, so a first sighting never
        # counted itself and the loop needed FAILURE_POLLS + 1 reads.
        seen = failure_polls + 1 if names == last_broken else 1
        if seen < FAILURE_POLLS:
            return Decision(
                Action.WAIT,
                f"red: {names} ({seen}/{FAILURE_POLLS} before reporting)",
                checks=snap.broken,
                broken_names=names,
                failure_seen=seen,
            )
        return Decision(
            Action.STOP_FAILED,
            names,
            checks=snap.broken,
            broken_names=names,
            failure_seen=seen,
        )

    if snap.merge_state in NEEDS_REBASE:
        return Decision(Action.REBASE, snap.merge_state)

    # A review still to come (#987). Below everything actionable now, above merging and
    # above the stuck report: a review on its way is neither mergeable nor structural.
    if await_review and snap.changes_requested:
        return Decision(
            Action.STOP_STUCK, f"changes requested by {', '.join(snap.changes_requested)}"
        )
    if await_review and snap.awaited:
        return Decision(Action.WAIT, snap.awaited)

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


#: The review states that mean a review has arrived and still stands (#1000).
#:
#: `--await-review` waits for a review to ARRIVE, so a review that has not been submitted
#: must not satisfy it. `PENDING` is one begun and not sent — GitHub shows it only to its
#: author, so it leaks when the watcher's `gh` identity is not the PR author's, and your
#: own half-written review would release the merge you are waiting on. `DISMISSED` was
#: submitted and withdrawn. An allow-list rather than a block-list, so a state this code
#: has never seen keeps the gate closed: for a merge gate, the safe mistake is to wait.
SUBMITTED_REVIEW_STATES = frozenset({"APPROVED", "CHANGES_REQUESTED", "COMMENTED"})


def _changes_requested(data: dict[str, Any]) -> tuple[str, ...]:
    """Non-authors whose latest submitted review requests changes.

    `--await-review` released on any review by someone other than the author, so a
    CHANGES_REQUESTED review with no inline thread opened the gate and the PR merged
    (WatchPR model, F5). The latest review per reviewer decides, so a later approval
    clears an earlier request, as it does on GitHub.
    """
    author = (data.get("author") or {}).get("login") or ""
    latest: dict[str, str] = {}
    for r in data.get("reviews") or []:
        if isinstance(r, dict) and r.get("state") in SUBMITTED_REVIEW_STATES:
            latest[(r.get("author") or {}).get("login") or "?"] = r["state"]
    return tuple(who for who, s in latest.items() if s == "CHANGES_REQUESTED" and who != author)


def _reviews(data: dict[str, Any]) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """The author, the pending requests and the reviewers, from `gh pr view --json`.

    A requested reviewer carries a `login` (a user or a bot) or a `slug` (a team). One
    carrying neither still counts, as "?": an unnamed wait is still a wait.
    """
    author = (data.get("author") or {}).get("login") or ""
    requested = tuple(
        r.get("login") or r.get("slug") or r.get("name") or "?"
        for r in data.get("reviewRequests") or []
        if isinstance(r, dict)
    )
    reviewed_by = tuple(
        (r.get("author") or {}).get("login") or "?"
        for r in data.get("reviews") or []
        if isinstance(r, dict) and r.get("state") in SUBMITTED_REVIEW_STATES
    )
    return author, requested, reviewed_by


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
            "state,mergeStateStatus,statusCheckRollup,author,reviewRequests,reviews,headRefOid",
        ]
    )
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    # The latest run of each check, which is what branch protection evaluates. A run
    # superseded on the same head can stay in the rollup as CANCELLED, and read as a
    # failure on a PR GitHub calls CLEAN (WatchPR model, F4). Keyed by workflow as well
    # as name: two workflows may both have a job called `build`, and a newer one must
    # not hide the other's failure.
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    rollup = [c for c in data.get("statusCheckRollup") or [] if isinstance(c, dict)]
    for c in sorted(rollup, key=lambda c: c.get("startedAt") or ""):
        latest[(c.get("workflowName") or "", c.get("name") or c.get("context") or "?")] = c
    checks = tuple(
        Check(
            name=name,
            status=c.get("status") or "",
            conclusion=c.get("conclusion") or "",
        )
        for (_, name), c in latest.items()
    )
    author, requested, reviewed_by = _reviews(data)

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
    # A thread listing that could not be read is a failed read, never "no threads".
    # `_gh` ignores the exit status, so an error reached here as empty output or a body
    # without `data`, and both read as a PR with no threads: a merge could go through
    # with a thread open (WatchPR model, `formal/tla/WatchPR`, F1). The poll now counts
    # as failed, which also keeps it out of the stuck streak.
    if not raw_threads:
        return None
    try:
        review_threads = json.loads(raw_threads)["data"]["repository"]["pullRequest"][
            "reviewThreads"
        ]
        nodes = review_threads["nodes"]
        # The query has always asked for this and nothing read it, so `truncated`
        # stayed False and the guard in `decide()` could not fire on real data.
        # `last:` pages from the end, so older threads are what `hasPreviousPage`
        # reports as unseen.
        truncated = bool((review_threads.get("pageInfo") or {}).get("hasPreviousPage"))
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
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
        author=author,
        requested=requested,
        reviewed_by=reviewed_by,
        head=data.get("headRefOid") or "",
        changes_requested=_changes_requested(data),
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


def watch(
    pr: int,
    repo: str,
    interval: int,
    max_polls: int,
    allow_merge: bool,
    await_review: bool = False,
) -> int:
    stuck_polls = 0
    failure_polls = 0
    last_broken = ""
    rejected = 0
    for poll in range(1, max_polls + 1):
        snap = fetch(pr, repo)
        if snap is None:
            # A failed read is not a sighting. Keeping the streak across it would let two
            # observations separated by a network blip count as consecutive, which is the
            # guarantee the threshold exists to provide (#922 review).
            stuck_polls = 0
            failure_polls = 0
            last_broken = ""
            time.sleep(interval)
            continue

        decision = decide(
            snap,
            allow_merge=allow_merge,
            await_review=await_review,
            stuck_polls=stuck_polls,
            failure_polls=failure_polls,
            last_broken=last_broken,
        )
        stuck_polls = stuck_polls + 1 if decision.stuck else 0
        # `decide` already counted this sighting, including the first one.
        failure_polls = decision.failure_seen
        last_broken = decision.broken_names

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
            # Pin the head that was evaluated: a push after the read would otherwise be
            # merged unseen (WatchPR model, F2). And read the answer: a refused merge was
            # retried blind every poll until --max-polls gave up with no reason (F3).
            pin = ["--match-head-commit", snap.head] if snap.head else []
            res = subprocess.run(
                ["gh", "pr", "merge", str(pr), "--repo", repo, "--squash", *pin],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                rejected += 1
                print(f"PR #{pr} merge refused: {res.stderr.strip()}")
                if rejected >= MERGE_REJECTIONS:
                    return 2
            else:
                rejected = 0
            time.sleep(min(interval, 10))
            continue
        rejected = 0

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
    ap.add_argument(
        "--await-review",
        action="store_true",
        help="hold the merge until requested reviews are in, for a repo that does not "
        "require conversation resolution",
    )
    args = ap.parse_args()
    return watch(
        args.pr,
        args.repo,
        args.interval,
        args.max_polls,
        not args.no_merge,
        await_review=args.await_review,
    )


if __name__ == "__main__":
    sys.exit(main())
