//! Integration tests for the transliteration public API — abjad script family.
//!
//! Covers Hebrew (and, via the shared mixture property tests in the base file,
//! Arabic / Syriac / Thaana / N'Ko). Arabic, Syriac, Thaana, and N'Ko property
//! tests live in a single multi-family `proptest!` block kept in the base
//! `integration_transliterate.rs`.

mod common;

use common::*;
use disarm::ErrorMode;
use proptest::prelude::*;

// --- Hebrew ---

#[test]
fn hebrew_unpointed() {
    let result = common::transliterate("שלום", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "shlvm");
}

#[test]
fn hebrew_final_forms() {
    let result = common::transliterate("ך", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "kh");
    let result = common::transliterate("ץ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "ts");
}

#[test]
fn hebrew_shin_sin_presentation() {
    // Shin with shin dot (FB2A) → sh
    let result =
        common::transliterate("\u{FB2A}", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "sh");
    // Shin with sin dot (FB2B) → s
    let result =
        common::transliterate("\u{FB2B}", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "s");
}

#[test]
fn hebrew_dagesh_presentation() {
    // Bet with dagesh (FB31) → b (vs plain bet → v)
    let result =
        common::transliterate("\u{FB31}", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "b");
    let result = common::transliterate("ב", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "v");
}

#[test]
fn hebrew_mixed_with_latin() {
    let result = common::transliterate(
        "שלום world",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "shlvm world");
}

#[test]
fn hebrew_produces_ascii() {
    let samples = ["שלום", "ישראל", "ירושלים"];
    for sample in &samples {
        let result =
            common::transliterate(sample, None, ErrorMode::Ignore, "", false, false, false);
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

// --- Hebrew property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_hebrew_produces_ascii(s in hebrew_text()) {
        let result = common::transliterate(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Hebrew: {:?}", result);
    }

    #[test]
    fn prop_hebrew_presentation_produces_ascii(s in hebrew_presentation_text()) {
        let result = common::transliterate(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Hebrew presentation: {:?}", result);
    }

    #[test]
    fn prop_hebrew_idempotent(s in hebrew_text()) {
        let once = common::transliterate(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = common::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }

    #[test]
    fn prop_hebrew_no_double_spaces(s in hebrew_text()) {
        let result = common::transliterate(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(!result.contains("  "), "Double space in: {:?}", result);
    }
}
