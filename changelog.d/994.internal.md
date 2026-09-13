- **Every pair of concurrent pull requests conflicted on `CHANGELOG.md`, because both
  prepended to the same anchor (#993).** Nothing about the content collided — it was
  positional. Each entry went to the top of `## [Unreleased]` → `### Fixed`, so merging
  the first guaranteed a conflict in the second, whatever the two said. #989 and #991 hit
  it on the same afternoon; the pull request that removes it hit it while being written.
  Entries here are essays — the four that seeded `changelog.d/` average 23 lines — so
  resolving one was never a two-line merge, and it landed at exactly the moment a pull
  request was otherwise ready.

  Unreleased entries are now one file per change in `changelog.d/`, assembled by
  `towncrier` at release time. Two fragments are two different files, and git only
  conflicts on the same region of the same file, so the class is gone rather than
  reduced. There is no `## [Unreleased]` section on `main` any more: read it with
  `towncrier build --draft --version NEXT`, or from the *Changelog fragment* job summary
  on any pull request. The 7,600 lines of shipped history are untouched — towncrier
  writes above a marker and never below it.

  **A fragment is named for the pull request, not the issue.** towncrier's default is the
  issue number, which would have rebuilt the conflict on day one: #972 alone produced
  #973, #975, #976 and #989 — four fragments, one filename. Several pull requests per
  issue is the norm here, not the exception.

  **A fragment is the entry, byte for byte.** Leading bullet, bold lead-in, two-space
  continuation indent; assembly concatenates and never reformats. That matters more than
  it sounds: a fragment is written in one release cycle and rendered in another, and
  nobody re-reads it in between, so the render has to hold no surprises. The stock
  towncrier markdown template supplies three — it prefixes `- ` to an entry that already
  opens with one, re-wraps at 79 columns, and appends its own `(#123)` where the prose
  has already placed the numbers. `changelog.d/_template.md` is what stops all three, and
  `tests/test_changelog_fragments.py` asserts the assembled output rather than the
  configuration that is supposed to produce it: against the stock template it fails.

  `merge=union` in `.gitattributes` was the five-minute alternative and is not what
  shipped. It resolves **silently**, and can interleave two entries into nonsense without
  saying so — the wrong shape for a repository whose method is to assert a thing rather
  than describe it.
