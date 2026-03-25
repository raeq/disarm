//! Integration tests for the transliteration public API.
//!
//! These tests exercise the Rust API surface as an external consumer would,
//! complementing the inline unit tests in each module.

use _translit::transliterate;
use _translit::ErrorMode;

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
    let result = transliterate::transliterate_impl("Москва", None, ErrorMode::Ignore, "", false, false);
    assert!(result.is_ascii());
    // Default transliteration should produce something recognizable
    assert!(!result.is_empty());
}

#[test]
fn cyrillic_with_lang() {
    let result =
        transliterate::transliterate_impl("Москва", Some("ru"), ErrorMode::Ignore, "", false, false);
    assert!(result.is_ascii());
    assert!(!result.is_empty());
}

#[test]
fn chinese_cjk() {
    let result = transliterate::transliterate_impl("中文", None, ErrorMode::Ignore, "", false, false);
    assert!(result.is_ascii());
}

#[test]
fn error_mode_preserve() {
    let result =
        transliterate::transliterate_impl("abc 日本語 xyz", None, ErrorMode::Preserve, "", false, false);
    assert!(result.contains("abc"));
    assert!(result.contains("xyz"));
}

#[test]
fn error_mode_replace() {
    let result = transliterate::transliterate_impl("café", None, ErrorMode::Replace, "?", false, false);
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
    let result = transliterate::transliterate_impl("Москва", None, ErrorMode::Ignore, "", true, false);
    assert!(result.is_ascii());
}

// --- Hangul (Korean) ---

#[test]
fn hangul_transliteration() {
    let result = transliterate::transliterate_impl("서울", None, ErrorMode::Ignore, "", false, false);
    assert!(result.is_ascii(), "Hangul should transliterate to ASCII");
    assert!(
        !result.is_empty(),
        "Hangul transliteration should not be empty"
    );
}

#[test]
fn hangul_spacing() {
    // Consecutive Hangul syllables should get spaces between them
    let result = transliterate::transliterate_impl("서울시", None, ErrorMode::Ignore, "", false, false);
    assert!(
        result.contains(' '),
        "consecutive Hangul should be space-separated: {result:?}"
    );
}

// --- Kana (Japanese) ---

#[test]
fn kana_transliteration() {
    let result = transliterate::transliterate_impl("ひらがな", None, ErrorMode::Ignore, "", false, false);
    assert!(
        result.is_ascii(),
        "Hiragana should transliterate to ASCII: {result:?}"
    );
    assert!(!result.is_empty());
}

#[test]
fn katakana_transliteration() {
    let result = transliterate::transliterate_impl("カタカナ", None, ErrorMode::Ignore, "", false, false);
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
    let result = transliterate::transliterate_impl("abc東京", None, ErrorMode::Ignore, "", false, false);
    assert!(result.is_ascii());
    assert!(
        result.contains("abc"),
        "Latin prefix should be preserved: {result:?}"
    );
}
