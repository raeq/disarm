# Dependency upgrades

This is the authoritative, repeatable methodology for keeping translit's dependencies
current. It exists so that dependency work is **never ad-hoc**: every update is
classified, soaked, decided, and verified to a depth proportional to its blast radius —
and the routine majority happens with **no manual triage at all**.

It is a companion to [RELEASING.md](RELEASING.md) (versioning + bad-release handling),
which it relies on for milestone semantics and the yank-on-bad-release path.

## Principle

> Stay current by default; let the test suite do the triage; reserve human effort for
> the upgrades that actually break.

Three failure modes are equally bad and this methodology guards all of them:

- **Bleeding edge** — adopting a release the day it lands and hitting bugs nobody has
  found yet.
- **Falling behind** — skipping versions until a four-step jump (e.g. pyo3 0.24 → 0.28)
  turns a cheap, incremental upgrade into one large, risky migration. Subtle changes
  accumulate and later versions assume them.
- **Bumping without adopting** — taking the new version but continuing to call its
  deprecated APIs, or ignoring the new capabilities it ships. A deprecation with a
  removal timeline is a *scheduled* future break; unharvested features are value left on
  the table. Upgrading means *using the version as intended*, not just satisfying the
  compiler.

## Timing — soak, then keep pace

**Soak.** Don't be the beta tester. A new release must age before we adopt it, so
upstream's own point-fixes appear and other projects surface regressions first. This is
enforced automatically by Dependabot **cooldown** — the PR isn't even opened until the
release is old enough:

| Bump | Cooldown |
|------|----------|
| patch | **2 days** |
| minor | **7 days** |
| major | **14 days** |

**Keep pace.** Staying current *is the default*. Take each release once it has soaked;
don't skip versions and don't let updates pile up. The anti-drift rule:

> A major update may not sit un-triaged for more than **21 days**. Within that window it
> is **taken**, **folded** into related work, or **skipped with a written reason** — never
> silently ignored.

(Example of "folded": the pyo3 0.28 migration is folded into the translit-core extraction
at 0.8 — #147 — rather than migrating the PyO3 boundary twice.)

## Two lanes — the test suite is the triage

Every update is routed by **CI outcome**, not by a human reading semver:

### Auto lane (default — no manual triage)
```
cooldown elapses → Dependabot opens the PR → CI (Tier 1) runs → green → auto-merge
```
Applies to **any** update — patch, minor, *or* major — that builds and passes the full
deterministic suite. A clean major sails straight through. Implemented by
`.github/workflows/dependabot-auto-merge.yml`, which arms auto-merge on every Dependabot
PR; branch protection (required checks + the unresolved-review-thread gate) means only
green, clean PRs actually merge.

### Manual lane (reserved for the genuinely hard)
A PR enters the manual lane only when **CI goes red** — i.e. the upgrade has a real
breaking change (the phf_codegen build break; a pyo3 boundary change). Auto-merge stays
armed but never fires; a human picks it up and runs the migration procedure below.
**Security advisories** (RustSec / GHSA) also enter here, to be expedited ahead of the
cooldown.

This is what "minimise manual triage" means in practice: humans spend time only where the
build actually broke.

### Catching what the auto-lane skips

**Hard deprecations** — anything `#[deprecated]` in code we call — are caught here for
free: CI runs clippy with `-D warnings`, so a green PR has none, and any that appear fail
the build and route to the manual lane. **Soft deprecations** (a release note saying "X
is removed at T, use Y", with no compiler attribute) and **new features** aren't
compiler-enforced, so a green minor/patch can auto-merge straight past them. These are
harvested by a **dependency-adoption review at each release's planning** (scope-based,
never by calendar): skim the changelogs of the deps bumped since the last release for
removal timelines to preempt and features worth adopting, and file issues. The fast lane
stays fast; nothing deprecated or beneficial is silently lost.

## Migration procedure (manual lane)

1. Read the upstream changelog / migration guide; **enumerate the breaking changes that
   touch *our* usage**.
2. Open or confirm a tracking issue with scope + acceptance criteria; set its milestone
   per [RELEASING.md](RELEASING.md) (routine bumps → patch; a breaking migration that
   reshapes internals → minor, or folded into the related refactor).
3. Branch → bump the version → **compile and catalogue every breakage first** (don't fix
   blind — in #135 the phf_codegen break hid the pyo3 breaks behind it).
4. Migrate the call sites; keep edits mechanical and reviewable; introduce **no `unsafe`**
   (the crate forbids it).
5. **Adopt, don't just bump.** Migrate off every API the new version deprecates or tells
   you to replace — even if it still compiles — and never silence it with
   `#[allow(deprecated)]`. Then evaluate the version's **new features** and adopt those
   that benefit us, filing a follow-up issue when non-trivial. (criterion 0.8: migrate
   `criterion::black_box` → `std::hint::black_box`; its new throughput reporting was
   evaluated and deferred to a follow-up.)
6. Verify to the depth in the next section.
7. Check transitive impact: `Cargo.lock`, the abi3 / Python-version floor, MSRV, no new
   transitive `unsafe`.
8. Update `CHANGELOG.md`, and **flag any output-affecting change explicitly** (the 0.6.2
   precedent).

## Verification depth — scaled to blast radius

Per-PR CI runs **Tier 1** (fast, deterministic). The manual lane adds targeted depth by
what the dependency touches:

| Dependency touches | Add to verification |
|--------------------|---------------------|
| **Build / codegen** (phf, phf_codegen) | `build.rs` compile-time assertions + full Rust suite |
| **PyO3 boundary** (pyo3) | full Python suite + a built **abi3 wheel** + a cross-Python-version smoke |
| **Core transform data / algorithms** | run **Tier 3** exhaustive / formal locally |
| **Dev-only** (criterion, proptest) | build + the bench/test that uses it; no shipped-artifact check |

**Tier 3 is the comprehensive net at release.** The exhaustive (`#[ignore]`) and formal
(`@pytest.mark.formal`) tiers are run as pre-release verification (see `CLAUDE.md`), so an
auto-merged dependency that is green-but-behaviourally-subtle is still caught before it
ships — backed further by the **soak window** and, as a last resort, the **bad-release
yank policy** in [RELEASING.md](RELEASING.md).

## Per-ecosystem

The same policy applies across all three Dependabot ecosystems (and, at 0.8, each
language binding's registry):

- **cargo** — keeps `Cargo.lock` fresh for RustSec advisory scanning.
- **uv** (Python dev/docs/test/bench extras) — the package itself has no runtime deps.
- **github-actions** — third-party actions are SHA-pinned; Dependabot bumps the pins.

Configuration lives in `.github/dependabot.yml` (cooldown + minor/patch grouping; majors
are never grouped, so each opens its own PR) and the auto-merge workflow above.
