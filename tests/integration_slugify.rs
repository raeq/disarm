//! Integration tests for slugification.

use _translit::slugify::{slugify_impl, SlugConfig};

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

#[test]
fn slugify_multibyte_with_entities() {
    // BUG-1 regression: decode_entities must not corrupt multi-byte UTF-8
    // when the input contains both non-ASCII chars and HTML entities.
    let config = SlugConfig::default();
    let result = slugify_impl("café &amp; résumé", &config);
    assert!(
        result.contains("cafe"),
        "expected 'cafe' in slug, got: {result:?}"
    );
    assert!(
        result.contains("resume"),
        "expected 'resume' in slug, got: {result:?}"
    );
}

#[test]
fn slugify_cjk_with_entities() {
    let config = SlugConfig::default();
    let result = slugify_impl("中文 &amp; test", &config);
    assert!(result.contains("test"), "expected 'test' in: {result:?}");
}
