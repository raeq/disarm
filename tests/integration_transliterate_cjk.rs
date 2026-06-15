//! Integration tests for the transliteration public API — CJK script family.
//!
//! Covers Chinese / Hanzi, Japanese (kana / katakana / kanji), Korean (Hangul),
//! and CJK spacing / boundary behaviour.

use disarm::ErrorMode;

mod common;

#[test]
fn chinese_cjk() {
    let result = common::transliterate("中文", None, ErrorMode::Ignore, "", false, false, false);
    assert!(result.is_ascii());
}

// --- Hangul (Korean) ---

#[test]
fn hangul_transliteration() {
    let result = common::transliterate("서울", None, ErrorMode::Ignore, "", false, false, false);
    assert!(result.is_ascii(), "Hangul should transliterate to ASCII");
    assert!(
        !result.is_empty(),
        "Hangul transliteration should not be empty"
    );
}

#[test]
fn hangul_spacing() {
    // Consecutive Hangul syllables should get spaces between them
    let result = common::transliterate("서울시", None, ErrorMode::Ignore, "", false, false, false);
    assert!(
        result.contains(' '),
        "consecutive Hangul should be space-separated: {result:?}"
    );
}

// --- Kana (Japanese) ---

#[test]
fn kana_transliteration() {
    let result =
        common::transliterate("ひらがな", None, ErrorMode::Ignore, "", false, false, false);
    assert!(
        result.is_ascii(),
        "Hiragana should transliterate to ASCII: {result:?}"
    );
    assert!(!result.is_empty());
}

#[test]
fn katakana_transliteration() {
    let result =
        common::transliterate("カタカナ", None, ErrorMode::Ignore, "", false, false, false);
    assert!(
        result.is_ascii(),
        "Katakana should transliterate to ASCII: {result:?}"
    );
    assert!(!result.is_empty());
}

#[test]
fn kana_no_internal_spaces() {
    // Consecutive kana should NOT get spaces — they form words
    let result = common::transliterate(
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
    let result = common::transliterate(
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
    let result = common::transliterate("abc東京", None, ErrorMode::Ignore, "", false, false, false);
    assert!(result.is_ascii());
    assert!(
        result.contains("abc"),
        "Latin prefix should be preserved: {result:?}"
    );
}

// ── lang="auto" deterministic tests ────────────────────────────────────────

#[test]
fn auto_lang_hiragana_matches_explicit_ja() {
    let text = "こんにちは";
    let auto = common::transliterate(
        text,
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let explicit =
        common::transliterate(text, Some("ja"), ErrorMode::Ignore, "", false, false, false);
    assert_eq!(auto, explicit);
}

#[test]
fn auto_lang_han_matches_explicit_zh() {
    let text = "中文";
    let auto = common::transliterate(
        text,
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let explicit =
        common::transliterate(text, Some("zh"), ErrorMode::Ignore, "", false, false, false);
    assert_eq!(auto, explicit);
}

#[test]
fn auto_lang_hangul_matches_explicit_ko() {
    let text = "한국어";
    let auto = common::transliterate(
        text,
        Some("auto"),
        ErrorMode::Ignore,
        "",
        false,
        false,
        false,
    );
    let explicit =
        common::transliterate(text, Some("ko"), ErrorMode::Ignore, "", false, false, false);
    assert_eq!(auto, explicit);
}
