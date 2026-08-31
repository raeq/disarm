//! Stream-Safe Text Format (UAX #15), from the public Rust surface.
//!
//! An interop bound, not a security control. The tests below are mostly about keeping
//! that distinction true, because every plausible misreading of this function is a way to
//! use it wrongly: as a zalgo control, as a size bound, or as a comparison key.

use disarm::api::{self, NormalizationForm};

/// The standard's bound is 30 non-starters. Below it nothing is inserted.
#[test]
fn a_short_stack_is_untouched() {
    let s = format!("a{}", "\u{0301}".repeat(29));
    assert_eq!(api::stream_safe(&s), s);
}

#[test]
fn a_long_stack_gets_a_joiner() {
    let s = format!("a{}", "\u{0301}".repeat(40));
    let out = api::stream_safe(&s);
    assert!(out.contains('\u{034F}'), "no CGJ inserted");
    assert!(out.len() > s.len());
}

/// The property that makes this unusable as a comparison key, asserted so nobody
/// reaches for it as one.
#[test]
fn it_is_not_canonically_equivalent() {
    let s = format!("a{}", "\u{0301}".repeat(40));
    let out = api::stream_safe(&s);
    assert_ne!(out, s);
    assert_ne!(
        api::normalize(&out, NormalizationForm::Nfc),
        api::normalize(&s, NormalizationForm::Nfc),
        "stream_safe must not be mistaken for a normalization"
    );
}

/// It is not a zalgo control: ordinary abuse is well under the bound and passes through
/// untouched, which is exactly why `strip_zalgo` exists separately.
#[test]
fn ordinary_zalgo_is_below_the_bound() {
    let zalgo = format!("a{}", "\u{0301}".repeat(8));
    assert_eq!(api::stream_safe(&zalgo), zalgo);
}

/// Real text with legitimate stacking is far below the bound.
#[test]
fn real_stacking_scripts_are_untouched() {
    for s in [
        "\u{05D0}\u{05B8}\u{05C1}\u{0591}",
        "\u{0628}\u{064E}\u{0651}",
        "\u{0915}\u{094D}\u{0937}",
    ] {
        assert_eq!(api::stream_safe(s), s, "{s:?} was modified");
    }
}

/// The predicate is a conjunction — upstream's own doc says "is Stream-Safe NFC" — so a
/// stream-safe but unnormalized string answers `false`. The name says so; this pins it.
#[test]
fn the_predicate_is_a_conjunction() {
    let decomposed = "a\u{0301}"; // stream-safe, but not NFC
    assert!(!api::is_normalized_stream_safe(
        decomposed,
        NormalizationForm::Nfc
    ));
    assert!(api::is_normalized_stream_safe(
        &api::normalize(decomposed, NormalizationForm::Nfc),
        NormalizationForm::Nfc
    ));
}

#[test]
fn every_form_is_accepted() {
    for form in [
        NormalizationForm::Nfc,
        NormalizationForm::Nfd,
        NormalizationForm::Nfkc,
        NormalizationForm::Nfkd,
    ] {
        let _ = api::is_normalized_stream_safe("abc", form);
    }
}

#[test]
fn ascii_is_a_no_op() {
    assert_eq!(api::stream_safe("Hello world"), "Hello world");
    assert!(api::is_normalized_stream_safe(
        "Hello world",
        NormalizationForm::Nfc
    ));
}
