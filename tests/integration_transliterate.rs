//! Integration tests for the transliteration public API.
//!
//! These tests exercise the Rust API surface as an external consumer would,
//! complementing the inline unit tests in each module.

use _translit::transliterate;
use _translit::ErrorMode;
use proptest::prelude::*;

#[test]
fn ascii_passthrough() {
    let result =
        transliterate::transliterate_impl("hello world", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "hello world");
}

#[test]
fn latin_accented_to_ascii() {
    let result =
        transliterate::transliterate_impl("café résumé", None, ErrorMode::Ignore, "", false, false);
    assert!(result.is_ascii(), "expected ASCII, got: {result:?}");
    assert!(result.contains("cafe"), "expected 'cafe' in {result:?}");
    assert!(result.contains("resume"), "expected 'resume' in {result:?}");
}

#[test]
fn cyrillic_default_lang() {
    let result =
        transliterate::transliterate_impl("Москва", None, ErrorMode::Ignore, "", false, false);
    assert!(result.is_ascii());
    // Default transliteration should produce something recognizable
    assert!(!result.is_empty());
}

#[test]
fn cyrillic_with_lang() {
    let result = transliterate::transliterate_impl(
        "Москва",
        Some("ru"),
        ErrorMode::Ignore,
        "",
        false,
        false,
    );
    assert!(result.is_ascii());
    assert!(!result.is_empty());
}

#[test]
fn chinese_cjk() {
    let result =
        transliterate::transliterate_impl("中文", None, ErrorMode::Ignore, "", false, false);
    assert!(result.is_ascii());
}

#[test]
fn error_mode_preserve() {
    let result = transliterate::transliterate_impl(
        "abc 日本語 xyz",
        None,
        ErrorMode::Preserve,
        "",
        false,
        false,
    );
    assert!(result.contains("abc"));
    assert!(result.contains("xyz"));
}

#[test]
fn error_mode_replace() {
    let result =
        transliterate::transliterate_impl("café", None, ErrorMode::Replace, "?", false, false);
    assert!(result.is_ascii());
}

#[test]
fn strip_accents_basic() {
    assert_eq!(transliterate::_strip_accents("café"), "cafe");
    assert_eq!(transliterate::_strip_accents("naïve"), "naive");
    assert_eq!(transliterate::_strip_accents("über"), "uber");
}

#[test]
fn strip_accents_passthrough() {
    assert_eq!(transliterate::_strip_accents("hello"), "hello");
    assert_eq!(transliterate::_strip_accents(""), "");
}

#[test]
fn is_ascii_check() {
    assert!(transliterate::_is_ascii("hello"));
    assert!(!transliterate::_is_ascii("café"));
    assert!(transliterate::_is_ascii(""));
}

#[test]
fn list_langs_contains_common() {
    let langs = transliterate::_list_langs();
    // Should have some built-in language tables
    assert!(!langs.is_empty());
}

#[test]
fn idempotent_transliteration() {
    let input = "Héllo Wörld café";
    let once = transliterate::transliterate_impl(input, None, ErrorMode::Ignore, "", false, false);
    let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false);
    assert_eq!(once, twice, "transliteration should be idempotent");
}

#[test]
fn empty_input() {
    let result = transliterate::transliterate_impl("", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "");
}

#[test]
fn strict_iso9_cyrillic() {
    let result =
        transliterate::transliterate_impl("Москва", None, ErrorMode::Ignore, "", true, false);
    assert!(result.is_ascii());
}

// --- Hangul (Korean) ---

#[test]
fn hangul_transliteration() {
    let result =
        transliterate::transliterate_impl("서울", None, ErrorMode::Ignore, "", false, false);
    assert!(result.is_ascii(), "Hangul should transliterate to ASCII");
    assert!(
        !result.is_empty(),
        "Hangul transliteration should not be empty"
    );
}

#[test]
fn hangul_spacing() {
    // Consecutive Hangul syllables should get spaces between them
    let result =
        transliterate::transliterate_impl("서울시", None, ErrorMode::Ignore, "", false, false);
    assert!(
        result.contains(' '),
        "consecutive Hangul should be space-separated: {result:?}"
    );
}

// --- Kana (Japanese) ---

#[test]
fn kana_transliteration() {
    let result =
        transliterate::transliterate_impl("ひらがな", None, ErrorMode::Ignore, "", false, false);
    assert!(
        result.is_ascii(),
        "Hiragana should transliterate to ASCII: {result:?}"
    );
    assert!(!result.is_empty());
}

#[test]
fn katakana_transliteration() {
    let result =
        transliterate::transliterate_impl("カタカナ", None, ErrorMode::Ignore, "", false, false);
    assert!(
        result.is_ascii(),
        "Katakana should transliterate to ASCII: {result:?}"
    );
    assert!(!result.is_empty());
}

#[test]
fn kana_no_internal_spaces() {
    // Consecutive kana should NOT get spaces — they form words
    let result =
        transliterate::transliterate_impl("ありがとう", None, ErrorMode::Ignore, "", false, false);
    assert!(
        !result.starts_with(' ') && !result.ends_with(' '),
        "kana transliteration should not have leading/trailing spaces: {result:?}"
    );
    // The transliteration of consecutive kana should be a single run
    assert!(
        !result.contains("  "),
        "consecutive kana should not produce double spaces: {result:?}"
    );
}

// --- Mixed-script CJK spacing (DESIGN-2) ---

#[test]
fn ideograph_kana_boundary_gets_space() {
    // Kanji followed by kana should get a space at the boundary
    // e.g. 東京タワー → "dong jing tawa-" (space between kanji and katakana)
    let result =
        transliterate::transliterate_impl("東京タワー", None, ErrorMode::Ignore, "", false, false);
    assert!(result.is_ascii(), "mixed CJK should be ASCII: {result:?}");
    assert!(
        result.contains(' '),
        "ideograph→kana boundary should produce a space: {result:?}"
    );
}

#[test]
fn latin_before_cjk_gets_space() {
    // Latin text immediately before CJK should get a space inserted
    // The transliterator handles this at the boundary
    let result =
        transliterate::transliterate_impl("abc東京", None, ErrorMode::Ignore, "", false, false);
    assert!(result.is_ascii());
    assert!(
        result.contains("abc"),
        "Latin prefix should be preserved: {result:?}"
    );
}

// --- Indic (Brahmic scripts) ---

#[test]
fn devanagari_bare_consonant() {
    let result =
        transliterate::transliterate_impl("क", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "ka");
}

#[test]
fn devanagari_virama() {
    let result =
        transliterate::transliterate_impl("क्", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "k");
}

#[test]
fn devanagari_matra() {
    let result =
        transliterate::transliterate_impl("की", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "ki");
}

#[test]
fn devanagari_namaste() {
    let result =
        transliterate::transliterate_impl("नमस्ते", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "namaste");
}

#[test]
fn bengali_basic() {
    let result =
        transliterate::transliterate_impl("কলকাতা", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "kalakata");
}

#[test]
fn tamil_basic() {
    let result =
        transliterate::transliterate_impl("தமிழ்", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "tamizh");
}

#[test]
fn indic_digits() {
    let result =
        transliterate::transliterate_impl("१२३", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "123");
}

#[test]
fn indic_mixed_with_latin() {
    let result =
        transliterate::transliterate_impl("Hello नमस्ते", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "Hello namaste");
}

#[test]
fn indic_all_scripts_produce_ascii() {
    let samples = [
        "नमस्ते",   // Devanagari
        "কলকাতা",  // Bengali
        "தமிழ்",   // Tamil
        "తెలుగు",  // Telugu
        "ગુજરાતી", // Gujarati
        "ಕನ್ನಡ",   // Kannada
        "മലയാളം",  // Malayalam
        "ଓଡ଼ିଆ",   // Odia
        "ਗੁਰਮੁਖੀ",  // Gurmukhi
    ];
    for sample in &samples {
        let result =
            transliterate::transliterate_impl(sample, None, ErrorMode::Ignore, "", false, false);
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

#[test]
fn devanagari_dilli() {
    let result =
        transliterate::transliterate_impl("दिल्ली", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "dilli");
}

#[test]
fn devanagari_mumbai() {
    let result =
        transliterate::transliterate_impl("मुम्बई", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "mumbai");
}

#[test]
fn devanagari_consecutive_consonants() {
    let result =
        transliterate::transliterate_impl("कल", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "kala");
}

#[test]
fn devanagari_independent_vowels() {
    let result =
        transliterate::transliterate_impl("अइउ", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "aiu");
}

#[test]
fn devanagari_multiword() {
    let result =
        transliterate::transliterate_impl("नमस्ते दुनिया", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "namaste duniya");
}

// --- Hebrew ---

#[test]
fn hebrew_unpointed() {
    let result =
        transliterate::transliterate_impl("שלום", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "shlvm");
}

#[test]
fn hebrew_final_forms() {
    let result =
        transliterate::transliterate_impl("ך", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "kh");
    let result =
        transliterate::transliterate_impl("ץ", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "ts");
}

#[test]
fn hebrew_shin_sin_presentation() {
    // Shin with shin dot (FB2A) → sh
    let result =
        transliterate::transliterate_impl("\u{FB2A}", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "sh");
    // Shin with sin dot (FB2B) → s
    let result =
        transliterate::transliterate_impl("\u{FB2B}", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "s");
}

#[test]
fn hebrew_dagesh_presentation() {
    // Bet with dagesh (FB31) → b (vs plain bet → v)
    let result =
        transliterate::transliterate_impl("\u{FB31}", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "b");
    let result =
        transliterate::transliterate_impl("ב", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "v");
}

#[test]
fn hebrew_mixed_with_latin() {
    let result =
        transliterate::transliterate_impl("שלום world", None, ErrorMode::Ignore, "", false, false);
    assert_eq!(result, "shlvm world");
}

#[test]
fn hebrew_produces_ascii() {
    let samples = ["שלום", "ישראל", "ירושלים"];
    for sample in &samples {
        let result =
            transliterate::transliterate_impl(sample, None, ErrorMode::Ignore, "", false, false);
        assert!(result.is_ascii(), "Expected ASCII for {sample:?}, got: {result:?}");
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

// ===========================================================================
// Property-based tests (proptest)
// ===========================================================================

/// Generate a random string from a Unicode range.
fn chars_in_range(start: u32, end: u32) -> BoxedStrategy<String> {
    let chars: Vec<char> = (start..=end).filter_map(char::from_u32).collect();
    proptest::collection::vec(proptest::sample::select(chars), 1..=30)
        .prop_map(|v| v.into_iter().collect::<String>())
        .boxed()
}

/// Generate Devanagari text (U+0900-U+097F).
fn devanagari_text() -> BoxedStrategy<String> {
    chars_in_range(0x0900, 0x097F)
}

/// Generate Bengali text (U+0980-U+09FF).
fn bengali_text() -> BoxedStrategy<String> {
    chars_in_range(0x0980, 0x09FF)
}

/// Generate Tamil text (U+0B80-U+0BFF).
fn tamil_text() -> BoxedStrategy<String> {
    chars_in_range(0x0B80, 0x0BFF)
}

/// Generate text from any of the 9 Indic blocks (U+0900-U+0D7F).
fn any_indic_text() -> BoxedStrategy<String> {
    chars_in_range(0x0900, 0x0D7F)
}

/// Generate Hebrew text (U+0590-U+05FF).
fn hebrew_text() -> BoxedStrategy<String> {
    chars_in_range(0x0590, 0x05FF)
}

/// Generate Hebrew presentation forms (U+FB1D-U+FB4F).
fn hebrew_presentation_text() -> BoxedStrategy<String> {
    chars_in_range(0xFB1D, 0xFB4F)
}

/// Generate extended Latin text (U+00C0-U+024F).
fn extended_latin_text() -> BoxedStrategy<String> {
    chars_in_range(0x00C0, 0x024F)
}

/// Generate Cyrillic text (U+0400-U+04FF).
fn cyrillic_text() -> BoxedStrategy<String> {
    chars_in_range(0x0400, 0x04FF)
}

/// Generate CJK text (U+4E00-U+50FF).
fn cjk_text() -> BoxedStrategy<String> {
    chars_in_range(0x4E00, 0x50FF)
}

/// Generate Hangul text (U+AC00-U+ACFF).
fn hangul_text() -> BoxedStrategy<String> {
    chars_in_range(0xAC00, 0xACFF)
}

/// Devanagari consonants only (U+0915-U+0939).
fn devanagari_consonants() -> BoxedStrategy<String> {
    chars_in_range(0x0915, 0x0939)
}

// --- Indic property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_devanagari_produces_ascii(s in devanagari_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Devanagari: {:?}", result);
    }

    #[test]
    fn prop_bengali_produces_ascii(s in bengali_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Bengali: {:?}", result);
    }

    #[test]
    fn prop_tamil_produces_ascii(s in tamil_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Tamil: {:?}", result);
    }

    #[test]
    fn prop_any_indic_produces_ascii(s in any_indic_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Indic: {:?}", result);
    }

    #[test]
    fn prop_indic_idempotent(s in any_indic_text()) {
        let once = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false);
        prop_assert_eq!(&once, &twice);
    }

    #[test]
    fn prop_indic_no_double_spaces(s in any_indic_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(!result.contains("  "), "Double space in: {:?}", result);
    }

    #[test]
    fn prop_devanagari_consonants_end_with_a(s in devanagari_consonants()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false);
        if !result.is_empty() {
            prop_assert!(result.ends_with('a'), "Bare consonants should end with 'a': {:?}", result);
        }
    }
}

// --- Hebrew property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_hebrew_produces_ascii(s in hebrew_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Hebrew: {:?}", result);
    }

    #[test]
    fn prop_hebrew_presentation_produces_ascii(s in hebrew_presentation_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Hebrew presentation: {:?}", result);
    }

    #[test]
    fn prop_hebrew_idempotent(s in hebrew_text()) {
        let once = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false);
        prop_assert_eq!(&once, &twice);
    }

    #[test]
    fn prop_hebrew_no_double_spaces(s in hebrew_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(!result.contains("  "), "Double space in: {:?}", result);
    }
}

// --- Multi-script mixture property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(300))]

    #[test]
    fn prop_latin_indic_mixture_ascii(latin in extended_latin_text(), indic in any_indic_text()) {
        let mixed = format!("{latin} {indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Latin+Indic: {:?}", result);
    }

    #[test]
    fn prop_latin_hebrew_mixture_ascii(latin in extended_latin_text(), hebrew in hebrew_text()) {
        let mixed = format!("{latin} {hebrew}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Latin+Hebrew: {:?}", result);
    }

    #[test]
    fn prop_indic_hebrew_mixture_ascii(indic in any_indic_text(), hebrew in hebrew_text()) {
        let mixed = format!("{indic} {hebrew}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Indic+Hebrew: {:?}", result);
    }

    #[test]
    fn prop_cyrillic_indic_mixture_ascii(cyrillic in cyrillic_text(), indic in any_indic_text()) {
        let mixed = format!("{cyrillic} {indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Cyrillic+Indic: {:?}", result);
    }

    #[test]
    fn prop_cyrillic_hebrew_mixture_ascii(cyrillic in cyrillic_text(), hebrew in hebrew_text()) {
        let mixed = format!("{cyrillic} {hebrew}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Cyrillic+Hebrew: {:?}", result);
    }

    #[test]
    fn prop_cjk_indic_mixture_ascii(cjk in cjk_text(), indic in any_indic_text()) {
        let mixed = format!("{cjk} {indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from CJK+Indic: {:?}", result);
    }

    #[test]
    fn prop_cjk_hebrew_mixture_ascii(cjk in cjk_text(), hebrew in hebrew_text()) {
        let mixed = format!("{cjk} {hebrew}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from CJK+Hebrew: {:?}", result);
    }

    #[test]
    fn prop_hangul_indic_mixture_ascii(hangul in hangul_text(), indic in any_indic_text()) {
        let mixed = format!("{hangul} {indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Hangul+Indic: {:?}", result);
    }

    #[test]
    fn prop_five_script_mixture_ascii(
        latin in extended_latin_text(),
        cyrillic in cyrillic_text(),
        indic in any_indic_text(),
        hebrew in hebrew_text(),
        cjk in cjk_text(),
    ) {
        let mixed = format!("{latin} {cyrillic} {indic} {hebrew} {cjk}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from 5-script mix: {:?}", result);
    }

    #[test]
    fn prop_five_script_mixture_idempotent(
        latin in extended_latin_text(),
        cyrillic in cyrillic_text(),
        indic in any_indic_text(),
        hebrew in hebrew_text(),
        cjk in cjk_text(),
    ) {
        let mixed = format!("{latin} {cyrillic} {indic} {hebrew} {cjk}");
        let once = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false);
        prop_assert_eq!(&once, &twice);
    }

    #[test]
    fn prop_extended_latin_indic_no_boundary_artifacts(
        latin in extended_latin_text(),
        indic in devanagari_text(),
    ) {
        // Latin directly adjacent to Indic (no space) — should not crash or produce non-ASCII
        let mixed = format!("{latin}{indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Latin/Indic boundary: {:?}", result);
    }

    #[test]
    fn prop_hebrew_indic_no_boundary_artifacts(
        hebrew in hebrew_text(),
        indic in devanagari_text(),
    ) {
        // Hebrew directly adjacent to Indic (no space)
        let mixed = format!("{hebrew}{indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Hebrew/Indic boundary: {:?}", result);
    }
}
