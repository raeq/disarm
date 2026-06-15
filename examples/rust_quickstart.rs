//! Minimal pure-Rust quickstart for the `disarm` crate (#42).
//!
//! Builds and runs against the default (pyo3-free) feature set — the same code a
//! crates.io consumer writes after `cargo add disarm`. No Python, no libpython.
//!
//! Run with: `cargo run --example rust_quickstart`

use disarm::api::{self, OnUnknown, Scheme, TargetScript, Transliterate};
use disarm::DisarmStr;

fn main() {
    // TR39 confusable folding (Cyrillic look-alikes → Latin prototypes) — free
    // function or, via the `DisarmStr` extension trait, method syntax.
    assert_eq!(
        api::normalize_confusables("раypal", TargetScript::Latin),
        "paypal"
    );
    assert_eq!(
        "раypal".normalize_confusables(TargetScript::Latin),
        "paypal"
    );

    // Standards-based transliteration to ASCII: the one-liner, then the builder.
    assert_eq!(api::transliterate("Москва"), "Moskva");
    let moscow = Transliterate::new()
        .scheme(Scheme::StrictIso9)
        .on_unknown(OnUnknown::Replace("?".into()))
        .run("Москва");
    assert!(moscow.is_ascii());

    // Canonicalization primitives.
    assert_eq!(api::strip_accents("café"), "cafe");
    assert_eq!(api::fold_case("ﬁ"), "fi");
    assert_eq!(
        api::slugify("Héllo Wörld", &api::SlugConfig::default()),
        "hello-world"
    );

    // IDN / hostname spoofing check (a `false` result is not a safety guarantee).
    let (suspicious, _analysis) = api::is_suspicious_hostname("раypal.com");
    assert!(suspicious);

    // Fallible surface: an unknown encoding label is rejected with a stable kind.
    let err = api::decode_to_utf8(b"x", Some("NO-SUCH-ENCODING"), 0.0, false).unwrap_err();
    assert_eq!(err.kind(), disarm::ErrorKind::InvalidArgument);

    println!("disarm pure-Rust quickstart: all assertions passed ✓");
}
