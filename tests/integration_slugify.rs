//! Integration tests for slugification.

use disarm::api::{slugify, SlugConfig};

#[test]
fn basic_slugify() {
    let config = SlugConfig::default();
    let result = slugify("Hello World", &config);
    assert_eq!(result, "hello-world");
}

#[test]
fn slugify_unicode() {
    let config = SlugConfig::default();
    let result = slugify("Héllo Wörld", &config);
    assert_eq!(result, "hello-world");
}

#[test]
fn slugify_custom_separator() {
    let config = SlugConfig::new().with_separator("_");
    let result = slugify("Hello World", &config);
    assert_eq!(result, "hello_world");
}

#[test]
fn slugify_max_length() {
    let config = SlugConfig::new().with_max_length(5);
    let result = slugify("Hello World", &config);
    assert!(result.len() <= 5, "expected max 5 chars, got: {result:?}");
}

#[test]
fn slugify_no_lowercase() {
    let config = SlugConfig::new().with_lowercase(false);
    let result = slugify("Hello World", &config);
    assert!(result.contains('H') || result.contains('W'));
}

#[test]
fn slugify_empty_input() {
    let config = SlugConfig::default();
    assert_eq!(slugify("", &config), "");
}

#[test]
fn slugify_only_special_chars() {
    let config = SlugConfig::default();
    let result = slugify("!@#$%^&*()", &config);
    assert!(result.is_empty() || result == "-");
}

#[test]
fn slugify_cjk() {
    let config = SlugConfig::default();
    let result = slugify("中文测试", &config);
    assert!(result.is_ascii());
}

#[test]
fn slugify_idempotent() {
    let config = SlugConfig::default();
    let once = slugify("Hello World", &config);
    let twice = slugify(&once, &config);
    assert_eq!(once, twice, "slugify should be idempotent");
}

#[test]
fn slugify_consecutive_separators_collapsed() {
    let config = SlugConfig::default();
    let result = slugify("hello---world", &config);
    assert!(
        !result.contains("--"),
        "consecutive separators should be collapsed"
    );
}

// --- BUG-1 regression: multi-byte UTF-8 + HTML entities ---

#[test]
fn slugify_multibyte_with_entities() {
    let config = SlugConfig::default();
    let result = slugify("café &amp; résumé", &config);
    assert_eq!(result, "cafe-resume", "full slug for 'café &amp; résumé'");
}

#[test]
fn slugify_cjk_with_entities() {
    let config = SlugConfig::default();
    let result = slugify("中文 &amp; test", &config);
    assert!(result.contains("test"), "expected 'test' in: {result:?}");
}

// --- BUG-2 regression: malformed numeric entity + multi-byte chars ---

#[test]
fn slugify_malformed_entity_multibyte_no_panic() {
    // This input triggered a panic in decode_numeric_entity_skip
    // when it walked through UTF-8 continuation bytes.
    let config = SlugConfig::new().with_max_length(1);
    let result = slugify("&#AaAA a0\u{1ACF0}\u{2D30}", &config);
    assert!(result.len() <= 1);
}

// --- DESIGN-1: decimal / hexadecimal flags ---

#[test]
fn slugify_decimal_disabled() {
    let config = SlugConfig::new().with_decimal(false);
    // &#65; is 'A' — with decimal=false it should NOT be decoded,
    // so the raw &#65; characters appear in the transliteration input.
    let result = slugify("&#65;", &config);
    // The '&', '#', '6', '5', ';' should survive as ASCII and produce something
    assert!(!result.is_empty());
    // Hex entities should still decode: &#x41; → 'A'
    let config_hex = SlugConfig::new().with_decimal(false);
    let result_hex = slugify("&#x41;", &config_hex);
    assert!(
        result_hex.contains('a'),
        "hex entity should decode to 'A' → 'a': {result_hex:?}"
    );
}

#[test]
fn slugify_hexadecimal_disabled() {
    let config = SlugConfig::new().with_hexadecimal(false);
    // &#x41; should NOT be decoded
    let result = slugify("&#x41;", &config);
    assert!(!result.is_empty());
    // Decimal entities should still decode: &#65; → 'A'
    let config_dec = SlugConfig::new().with_hexadecimal(false);
    let result_dec = slugify("&#65;", &config_dec);
    assert!(
        result_dec.contains('a'),
        "decimal entity should decode to 'A' → 'a': {result_dec:?}"
    );
}

// --- Stopwords ---

#[test]
fn slugify_stopwords() {
    let config = SlugConfig::new().with_stopwords(["the", "a"]);
    let result = slugify("The quick brown fox", &config);
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
    let config = SlugConfig::new().with_entities(false);
    // With entities disabled, &amp; is treated as literal characters
    let result = slugify("AT&amp;T", &config);
    assert!(
        result.contains("amp"),
        "with entities=false, 'amp' should appear in slug: {result:?}"
    );
}

// --- Allow unicode ---

#[test]
fn slugify_allow_unicode() {
    let config = SlugConfig::new().with_allow_unicode(true);
    let result = slugify("café latte", &config);
    assert!(
        result.contains("café"),
        "allow_unicode should preserve 'café': {result:?}"
    );
}

// --- Replacements ---

#[test]
fn slugify_replacements() {
    let config = SlugConfig::new().with_replacements([("@", "at")]);
    let result = slugify("user@example", &config);
    assert!(
        result.contains("at"),
        "replacement '@' → 'at' should apply: {result:?}"
    );
    assert!(!result.contains('@'), "'@' should be replaced: {result:?}");
}

// --- Word boundary truncation ---

#[test]
fn slugify_word_boundary_truncation() {
    let config = SlugConfig::new()
        .with_max_length(12)
        .with_word_boundary(true);
    let result = slugify("hello world foo bar", &config);
    assert!(result.len() <= 12, "should respect max_length: {result:?}");
    // Should truncate at a word boundary (separator), not mid-word
    assert!(
        !result.ends_with('-'),
        "should not end with separator: {result:?}"
    );
}
