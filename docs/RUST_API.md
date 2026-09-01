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
TR39 tables are updated, with no signature touched. *When* they are allowed to
change differs, and the line is drawn by whether the key-stability fixture watches
the function rather than by what it is called: the **eight** functions
`tests/test_key_stability.py` recomputes — the three key builders plus
`canonicalize`, `canonicalize_strict`, `strip_obfuscation`, `normalize_confusables`
and `fold_case` — are confined to minor releases by the contract in the next
section. Everything else named here, including `is_suspicious_hostname` and the
transliteration output, may move in any release. For example, #336 extended
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

### The five the gate watches and the contract did not cover (#733)

`tests/test_key_stability.py` recomputes **eight** functions against a stored fixture. The
paragraph above names **three**. The other five were watched and uncovered, and their
docstrings said nothing either way — so a reader asking "may I store this?" got no answer
for the entry point most likely to be stored.

| function | watched by the gate | covered above | inline note |
| --- | --- | --- | --- |
| `search_key`, `catalog_key`, `sort_key` | yes | yes | yes |
| `canonicalize` | yes | **now yes** | **now yes** |
| `canonicalize_strict`, `strip_obfuscation`, `normalize_confusables`, `fold_case` | yes | **now yes** | **now yes** |

**The contract extends to all eight.** A patch release never changes any of their output;
a minor release may. That was already the *behaviour* the gate enforced — the fixture has
watched eight since #644 and a moved row fails CI whichever function moved it — so this
records a promise already being kept rather than making a new one.

`canonicalize` is called out because it is the comparison entry point. It is what the
guide pages hand untrusted text to, it is what a caller reaches for to decide whether two
strings are "the same", and a value you use to decide that is a value you store. It has
moved twice in this release alone — noncharacters (#805) and the combining-mark class
rule (#842) — both listed under *Upgrade notes*, which is exactly the mechanism this
contract exists to point at.


### What a key does *not* promise: it is not closed under concatenation (#787)

The contract above is about time — a key you stored last year. There is a second thing a
caller may not rely on, and it holds *within* one release: **normalizing two fields and
joining them is not the same as joining them and normalizing.**

```python
from disarm import canonicalize

a, b = "a", "\u0301e"  # part B legitimately begins with a combining acute

assert canonicalize(a) + canonicalize(b) == "a\u0301e"  # U+0061 U+0301 U+0065
assert canonicalize(a + b) == "\u00e1e"  # U+00E1 U+0065
```

The two render identically, which is what makes it a comparison bug rather than a display
one. Four surfaces show it — `canonicalize`, `canonicalize_strict`, `sort_key` and
`normalize_confusables` — and three do not: `search_key` and `catalog_key` agree because
`strip_accents` removes the mark either way, and `fold_case` agrees because it normalizes
nothing. So a caller cannot infer the property from one function to another.

This is a property of Unicode normalization rather than of disarm. NFC composes across a
boundary that did not exist before the join, and no implementation can avoid that while
still being NFC.

**Check the boundary, do not normalize the parts.** The cheap test is whether the second
part begins with a non-starter:

```python
import unicodedata


def unsafe_boundary(a: str, b: str) -> bool:
    return bool(a and b and unicodedata.combining(unicodedata.normalize("NFD", b)[0]))


assert unsafe_boundary("a", "\u0301e")  # composes across the seam
assert not unsafe_boundary("a", "example")  # a starter cannot compose backwards
```

Measured over 4,000 random pairs from a 13-character alphabet of bases and marks: **zero
false negatives** — it never calls a boundary safe when the two routes disagree. It errs
the other way, calling 838 boundaries unsafe whose results happened to match anyway, which
is the direction that costs a caller a join rather than a wrong key. (That figure was 813
before #842 stopped `canonicalize` truncating class-0 marks; the check itself did not
change, the text it is measured over did. It is asserted in
`tests/test_concat_normalization.py` rather than trusted, which is how the move was
noticed.)

The rule that follows is one line: **normalize the joined string, not the fields.** If the
fields must be normalized separately — because they are stored that way — then join with a
separator that is a starter **and that survives the pipeline**. Both halves are load-bearing.
`U+0000` is a starter, so the first half admits it; but `canonicalize` strips it as an
invisible, the two parts become adjacent again, and the mark composes exactly as it would
have with no separator at all. A space, `-` or `/` all hold. Test the separator you pick
rather than reasoning from its combining class.

`find_key_collisions` is the exception, and usefully so. It re-reduces the values it is
given rather than comparing them, so the field-wise spelling composes on the way in and the
two land in one group — measured over 600 random pairs, it grouped all 90 that differ. If
you already run a batch through it, a splice upstream of you does not survive the check.
The caveat above is about your own comparison, not about that one.

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

`0.13.0` → `0.14.0` reads as 1.2% of the 12,285 probes. At word level it is most
of a Cyrillic index, because the Russian soft and hard signs are in the changed
set:

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

By a gate, since #644. `tests/test_key_stability.py` recomputes eight key-producing
functions over a fixed 22,878-row corpus and fails on any change, reporting a
per-function count and a sample of what moved. Regenerating the fixture is the act
of accepting the change, and it belongs in the same commit as the change that
caused it.

Review alone did not catch this, and the history says so. `0.14.0` moved
`search_key` on 4.1% of a 5,030-input corpus, and the change responsible (#602)
was a correctness fix whose diff said nothing about keys — it stopped
`ErrorMode::Preserve` excepting itself from the table's empty mappings. Nobody
reading that diff would have thought *reindex*.

Checked against the published `0.13.0` wheel, the gate reports the movement it was
built for:

| function | rows changed | share of 22,878 |
| --- | ---: | ---: |
| `sort_key` | 3,026 | 13.23% |
| `canonicalize_strict` | 604 | 2.64% |
| `search_key` | 267 | 1.17% |
| `catalog_key` | 267 | 1.17% |
| `canonicalize` | 249 | 1.09% |
| `normalize_confusables` | 249 | 1.09% |
| `strip_obfuscation` | 164 | 0.72% |

Every one of those is a correctness fix, which is the point rather than a
complication: `banĸ.example` really should become `bank.example`, and it still
invalidates a stored key. The gate does not judge whether a change is right. It
makes the change visible, and forces somebody to decide.

What it still does not give a consumer is a signal they can assert in their own
CI. That is `KEY_SCHEMA_VERSION` (#645), which is downstream of this fixture: a
constant is only meaningful once something detects that the thing it counts has
moved.

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
