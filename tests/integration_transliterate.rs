//! Integration tests for the transliteration public API.
//!
//! These tests exercise the Rust API surface as an external consumer would,
//! complementing the inline unit tests in each module.
//!
//! This file holds the base / cross-cutting invariants (ascii passthrough,
//! idempotence, empty input, error modes, `is_ascii`, `list_langs`,
//! `strip_accents`) plus the multi-script mixture / multi-family property
//! tests that genuinely span several script families. Per-family tests live in
//! the sibling `integration_transliterate_{cjk,indic,abjad,european}.rs` files.

mod common;

use common::*;
use disarm::api;
use disarm::ErrorMode;
use proptest::prelude::*;

#[test]
fn ascii_passthrough() {
    let result = common::transliterate(
        "hello world",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "hello world");
}

#[test]
fn error_mode_preserve() {
    let result = common::transliterate(
        "abc 日本語 xyz",
        None,
        ErrorMode::Preserve,
        "",
        false,
        false,
        false,
    );
    assert!(result.contains("abc"));
    assert!(result.contains("xyz"));
}

#[test]
fn error_mode_replace() {
    let result = common::transliterate("café", None, ErrorMode::Replace, "?", false, false, false);
    assert!(result.is_ascii());
}

#[test]
fn strip_accents_basic() {
    assert_eq!(api::strip_accents("café"), "cafe");
    assert_eq!(api::strip_accents("naïve"), "naive");
    assert_eq!(api::strip_accents("über"), "uber");
}

#[test]
fn strip_accents_passthrough() {
    assert_eq!(api::strip_accents("hello"), "hello");
    assert_eq!(api::strip_accents(""), "");
}

#[test]
fn is_ascii_check() {
    assert!(api::is_ascii("hello"));
    assert!(!api::is_ascii("café"));
    assert!(api::is_ascii(""));
}

#[test]
fn list_langs_contains_common() {
    let langs = api::list_langs();
    // Should have some built-in language tables
    assert!(!langs.is_empty());
}

#[test]
fn idempotent_transliteration() {
    let input = "Héllo Wörld café";
    let once = common::transliterate(input, None, ErrorMode::Ignore, "", false, false, false);
    let twice = common::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(once, twice, "transliteration should be idempotent");
}

#[test]
fn empty_input() {
    let result = common::transliterate("", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "");
}

// ===========================================================================
// Property-based tests (proptest)
// ===========================================================================

// --- Multi-script mixture property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(300))]

    #[test]
    fn prop_latin_indic_mixture_ascii(latin in extended_latin_text(), indic in any_indic_text()) {
        let mixed = format!("{latin} {indic}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Latin+Indic: {:?}", result);
    }

    #[test]
    fn prop_latin_hebrew_mixture_ascii(latin in extended_latin_text(), hebrew in hebrew_text()) {
        let mixed = format!("{latin} {hebrew}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Latin+Hebrew: {:?}", result);
    }

    #[test]
    fn prop_indic_hebrew_mixture_ascii(indic in any_indic_text(), hebrew in hebrew_text()) {
        let mixed = format!("{indic} {hebrew}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Indic+Hebrew: {:?}", result);
    }

    #[test]
    fn prop_cyrillic_indic_mixture_ascii(cyrillic in cyrillic_text(), indic in any_indic_text()) {
        let mixed = format!("{cyrillic} {indic}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Cyrillic+Indic: {:?}", result);
    }

    #[test]
    fn prop_cyrillic_hebrew_mixture_ascii(cyrillic in cyrillic_text(), hebrew in hebrew_text()) {
        let mixed = format!("{cyrillic} {hebrew}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Cyrillic+Hebrew: {:?}", result);
    }

    #[test]
    fn prop_cjk_indic_mixture_ascii(cjk in cjk_text(), indic in any_indic_text()) {
        let mixed = format!("{cjk} {indic}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from CJK+Indic: {:?}", result);
    }

    #[test]
    fn prop_cjk_hebrew_mixture_ascii(cjk in cjk_text(), hebrew in hebrew_text()) {
        let mixed = format!("{cjk} {hebrew}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from CJK+Hebrew: {:?}", result);
    }

    #[test]
    fn prop_hangul_indic_mixture_ascii(hangul in hangul_text(), indic in any_indic_text()) {
        let mixed = format!("{hangul} {indic}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Hangul+Indic: {:?}", result);
    }

    #[test]
    fn prop_latin_thai_mixture_ascii(latin in extended_latin_text(), thai in thai_text()) {
        let mixed = format!("{latin} {thai}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Latin+Thai: {:?}", result);
    }

    #[test]
    fn prop_latin_lao_mixture_ascii(latin in extended_latin_text(), lao in lao_text()) {
        let mixed = format!("{latin} {lao}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Latin+Lao: {:?}", result);
    }

    #[test]
    fn prop_thai_lao_mixture_ascii(thai in thai_text(), lao in lao_text()) {
        let mixed = format!("{thai} {lao}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Thai+Lao: {:?}", result);
    }

    #[test]
    fn prop_indic_thai_mixture_ascii(indic in any_indic_text(), thai in thai_text()) {
        let mixed = format!("{indic} {thai}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Indic+Thai: {:?}", result);
    }

    #[test]
    fn prop_cjk_tai_mixture_ascii(cjk in cjk_text(), tai in any_tai_text()) {
        let mixed = format!("{cjk} {tai}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from CJK+Tai: {:?}", result);
    }

    #[test]
    fn prop_hebrew_tai_mixture_ascii(hebrew in hebrew_text(), tai in any_tai_text()) {
        let mixed = format!("{hebrew} {tai}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Hebrew+Tai: {:?}", result);
    }

    #[test]
    fn prop_seven_script_mixture_ascii(
        latin in extended_latin_text(),
        cyrillic in cyrillic_text(),
        indic in any_indic_text(),
        hebrew in hebrew_text(),
        cjk in cjk_text(),
        thai in thai_text(),
        lao in lao_text(),
    ) {
        let mixed = format!("{latin} {cyrillic} {indic} {hebrew} {cjk} {thai} {lao}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from 7-script mix: {:?}", result);
    }

    #[test]
    fn prop_seven_script_mixture_idempotent(
        latin in extended_latin_text(),
        cyrillic in cyrillic_text(),
        indic in any_indic_text(),
        hebrew in hebrew_text(),
        cjk in cjk_text(),
        thai in thai_text(),
        lao in lao_text(),
    ) {
        let mixed = format!("{latin} {cyrillic} {indic} {hebrew} {cjk} {thai} {lao}");
        let once = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        let twice = common::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }

    #[test]
    fn prop_extended_latin_indic_no_boundary_artifacts(
        latin in extended_latin_text(),
        indic in devanagari_text(),
    ) {
        // Latin directly adjacent to Indic (no space) — should not crash or produce non-ASCII
        let mixed = format!("{latin}{indic}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Latin/Indic boundary: {:?}", result);
    }

    #[test]
    fn prop_hebrew_indic_no_boundary_artifacts(
        hebrew in hebrew_text(),
        indic in devanagari_text(),
    ) {
        // Hebrew directly adjacent to Indic (no space)
        let mixed = format!("{hebrew}{indic}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Hebrew/Indic boundary: {:?}", result);
    }

    #[test]
    fn prop_thai_indic_no_boundary_artifacts(
        thai in thai_text(),
        indic in devanagari_text(),
    ) {
        // Thai directly adjacent to Indic (no space)
        let mixed = format!("{thai}{indic}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Thai/Indic boundary: {:?}", result);
    }

    #[test]
    fn prop_latin_thai_no_boundary_artifacts(
        latin in extended_latin_text(),
        thai in thai_text(),
    ) {
        // Latin directly adjacent to Thai (no space)
        let mixed = format!("{latin}{thai}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Latin/Thai boundary: {:?}", result);
    }
}

// ── Property tests for new scripts (v0.1.5) ─────────────────────────────────
//
// This block spans several script families (abjad: Arabic / Syriac / Thaana /
// N'Ko; European-adjacent: Coptic / Cherokee / Canadian / Vai / Mongolian /
// Runic / Ogham; Brahmic: Balinese / Javanese / Tai Le / New Tai Lue). Because
// a single `proptest!` block must stay intact and it genuinely spans families,
// it is kept here in the base file.

proptest! {
    #![proptest_config(ProptestConfig::with_cases(300))]

    // Arabic
    #[test]
    fn prop_arabic_produces_ascii(text in arabic_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Arabic: {:?}", result);
    }

    #[test]
    fn prop_arabic_idempotent(text in arabic_text()) {
        let once = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = common::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    #[test]
    fn prop_arabic_presentation_ascii(text in arabic_presentation_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Arabic Presentation: {:?}", result);
    }

    // Syriac
    #[test]
    fn prop_syriac_produces_ascii(text in syriac_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Syriac: {:?}", result);
    }

    #[test]
    fn prop_syriac_idempotent(text in syriac_text()) {
        let once = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = common::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Thaana
    #[test]
    fn prop_thaana_produces_ascii(text in thaana_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Thaana: {:?}", result);
    }

    #[test]
    fn prop_thaana_idempotent(text in thaana_text()) {
        let once = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = common::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // N'Ko
    #[test]
    fn prop_nko_produces_ascii(text in nko_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from N'Ko: {:?}", result);
    }

    // Coptic
    #[test]
    fn prop_coptic_produces_ascii(text in coptic_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Coptic: {:?}", result);
    }

    #[test]
    fn prop_coptic_idempotent(text in coptic_text()) {
        let once = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = common::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Cherokee
    #[test]
    fn prop_cherokee_produces_ascii(text in cherokee_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Cherokee: {:?}", result);
    }

    #[test]
    fn prop_cherokee_idempotent(text in cherokee_text()) {
        let once = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = common::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Canadian Aboriginal
    #[test]
    fn prop_canadian_produces_ascii(text in canadian_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Canadian Aboriginal: {:?}", result);
    }

    // Vai
    #[test]
    fn prop_vai_produces_ascii(text in vai_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Vai: {:?}", result);
    }

    // Mongolian
    #[test]
    fn prop_mongolian_produces_ascii(text in mongolian_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Mongolian: {:?}", result);
    }

    #[test]
    fn prop_mongolian_idempotent(text in mongolian_text()) {
        let once = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = common::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Runic
    #[test]
    fn prop_runic_produces_ascii(text in runic_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Runic: {:?}", result);
    }

    #[test]
    fn prop_runic_idempotent(text in runic_text()) {
        let once = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = common::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Ogham
    #[test]
    fn prop_ogham_produces_ascii(text in ogham_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Ogham: {:?}", result);
    }

    // Balinese
    #[test]
    fn prop_balinese_produces_ascii(text in balinese_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Balinese: {:?}", result);
    }

    #[test]
    fn prop_balinese_idempotent(text in balinese_text()) {
        let once = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = common::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    #[test]
    fn prop_balinese_consonants_end_with_a(s in balinese_consonants()) {
        let result = common::transliterate(&s, None, ErrorMode::Ignore, "", false, false, false);
        if !result.is_empty() {
            prop_assert!(result.ends_with('a'), "Bare Balinese consonants should end with 'a': {:?}", result);
        }
    }

    // Javanese
    #[test]
    fn prop_javanese_produces_ascii(text in javanese_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Javanese: {:?}", result);
    }

    #[test]
    fn prop_javanese_idempotent(text in javanese_text()) {
        let once = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = common::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    #[test]
    fn prop_javanese_consonants_end_with_a(s in javanese_consonants()) {
        let result = common::transliterate(&s, None, ErrorMode::Ignore, "", false, false, false);
        if !result.is_empty() {
            prop_assert!(result.ends_with('a'), "Bare Javanese consonants should end with 'a': {:?}", result);
        }
    }

    // Tai Le
    #[test]
    fn prop_tai_le_produces_ascii(text in tai_le_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Tai Le: {:?}", result);
    }

    // New Tai Lue
    #[test]
    fn prop_new_tai_lue_produces_ascii(text in new_tai_lue_text()) {
        let result = common::transliterate(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from New Tai Lue: {:?}", result);
    }
}

// ── lang="auto" deterministic tests ────────────────────────────────────────

#[test]
fn auto_lang_ascii_passthrough() {
    let result = common::transliterate(
        "hello",
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "hello");
}

// ── Expanded multi-script mixture property tests (including new scripts) ────

proptest! {
    #![proptest_config(ProptestConfig::with_cases(200))]

    #[test]
    fn prop_arabic_latin_mixture_ascii(arabic in arabic_text(), latin in extended_latin_text()) {
        let mixed = format!("{arabic} {latin}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Arabic+Latin: {:?}", result);
    }

    #[test]
    fn prop_arabic_indic_mixture_ascii(arabic in arabic_text(), indic in any_indic_text()) {
        let mixed = format!("{arabic} {indic}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Arabic+Indic: {:?}", result);
    }

    #[test]
    fn prop_cherokee_latin_mixture_ascii(cherokee in cherokee_text(), latin in extended_latin_text()) {
        let mixed = format!("{cherokee} {latin}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Cherokee+Latin: {:?}", result);
    }

    #[test]
    fn prop_mongolian_cyrillic_mixture_ascii(mongolian in mongolian_text(), cyrillic in cyrillic_text()) {
        let mixed = format!("{mongolian} {cyrillic}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Mongolian+Cyrillic: {:?}", result);
    }

    #[test]
    fn prop_balinese_javanese_mixture_ascii(balinese in balinese_text(), javanese in javanese_text()) {
        let mixed = format!("{balinese} {javanese}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Balinese+Javanese: {:?}", result);
    }

    #[test]
    fn prop_balinese_indic_mixture_ascii(balinese in balinese_text(), indic in any_indic_text()) {
        let mixed = format!("{balinese} {indic}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Balinese+Indic: {:?}", result);
    }

    #[test]
    fn prop_syriac_arabic_mixture_ascii(syriac in syriac_text(), arabic in arabic_text()) {
        let mixed = format!("{syriac} {arabic}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Syriac+Arabic: {:?}", result);
    }

    #[test]
    fn prop_tai_le_thai_mixture_ascii(tai_le in tai_le_text(), thai in thai_text()) {
        let mixed = format!("{tai_le} {thai}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from TaiLe+Thai: {:?}", result);
    }

    #[test]
    fn prop_grand_mixture_ascii(
        latin in extended_latin_text(),
        cyrillic in cyrillic_text(),
        arabic in arabic_text(),
        indic in any_indic_text(),
        hebrew in hebrew_text(),
        cjk in cjk_text(),
        thai in thai_text(),
        cherokee in cherokee_text(),
        balinese in balinese_text(),
        mongolian in mongolian_text(),
    ) {
        let mixed = format!(
            "{latin} {cyrillic} {arabic} {indic} {hebrew} {cjk} {thai} {cherokee} {balinese} {mongolian}"
        );
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from grand mix: {:?}", result);
    }

    #[test]
    fn prop_grand_mixture_idempotent(
        latin in extended_latin_text(),
        cyrillic in cyrillic_text(),
        arabic in arabic_text(),
        indic in any_indic_text(),
        hebrew in hebrew_text(),
        cjk in cjk_text(),
        thai in thai_text(),
        cherokee in cherokee_text(),
        balinese in balinese_text(),
        mongolian in mongolian_text(),
    ) {
        let mixed = format!(
            "{latin} {cyrillic} {arabic} {indic} {hebrew} {cjk} {thai} {cherokee} {balinese} {mongolian}"
        );
        let once = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        let twice = common::transliterate(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Boundary tests — scripts directly adjacent (no space)
    #[test]
    fn prop_arabic_indic_no_boundary_artifacts(arabic in arabic_text(), indic in devanagari_text()) {
        let mixed = format!("{arabic}{indic}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Arabic/Indic boundary: {:?}", result);
    }

    #[test]
    fn prop_balinese_javanese_no_boundary_artifacts(balinese in balinese_text(), javanese in javanese_text()) {
        let mixed = format!("{balinese}{javanese}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Balinese/Javanese boundary: {:?}", result);
    }

    #[test]
    fn prop_cherokee_canadian_no_boundary_artifacts(cherokee in cherokee_text(), canadian in canadian_text()) {
        let mixed = format!("{cherokee}{canadian}");
        let result = common::transliterate(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Cherokee/Canadian boundary: {:?}", result);
    }

    /// lang="auto" must never panic on arbitrary input.
    #[test]
    fn prop_auto_lang_never_panics(text in "\\PC*") {
        let _ = common::transliterate(&text, Some("auto"), ErrorMode::Ignore, "", false, false, false);
    }
}
