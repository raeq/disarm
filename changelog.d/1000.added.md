- **`scripts/watch_pr.py --await-review`, for a repo that does not require conversation
  resolution (#987).** On such a repo a green PR is mergeable before its reviewer has said
  anything: on raeq/ibook2epub#11 CI finished three minutes before Copilot's review, and
  the watcher would have squashed the PR in between. The flag holds the merge while a
  review request is pending and until someone other than the author has reviewed.
  Unresolved threads, failed checks and a needed rebase still come first. The default is
  unchanged, because this repo's branch protection does the same job.
