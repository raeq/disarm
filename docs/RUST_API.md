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
  `AutoLangInspection`, `HostnameAnalysis`, …), and the
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

Note: transliteration **output** is data-driven (Unicode tables, romanization
standards). Output changes from table/standard updates are documented in the
changelog but are **not** treated as semver-breaking — pin a version if you need
byte-stable output.

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
