- **`scripts/watch_pr.py` could merge with a thread open, merge a head it never looked at,
  and retry a refused merge blind.** Found by a TLA+ model of the watcher and GitHub
  (`formal/tla/WatchPR`), each counterexample replayed against the real script in
  `tests/test_watch_pr_protocol.py`. A review-thread query that failed read as "no
  threads", so under `--await-review` a green PR merged over an unresolved thread, and the
  failed read still counted towards the stuck streak. `gh pr merge` named no head, so a
  push landing after the last read was merged unseen; it now passes
  `--match-head-commit`. A refused merge's reason was discarded and the merge retried
  every poll until `--max-polls`; it is now printed, and two refusals stop the watcher
  with exit `2`. Only the latest run of each check counts, as for branch protection. And
  `--await-review` no longer merges while a reviewer's latest review requests changes.
  The module docstring said the order of the two reads did not matter; it does, and it
  now says so.
