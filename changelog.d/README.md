# Changelog fragments

Every change that belongs in [CHANGELOG.md](../CHANGELOG.md) arrives as **its own file
in this directory**. `towncrier` concatenates them into a release section when the
release is cut. Nothing in `CHANGELOG.md` is edited by hand any more.

## Why

Two pull requests open at once used to conflict on `CHANGELOG.md` every time,
whatever they said. Nothing about the content collided — it was positional: every
entry was prepended to the same anchor (`## [Unreleased]` → `### Fixed`), so the
conflict was a function of concurrency alone. #989 and #991 hit it on the same
afternoon, and this pull request hit it again while it was being written.

Entries here are essays — the four that seeded this directory average 23 lines — so
resolving one is not a two-line merge, and it lands at exactly the moment a pull
request is otherwise ready to go.

Two fragments are two different files. Git only conflicts on the same region of the
same file, so the class is gone rather than reduced.

## Naming: `<pull-request>.<type>.md`

```
991.fixed.md
989.fixed.md
```

**The number is the pull request, not the issue.** towncrier's default is the issue
number, which would rebuild the conflict on day one: #972 alone produced #973, #975,
#976 and #989 — four fragments, one filename. Same shape for #974→#979, #977→#978,
#980→#982, #816→#969. Several pull requests per issue is the norm here, not the
exception; a pull request number is unique by construction.

Before the pull request exists there is no number, so use the orphan form —
`+short-slug.type.md` — and rename it once the number is known.

`<type>` is one of:

| directory | heading |
|---|---|
| `upgrade` | Upgrade notes |
| `added` | Added |
| `changed` | Changed |
| `breaking` | Changed (breaking) |
| `fixed` | Fixed |
| `security` | Security |
| `performance` | Performance |
| `docs` | Documentation |
| `internal` | Internal |

The table is in the order the headings are written, and *Upgrade notes* comes first,
as it does in `0.16.0`, `0.15.0` and `0.14.0`.

`upgrade` is where a key-moving change explains itself. `KEY_SCHEMA_VERSION` bumps go
there, alongside the *Added* or *Changed (breaking)* fragment for the change itself —
that is how `0.16.0` is written, and the release step reassembles it the same way.

## Writing one

**A fragment is the entry, exactly as it will appear.** Leading `- `, bold lead-in,
two-space continuation indent and all. Assembly concatenates; it never reformats,
re-wraps, or adds a bullet, so what is reviewed in the pull request is what ships.
`changelog.d/_template.md` is what makes that true, and says why the stock towncrier
template cannot.

Two conventions the repository already had, unchanged:

- The bold lead-in names the defect or capability and carries its **issue and pull
  request numbers inline** — `**Thing that was broken (#990).**`. towncrier's own
  `(#123)` suffix is suppressed (`issue_format = ""`) because the prose already places
  those numbers where it wants them.
- Name a documentation path as inline code with no link — `` `docs/limitations.md` `` —
  because `CHANGELOG.md` is read both from the repository root and, through a symlink,
  as a page on the docs site, where a relative link would resolve differently.

## Reading what is unreleased

There is no `## [Unreleased]` section on `main` any more; it exists only as the set of
files here. To read it as it will ship:

```sh
towncrier build --draft --version NEXT
```

CI renders the same thing into the job summary of every pull request that touches code,
a binding or the docs — a fragment is a docs change — so a reviewer sees the assembled
section without running anything.

## What CI enforces

The *Changelog fragment* job, on pull requests only:

- **A shipped change carries a fragment.** Code, Python, the workflows, or anything
  under `bindings/` — a Java, Ruby, TypeScript or C change owes one as much as a Rust
  change does. A docs-only pull request does not. Dependabot's are exempt.
- **`CHANGELOG.md` is not edited by hand.** `towncrier check` counts any edit to it as
  the news, so on its own it would pass a hand-written entry. The job fails a pull
  request that changes `CHANGELOG.md` without deleting a fragment; the release pull
  request deletes the fragments it consumed, and that is how it is told apart.
- **The escape hatch is a `no changelog` label.** A label change does not start a run,
  so add the label and then re-run the failed job. The job reads the labels from the
  API when it runs, because a re-run replays the original event, and that event's label
  list predates yours.

## Assembling a release

See [RELEASING.md](../RELEASING.md). One command, in the release pull request:

```sh
towncrier build --version 0.17.0 --yes
```

It inserts the release directly below `<!-- towncrier release notes start -->`, above
the previous release, and deletes the fragments it consumed. Nothing already in the file
changes.
