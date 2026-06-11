//! Integration tests for emoji processing (demojize_rust).

use _disarm::emoji::demojize_rust;

// --- Basic demojize ---

#[test]
fn demojize_single_emoji() {
    let result = demojize_rust("😀", false);
    assert_eq!(result, "grinning face");
}

#[test]
fn demojize_emoji_in_text() {
    let result = demojize_rust("Hello 😀 world", false);
    assert_eq!(result, "Hello grinning face world");
}

#[test]
fn demojize_multiple_emoji() {
    let result = demojize_rust("😀😂", false);
    assert!(
        result.contains("grinning face"),
        "should contain first emoji name: {result:?}"
    );
    assert!(
        result.contains("face with tears of joy"),
        "should contain second emoji name: {result:?}"
    );
}

#[test]
fn demojize_no_emoji() {
    let result = demojize_rust("Hello world", false);
    assert_eq!(result, "Hello world");
}

#[test]
fn demojize_empty() {
    assert_eq!(demojize_rust("", false), "");
}

// --- PERF-1: ASCII fast-path ---

#[test]
fn demojize_ascii_fast_path() {
    // Pure ASCII should return an identical copy without scanning
    let input = "The quick brown fox jumps over the lazy dog 12345!@#";
    let result = demojize_rust(input, false);
    assert_eq!(result, input);
}

#[test]
fn demojize_ascii_with_special_chars() {
    // ASCII punctuation, digits, control-like chars — all fast-path
    let input = "hello\tworld\n123 <>&\"'";
    let result = demojize_rust(input, false);
    assert_eq!(result, input);
}

// --- strip_modifiers ---

#[test]
fn demojize_strip_modifiers() {
    // With strip_modifiers=true, skin tone suffixes like ": light skin tone"
    // should be stripped from the CLDR name
    let with_mods = demojize_rust("👋", true);
    let without_mods = demojize_rust("👋", false);
    // Both should produce a name; with strip_modifiers they should be equal
    // for a base emoji (no modifier), but the function should not panic
    assert!(!with_mods.is_empty());
    assert!(!without_mods.is_empty());
}

// --- Non-ASCII non-emoji text ---

#[test]
fn demojize_non_ascii_non_emoji() {
    // Accented Latin, CJK, Cyrillic — none are emoji, should pass through
    let input = "café 中文 Москва";
    let result = demojize_rust(input, false);
    assert_eq!(
        result, input,
        "non-emoji text should pass through unchanged"
    );
}

// --- Mixed emoji and non-ASCII ---

#[test]
fn demojize_mixed_emoji_and_unicode() {
    let result = demojize_rust("café 😀 résumé", false);
    assert!(
        result.contains("café"),
        "non-emoji text preserved: {result:?}"
    );
    assert!(
        result.contains("grinning face"),
        "emoji expanded: {result:?}"
    );
    assert!(
        result.contains("résumé"),
        "non-emoji text preserved: {result:?}"
    );
}
