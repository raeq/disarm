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
