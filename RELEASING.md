# Releasing disarm

This document is the authoritative policy for **how disarm is versioned** and **what
we do when a release turns out to be bad**. It is written for maintainers, but it is
public on purpose: downstream users should be able to predict exactly what a version
number means and what happens if a release has to be pulled.

It complements two neighbouring documents and does not repeat them:

- [SECURITY.md](SECURITY.md) — how to report a vulnerability privately, and the
  supported-version window.
- [CHANGELOG.md](CHANGELOG.md) — the per-release record of what actually changed.
- [DEPENDENCY_UPGRADES.md](DEPENDENCY_UPGRADES.md) — the repeatable methodology for
  keeping dependencies current (soak windows, auto/manual lanes, verification depth).

## Versioning

disarm version numbers use the familiar `MAJOR.MINOR.PATCH` shape, but the **major**
component does **not** carry the plain Semantic Versioning "incompatible API change"
meaning. We borrow the shape, not the major-version semantics. Within the `0.x` series
that we expect to occupy for a long time, the rules are:

### Patch / point release — `0.6.1`, `0.6.2`, `0.6.3` (a future `0.22.48`)

Three-component. The bucket for **bug fixes, cleanups, documentation improvements, and
other minor things**. A point release never introduces a new capability.

### Minor / feature release — `0.6`, `0.7`, `0.8` (a future `0.22`, `0.37`)

Two-component. The bucket for **new capabilities or major internal refactorings** — for
example, the extraction of the pure-Rust core — published canonically as the `disarm`
crate on crates.io (not `disarm-core`) — and its other-language bindings is the `0.10`
release. (The `0.9` release is the `translit` → `disarm` rename; #264.)

Documentation that a feature **requires** ships **with** that feature, in the same minor
release — it is never split out into a separate point release. (Standalone documentation
improvements unattached to any feature still belong in a point release, per above.)

### Major — `1.0`, and `2.0`+

`1.0` is reached **only when a supported (paid) path exists**. The repository being public
does **not** imply `1.0`; this is a commercial-support milestone, not a launch milestone.
We will very likely stay below `1.0` for a long time, and that is by design.

`2.0` and later majors are cut **when support for the previous major expires**.

### No calendars

Milestones are buckets ordered by **scope and readiness, never by date**. We do not set
due dates on milestones, and we do not commit to release dates or ETAs. A milestone *is*
a release — "milestone" is just the planning-side name for the same thing.

### Across languages — lockstep minors, independent patches

disarm ships **one core to many ecosystems** (the `disarm` crate on crates.io, the
`disarm` wheel on PyPI, the `disarm` gem on RubyGems, and — as bindings land — npm and
others). Unlike projects that hide the core as a private engine, disarm's Rust core is
itself a first-class, user-facing library, so the version number must mean something in
every ecosystem at once. Two rules keep that honest without forcing wasteful releases:

1. **Minor / feature releases are lockstep.** A new capability — a new transform, or a
   whole new language binding — bumps the **same minor across every registry**. The
   JavaScript binding is `0.11` *everywhere*, exactly as the Ruby binding was `0.10`
   everywhere. The headline `0.MINOR` is a promise: the same capability set exists in
   every ecosystem at that minor. Re-publishing an otherwise-unchanged binding to carry
   the new minor is fine and expected — the alignment **is** the point.

2. **Patch / point releases may be per-registry.** A fix that only touches one binding (a
   packaging bug in the gem, a wrong type in the npm package) ships as a point release
   **in that ecosystem only** — e.g. an npm-only `0.11.3` — without re-cutting
   crates.io / PyPI / RubyGems. Because a point release **never adds a capability** (see
   *Patch* above), per-registry patch numbers can drift without the feature set ever
   drifting. Do **not** cut no-op point releases in the other ecosystems just to keep the
   third component identical.

The consequence: at any minor, the shared `0.MINOR` *is* the compatibility statement — a
binding's `0.11.x` wraps core `0.11`. Once per-registry patch numbers have diverged
enough to be confusing, add a one-line compatibility note to the docs (e.g. "disarm npm
`0.11.x` ↔ core `0.11`") — the cheap insurance that lets the patch lanes move
independently without anyone having to guess which core a binding wraps.

> A note on the term "Semantic Versioning": [CHANGELOG.md](CHANGELOG.md) currently states
> versions follow SemVer. We follow SemVer's *format* and its patch/minor change
> discipline within `0.x`, but our **major**-version semantics are defined above
> (support status), not by API compatibility.

### Where the version lives — bump all six

A version bump touches **six** files. Missing one ships inconsistent metadata (the
`0.11.1` PR initially left the last two stale — caught in review before publish):

1. `Cargo.toml` — `version = "..."`
2. `pyproject.toml` — `version = "..."`
3. `bindings/node/package.json` — `"version": "..."`
4. `bindings/ruby/lib/disarm/version.rb` — `VERSION = "..."`
5. `CITATION.cff` — `version: "..."` (citation metadata; not near the manifests)
6. `uv.lock` — the `disarm` editable entry; regenerate with `uv lock`, which bumps
   only that entry with no dependency churn.

Two things that look like versions but must **not** change: the
`#[deprecated(since = "X")]` (Rust) and `.. deprecated:: X` (Python docstring) markers
record the version in which something was *deprecated*, not the current release. The
binding **glue** crates (`bindings/node/Cargo.toml`, `bindings/ruby/ext/disarm/Cargo.toml`)
stay pinned at `version = "0.0.0"`; their
`disarm_core = { package = "disarm", version = "0.<minor>" }` dependency uses a
**minor-only** requirement, so a patch never touches them — only a minor bumps that pin.

Before tagging, sweep for stray references and eyeball what is left (the surviving hits
should only be the `deprecated` markers above):

```sh
grep -rn "<old-version>" --exclude=CHANGELOG.md . | grep -v deprecated
```

## Bad releases

A *bad release* is one that should not be used: a security vulnerability, data
corruption, a release that leaks secrets, a wrong or broken artifact, or a build that
will not install. This section defines exactly what we do.

### The core principle: you cannot un-ship

Every registry disarm targets is **immutable or near-immutable** — once a version is
published, you can essentially never take it back cleanly. Deleting it is the *wrong*
tool: it breaks everyone who pinned that version, and on PyPI, crates.io, RubyGems, and
Maven Central you **still cannot reuse the version number** afterward, so you gain
nothing.

So a bad release is never deleted. It is **yanked**, **superseded** by a fresh point
release, and **announced**. Three rules follow:

1. **Never delete; yank or retract.** These are non-destructive "do not use this"
   signals, reversible where the registry supports it, and they preserve pinned users.
2. **Never reuse a version number.** A bad `0.6.3` is fixed by shipping `0.6.4` — never
   by re-cutting `0.6.3`.
3. **Yank immediately on confirmation — do not wait for the fix.** Yanking the bad
   version makes every resolver (pip, cargo, npm, …) fall back to the **previous
   non-yanked release**, which stays fully discoverable and installable. The only people
   affected are those who explicitly pinned `==<bad version>` — and they are exactly the
   ones who should see the signal. Waiting for the fix only prolongs exposure.
   - **Sole exception:** if the bad release is the *first-ever* release, there is no good
     version to fall back to — only then must the fix ship together with (or before) the
     yank.

### Severity → response

| Tier | Examples | Response |
|------|----------|----------|
| **Critical** | Security vulnerability, data corruption, leaked secrets, wrong artifact uploaded | Yank immediately + superseding release ASAP. Issue a GHSA only if it meets the bar below. |
| **High** | Won't install or build, import crashes, a core API is broken | Yank + superseding release + a CHANGELOG entry and release-note callout. |
| **Low** | Cosmetic, docs-only, a minor non-blocking bug | **Do not yank.** Fix forward in the next normal release. |

### When we publish a security advisory (GHSA)

We open a [GitHub Security Advisory](https://github.com/raeq/disarm/security/advisories)
**only** when the issue is **trivially exploitable by an unauthenticated attacker
remotely** — that is, through untrusted text input, which is disarm's exact use case
(cleaning untrusted text). A bug that requires local access or credentials is still
yanked and fixed forward, but it does not warrant a GHSA. A CVE flows from the GHSA when
one is opened; link it from the yank reason. For private reporting of suspected issues,
see [SECURITY.md](SECURITY.md).

### Per-registry mechanism

disarm ships to several ecosystems; the "yank" verb differs in each. The current
artifact is PyPI; the rest arrive with the `0.10` pure-Rust core (`disarm` on crates.io)
and its bindings.

| Artifact | Mechanism | Destructive? | Notes |
|----------|-----------|--------------|-------|
| **PyPI** (`disarm`) | Yank (PEP 592), with a reason | No — reversible | pip skips it unless someone pins `==`. Never use "Delete release". |
| **crates.io** | `cargo yank --version X` (`--undo` to reverse) | No | Existing `Cargo.lock` still resolves; new dependents blocked. |
| **npm** | `npm deprecate pkg@X "msg"` | No | `unpublish` is only allowed <72h or with no dependents — do not rely on it. |
| **Go** (`pkg.go.dev`) | `retract` directive in `go.mod`, shipped in the next tag | No | The module proxy is immutable; you retract by releasing forward. |
| **RubyGems** | `gem yank -v X` | Pulls from index | More aggressive than PyPI; still cannot re-push the number. |
| **Maven Central** | None — cannot yank or delete | Immutable | Only remedy: publish a fixed version and document it (optional POM relocation). |
| **CRAN** | Submit a corrected version | Old version archived | CRAN archives the superseded release. |

### Communication (every tier ≥ High)

- Prepend `⚠️ YANKED — do not use, see vX.Y.Z+1` to the bad GitHub Release's notes.
- Add a [CHANGELOG.md](CHANGELOG.md) entry under the superseding version explaining the
  fault.
- If the issue meets the GHSA bar, open the advisory and link it from the yank reasons.
- Keep the yank-reason text consistent across every registry the bad version reached.
