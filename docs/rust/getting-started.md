# disarm for Rust

disarm is a standalone Rust crate. The **default build is pure Rust** — no
Python, no `pyo3`, no `libpython` — so it drops into any project as an ordinary
dependency, and the whole crate is `unsafe_code = "forbid"`.

## Install

```bash
cargo add disarm
```

The minimum supported Rust version (MSRV) is 1.81. The `extension-module`
feature (which pulls in `pyo3`) exists **only** to build the Python wheel — Rust
consumers never enable it.

## Quick start

The public surface is the [`disarm::api`](https://docs.rs/disarm/latest/disarm/api/)
module plus the error types. The two operations people most often confuse are
*visual* confusable folding (homoglyph defence) and *phonetic* transliteration
(romanization) — see [Which function do I want?](../concepts/which-function.md).

```rust
use disarm::{api, DisarmStr};
use disarm::api::{Transliterate, Scheme, TargetScript};

// Visual (TR39) confusable folding — homoglyph defence
assert_eq!(api::normalize_confusables("раypal", TargetScript::Latin), "paypal");
// …or via the DisarmStr extension trait on any string:
assert_eq!("раypal".normalize_confusables(TargetScript::Latin), "paypal");

// Phonetic romanization — readable ASCII, NOT a security control.
// A language profile sharpens the result: the uk profile gives Київ → Kyiv.
assert_eq!(Transliterate::new().lang("uk").run("Київ"), "Kyiv");
// …or pick a scholarly scheme via the same builder:
let scholarly = Transliterate::new().scheme(Scheme::StrictIso9).run("Київ");
assert!(scholarly.is_ascii());

// Canonicalization primitives borrow on the no-op path (Cow)
assert_eq!(api::strip_accents("café"), "cafe");
```

## Bundled data version

`disarm::api::CONFUSABLES_VERSION` (also available as
`disarm::api::confusables_version()`) reports the Unicode `confusables.txt` release the
bundled confusable tables were folded from:

```rust
assert!(disarm::api::CONFUSABLES_VERSION.starts_with("17."));
```

This is the **data** vintage, not the crate version, and the two move independently. A
confusable fold is only as current as its table, so this is the number to compare when
auditing exposure or benchmarking against another tool.

It is deliberately not called a Unicode version: disarm's tables do not all track one
release (case folding is 16.0, East Asian width 15.1.0 — see
[Provenance](../provenance.md)), and the confusable tables also carry disarm's own
cross-script additions, so they are a superset of the named release rather than a
verbatim snapshot.

## Digit policy

disarm folds a non-Latin digit to the ASCII **digit**; upstream TR39 folds most of them
to a Latin **letter** — `०` to `o`, `೦` to `O`, `١` to `l`. Neither is wrong. disarm's
reading is right for prose, where a Devanagari zero really is a zero and folding it to a
letter corrupts the number. TR39's is right for an identifier *skeleton*, whose only job
is to make two confusable identifiers collide; it does not care whether the collision
target reads sensibly.
Three of the 45 divergent rows do not land on a letter: `٠` (U+0660) and `۰` (U+06F0)
fold to `.`, and `𑣣` (U+118E3) folds to the two characters `rn`. If the skeleton feeds a
label- or path-shaped key, that extra `.` changes its structure. Every value in the
override set is ASCII — `build.rs` asserts it — so nothing else needs guarding.


The two differ on 45 rows and agree on everything else. Reach for `tr39` when
comparing against a TR39-derived benchmark, and leave the default alone for text.

The policy is scoped to the Latin target. The override rows are generated from the
Latin table and carry TR39's Latin-script targets, so they mean nothing for another
script — with the target set to Cyrillic the policy is a no-op and the fold stays
numeric.

```rust
use disarm::api::{normalize_confusables, normalize_confusables_with, DigitPolicy, TargetScript};

let spoof = "g\u{0966}\u{0966}gle";
assert_eq!(normalize_confusables(spoof, TargetScript::Latin), "g00gle");
assert_eq!(
    normalize_confusables_with(spoof, TargetScript::Latin, DigitPolicy::Tr39),
    "google"
);
```

`normalize_confusables_with` is a separate entry point rather than a third parameter on
`normalize_confusables`. That function is the crate's most-used security primitive and the
policy is a rarely-set option, so widening it would tax every call site for something
almost none of them need.

## Coverage introspection

Coverage is not a score. A tool that folds 95% of known confusable sources is not 95%
safe — it is one query away from the other 5%. These accessors report **exposure**: the
sources disarm's bundled table does not fold, globally and for one input.

Most of the set is out of scope rather than missing (a source folding to a non-Latin
target does not belong in the to-Latin table), and it includes five ASCII characters —
`%`, `0`, `1`, `I`, `m` — because TR39 is a skeleton transform (m→rn, I/1→l, 0→O) whose
rows disarm deliberately does not apply. Nothing is filtered out: a coverage report that
quietly drops rows reads as coverage it does not have.

```rust
use disarm::api::{find_unmapped_confusables, unmapped_confusables, TargetScript};

let exposure = unmapped_confusables(TargetScript::Latin);   // sorted Vec<char>
assert!(!exposure.contains(&'\u{0430}'));                    // Cyrillic а folds
assert!(exposure.contains(&'m'));                            // TR39 skeleton source

// The per-input scan mirrors `Transliterate::find_untranslatable`.
assert!(find_unmapped_confusables("p\u{0430}ypal", TargetScript::Latin).is_empty());
```
## Errors

Fallible operations (`sanitize_filename`, `decode_to_utf8`,
`strip_log_injection`, the key/clean presets) return `Result<_, disarm::Error>`;
inspect [`Error::kind()`](https://docs.rs/disarm/latest/disarm/struct.Error.html)
for a stable [`ErrorKind`](https://docs.rs/disarm/latest/disarm/enum.ErrorKind.html).

## Where next

- **Concepts** (shared across every language) — start with
  [Which function do I want?](../concepts/which-function.md), then the topic
  guides under *Guide* in the sidebar.
- **API reference** — the canonical, versioned Rust reference is on
  [docs.rs/disarm](https://docs.rs/disarm); the semver policy is in the
  [Rust API & semver policy](../RUST_API.md).
- **Logging** is opt-in behind the `log` Cargo feature and emits redacted
  metadata only (never the input or output text).
