# WatchPR: a TLA+ model of `scripts/watch_pr.py`

This models the merge protocol of `scripts/watch_pr.py`, together with the GitHub pull
request it polls, which changes while the watcher is reading it. TLC checks the model for
safety and liveness. Each counterexample was replayed against the real script as a
failing unit test and then classified. Line numbers refer to `scripts/watch_pr.py` at
`bec93cf`.

> **Status.** F1-F5 and F8 are fixed in the pull request that added this model; the
> replays live on in `tests/test_watch_pr_protocol.py`, where 9 of them failed against
> the script as it was. F4's fix keys the latest run by workflow as well as name, not by
> name as first proposed, so one workflow's job cannot hide another's failure. F6 is
> documented in the script and in CONTRIBUTING rather than changed: requiring a review
> of every head would hold a merge forever after a nit fix pushed on top of an approval,
> and GitHub's "dismiss stale pull request approvals" setting does it on the server.
> The counterexample traces are not committed; `run_tlc.py` regenerates them.

| file | what |
|---|---|
| `WatchPR.tla` | the spec: watcher, environment, GitHub's merge rules, properties |
| `run_tlc.py` | runs every experiment and prints the results table (one verdict and one shortest trace per property) |
| `cfg/*.cfg` | the generated configurations (one per row of the results table) |
| `traces/*.txt` | written by `run_tlc.py`: the full TLC output of every violated property (not committed) |
| `trace_summary.py` | shrinks a trace to one line per step: the action and what changed |
| `tests/test_watch_pr_protocol.py` | the counterexamples replayed against the real script, in the suite |

```bash
TLA2TOOLS=/path/to/tla2tools.jar python3 formal/tla/WatchPR/run_tlc.py [name-filter]
python3 formal/tla/WatchPR/trace_summary.py formal/tla/WatchPR/traces/<run>.txt
python3 -m pytest tests/test_watch_pr_protocol.py -n 0
```

TLC 2026.09.22 (rev 35d40c9), 4 workers, `-deadlock` (a stopped watcher facing a closed PR has no next step, which is not an error).

## The model

Two processes interleave with no constraints. Each watcher step is atomic, and so is each
environment step.

### The watcher: one poll is five atomic steps

| step | model | code |
|---|---|---|
| `R1` | start a poll, bounded by `MaxPolls` (0 means unbounded, used for liveness); first read | `watch()` :442, :488-489 |
| `ReadView` | `gh pr view --json state,mergeStateStatus,statusCheckRollup,author,reviewRequests,reviews`. This is one GraphQL query, so its fields agree with each other, but they describe `viewHead`. It can fail and return None | `fetch()` :329-356, :340-345 |
| `ReadThreads` | the `reviewThreads(last:100)` query, with three outcomes: `ok`; `trunc` (`hasPreviousPage`: the visible page may miss the unresolved threads); `fail` (empty stdout, non-JSON, or `data:null`/`pullRequest:null`). A `fail` falls through to `threads=()` and `truncated=False` | `fetch()` :362-393 |
| `DecideStep` | `decide()`, copied branch for branch into `Decide`, together with the counter updates | :190-285, :462-465 |
| `MergeStep` | `gh pr merge N --squash` is judged by GitHub against the state at the moment of the merge (`ServerAccepts`). The exit status is ignored and the watcher polls again | :480-484, `_gh` :292-293 |
| `FailedPoll` | a read that returned None resets `stuck_polls`, `failure_polls` and `last_broken` | :444-452 |

The streak counters are modelled exactly. `lastBroken` holds the *number* of broken
entries rather than the joined names, because every entry in the model has the same name
`X` and so the two carry the same information. `STUCK_POLLS = 3` and `FAILURE_POLLS = 2`
match :81 and :87.

### The environment: GitHub, CI and the people involved

- `Push`: a new head, whose check X starts as `none` (not created yet). The run on the
  previous head is `cancelled`, because `ci.yml:11-13` sets `concurrency: cancel-in-progress`.
  A push may also rebase, which clears `behind`.
- `Sync` (`EnvLag`): `gh pr view` keeps reporting the old head for a while after a push
  (`viewHead < head`). This is the eventual consistency behind #921 and #926.
- `CreateChecks`, `Complete` (to success or failure), `Rerun` (red back to pending).
- `Dup` (`EnvGhost`): a second run of the same workflow on the same head, for example after
  a reopen or a re-trigger. The first run is cancelled by the concurrency group and stays
  in the rollup as `X: CANCELLED`, next to the live `X`.
- `OpenThread`, `ResolveThread`, `Overflow` (more threads than one page).
- `RequestReview`; `SubmitReview(comment|changes, withThread)`, which clears the request
  and can add an inline thread in the same atomic event (this is how Copilot reviews
  arrive); `DismissReview`.
- `BaseMoves` (`Strict`, which leads to `BEHIND`), and `CloseOrMergeElsewhere`.
- `EnvBetweenReads` and `EnvInWindow` switch off environment steps between the two reads,
  or between the last read and the merge. This lets a violation be traced to the window
  that causes it.

`MS(h)` gives the mergeStateStatus GitHub reports for commit `h`. `ServerAccepts` is
branch protection applied to the actual head at merge time: required X is green, no
unresolved threads (when conversation resolution is required), the branch is up to date,
the head matches `--match-head-commit` (with `FixMatchHead`), and `SquashRejected` is off.

The configurations used:

- `DISARM` is this repository: X is required (the roll-up "All checks passed", #583),
  conversation resolution is required, and branches must be up to date.
- `AWAIT` is a repository run with `--await-review`, where X is required but
  conversation resolution is not (#987).
- `AWAIT_NOREQ` is the same with no required check.

The bounds are `MaxHead = 3` (two pushes), `MaxUnres = 1` and `MaxReadFails = 2`. The
`AWAIT` configurations use `MaxReadFails = 1` and switch off base moves, overflow and
close. Those behaviours are covered by the `DISARM` runs, and the review state already
multiplies the state space: about 5M distinct states, against 1.9M for `DISARM`.

Each `Fix*` constant switches on one proposed fix. That way every finding is checked
twice: it is VIOLATED on the current code and it HOLDS with the fix.

### Properties

| id | property | meaning |
|---|---|---|
| S1 | `IssueEvaluatedHead` | the watcher never *sends* a merge while the head differs from the one it evaluated |
| S2 | `IssueGreen` | ... nor while the head's check is not green |
| S3 | `MergedEvaluatedHead` | a merge that *landed* was of the evaluated head |
| S3b | `UnevaluatedNotRed` | a head the watcher did *not* evaluate is never merged red (the head race on its own) |
| S4 | `MergedNotRed` | a merge that landed was not of a red head |
| S4b | `MergedCompletedGreen` | a merge that landed was of a completed green head |
| S5 | `MergedNoUnresolved` | a merge that landed had no unresolved thread at merge time |
| S6 | `ThreadGateSound` | the thread gate is passed only on a complete (`ok`) listing: a failed or truncated read never counts as "no threads" |
| S6b | `StreakFromCompleteReads` | a stuck or failure sighting counts only on a complete read (CONTRIBUTING: "A poll whose read failed does not count towards the streak") |
| S7 | `AwaitContract` | `--await-review`: no merge while a request is pending, and none before a non-author review stands |
| S8 | `AwaitNoChangesRequested` | (intent) `--await-review` never merges over a standing CHANGES_REQUESTED |
| S9 | `AwaitReviewedThisHead` | (intent) `--await-review` never merges a head that no reviewer saw |
| S10 | `NoStaleFailStop` | STOP_FAILED only when the latest run of X on the PR's *actual* head was red at the time of the read |
| S11 | `NoFalseStuck` | STOP_STUCK never fires while the current head's checks simply have not been created yet |
| L1 | `EventuallyStops` | `<>[]Good => <>(pc = "done")`, under weak fairness of the watcher with `MaxPolls = 0` |
| L2 | `EventuallyMerges` | `[]((pc = "r1" /\ []Good) => <>(done by STOP_MERGED or STOP_NOMERGE))`: once a poll *starts* with the PR good forever after, the watcher merges. The first attempt, `<>[]Good => <>merged`, was too strong. TLC showed a poll that read a thread which was resolved before `decide()`, and stopping with STOP_THREADS on that is correct |

`Good` means the PR is open, the view is in sync, X is green on the head with no ghost
run, there are no threads, no overflow and no `BEHIND`, and (with `--await-review`) a
review stands and no request is pending.

S1 and S2 are about the *client*. They are expected to fail whenever the environment can
act after the last read (every configuration except the `*_quiet` ones), because no
client can close the gap between reading a PR and merging it. They show that the window
exists. S3 to S5 are what counts: whether a merge through that window can land.

## TLC results

One TLC run per verdict, except that invariants which HOLD share their final run (see
`run_tlc.py`, `experiment()`). Each row's single-property configuration is in
`cfg/<experiment>__<property>.cfg`, and every VIOLATED row has its trace in
`traces/<experiment>__<property>.txt`. For a VIOLATED row the depth is the length of
the counterexample; for a HOLDS row it is the diameter of the complete state graph. With 4
workers the search order is not deterministic, so a VIOLATED row's state count, and
occasionally its depth (by one step), can differ from run to run. HOLDS rows are exact.

Three properties were added to `WatchPR.tla` after the first batch of runs:
`UnevaluatedNotRed`, `StreakFromCompleteReads`, and the final form of `EventuallyMerges`.
The rows that use them (`await_noreq_*`, `disarm_streak_*`, `live_*`) were re-run against
the committed spec. The other rows are unaffected, because adding a property does not
change the behaviours.

| experiment | property | verdict | states generated | distinct | depth |
|---|---|---|---|---|---|
| disarm_current | ThreadGateSound | VIOLATED | 1596 | 380 | 4 |
| disarm_current | IssueEvaluatedHead | VIOLATED | 53603 | 13611 | 8 |
| disarm_current | IssueGreen | VIOLATED | 59949 | 15388 | 8 |
| disarm_current | MergedEvaluatedHead | VIOLATED | 286599 | 75963 | 10 |
| disarm_current | NoFalseStuck | VIOLATED | 561283 | 149665 | 11 |
| disarm_current | TypeOK | HOLDS | 7937290 | 1880208 | 26 |
| disarm_current | MergedNotRed | HOLDS | 7937290 | 1880208 | 26 |
| disarm_current | MergedCompletedGreen | HOLDS | 7937290 | 1880208 | 26 |
| disarm_current | MergedNoUnresolved | HOLDS | 7937290 | 1880208 | 26 |
| disarm_current | AwaitContract | HOLDS | 7937290 | 1880208 | 26 |
| disarm_current | AwaitNoChangesRequested | HOLDS | 7937290 | 1880208 | 26 |
| disarm_current | AwaitReviewedThisHead | HOLDS | 7937290 | 1880208 | 26 |
| disarm_current | NoStaleFailStop | HOLDS | 7937290 | 1880208 | 26 |
| disarm_fixed | IssueEvaluatedHead | VIOLATED | 39978 | 9831 | 7 |
| disarm_fixed | IssueGreen | VIOLATED | 54473 | 13699 | 8 |
| disarm_fixed | NoFalseStuck | VIOLATED | 245537 | 63915 | 10 |
| disarm_fixed | MergedEvaluatedHead | HOLDS | 7152023 | 1688358 | 26 |
| disarm_fixed | MergedNotRed | HOLDS | 7152023 | 1688358 | 26 |
| disarm_fixed | MergedCompletedGreen | HOLDS | 7152023 | 1688358 | 26 |
| disarm_fixed | MergedNoUnresolved | HOLDS | 7152023 | 1688358 | 26 |
| disarm_fixed | ThreadGateSound | HOLDS | 7152023 | 1688358 | 26 |
| disarm_fixed | AwaitContract | HOLDS | 7152023 | 1688358 | 26 |
| disarm_fixed | AwaitNoChangesRequested | HOLDS | 7152023 | 1688358 | 26 |
| disarm_fixed | AwaitReviewedThisHead | HOLDS | 7152023 | 1688358 | 26 |
| disarm_fixed | NoStaleFailStop | HOLDS | 7152023 | 1688358 | 26 |
| disarm_streak_current | StreakFromCompleteReads | VIOLATED | 1961 | 426 | 5 |
| disarm_streak_fixed | StreakFromCompleteReads | HOLDS | 6642314 | 1569468 | 26 |
| disarm_lag | NoStaleFailStop | VIOLATED | 47645 | 14441 | 8 |
| disarm_lag | NoFalseStuck | VIOLATED | 153679 | 47748 | 11 |
| disarm_ghost | NoStaleFailStop | VIOLATED | 70526 | 22675 | 9 |
| disarm_ghost_fixdedup | NoStaleFailStop | HOLDS | 4339640 | 1299003 | 26 |
| await_current | ThreadGateSound | VIOLATED | 2357 | 396 | 4 |
| await_current | AwaitNoChangesRequested | VIOLATED | 171090 | 23769 | 7 |
| await_current | MergedNoUnresolved | VIOLATED | 193735 | 26666 | 7 |
| await_current | IssueEvaluatedHead | VIOLATED | 479918 | 62652 | 8 |
| await_current | IssueGreen | VIOLATED | 367363 | 49324 | 8 |
| await_current | AwaitContract | VIOLATED | 412414 | 54199 | 8 |
| await_current | AwaitReviewedThisHead | VIOLATED | 1357348 | 164817 | 9 |
| await_current | MergedEvaluatedHead | VIOLATED | 2768223 | 308587 | 10 |
| await_current | NoFalseStuck | VIOLATED | 5058164 | 520482 | 11 |
| await_current | MergedNotRed | HOLDS | 81252368 | 5036772 | 26 |
| await_current | MergedCompletedGreen | HOLDS | 81252368 | 5036772 | 26 |
| await_current | NoStaleFailStop | HOLDS | 81252368 | 5036772 | 26 |
| await_fixed | MergedNoUnresolved | VIOLATED | 467107 | 60807 | 8 |
| await_fixed | IssueEvaluatedHead | VIOLATED | 421665 | 54176 | 8 |
| await_fixed | AwaitContract | VIOLATED | 422098 | 54229 | 8 |
| await_fixed | IssueGreen | VIOLATED | 451745 | 58253 | 8 |
| await_fixed | AwaitNoChangesRequested | VIOLATED | 412170 | 53446 | 8 |
| await_fixed | NoFalseStuck | VIOLATED | 5313957 | 534695 | 11 |
| await_fixed | MergedEvaluatedHead | HOLDS | 71161232 | 4468964 | 27 |
| await_fixed | MergedNotRed | HOLDS | 71161232 | 4468964 | 27 |
| await_fixed | MergedCompletedGreen | HOLDS | 71161232 | 4468964 | 27 |
| await_fixed | ThreadGateSound | HOLDS | 71161232 | 4468964 | 27 |
| await_fixed | AwaitReviewedThisHead | HOLDS | 71161232 | 4468964 | 27 |
| await_fixed | NoStaleFailStop | HOLDS | 71161232 | 4468964 | 27 |
| await_current_quiet | ThreadGateSound | VIOLATED | 843 | 349 | 4 |
| await_current_quiet | MergedNoUnresolved | VIOLATED | 18249 | 6015 | 7 |
| await_current_quiet | AwaitNoChangesRequested | VIOLATED | 13721 | 4617 | 7 |
| await_current_quiet | AwaitReviewedThisHead | VIOLATED | 59752 | 18247 | 9 |
| await_current_quiet | NoFalseStuck | VIOLATED | 186042 | 49284 | 11 |
| await_current_quiet | IssueEvaluatedHead | HOLDS | 500442 | 114078 | 20 |
| await_current_quiet | IssueGreen | HOLDS | 500442 | 114078 | 20 |
| await_current_quiet | MergedEvaluatedHead | HOLDS | 500442 | 114078 | 20 |
| await_current_quiet | MergedNotRed | HOLDS | 500442 | 114078 | 20 |
| await_current_quiet | MergedCompletedGreen | HOLDS | 500442 | 114078 | 20 |
| await_current_quiet | AwaitContract | HOLDS | 500442 | 114078 | 20 |
| await_current_quiet | NoStaleFailStop | HOLDS | 500442 | 114078 | 20 |
| await_fixed_quiet | NoFalseStuck | VIOLATED | 149086 | 38275 | 12 |
| await_fixed_quiet | IssueEvaluatedHead | HOLDS | 362375 | 84957 | 22 |
| await_fixed_quiet | IssueGreen | HOLDS | 362375 | 84957 | 22 |
| await_fixed_quiet | MergedEvaluatedHead | HOLDS | 362375 | 84957 | 22 |
| await_fixed_quiet | MergedNotRed | HOLDS | 362375 | 84957 | 22 |
| await_fixed_quiet | MergedCompletedGreen | HOLDS | 362375 | 84957 | 22 |
| await_fixed_quiet | MergedNoUnresolved | HOLDS | 362375 | 84957 | 22 |
| await_fixed_quiet | ThreadGateSound | HOLDS | 362375 | 84957 | 22 |
| await_fixed_quiet | AwaitContract | HOLDS | 362375 | 84957 | 22 |
| await_fixed_quiet | AwaitNoChangesRequested | HOLDS | 362375 | 84957 | 22 |
| await_fixed_quiet | AwaitReviewedThisHead | HOLDS | 362375 | 84957 | 22 |
| await_fixed_quiet | NoStaleFailStop | HOLDS | 362375 | 84957 | 22 |
| await_threadsfirst_tailquiet | MergedNoUnresolved | VIOLATED | 25977 | 4755 | 7 |
| await_viewfirst_tailquiet | MergedNoUnresolved | HOLDS | 15332448 | 2949838 | 26 |
| await_noreq_current | MergedCompletedGreen | VIOLATED | 55218 | 8128 | 6 |
| await_noreq_current | MergedEvaluatedHead | VIOLATED | 157910 | 22104 | 7 |
| await_noreq_current | MergedNotRed | VIOLATED | 178881 | 25269 | 7 |
| await_noreq_current | UnevaluatedNotRed | VIOLATED | 1348824 | 168090 | 9 |
| await_noreq_fixmatchhead | MergedCompletedGreen | VIOLATED | 62582 | 9111 | 6 |
| await_noreq_fixmatchhead | MergedNotRed | VIOLATED | 203195 | 28821 | 7 |
| await_noreq_fixmatchhead | MergedEvaluatedHead | HOLDS | 69811356 | 3664560 | 23 |
| await_noreq_fixmatchhead | UnevaluatedNotRed | HOLDS | 69811356 | 3664560 | 23 |
| live_disarm_current | EventuallyStops | HOLDS | 3010370 | 750942 | 23 |
| live_disarm_current | EventuallyMerges | HOLDS | 3010370 | 750942 | 24 |
| live_disarm_rejected | EventuallyStops | VIOLATED | 139108 | 38769 | 9 |
| live_disarm_rejected_fix | EventuallyStops | HOLDS | 3240232 | 809058 | 23 |
| live_await_current | EventuallyStops | HOLDS | 81252368 | 5036772 | 26 |
| live_await_current | EventuallyMerges | HOLDS | 81252368 | 5036772 | 26 |
| live_await_fixed | EventuallyStops | HOLDS | 71161232 | 4468964 | 27 |
| live_await_fixed | EventuallyMerges | HOLDS | 71161232 | 4468964 | 27 |

## Findings

Every repro test below failed against the script at `bec93cf`, and each finding is
described as it was found there. The fixes that were adopted are listed under *Status*
above. Each trace can be read with `trace_summary.py traces/<row>.txt` once `run_tlc.py`
has written it.

### F1: a failed thread query reads as "no unresolved threads" (real bug)

*Properties:* `ThreadGateSound` (VIOLATED, depth 4), `MergedNoUnresolved` in `AWAIT`
(VIOLATED, depth 7). Both HOLD with `FixThreadRead`, and `MergedNoUnresolved` HOLDS in
`await_fixed_quiet`.

*Trace (`await_current__MergedNoUnresolved`):* X goes green. Copilot submits a review that
opens a thread. The watcher reads the view (reviewed, no request pending, CLEAN) and then
the thread query *fails*. `decide()` sees nothing unresolved and returns MERGE. GitHub has
no conversation-resolution rule here, so the merge goes through with the thread still open.

*Code:* `fetch()` :368-383. An empty stdout skips the `if raw_threads:` block. A body that
is not JSON, or that carries `{"data": null}` or `pullRequest: null` with `errors`, is
caught by the `except` at :382, which sets `nodes = []`. Either way the result is
`threads=()` and `truncated=False`. `_gh` ignores the exit status (:292-293), so an error
body `gh` writes to stdout is parsed like an answer. The truncation guard at :220 does not
help, because nothing marks the listing as incomplete.

*Repro:* `test_f1_a_failed_thread_query_never_reads_as_no_threads[4 variants]`. Against
the current code it fails with `Snapshot(... threads=(), threads_truncated=False,
reviewed_by=('copilot-pull-request-reviewer',))` and `decide(...)` returns `Action.MERGE`.

*F1b, a side effect:* the same failed read still counts as a *sighting* for the stuck and
failure streaks. `StreakFromCompleteReads` is VIOLATED in `disarm_streak_current` at depth
5: a thread read fails and `stuck_polls` becomes 1. It HOLDS in `disarm_streak_fixed`.
CONTRIBUTING says "A poll whose read failed does not count towards the streak", but that
is true only for the PR view.
`test_f1b_a_failed_thread_read_does_not_count_towards_the_stuck_streak` fails with
`assert 2 == 3`: the watcher stopped as stuck.

*Severity:*
- **High** under `--await-review`. This is exactly the #987 failure the flag exists to
  prevent, reached through the I/O layer.
- **Low** in this repo. Conversation resolution rejects the merge on GitHub's side, the
  rejection is invisible (see F3), and the next good read reports STOP_THREADS.

*Fix:* treat an unreadable listing as a failed read. Return `None` when `raw_threads` is
empty and in the `except` (2 lines). The existing None path then resets the streaks (:444-452).

### F2: `gh pr merge` does not pin the evaluated head (real bug; mitigated by branch protection here)

*Properties:* `IssueEvaluatedHead` and `IssueGreen` are VIOLATED wherever the
environment can act after the last read (the window exists). `MergedEvaluatedHead` is
VIOLATED in `disarm_current`, `await_current` and `await_noreq_current`, and
`UnevaluatedNotRed` is VIOLATED in `await_noreq_current`. With `FixMatchHead`, both HOLD
in every configuration where they were checked (`disarm_fixed`, `await_fixed`,
`await_fixed_quiet`, `await_noreq_fixmatchhead`).

*Trace (`await_noreq_current__UnevaluatedNotRed`, depth 9):* the watcher reads head 1 as
reviewed and UNSTABLE (X is running and not required, so UNSTABLE counts as mergeable).
Head 2 is pushed between the two reads, and its X starts and fails while `decide()`
returns MERGE. `gh pr merge --squash` then merges head 2, which is red and was never
evaluated. In this repo's configuration (`disarm_current__MergedEvaluatedHead`, depth 10) the only way
through is for the new head's required check to complete green inside the window. That
is harmless, since the head is green and has no threads, and implausible in time, since CI
takes minutes and the window is about a second. Everything else is refused server-side.

*Code:* :482 `_gh(["pr", "merge", str(pr), "--repo", repo, "--squash"])` passes no SHA.
The view at :337 does not request `headRefOid`, so the watcher cannot name the head it
evaluated.

*Repro:* `test_f2_a_head_pushed_after_the_read_is_not_merged` fails with `merged ['bbb'],
but only 'aaa' was evaluated`. `test_f2_server_side_mitigation_in_this_repo` passes. It
shows what happens after a rejection in this repo: no crash and no report. `_gh` swallows
the refusal, the next poll reads `bbb` as red, and after FAILURE_POLLS polls the watcher
stops with exit 2 "checks failed".

*Severity:*
- **High** on a `--await-review` repository with no required check. The watcher can merge
  a red, unreviewed head.
- **Low** here.

*Fix:* request `headRefOid` in the view, keep it on the `Snapshot`, and pass
`--match-head-commit <sha>`. GitHub then refuses the merge if the head has moved.

### F3: a refused merge is invisible, and the watcher retries it blind (real bug; liveness)

*Properties:* `EventuallyStops` is VIOLATED in `live_disarm_rejected`: a lasso
MERGE, refused, MERGE, ... with `--max-polls` unbounded. It HOLDS with `FixMergeReject`.

*Code:* `_gh` (:292-293) returns stdout only and ignores `returncode` and stderr. After
:482 the loop sleeps and polls again (:483-484). A merge GitHub refuses every time, for
example because squash is disabled, a merge queue is required, or a ruleset is invisible
to `gh`'s preflight, is re-sent on every poll. With the real `--max-polls` the run ends
with "gave up" and exit 3, which is documented as "gave up after --max-polls". The reason
is printed nowhere. With the defaults that is 200 blind attempts over about 33 minutes.

*Repro:* `test_f3_a_rejected_merge_is_reported_not_retried_blind` fails with `rc=3, 5
blind merge attempts; the refusal was never shown`.

*Severity:* **Medium-low**. Nothing unsafe happens, but the report is wrong and the time
is wasted.

*Fix:* run the merge with its exit status checked. Print the stderr. After
`MERGE_REJECTIONS` (2) consecutive refusals, stop with exit 2. A single refusal caused by
the F2 head race still re-polls.

### F4: a superseded CANCELLED run on the same head stops a green PR (conditional bug)

*Properties:* `NoStaleFailStop` is VIOLATED in `disarm_ghost` and HOLDS in
`disarm_ghost_fixdedup`.

*Trace:* a second run of X on head 1 cancels the first, which becomes `ghost`. Two polls
each see `X: CANCELLED` beside the live X (pending or green). `decide()` counts the
cancelled entry as broken (:229-250) and the names match on both polls, so it returns
STOP_FAILED. Meanwhile GitHub, which evaluates the latest run, reports CLEAN, or BLOCKED
while pending.

*Code:* `fetch()` :347-355 turns every rollup entry into a `Check` with no de-duplication.
`decide()` :229 then treats any `CANCELLED` entry as broken.

*Repro:* `test_f4_a_superseded_cancelled_run_does_not_stop_a_green_pr` fails with
`rc=2: stopped on a superseded run`, printing `checks failed: All checks passed`.

*Condition:* this needs `statusCheckRollup` to list the superseded run next to the live
one. That happens when the same workflow runs twice on one SHA and `ci.yml`'s
`cancel-in-progress` group cancels the first. Typical causes are a close and reopen, a
second triggering event, or a manual re-trigger. I could not confirm this against the live
API from this sandbox (there is no `gh` here and no network to GitHub).

*Severity:* **Low**. It is a false stop with exit 2, not an unsafe merge.

*Fix:* keep only the latest entry per check name, ordered by `startedAt`, before building
`checks`.

### F5 and F6: the `--await-review` gate's intent (design gaps; decide deliberately)

*Properties:* `AwaitNoChangesRequested` and `AwaitReviewedThisHead` are VIOLATED even with
the environment silent during the fetch and merge (`await_current_quiet`). They HOLD with
`FixChanges` and `FixReviewHead` (`await_fixed_quiet`).

- **F5:** a reviewer submits CHANGES_REQUESTED with a body and no inline comment. The gate
  opens, because any non-author submitted review counts (:304, :319-323 discards the
  state). No thread is open, so the PR merges over the request.
  `test_f5_changes_requested_does_not_release_the_await_gate` fails with `merged over a
  standing CHANGES_REQUESTED review`.
- **F6:** Copilot reviews `aaa`, then the author pushes `bbb`. The re-review request has
  not been created yet (the #987 race again, this time on a push instead of on open).
  `awaited` (:163-173) sees a non-author review and no pending request, so `bbb` merges
  without anyone having reviewed it. `test_f6_a_review_of_an_earlier_head_does_not_release_the_gate`
  fails with `merged a head no reviewer has seen`.

Both follow the documented contract to the letter: "until someone other than the author
has reviewed". I report them as intent gaps, not defects.

*Fix, if wanted:*
- F5: stop when a non-author's latest review is CHANGES_REQUESTED.
- F6: count only reviews whose `commit.oid` equals `headRefOid`.

F5's fix was adopted. F6's was not; see *Status* above.

### F7: a stop caused by timing (model artefact; the documented timing assumption)

*Properties:*
- `NoFalseStuck` is VIOLATED in every configuration, including with all fixes.
- `NoStaleFailStop` is VIOLATED in `disarm_lag`.

The model has no clock, so "the checks are created after 3 polls" and "the view lags a
push across 2 polls" are both allowed. The watcher then reports STOP_STUCK, or STOP_FAILED
on the old head's run that was cancelled by supersession. That is the #921 and #926 race,
where the watcher waits `STUCK_POLLS`/`FAILURE_POLLS` polls and assumes GitHub catches up
sooner. It is a documented assumption, not a new bug. With the default `--interval 20` it
needs GitHub to lag for more than 40 or 60 seconds.

Reading `headRefOid` (F2's fix) would allow a further hardening: reset the failure streak
when the head changes between polls. A lagging view cannot be detected from the client
at all, so I did not model this and do not propose it.

### F8: the order of the two reads matters (docs; pinned)

`await_threadsfirst_tailquiet__MergedNoUnresolved` is VIOLATED and
`await_viewfirst_tailquiet__MergedNoUnresolved` HOLDS. Both have every fix applied and the
environment silent after the last read. If threads were read first, a Copilot review that
lands between the two reads, together with its inline thread, would be seen as "reviewed,
no threads". The module docstring (:10-12) says "The order of the two network calls in
`fetch()` is irrelevant". Under `--await-review` that is wrong, and the current
view-then-threads order is what makes it safe.

`test_pin_the_view_is_read_before_the_threads` passes, and pins the order.
`test_pin_truncation_never_reads_as_no_threads` passes too: `hasPreviousPage` is honoured,
and the `trunc` outcome never passes the gate.

### Inherent: the gap between the last read and the merge

Under `--await-review`, `AwaitContract`, `MergedNoUnresolved` and `AwaitNoChangesRequested`
stay VIOLATED in `await_fixed`, with every fix applied. The cause is a review request, a
new thread or a CHANGES_REQUESTED review arriving between the last read and
`gh pr merge`. All three HOLD in `await_fixed_quiet`. No
client can close this window, and `--match-head-commit` pins only the head.

The server-side answer is the one this repo already uses: require conversation
resolution, and required reviews where a review must gate the merge.

Without a required check (`AWAIT_NOREQ`), `MergedNotRed` and `MergedCompletedGreen` are
VIOLATED even with `FixMatchHead`. The trace `await_noreq_fixmatchhead__MergedNotRed` shows
the watcher reading X as pending, which GitHub reports as UNSTABLE and counts as mergeable
(bug 4, by design). X then fails in the window, and the merge lands red on the *evaluated*
head. The watcher is only safe when the checks that matter are *required*. The docs could
say so explicitly.

## What holds

The following hold on the current code:

- **This repository's configuration.** A merge that lands is never of a red head, never of
  one whose check has not completed, and never of one with an unresolved thread (S4, S4b and
  S5 in `disarm_current`). The risks F1 and F2 describe are closed here by branch
  protection, not by the watcher.
- **Duplicate runs, provided they are absent.** No STOP_FAILED fires on a superseded run
  when there are no duplicate runs and no view lag (S10 in `disarm_current` and
  `await_current`).
- **Truncation.** A truncated listing is never mistaken for "no threads".
  `ThreadGateSound` HOLDS in `disarm_fixed`, where overflow is still enabled and only the
  `fail` outcome has been fixed.
- **Liveness.** When GitHub accepts the merge, a PR that stays mergeable is merged and the
  watcher never polls forever (L1 and L2 in `live_disarm_current` and `live_await_current`).
  L1 fails only when GitHub refuses every merge (F3).

`--no-merge` (`AllowMerge = FALSE`) was not model-checked. `decide()` returns before the
merge branch, which `test_no_merge_mode_reports_instead_of_merging` already pins.
