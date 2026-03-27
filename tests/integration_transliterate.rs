//! Integration tests for the transliteration public API.
//!
//! These tests exercise the Rust API surface as an external consumer would,
//! complementing the inline unit tests in each module.

use _translit::transliterate;
use _translit::ErrorMode;
use proptest::prelude::*;

#[test]
fn ascii_passthrough() {
    let result = transliterate::transliterate_impl(
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
fn latin_accented_to_ascii() {
    let result = transliterate::transliterate_impl(
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
    let result = transliterate::transliterate_impl(
        "Москва",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
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
        false,
    );
    assert!(result.is_ascii());
    assert!(!result.is_empty());
}

#[test]
fn chinese_cjk() {
    let result =
        transliterate::transliterate_impl("中文", None, ErrorMode::Ignore, "", false, false, false);
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
        false,
    );
    assert!(result.contains("abc"));
    assert!(result.contains("xyz"));
}

#[test]
fn error_mode_replace() {
    let result = transliterate::transliterate_impl(
        "café",
        None,
        ErrorMode::Replace,
        "?",
        false,
        false,
        false,
    );
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
    let once =
        transliterate::transliterate_impl(input, None, ErrorMode::Ignore, "", false, false, false);
    let twice =
        transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(once, twice, "transliteration should be idempotent");
}

#[test]
fn empty_input() {
    let result =
        transliterate::transliterate_impl("", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "");
}

#[test]
fn strict_iso9_cyrillic() {
    let result = transliterate::transliterate_impl(
        "Москва",
        None,
        ErrorMode::Ignore,
        "",
        true,
        false,
        false,
    );
    assert!(result.is_ascii());
}

// --- Hangul (Korean) ---

#[test]
fn hangul_transliteration() {
    let result =
        transliterate::transliterate_impl("서울", None, ErrorMode::Ignore, "", false, false, false);
    assert!(result.is_ascii(), "Hangul should transliterate to ASCII");
    assert!(
        !result.is_empty(),
        "Hangul transliteration should not be empty"
    );
}

#[test]
fn hangul_spacing() {
    // Consecutive Hangul syllables should get spaces between them
    let result = transliterate::transliterate_impl(
        "서울시",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert!(
        result.contains(' '),
        "consecutive Hangul should be space-separated: {result:?}"
    );
}

// --- Kana (Japanese) ---

#[test]
fn kana_transliteration() {
    let result = transliterate::transliterate_impl(
        "ひらがな",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert!(
        result.is_ascii(),
        "Hiragana should transliterate to ASCII: {result:?}"
    );
    assert!(!result.is_empty());
}

#[test]
fn katakana_transliteration() {
    let result = transliterate::transliterate_impl(
        "カタカナ",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert!(
        result.is_ascii(),
        "Katakana should transliterate to ASCII: {result:?}"
    );
    assert!(!result.is_empty());
}

#[test]
fn kana_no_internal_spaces() {
    // Consecutive kana should NOT get spaces — they form words
    let result = transliterate::transliterate_impl(
        "ありがとう",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
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
    let result = transliterate::transliterate_impl(
        "東京タワー",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
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
    let result = transliterate::transliterate_impl(
        "abc東京",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
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
        transliterate::transliterate_impl("क", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "ka");
}

#[test]
fn devanagari_virama() {
    let result =
        transliterate::transliterate_impl("क्", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "k");
}

#[test]
fn devanagari_matra() {
    let result =
        transliterate::transliterate_impl("की", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "ki");
}

#[test]
fn devanagari_namaste() {
    let result =
        transliterate::transliterate_impl("नमस्ते", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "namaste");
}

#[test]
fn bengali_basic() {
    let result =
        transliterate::transliterate_impl("কলকাতা", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "kalakata");
}

#[test]
fn tamil_basic() {
    let result =
        transliterate::transliterate_impl("தமிழ்", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "tamizh");
}

#[test]
fn indic_digits() {
    let result =
        transliterate::transliterate_impl("१२३", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "123");
}

#[test]
fn indic_mixed_with_latin() {
    let result = transliterate::transliterate_impl(
        "Hello नमस्ते",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "Hello namaste");
}

#[test]
fn indic_all_scripts_produce_ascii() {
    let samples = [
        "नमस्ते",   // Devanagari
        "কলকাতা",   // Bengali
        "தமிழ்",   // Tamil
        "తెలుగు",  // Telugu
        "ગુજરાતી", // Gujarati
        "ಕನ್ನಡ",   // Kannada
        "മലയാളം",  // Malayalam
        "ଓଡ଼ିଆ",    // Odia
        "ਗੁਰਮੁਖੀ",  // Gurmukhi
    ];
    for sample in &samples {
        let result = transliterate::transliterate_impl(
            sample,
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        );
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

#[test]
fn devanagari_dilli() {
    let result = transliterate::transliterate_impl(
        "दिल्ली",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "dilli");
}

#[test]
fn devanagari_mumbai() {
    let result =
        transliterate::transliterate_impl("मुम्बई", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "mumbai");
}

#[test]
fn devanagari_consecutive_consonants() {
    let result =
        transliterate::transliterate_impl("कल", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "kala");
}

#[test]
fn devanagari_independent_vowels() {
    let result =
        transliterate::transliterate_impl("अइउ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "aiu");
}

#[test]
fn devanagari_multiword() {
    let result = transliterate::transliterate_impl(
        "नमस्ते दुनिया",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "namaste duniya");
}

// --- Hebrew ---

#[test]
fn hebrew_unpointed() {
    let result =
        transliterate::transliterate_impl("שלום", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "shlvm");
}

#[test]
fn hebrew_final_forms() {
    let result =
        transliterate::transliterate_impl("ך", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "kh");
    let result =
        transliterate::transliterate_impl("ץ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "ts");
}

#[test]
fn hebrew_shin_sin_presentation() {
    // Shin with shin dot (FB2A) → sh
    let result = transliterate::transliterate_impl(
        "\u{FB2A}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "sh");
    // Shin with sin dot (FB2B) → s
    let result = transliterate::transliterate_impl(
        "\u{FB2B}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "s");
}

#[test]
fn hebrew_dagesh_presentation() {
    // Bet with dagesh (FB31) → b (vs plain bet → v)
    let result = transliterate::transliterate_impl(
        "\u{FB31}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "b");
    let result =
        transliterate::transliterate_impl("ב", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "v");
}

#[test]
fn hebrew_mixed_with_latin() {
    let result = transliterate::transliterate_impl(
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
        let result = transliterate::transliterate_impl(
            sample,
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        );
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

// --- Sinhala ---

#[test]
fn sinhala_bare_consonant() {
    let result = transliterate::transliterate_impl(
        "\u{0D9A}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "ka");
}

#[test]
fn sinhala_virama() {
    let result = transliterate::transliterate_impl(
        "\u{0D9A}\u{0DCA}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "k");
}

#[test]
fn sinhala_matra() {
    let result = transliterate::transliterate_impl(
        "\u{0D9A}\u{0DD2}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "ki");
}

#[test]
fn sinhala_word() {
    let result =
        transliterate::transliterate_impl("සිංහල", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "simhala");
}

#[test]
fn sinhala_digits() {
    let result =
        transliterate::transliterate_impl("෧෨෩", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "123");
}

#[test]
fn sinhala_produces_ascii() {
    let samples = ["සිංහල", "ලංකා", "කොළඹ"];
    for sample in &samples {
        let result = transliterate::transliterate_impl(
            sample,
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        );
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

// --- Georgian ---

#[test]
fn georgian_tbilisi() {
    let result = transliterate::transliterate_impl(
        "თბილისი",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "tbilisi");
}

#[test]
fn georgian_sakartvelo() {
    let result = transliterate::transliterate_impl(
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
        let result = transliterate::transliterate_impl(
            sample,
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        );
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

#[test]
fn georgian_digraphs() {
    let result =
        transliterate::transliterate_impl("ჟ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "zh");
    let result =
        transliterate::transliterate_impl("შ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "sh");
}

// --- Armenian ---

#[test]
fn armenian_hayastan() {
    let result = transliterate::transliterate_impl(
        "Հայաստان",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "Hayastan");
}

#[test]
fn armenian_yerevan() {
    let result = transliterate::transliterate_impl(
        "Երևան",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "Eryevan");
}

#[test]
fn armenian_yev_ligature() {
    let result =
        transliterate::transliterate_impl("և", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(result, "yev");
}

#[test]
fn armenian_presentation_ligatures() {
    let result = transliterate::transliterate_impl(
        "\u{FB13}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "mn");
    let result = transliterate::transliterate_impl(
        "\u{FB17}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "mkh");
}

#[test]
fn armenian_produces_ascii() {
    let samples = ["Հայաստան", "Երևան", "Հայերեն"];
    for sample in &samples {
        let result = transliterate::transliterate_impl(
            sample,
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        );
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

// ===========================================================================
// Thai example tests
// ===========================================================================

#[test]
fn thai_consonants() {
    let result = transliterate::transliterate_impl(
        "\u{0E01}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "k");
}

#[test]
fn thai_bangkok() {
    let result = transliterate::transliterate_impl(
        "\u{0E01}\u{0E23}\u{0E38}\u{0E07}\u{0E40}\u{0E17}\u{0E1E}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert!(result.is_ascii(), "Expected ASCII, got: {result:?}");
    assert!(result.contains('k'), "Expected 'k' in result: {result:?}");
}

#[test]
fn thai_tone_marks_dropped() {
    // น้ำ = น(n) + ้(tone mark) + ำ(am) → "nam"
    let result = transliterate::transliterate_impl(
        "\u{0E19}\u{0E49}\u{0E33}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "nam");
}

#[test]
fn thai_digits() {
    let result = transliterate::transliterate_impl(
        "\u{0E50}\u{0E51}\u{0E52}\u{0E53}\u{0E54}\u{0E55}\u{0E56}\u{0E57}\u{0E58}\u{0E59}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "0123456789");
}

#[test]
fn thai_produces_ascii() {
    let samples = [
        "\u{0E01}\u{0E23}\u{0E38}\u{0E07}\u{0E40}\u{0E17}\u{0E1E}",
        "\u{0E1B}\u{0E23}\u{0E30}\u{0E40}\u{0E17}\u{0E28}\u{0E44}\u{0E17}\u{0E22}",
        "\u{0E20}\u{0E32}\u{0E29}\u{0E32}\u{0E44}\u{0E17}\u{0E22}",
    ];
    for sample in &samples {
        let result = transliterate::transliterate_impl(
            sample,
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        );
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
        assert!(!result.is_empty(), "Expected non-empty for {sample:?}");
    }
}

// ===========================================================================
// Lao example tests
// ===========================================================================

#[test]
fn lao_word_lao() {
    let result = transliterate::transliterate_impl(
        "\u{0EA5}\u{0EB2}\u{0EA7}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "law");
}

#[test]
fn lao_consonants() {
    let result = transliterate::transliterate_impl(
        "\u{0E81}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "k");
}

#[test]
fn lao_digits() {
    let result = transliterate::transliterate_impl(
        "\u{0ED0}\u{0ED1}\u{0ED2}\u{0ED3}\u{0ED4}\u{0ED5}\u{0ED6}\u{0ED7}\u{0ED8}\u{0ED9}",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(result, "0123456789");
}

#[test]
fn lao_composite_consonants() {
    assert_eq!(
        transliterate::transliterate_impl(
            "\u{0EDC}",
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        ),
        "hn"
    );
    assert_eq!(
        transliterate::transliterate_impl(
            "\u{0EDD}",
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        ),
        "hm"
    );
}

#[test]
fn lao_produces_ascii() {
    let samples = [
        "\u{0EA5}\u{0EB2}\u{0EA7}",
        "\u{0EA7}\u{0EBD}\u{0E87}\u{0E88}\u{0EB1}\u{0E99}",
    ];
    for sample in &samples {
        let result = transliterate::transliterate_impl(
            sample,
            None,
            ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        );
        assert!(
            result.is_ascii(),
            "Expected ASCII for {sample:?}, got: {result:?}"
        );
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

/// Generate text from any of the 10 Indic blocks (U+0900-U+0DFF, includes Sinhala).
fn any_indic_text() -> BoxedStrategy<String> {
    chars_in_range(0x0900, 0x0DFF)
}

/// Generate Hebrew text (U+0590-U+05FF).
fn hebrew_text() -> BoxedStrategy<String> {
    chars_in_range(0x0590, 0x05FF)
}

/// Generate Hebrew presentation forms (U+FB1D-U+FB4F).
fn hebrew_presentation_text() -> BoxedStrategy<String> {
    chars_in_range(0xFB1D, 0xFB4F)
}

/// Generate Sinhala text (U+0D80-U+0DFF).
fn sinhala_text() -> BoxedStrategy<String> {
    chars_in_range(0x0D80, 0x0DFF)
}

/// Generate Georgian text (U+10D0-U+10F0 Mkhedruli).
fn georgian_text() -> BoxedStrategy<String> {
    chars_in_range(0x10D0, 0x10F0)
}

/// Generate Armenian text (U+0530-U+058F).
fn armenian_text() -> BoxedStrategy<String> {
    chars_in_range(0x0531, 0x0587)
}

/// Generate Thai text (U+0E01-U+0E4B, consonants + vowels + tone marks).
fn thai_text() -> BoxedStrategy<String> {
    chars_in_range(0x0E01, 0x0E4B)
}

/// Generate Thai consonants only (U+0E01-U+0E2E).
fn thai_consonants_strat() -> BoxedStrategy<String> {
    chars_in_range(0x0E01, 0x0E2E)
}

/// Generate Thai digits only (U+0E50-U+0E59).
fn thai_digits_strat() -> BoxedStrategy<String> {
    chars_in_range(0x0E50, 0x0E59)
}

/// Generate Lao text (U+0E81-U+0ECD).
fn lao_text() -> BoxedStrategy<String> {
    chars_in_range(0x0E81, 0x0ECD)
}

/// Generate any Tai text (Thai or Lao).
fn any_tai_text() -> BoxedStrategy<String> {
    proptest::strategy::Union::new(vec![thai_text(), lao_text()]).boxed()
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
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Devanagari: {:?}", result);
    }

    #[test]
    fn prop_bengali_produces_ascii(s in bengali_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Bengali: {:?}", result);
    }

    #[test]
    fn prop_tamil_produces_ascii(s in tamil_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Tamil: {:?}", result);
    }

    #[test]
    fn prop_any_indic_produces_ascii(s in any_indic_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Indic: {:?}", result);
    }

    #[test]
    fn prop_indic_idempotent(s in any_indic_text()) {
        let once = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }

    #[test]
    fn prop_indic_no_double_spaces(s in any_indic_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(!result.contains("  "), "Double space in: {:?}", result);
    }

    #[test]
    fn prop_devanagari_consonants_end_with_a(s in devanagari_consonants()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
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
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Hebrew: {:?}", result);
    }

    #[test]
    fn prop_hebrew_presentation_produces_ascii(s in hebrew_presentation_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Hebrew presentation: {:?}", result);
    }

    #[test]
    fn prop_hebrew_idempotent(s in hebrew_text()) {
        let once = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }

    #[test]
    fn prop_hebrew_no_double_spaces(s in hebrew_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(!result.contains("  "), "Double space in: {:?}", result);
    }
}

// --- Sinhala property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_sinhala_produces_ascii(s in sinhala_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Sinhala: {:?}", result);
    }

    #[test]
    fn prop_sinhala_idempotent(s in sinhala_text()) {
        let once = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }
}

// --- Georgian property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_georgian_produces_ascii(s in georgian_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Georgian: {:?}", result);
    }

    #[test]
    fn prop_georgian_idempotent(s in georgian_text()) {
        let once = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }
}

// --- Armenian property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_armenian_produces_ascii(s in armenian_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Armenian: {:?}", result);
    }

    #[test]
    fn prop_armenian_idempotent(s in armenian_text()) {
        let once = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }
}

// --- Thai property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_thai_produces_ascii(s in thai_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Thai: {:?}", result);
    }

    #[test]
    fn prop_thai_idempotent(s in thai_text()) {
        let once = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }

    #[test]
    fn prop_thai_consonants_nonempty(s in thai_consonants_strat()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(!result.is_empty(), "Empty result from Thai consonants: {:?}", s);
    }

    #[test]
    fn prop_thai_no_double_spaces(s in thai_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(!result.contains("  "), "Double space in: {:?}", result);
    }

    #[test]
    fn prop_thai_digits_are_arabic(s in thai_digits_strat()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.chars().all(|c| c.is_ascii_digit()), "Non-digit from Thai digits: {:?}", result);
        prop_assert_eq!(result.len(), s.chars().count());
    }
}

// --- Lao property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(500))]

    #[test]
    fn prop_lao_produces_ascii(s in lao_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Lao: {:?}", result);
    }

    #[test]
    fn prop_lao_idempotent(s in lao_text()) {
        let once = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }

    #[test]
    fn prop_lao_no_double_spaces(s in lao_text()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(!result.contains("  "), "Double space in: {:?}", result);
    }
}

// --- Multi-script mixture property tests ---

proptest! {
    #![proptest_config(ProptestConfig::with_cases(300))]

    #[test]
    fn prop_latin_indic_mixture_ascii(latin in extended_latin_text(), indic in any_indic_text()) {
        let mixed = format!("{latin} {indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Latin+Indic: {:?}", result);
    }

    #[test]
    fn prop_latin_hebrew_mixture_ascii(latin in extended_latin_text(), hebrew in hebrew_text()) {
        let mixed = format!("{latin} {hebrew}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Latin+Hebrew: {:?}", result);
    }

    #[test]
    fn prop_indic_hebrew_mixture_ascii(indic in any_indic_text(), hebrew in hebrew_text()) {
        let mixed = format!("{indic} {hebrew}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Indic+Hebrew: {:?}", result);
    }

    #[test]
    fn prop_cyrillic_indic_mixture_ascii(cyrillic in cyrillic_text(), indic in any_indic_text()) {
        let mixed = format!("{cyrillic} {indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Cyrillic+Indic: {:?}", result);
    }

    #[test]
    fn prop_cyrillic_hebrew_mixture_ascii(cyrillic in cyrillic_text(), hebrew in hebrew_text()) {
        let mixed = format!("{cyrillic} {hebrew}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Cyrillic+Hebrew: {:?}", result);
    }

    #[test]
    fn prop_cjk_indic_mixture_ascii(cjk in cjk_text(), indic in any_indic_text()) {
        let mixed = format!("{cjk} {indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from CJK+Indic: {:?}", result);
    }

    #[test]
    fn prop_cjk_hebrew_mixture_ascii(cjk in cjk_text(), hebrew in hebrew_text()) {
        let mixed = format!("{cjk} {hebrew}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from CJK+Hebrew: {:?}", result);
    }

    #[test]
    fn prop_hangul_indic_mixture_ascii(hangul in hangul_text(), indic in any_indic_text()) {
        let mixed = format!("{hangul} {indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Hangul+Indic: {:?}", result);
    }

    #[test]
    fn prop_latin_thai_mixture_ascii(latin in extended_latin_text(), thai in thai_text()) {
        let mixed = format!("{latin} {thai}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Latin+Thai: {:?}", result);
    }

    #[test]
    fn prop_latin_lao_mixture_ascii(latin in extended_latin_text(), lao in lao_text()) {
        let mixed = format!("{latin} {lao}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Latin+Lao: {:?}", result);
    }

    #[test]
    fn prop_thai_lao_mixture_ascii(thai in thai_text(), lao in lao_text()) {
        let mixed = format!("{thai} {lao}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Thai+Lao: {:?}", result);
    }

    #[test]
    fn prop_indic_thai_mixture_ascii(indic in any_indic_text(), thai in thai_text()) {
        let mixed = format!("{indic} {thai}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Indic+Thai: {:?}", result);
    }

    #[test]
    fn prop_cjk_tai_mixture_ascii(cjk in cjk_text(), tai in any_tai_text()) {
        let mixed = format!("{cjk} {tai}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from CJK+Tai: {:?}", result);
    }

    #[test]
    fn prop_hebrew_tai_mixture_ascii(hebrew in hebrew_text(), tai in any_tai_text()) {
        let mixed = format!("{hebrew} {tai}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
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
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
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
        let once = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&once, &twice);
    }

    #[test]
    fn prop_extended_latin_indic_no_boundary_artifacts(
        latin in extended_latin_text(),
        indic in devanagari_text(),
    ) {
        // Latin directly adjacent to Indic (no space) — should not crash or produce non-ASCII
        let mixed = format!("{latin}{indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Latin/Indic boundary: {:?}", result);
    }

    #[test]
    fn prop_hebrew_indic_no_boundary_artifacts(
        hebrew in hebrew_text(),
        indic in devanagari_text(),
    ) {
        // Hebrew directly adjacent to Indic (no space)
        let mixed = format!("{hebrew}{indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Hebrew/Indic boundary: {:?}", result);
    }

    #[test]
    fn prop_thai_indic_no_boundary_artifacts(
        thai in thai_text(),
        indic in devanagari_text(),
    ) {
        // Thai directly adjacent to Indic (no space)
        let mixed = format!("{thai}{indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Thai/Indic boundary: {:?}", result);
    }

    #[test]
    fn prop_latin_thai_no_boundary_artifacts(
        latin in extended_latin_text(),
        thai in thai_text(),
    ) {
        // Latin directly adjacent to Thai (no space)
        let mixed = format!("{latin}{thai}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Latin/Thai boundary: {:?}", result);
    }
}

// ── Ethiopic tests ──────────────────────────────────────────────────────────

#[test]
fn ethiopic_syllable_orders() {
    let r = |s| {
        transliterate::transliterate_impl(s, None, ErrorMode::Ignore, "", false, false, false)
            .into_owned()
    };
    assert_eq!(r("ሀ"), "he"); // order 1
    assert_eq!(r("ሁ"), "hu"); // order 2
    assert_eq!(r("ሂ"), "hi"); // order 3
    assert_eq!(r("ሃ"), "ha"); // order 4
    assert_eq!(r("ህ"), "h"); // order 6 (bare)
    assert_eq!(r("ሆ"), "ho"); // order 7
}

#[test]
fn ethiopic_ethiopia() {
    let result = transliterate::transliterate_impl(
        "ኢትዮጵያ",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(&*result, "ityopya");
}

#[test]
fn ethiopic_digits() {
    let result =
        transliterate::transliterate_impl("፩፪፫", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "123");
}

#[test]
fn ethiopic_produces_ascii() {
    let result = transliterate::transliterate_impl(
        "ኢትዮጵያ",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert!(result.is_ascii());
}

// ── Myanmar tests ───────────────────────────────────────────────────────────

#[test]
fn myanmar_consonant() {
    let result =
        transliterate::transliterate_impl("က", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "ka");
}

#[test]
fn myanmar_virama_strips_a() {
    let result =
        transliterate::transliterate_impl("န်", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "n");
}

#[test]
fn myanmar_dependent_vowel() {
    let result =
        transliterate::transliterate_impl("ကိ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "ki");
}

#[test]
fn myanmar_digits() {
    let result =
        transliterate::transliterate_impl("၀၁၉", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "019");
}

#[test]
fn myanmar_produces_ascii() {
    let result = transliterate::transliterate_impl(
        "မြန်မာ",
        None,
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert!(result.is_ascii());
}

// ── Khmer tests ─────────────────────────────────────────────────────────────

#[test]
fn khmer_consonant() {
    let result =
        transliterate::transliterate_impl("ក", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "ka");
}

#[test]
fn khmer_cambodia() {
    let result =
        transliterate::transliterate_impl("កម្ពុជា", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "kampucha");
}

#[test]
fn khmer_coeng_stacks() {
    let result =
        transliterate::transliterate_impl("ក្រ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "kra");
}

#[test]
fn khmer_digits() {
    let result =
        transliterate::transliterate_impl("០១៩", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "019");
}

#[test]
fn khmer_produces_ascii() {
    let result =
        transliterate::transliterate_impl("កម្ពុជា", None, ErrorMode::Ignore, "", false, false, false);
    assert!(result.is_ascii());
}

// ── Tibetan tests ───────────────────────────────────────────────────────────

#[test]
fn tibetan_consonant() {
    let result =
        transliterate::transliterate_impl("ཀ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "ka");
}

#[test]
fn tibetan_vowel_sign() {
    let result =
        transliterate::transliterate_impl("ཀི", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "ki");
}

#[test]
fn tibetan_om() {
    let result =
        transliterate::transliterate_impl("ༀ", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "om");
}

#[test]
fn tibetan_digits() {
    let result =
        transliterate::transliterate_impl("༠༡༩", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(&*result, "019");
}

#[test]
fn tibetan_produces_ascii() {
    let result =
        transliterate::transliterate_impl("བོད", None, ErrorMode::Ignore, "", false, false, false);
    assert!(result.is_ascii());
}

// ── Property tests for new scripts ──────────────────────────────────────────

fn ethiopic_text() -> BoxedStrategy<String> {
    let chars: Vec<char> = (0x1200u32..=0x1357)
        .filter(|cp| {
            let block_offset = cp & 0x07;
            block_offset < 7 // skip labialized gap at offset 7
        })
        .filter_map(char::from_u32)
        .collect();
    proptest::collection::vec(proptest::sample::select(chars), 1..=20)
        .prop_map(|v| v.into_iter().collect::<String>())
        .boxed()
}

fn myanmar_text() -> BoxedStrategy<String> {
    let chars: Vec<char> = (0x1000u32..=0x104B).filter_map(char::from_u32).collect();
    proptest::collection::vec(proptest::sample::select(chars), 1..=20)
        .prop_map(|v| v.into_iter().collect::<String>())
        .boxed()
}

fn khmer_text() -> BoxedStrategy<String> {
    let chars: Vec<char> = (0x1780u32..=0x17E9).filter_map(char::from_u32).collect();
    proptest::collection::vec(proptest::sample::select(chars), 1..=20)
        .prop_map(|v| v.into_iter().collect::<String>())
        .boxed()
}

fn tibetan_text() -> BoxedStrategy<String> {
    let chars: Vec<char> = (0x0F00u32..=0x0F6A)
        .chain(0x0F71..=0x0F84)
        .chain(0x0F90..=0x0FBC)
        .filter_map(char::from_u32)
        .filter(|c| c.is_alphanumeric() || !c.is_control())
        .collect();
    proptest::collection::vec(proptest::sample::select(chars), 1..=20)
        .prop_map(|v| v.into_iter().collect::<String>())
        .boxed()
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(300))]

    // Ethiopic
    #[test]
    fn prop_ethiopic_produces_ascii(text in ethiopic_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Ethiopic: {:?}", result);
    }

    #[test]
    fn prop_ethiopic_idempotent(text in ethiopic_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Myanmar
    #[test]
    fn prop_myanmar_produces_ascii(text in myanmar_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Myanmar: {:?}", result);
    }

    #[test]
    fn prop_myanmar_idempotent(text in myanmar_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Khmer
    #[test]
    fn prop_khmer_produces_ascii(text in khmer_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Khmer: {:?}", result);
    }

    #[test]
    fn prop_khmer_idempotent(text in khmer_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Tibetan
    #[test]
    fn prop_tibetan_produces_ascii(text in tibetan_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Tibetan: {:?}", result);
    }

    #[test]
    fn prop_tibetan_idempotent(text in tibetan_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }
}

// ── Strategies for new scripts (v0.1.5) ─────────────────────────────────────

/// Generate Arabic text (U+0621-U+064A).
fn arabic_text() -> BoxedStrategy<String> {
    chars_in_range(0x0621, 0x064A)
}

/// Generate Arabic Presentation Forms-B (U+FE70-U+FEFF).
fn arabic_presentation_text() -> BoxedStrategy<String> {
    chars_in_range(0xFE70, 0xFEFC)
}

/// Generate Syriac text (U+0710-U+0740).
fn syriac_text() -> BoxedStrategy<String> {
    chars_in_range(0x0710, 0x073F)
}

/// Generate Thaana text (U+0780-U+07B0).
fn thaana_text() -> BoxedStrategy<String> {
    chars_in_range(0x0780, 0x07B0)
}

/// Generate N'Ko text (U+07C0-U+07F9).
fn nko_text() -> BoxedStrategy<String> {
    chars_in_range(0x07C0, 0x07E7)
}

/// Generate Coptic text (U+2C80-U+2CC1).
fn coptic_text() -> BoxedStrategy<String> {
    chars_in_range(0x2C80, 0x2CC1)
}

/// Generate Cherokee text (U+13A0-U+13F5).
fn cherokee_text() -> BoxedStrategy<String> {
    chars_in_range(0x13A0, 0x13F5)
}

/// Generate Canadian Aboriginal Syllabics text (U+1401-U+1676).
fn canadian_text() -> BoxedStrategy<String> {
    chars_in_range(0x1401, 0x1676)
}

/// Generate Vai text (U+A500-U+A62B).
fn vai_text() -> BoxedStrategy<String> {
    chars_in_range(0xA500, 0xA62B)
}

/// Generate Mongolian text (U+1820-U+1878).
fn mongolian_text() -> BoxedStrategy<String> {
    chars_in_range(0x1820, 0x1878)
}

/// Generate Runic text (U+16A0-U+16EA).
fn runic_text() -> BoxedStrategy<String> {
    chars_in_range(0x16A0, 0x16EA)
}

/// Generate Ogham text (U+1681-U+169A).
fn ogham_text() -> BoxedStrategy<String> {
    chars_in_range(0x1681, 0x169A)
}

/// Generate Balinese text (U+1B05-U+1B59).
fn balinese_text() -> BoxedStrategy<String> {
    chars_in_range(0x1B05, 0x1B44)
}

/// Generate Balinese consonants (U+1B13-U+1B33).
fn balinese_consonants() -> BoxedStrategy<String> {
    chars_in_range(0x1B13, 0x1B33)
}

/// Generate Javanese text (U+A984-U+A9C0).
fn javanese_text() -> BoxedStrategy<String> {
    chars_in_range(0xA984, 0xA9C0)
}

/// Generate Javanese consonants (U+A990-U+A9B2).
fn javanese_consonants() -> BoxedStrategy<String> {
    chars_in_range(0xA990, 0xA9B2)
}

/// Generate Tai Le text (U+1950-U+196D).
fn tai_le_text() -> BoxedStrategy<String> {
    chars_in_range(0x1950, 0x196D)
}

/// Generate New Tai Lue text (U+1980-U+19C9).
fn new_tai_lue_text() -> BoxedStrategy<String> {
    chars_in_range(0x1980, 0x19C9)
}

// ── Property tests for new scripts ──────────────────────────────────────────

proptest! {
    #![proptest_config(ProptestConfig::with_cases(300))]

    // Arabic
    #[test]
    fn prop_arabic_produces_ascii(text in arabic_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Arabic: {:?}", result);
    }

    #[test]
    fn prop_arabic_idempotent(text in arabic_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    #[test]
    fn prop_arabic_presentation_ascii(text in arabic_presentation_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Arabic Presentation: {:?}", result);
    }

    // Syriac
    #[test]
    fn prop_syriac_produces_ascii(text in syriac_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Syriac: {:?}", result);
    }

    #[test]
    fn prop_syriac_idempotent(text in syriac_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Thaana
    #[test]
    fn prop_thaana_produces_ascii(text in thaana_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Thaana: {:?}", result);
    }

    #[test]
    fn prop_thaana_idempotent(text in thaana_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // N'Ko
    #[test]
    fn prop_nko_produces_ascii(text in nko_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from N'Ko: {:?}", result);
    }

    // Coptic
    #[test]
    fn prop_coptic_produces_ascii(text in coptic_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Coptic: {:?}", result);
    }

    #[test]
    fn prop_coptic_idempotent(text in coptic_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Cherokee
    #[test]
    fn prop_cherokee_produces_ascii(text in cherokee_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Cherokee: {:?}", result);
    }

    #[test]
    fn prop_cherokee_idempotent(text in cherokee_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Canadian Aboriginal
    #[test]
    fn prop_canadian_produces_ascii(text in canadian_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Canadian Aboriginal: {:?}", result);
    }

    // Vai
    #[test]
    fn prop_vai_produces_ascii(text in vai_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Vai: {:?}", result);
    }

    // Mongolian
    #[test]
    fn prop_mongolian_produces_ascii(text in mongolian_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Mongolian: {:?}", result);
    }

    #[test]
    fn prop_mongolian_idempotent(text in mongolian_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Runic
    #[test]
    fn prop_runic_produces_ascii(text in runic_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Runic: {:?}", result);
    }

    #[test]
    fn prop_runic_idempotent(text in runic_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Ogham
    #[test]
    fn prop_ogham_produces_ascii(text in ogham_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Ogham: {:?}", result);
    }

    // Balinese
    #[test]
    fn prop_balinese_produces_ascii(text in balinese_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Balinese: {:?}", result);
    }

    #[test]
    fn prop_balinese_idempotent(text in balinese_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    #[test]
    fn prop_balinese_consonants_end_with_a(s in balinese_consonants()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        if !result.is_empty() {
            prop_assert!(result.ends_with('a'), "Bare Balinese consonants should end with 'a': {:?}", result);
        }
    }

    // Javanese
    #[test]
    fn prop_javanese_produces_ascii(text in javanese_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Javanese: {:?}", result);
    }

    #[test]
    fn prop_javanese_idempotent(text in javanese_text()) {
        let once = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    #[test]
    fn prop_javanese_consonants_end_with_a(s in javanese_consonants()) {
        let result = transliterate::transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
        if !result.is_empty() {
            prop_assert!(result.ends_with('a'), "Bare Javanese consonants should end with 'a': {:?}", result);
        }
    }

    // Tai Le
    #[test]
    fn prop_tai_le_produces_ascii(text in tai_le_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Tai Le: {:?}", result);
    }

    // New Tai Lue
    #[test]
    fn prop_new_tai_lue_produces_ascii(text in new_tai_lue_text()) {
        let result = transliterate::transliterate_impl(&text, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from New Tai Lue: {:?}", result);
    }
}

// ── lang="auto" deterministic tests ────────────────────────────────────────

#[test]
fn auto_lang_cyrillic_matches_explicit_ru() {
    let text = "Москва";
    let auto = transliterate::transliterate_impl(
        text,
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let explicit = transliterate::transliterate_impl(
        text,
        Some("ru"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(auto, explicit);
}

#[test]
fn auto_lang_thai_matches_explicit_th() {
    let text = "ภาษาไทย";
    let auto = transliterate::transliterate_impl(
        text,
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let explicit = transliterate::transliterate_impl(
        text,
        Some("th"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(auto, explicit);
}

#[test]
fn auto_lang_hiragana_matches_explicit_ja() {
    let text = "こんにちは";
    let auto = transliterate::transliterate_impl(
        text,
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let explicit = transliterate::transliterate_impl(
        text,
        Some("ja"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(auto, explicit);
}

#[test]
fn auto_lang_han_matches_explicit_zh() {
    let text = "中文";
    let auto = transliterate::transliterate_impl(
        text,
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let explicit = transliterate::transliterate_impl(
        text,
        Some("zh"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(auto, explicit);
}

#[test]
fn auto_lang_hangul_matches_explicit_ko() {
    let text = "한국어";
    let auto = transliterate::transliterate_impl(
        text,
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let explicit = transliterate::transliterate_impl(
        text,
        Some("ko"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    assert_eq!(auto, explicit);
}

#[test]
fn auto_lang_ascii_passthrough() {
    let result = transliterate::transliterate_impl(
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

#[test]
fn auto_lang_latin_accented_uses_default() {
    let auto = transliterate::transliterate_impl(
        "café",
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let default =
        transliterate::transliterate_impl("café", None, ErrorMode::Ignore, "", false, false, false);
    assert_eq!(auto, default);
}

#[test]
fn auto_lang_mixed_latin_cyrillic_first_nonlatin_wins() {
    let auto = transliterate::transliterate_impl(
        "Hello Москва",
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let explicit = transliterate::transliterate_impl(
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

// ── Expanded multi-script mixture property tests (including new scripts) ────

proptest! {
    #![proptest_config(ProptestConfig::with_cases(200))]

    #[test]
    fn prop_arabic_latin_mixture_ascii(arabic in arabic_text(), latin in extended_latin_text()) {
        let mixed = format!("{arabic} {latin}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Arabic+Latin: {:?}", result);
    }

    #[test]
    fn prop_arabic_indic_mixture_ascii(arabic in arabic_text(), indic in any_indic_text()) {
        let mixed = format!("{arabic} {indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Arabic+Indic: {:?}", result);
    }

    #[test]
    fn prop_cherokee_latin_mixture_ascii(cherokee in cherokee_text(), latin in extended_latin_text()) {
        let mixed = format!("{cherokee} {latin}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Cherokee+Latin: {:?}", result);
    }

    #[test]
    fn prop_mongolian_cyrillic_mixture_ascii(mongolian in mongolian_text(), cyrillic in cyrillic_text()) {
        let mixed = format!("{mongolian} {cyrillic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Mongolian+Cyrillic: {:?}", result);
    }

    #[test]
    fn prop_balinese_javanese_mixture_ascii(balinese in balinese_text(), javanese in javanese_text()) {
        let mixed = format!("{balinese} {javanese}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Balinese+Javanese: {:?}", result);
    }

    #[test]
    fn prop_balinese_indic_mixture_ascii(balinese in balinese_text(), indic in any_indic_text()) {
        let mixed = format!("{balinese} {indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Balinese+Indic: {:?}", result);
    }

    #[test]
    fn prop_syriac_arabic_mixture_ascii(syriac in syriac_text(), arabic in arabic_text()) {
        let mixed = format!("{syriac} {arabic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII from Syriac+Arabic: {:?}", result);
    }

    #[test]
    fn prop_tai_le_thai_mixture_ascii(tai_le in tai_le_text(), thai in thai_text()) {
        let mixed = format!("{tai_le} {thai}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
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
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
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
        let once = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        let twice = transliterate::transliterate_impl(&once, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert_eq!(&*once, &*twice);
    }

    // Boundary tests — scripts directly adjacent (no space)
    #[test]
    fn prop_arabic_indic_no_boundary_artifacts(arabic in arabic_text(), indic in devanagari_text()) {
        let mixed = format!("{arabic}{indic}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Arabic/Indic boundary: {:?}", result);
    }

    #[test]
    fn prop_balinese_javanese_no_boundary_artifacts(balinese in balinese_text(), javanese in javanese_text()) {
        let mixed = format!("{balinese}{javanese}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Balinese/Javanese boundary: {:?}", result);
    }

    #[test]
    fn prop_cherokee_canadian_no_boundary_artifacts(cherokee in cherokee_text(), canadian in canadian_text()) {
        let mixed = format!("{cherokee}{canadian}");
        let result = transliterate::transliterate_impl(&mixed, None, ErrorMode::Ignore, "", false, false, false);
        prop_assert!(result.is_ascii(), "Non-ASCII at Cherokee/Canadian boundary: {:?}", result);
    }

    /// lang="auto" must never panic on arbitrary input.
    #[test]
    fn prop_auto_lang_never_panics(text in "\\PC*") {
        let _ = transliterate::transliterate_impl(&text, Some("auto"), ErrorMode::Ignore, "", false, false, false);
    }
}
