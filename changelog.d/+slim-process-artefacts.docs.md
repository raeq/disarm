- **Shorter entry points: `CHANGELOG.md`, `CONTRIBUTING.md` and the `pyproject.toml`
  comments.** `CHANGELOG.md` keeps the 0.16.x and 0.15.x releases, and 0.14.1 back to
  0.1.0 move verbatim to one page per minor series under `docs/changelog/`, in the docs
  site's nav. The cut is 0.15.0 because that release introduced `KEY_SCHEMA_VERSION`, so
  every upgrade note about stored keys stays on the main page. `CONTRIBUTING.md` goes
  from 44 KB to 8 KB: setup, the everyday and pre-push commands, sign-off, the pull
  request steps, changelog fragments and a table of contents. Test architecture, linting
  and binding gates, documentation and doc-tests, key stability, conventions, AI
  attribution and `scripts/watch_pr.py` move to `docs/contributing/`. The decision log
  in `pyproject.toml`'s comments moves to `docs/contributing/packaging.md`, one section
  per setting, with a one- or two-line pointer left beside each setting; no setting
  changes. Moved text is not reworded, and every link, anchor and test that read the old
  locations reads the new ones.
