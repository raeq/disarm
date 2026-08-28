# Rust API & semver policy

`disarm` ships two surfaces from one crate, governed by **two independent
stability policies**:

| Surface | Where | Stability |
| --- | --- | --- |
| **Rust crate** | `disarm::api` + error types | semver, described below |
| **Python package** | `import disarm` | the pinned Python API (enforced by `tests/test_api_stability.py`) |

A change can be breaking for one and not the other. The Rust semver version (the
crate `version` in `Cargo.toml`) and the Python distribution version are kept in
lockstep numerically, but the guarantees below apply only to the Rust surface.

## The public Rust surface

The **only** semver-governed Rust API is:

- the [`disarm::api`](https://docs.rs/disarm/latest/disarm/api/) module — the
  idiomatic, `pyo3`-free function surface, its parameter/builder types
  (`TargetScript`, `NormalizationForm`, `UrlComponent`, `ReverseLang`,
  `Platform`, `SlugConfig`, `Scheme`, `OnUnknown`, `Transliterate`,
  `AutoLangInspection`, `HostnameAnalysis`, `AnomalyReport`, `AnomalyKind`, `Finding`, …), and the
  [`DisarmStr`](https://docs.rs/disarm/latest/disarm/trait.DisarmStr.html)
  extension trait (re-exported at the crate root);
- the error types [`Error`](https://docs.rs/disarm/latest/disarm/struct.Error.html),
  [`ErrorKind`](https://docs.rs/disarm/latest/disarm/enum.ErrorKind.html), and
  [`ErrorMode`](https://docs.rs/disarm/latest/disarm/enum.ErrorMode.html).

Wide functions use the builder pattern: [`Transliterate`] collapses the
mutually-exclusive Cyrillic schemes into [`Scheme`] (so the illegal
`iso9 && gost` state can't be built) and folds the replacement string into
[`OnUnknown`]. The public enums are `#[non_exhaustive]` and implement
`FromStr` + `Display`; the no-op-returning transforms (`strip_accents`,
`fold_case`, `normalize_confusables`, …) return `Cow<'_, str>` and borrow on the
unchanged path. Pure functions are `#[must_use]`.

`api::CONFUSABLES_VERSION` (and `api::confusables_version()`) is a special case: the
*item* is semver-governed like any other, but its **value** is bundled data and moves
with a table refresh, which the semver policy already allows without a breaking bump.
Do not pin behaviour to a specific value — read it, report it, compare it.

Everything else is an implementation detail and carries **no** guarantee:

- modules declared `pub(crate)` (the Layer-1 algorithm cores);
- the three `#[doc(hidden)] pub` modules (`emoji`, `transliterate`, `tables`),
  exposed only so the in-repo Criterion/iai benchmarks — separate crates that can
  see just `pub` items — can measure the cores directly. They are excluded from
  docs.rs and from `cargo-semver-checks`. Do not depend on them.
- the `extension-module` feature and the `disarm._core` PyO3 layer.

If you find yourself reaching past `disarm::api`, please open an issue — the
missing capability belongs in `api`.

## What counts as a breaking change

Following [SemVer](https://semver.org/) and the
[Rust API guidelines](https://rust-lang.github.io/api-guidelines/), a **major**
bump is required to:

- remove or rename a public `api` item, or change a function signature;
- add a field to a public struct that is **not** `#[non_exhaustive]`, or a
  variant to a non-`#[non_exhaustive]` enum;
- raise the MSRV (see below).

A **minor** bump covers additive changes: new `api` functions, new
`#[non_exhaustive]` enum variants, new struct fields behind `#[non_exhaustive]`.

The public enums (`ErrorKind`, `TargetScript`, `NormalizationForm`, …) are marked
`#[non_exhaustive]` precisely so new variants are a minor, not major, change —
always include a `_ =>` arm when matching them.

Note: **data-driven output is not semver-stable, and this covers the security
surfaces and the key builders too.** Transliteration output (Unicode tables,
romanization standards), the confusable/security functions —
`normalize_confusables`, `strip_obfuscation`, `is_suspicious_hostname`, and the
`canonicalize*` presets — **and the three key builders `search_key`,
`catalog_key` and `sort_key`** all change behavior when the bundled Unicode /
TR39 tables are updated, with no signature touched. For example, #336 extended
`normalize_confusables` with cross-script pairs absent from upstream TR39 17.0,
which changes what a deployed filter chain catches. Such changes are documented
in the changelog but are **not** treated as semver-breaking. **Pin a version if
you need byte-stable output — this applies to security-filter behavior (what
`is_suspicious_hostname` flags), not just romanization.** The bundled data
vintage per release is recorded in [provenance.md](provenance.md).

## Key stability — what a stored key is worth

`search_key`, `catalog_key` and `sort_key` exist to produce a value you **store**
and compare later, so "not semver-stable" costs more for them than for a function
whose output you look at once. Until #644 the clause above named four other things
and not these three, which left the question open. It is answered here:

> **A patch release never changes key-builder output. A minor release may.**

That is the contract, and it is what a consumer can plan against:

| upgrade | what it means |
| --- | --- |
| `0.14.0` → `0.14.3` | Nothing to do. A key you stored still compares equal. |
| `0.14.x` → `0.15.0` | Read the changelog's **Upgrade notes** first. Treat it as a possible reindex until they say otherwise. |

The same rule holds in every binding, because they all wrap one core.

### This is what has always happened

Measured across every version disarm has published, on 12,285 fixed inputs — the
code points `U+0020`–`U+2FFF` plus a word list in 13 scripts — with each release
installed from PyPI into a clean virtualenv:

| transition | | `search_key` | `catalog_key` | `sort_key` |
| --- | --- | ---: | ---: | ---: |
| `0.9.0` → `0.9.1` | patch | 0 | 0 | 0 |
| `0.9.1` → `0.10.0` | minor | 0 | 19 | 0 |
| `0.10.0` → `0.11.0` | minor | 62 | 73 | 1021 |
| `0.11.0` → `0.11.1` | patch | 0 | 0 | 0 |
| `0.11.1` → `0.12.0` | minor | 0 | 0 | 0 |
| `0.12.0` → `0.13.0` | minor | 0 | 0 | 0 |
| `0.13.0` → `0.14.0` | minor | 147 | 148 | 416 |

Both patch releases moved nothing. Three of the five minors moved nothing either
— which is the reason a consumer could not tell the difference from outside, and
the reason the rule has to be written down rather than inferred.

### The rate understates it, because the characters are common

`0.13.0` → `0.14.0` reads as 1.2% of code points. At word level it is most of a
Cyrillic index, because the Russian soft and hard signs are in the changed set:

| word | `search_key` on `0.13.0` | on `0.14.0` |
| --- | --- | --- |
| `подъезд` | `podъezd` | `podezd` |
| `Игорь` | `igorь` | `igor` |
| `Соловьёв` | `solovьyov` | `solovyov` |

`adolf` is right and `adolьf` was wrong — the key builders had stopped applying
134 empty table mappings that `transliterate()` honours (#602). Nobody should
want that reverted, which is exactly why the cadence matters: a consumer cannot
tell a release that fixes their keys from one that leaves them alone, and both
are correct behaviour.

### How the rule is kept

Today, by review: a change to the key path is visible in the diff, and moving
keys is a decision a reviewer has to make deliberately. That is weaker than the
rest of this document, where claims are gated. The golden-corpus fixture that
turns it into a gate — recompute every key over a fixed corpus, fail on any
change, regenerate only as a reviewed act — is the remaining work on #644, and
`KEY_SCHEMA_VERSION` (#645) is the signal a consumer could assert in their own CI.
Neither exists yet. Until they do, the statement above is a policy the project
holds itself to, not one a machine enforces.

## MSRV

The minimum supported Rust version is recorded as `rust-version` in
`Cargo.toml`. An MSRV increase is a minor-version change and is called out in the
changelog. (Dev-only tooling — benches, `cargo test --all-targets` — may require
a newer toolchain than the shipped library; that is not part of the MSRV
contract.)

## Feature flags

| Feature | Default | Purpose |
| --- | --- | --- |
| *(none)* | ✅ | Pure-Rust core. No `pyo3`, no `libpython`. This is what `cargo add disarm` gives you. |
| `extension-module` | — | Builds the `disarm._core` Python extension (pulls in `pyo3`). **Python wheel only** — Rust consumers never enable it; a bare `cargo build --features extension-module` fails to link without an interpreter. |
| `embed-dicts` | — | Embeds the compiled Arabic/Persian/Hebrew context dictionaries into the binary (otherwise they are loaded at runtime). |
| `log` | — | Opt-in diagnostic logging via the [`log`](https://docs.rs/log) facade (#208). OFF by default — the shipped artifact has **no** logging code in the hot path unless turned on. Records carry only **metadata** (lengths, lang, mode, flags, counts, durations, error codes) — never input/output text. The *sink* is the consumer's choice (`env_logger`, `tracing-subscriber`, …). A library **must not** set `log`'s `release_max_level_*` — that is the application's call. |
| `log-content` | — | Escape hatch: TRACE-only, possibly-truncated content samples for local debugging. Never enable in production. |

## Verifying the published surface

```bash
# The pure dependency tree must carry no pyo3 (the crates.io core is libpython-free)
cargo tree -e no-dev | grep -qi pyo3 && echo "pyo3 leaked!" || echo "pure core OK"

# What cargo would publish
cargo package --list

# API-compatibility check against the last release
cargo semver-checks check-release
```
