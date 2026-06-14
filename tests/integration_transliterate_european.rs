//! Integration tests for the transliteration public API — European script family.
//!
//! Covers Latin (accented / diacritics), Cyrillic, ISO-9 / GOST romanization,
//! and the alphabetic scripts Georgian and Armenian.

mod common;

use _disarm::api;
use _disarm::ErrorMode;
use common::*;
use proptest::prelude::*;

#[test]
fn latin_accented_to_ascii() {
    let result = api::transliterate(
        "café résumé",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert!(result.is_ascii(), "expected ASCII, got: {result:?}");
    assert!(result.contains("cafe"), "expected 'cafe' in {result:?}");
    assert!(result.contains("resume"), "expected 'resume' in {result:?}");
}

#[test]
fn cyrillic_default_lang() {
    let result = api::transliterate("Москва", None, ErrorMode::Ignore, "", false, false, false);
    assert!(result.is_ascii());
    // Default transliteration should produce something recognizable
    assert!(!result.is_empty());
}

#[test]
fn cyrillic_with_lang() {
    let result = api::transliterate(
        "Москва",
        Some("ru"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert!(result.is_ascii());
    assert!(!result.is_empty());
}

#[test]
fn strict_iso9_cyrillic() {
    let result = api::transliterate("Москва", None, ErrorMode::Ignore, "", false, true, false);
    assert!(result.is_ascii());
}

// --- Georgian ---

#[test]
fn georgian_tbilisi() {
    let result = api::transliterate("თბილისი", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "tbilisi");
}

#[test]
fn georgian_sakartvelo() {
    let result = api::transliterate(
        "საქართველო",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "sakartvelo");
}

#[test]
fn georgian_produces_ascii() {
    let samples = ["თბილისი", "საქართველო", "ქართული", "ბათუმი"];
    for sample in &samples {
        let result = api::transliterate(sample, None, ErrorMode::Ignore, "", false, false, false);
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

#[test]
fn georgian_digraphs() {
    let result = api::transliterate("ჟ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "zh");
    let result = api::transliterate("შ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "sh");
}

// --- Armenian ---

#[test]
fn armenian_hayastan() {
    let result = api::transliterate("Հայաստան", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "Hayastan");
}

#[test]
fn armenian_yerevan() {
    let result = api::transliterate("Երևան", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "Eryevan");
}

#[test]
fn armenian_yev_ligature() {
    let result = api::transliterate("և", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "yev");
}

#[test]
fn armenian_presentation_ligatures() {
    let result = api::transliterate("\u{FB13}", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "mn");
    let result = api::transliterate("\u{FB17}", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "mkh");
}

#[test]
fn armenian_produces_ascii() {
    let samples = ["Հայաստան", "Երևան", "Հայերեն"];
    for sample in &samples {
        let result = api::transliterate(sample, None, ErrorMode::Ignore, "", false, false, false);
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

// --- Georgian property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_georgian_produces_ascii(s in georgian_text()) {
        let result = api::transliterate(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Georgian: {:?}", result);
    }

    #[test]
    fn prop_georgian_idempotent(s in georgian_text()) {
        let once = api::transliterate(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = api::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }
}

// --- Armenian property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_armenian_produces_ascii(s in armenian_text()) {
        let result = api::transliterate(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Armenian: {:?}", result);
    }

    #[test]
    fn prop_armenian_idempotent(s in armenian_text()) {
        let once = api::transliterate(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = api::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }
}

// ── lang="auto" deterministic tests ────────────────────────────────────────

#[test]
fn auto_lang_cyrillic_matches_explicit_ru() {
    let text = "Москва";
    let auto = api::transliterate(
        text,
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let explicit = api::transliterate(text, Some("ru"), ErrorMode::Ignore, "", false, false, false);
    assert_eq!(auto, explicit);
}

#[test]
fn auto_lang_latin_accented_uses_default() {
    let auto = api::transliterate(
        "café",
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let default = api::transliterate("café", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(auto, default);
}

#[test]
fn auto_lang_mixed_latin_cyrillic_first_nonlatin_wins() {
    let auto = api::transliterate(
        "Hello Москва",
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let explicit = api::transliterate(
        "Hello Москва",
        Some("ru"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(auto, explicit);
}
