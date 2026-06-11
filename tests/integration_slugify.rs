//! Integration tests for slugification.

use _disarm::slugify::{slugify_impl, SlugConfig};

#[test]
fn basic_slugify() {
    let config = SlugConfig::default();
    let result = slugify_impl("Hello World", &config);
    assert_eq!(result, "hello-world");
}

#[test]
fn slugify_unicode() {
    let config = SlugConfig::default();
    let result = slugify_impl("Héllo Wörld", &config);
    assert_eq!(result, "hello-world");
}

#[test]
fn slugify_custom_separator() {
    let config = SlugConfig {
        separator: "_".to_owned(),
        ..Default::default()
    };
    let result = slugify_impl("Hello World", &config);
    assert_eq!(result, "hello_world");
}

#[test]
fn slugify_max_length() {
    let config = SlugConfig {
        max_length: 5,
        ..Default::default()
    };
    let result = slugify_impl("Hello World", &config);
    assert!(result.len() <= 5, "expected max 5 chars, got: {result:?}");
}

#[test]
fn slugify_no_lowercase() {
    let config = SlugConfig {
        lowercase: false,
        ..Default::default()
    };
    let result = slugify_impl("Hello World", &config);
    assert!(result.contains('H') || result.contains('W'));
}

#[test]
fn slugify_empty_input() {
    let config = SlugConfig::default();
    assert_eq!(slugify_impl("", &config), "");
}

#[test]
fn slugify_only_special_chars() {
    let config = SlugConfig::default();
    let result = slugify_impl("!@#$%^&*()", &config);
    assert!(result.is_empty() || result == "-");
}

#[test]
fn slugify_cjk() {
    let config = SlugConfig::default();
    let result = slugify_impl("中文测试", &config);
    assert!(result.is_ascii());
}

#[test]
fn slugify_idempotent() {
    let config = SlugConfig::default();
    let once = slugify_impl("Hello World", &config);
    let twice = slugify_impl(&once, &config);
    assert_eq!(once, twice, "slugify should be idempotent");
}

#[test]
fn slugify_consecutive_separators_collapsed() {
    let config = SlugConfig::default();
    let result = slugify_impl("hello---world", &config);
    assert!(
        !result.contains("--"),
        "consecutive separators should be collapsed"
    );
}

// --- BUG-1 regression: multi-byte UTF-8 + HTML entities ---

#[test]
fn slugify_multibyte_with_entities() {
    let config = SlugConfig::default();
    let result = slugify_impl("café &amp; résumé", &config);
    assert_eq!(result, "cafe-resume", "full slug for 'café &amp; résumé'");
}

#[test]
fn slugify_cjk_with_entities() {
    let config = SlugConfig::default();
    let result = slugify_impl("中文 &amp; test", &config);
    assert!(result.contains("test"), "expected 'test' in: {result:?}");
}

// --- BUG-2 regression: malformed numeric entity + multi-byte chars ---

#[test]
fn slugify_malformed_entity_multibyte_no_panic() {
    // This input triggered a panic in decode_numeric_entity_skip
    // when it walked through UTF-8 continuation bytes.
    let config = SlugConfig {
        max_length: 1,
        ..Default::default()
    };
    let result = slugify_impl("&#AaAA a0\u{1ACF0}\u{2D30}", &config);
    assert!(result.len() <= 1);
}

// --- DESIGN-1: decimal / hexadecimal flags ---

#[test]
fn slugify_decimal_disabled() {
    let config = SlugConfig {
        decimal: false,
        ..Default::default()
    };
    // &#65; is 'A' — with decimal=false it should NOT be decoded,
    // so the raw &#65; characters appear in the transliteration input.
    let result = slugify_impl("&#65;", &config);
    // The '&', '#', '6', '5', ';' should survive as ASCII and produce something
    assert!(!result.is_empty());
    // Hex entities should still decode: &#x41; → 'A'
    let config_hex = SlugConfig {
        decimal: false,
        ..Default::default()
    };
    let result_hex = slugify_impl("&#x41;", &config_hex);
    assert!(
        result_hex.contains('a'),
        "hex entity should decode to 'A' → 'a': {result_hex:?}"
    );
}

#[test]
fn slugify_hexadecimal_disabled() {
    let config = SlugConfig {
        hexadecimal: false,
        ..Default::default()
    };
    // &#x41; should NOT be decoded
    let result = slugify_impl("&#x41;", &config);
    assert!(!result.is_empty());
    // Decimal entities should still decode: &#65; → 'A'
    let config_dec = SlugConfig {
        hexadecimal: false,
        ..Default::default()
    };
    let result_dec = slugify_impl("&#65;", &config_dec);
    assert!(
        result_dec.contains('a'),
        "decimal entity should decode to 'A' → 'a': {result_dec:?}"
    );
}

// --- Stopwords ---

#[test]
fn slugify_stopwords() {
    let config = SlugConfig {
        stopwords: vec!["the".to_owned(), "a".to_owned()],
        ..Default::default()
    };
    let result = slugify_impl("The quick brown fox", &config);
    assert!(
        !result.contains("the"),
        "stopword 'the' should be removed: {result:?}"
    );
    assert!(
        result.contains("quick"),
        "non-stopword should remain: {result:?}"
    );
}

// --- Entities disabled ---

#[test]
fn slugify_entities_disabled() {
    let config = SlugConfig {
        entities: false,
        ..Default::default()
    };
    // With entities disabled, &amp; is treated as literal characters
    let result = slugify_impl("AT&amp;T", &config);
    assert!(
        result.contains("amp"),
        "with entities=false, 'amp' should appear in slug: {result:?}"
    );
}

// --- Allow unicode ---

#[test]
fn slugify_allow_unicode() {
    let config = SlugConfig {
        allow_unicode: true,
        ..Default::default()
    };
    let result = slugify_impl("café latte", &config);
    assert!(
        result.contains("café"),
        "allow_unicode should preserve 'café': {result:?}"
    );
}

// --- Replacements ---

#[test]
fn slugify_replacements() {
    let config = SlugConfig {
        replacements: vec![("@".to_owned(), "at".to_owned())],
        ..Default::default()
    };
    let result = slugify_impl("user@example", &config);
    assert!(
        result.contains("at"),
        "replacement '@' → 'at' should apply: {result:?}"
    );
    assert!(!result.contains('@'), "'@' should be replaced: {result:?}");
}

// --- Word boundary truncation ---

#[test]
fn slugify_word_boundary_truncation() {
    let config = SlugConfig {
        max_length: 12,
        word_boundary: true,
        ..Default::default()
    };
    let result = slugify_impl("hello world foo bar", &config);
    assert!(result.len() <= 12, "should respect max_length: {result:?}");
    // Should truncate at a word boundary (separator), not mid-word
    assert!(
        !result.ends_with('-'),
        "should not end with separator: {result:?}"
    );
}
