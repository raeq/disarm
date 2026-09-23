# Pull requests

The [pull request steps](../CONTRIBUTING.md#submitting-changes) and how to write a
changelog fragment are in `CONTRIBUTING.md`. This page holds why fragments exist,
what CI checks about them, and the script that watches a pull request to merge.

## Changelog fragments: why, and what CI checks (#993)

`CHANGELOG.md` is assembled from one `changelog.d/` fragment per pull request and
is never edited by hand.

This is not a style preference. Every entry used to be prepended to the same anchor, so
two pull requests open at once conflicted on that file *every time*, whatever they said —
and entries here are essays, averaging 23 lines, so resolving one was never a two-line
merge. Two fragments are two different files, and git only conflicts on the same region
of the same file.

CI's *Changelog fragment* job requires one on any pull request that changes code or a
binding (anything under `bindings/`), fails one that edits `CHANGELOG.md` by hand, and
renders the draft into its job summary — docs-only pull requests included — so reviewers
see the assembled section without checking the branch out. Dependabot's pull requests are
exempt — a lockfile bump has nothing to say in a changelog, and its auto-merge lane has
to stay hands-off green. For anything else, the escape hatch is a deliberate, visible
`no changelog` label. Adding a label does not start a CI run: add it, then re-run the
failed *Changelog fragment* job, which reads the labels as they are when it runs.

## Watching a PR to merge

`scripts/watch_pr.py` polls a PR and stops the moment a human has to act:

```bash
python scripts/watch_pr.py 912              # poll, then squash when mergeable
python scripts/watch_pr.py 912 --no-merge   # report only
```

It exits `0` merged, `1` closed without merging (or a merge it could not confirm),
`2` when you are needed — an unresolved review thread, printed with its file, line and
body; a failed check; a stale branch; a structural block; a thread listing too long
to read in one page; or a merge GitHub refused twice, with GitHub's reason — and `3` if
it gave up. The merge names the head it evaluated (`--match-head-commit`), so a push
that lands after the last read is refused rather than merged unseen.

On a repo whose branch protection does not require conversation resolution, pass
`--await-review` (#987). A green PR is mergeable there before its reviewer has said
anything, and a thread not yet written cannot be unresolved, so the flag holds the merge
while a review request is pending and until someone other than the author has reviewed,
and stops (`2`) while a reviewer's latest review requests changes. Unresolved threads,
failed checks and a needed rebase still come first, and a review that never arrives waits
out `--max-polls` and exits `3`. This repo requires resolution, so it does not need the
flag.

What the flag cannot do, and a TLA+ model of the watcher (`formal/tla/WatchPR`) shows no
client can: a review, thread or change request that arrives between the watcher's last
read and its merge still gets through, so on a repo where that matters, require
conversation resolution on the server. A review of an earlier head still counts after a
push; GitHub's "dismiss stale pull request approvals" setting is the way to require one
per head. And a check that is not required does not hold the merge, so make the checks
that matter required.

Two stop conditions need confirming before they are reported, because for a few seconds
after a push GitHub still describes the previous run. A structural block must hold for
`STUCK_POLLS` polls (currently 3). A failed check must show the same check names for
`FAILURE_POLLS` polls (currently 2), since the rollup can still carry conclusions from the
SHA before the fix. For a few seconds after a push GitHub reports the PR as blocked with the
previous run's checks complete and the new ones not yet created, which in a single
snapshot is indistinguishable from a required review that will never arrive. A poll whose
read failed — the PR view or the review-thread listing — does not count towards the streak.

Two behaviours are worth knowing, because hand-written loops keep getting
them wrong: review threads rank *above* checks in `decide()`, so a comment never waits
out a CI run (the reads themselves go the other way, PR view first, which is what lets a
review that lands between them bring its threads along), and `UNSTABLE` counts as mergeable, so a still-running non-required job does
not hold the merge. `tests/test_watch_pr.py` pins both. `tests/test_watch_pr_protocol.py`
replays the model's counterexamples against a fake GitHub, through the real I/O layer.
