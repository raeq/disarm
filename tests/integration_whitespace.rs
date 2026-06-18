//! Integration tests for whitespace, control char, and zero-width stripping.

use disarm::api;

#[test]
fn collapse_basic() {
    assert_eq!(api::collapse_whitespace("hello   world"), "hello world");
}

#[test]
fn collapse_strips_leading_trailing() {
    assert_eq!(api::collapse_whitespace("  hello  "), "hello");
}

#[test]
fn collapse_folds_only_preserves_control() {
    // #433: collapse folds whitespace ONLY — a non-whitespace control (NUL) is
    // NOT deleted here (that is strip_control_chars' job); it passes through.
    assert_eq!(api::collapse_whitespace("hello\x00world"), "hello\x00world");
}

#[test]
fn collapse_folds_only_preserves_zero_width() {
    // #433: zero-width is preserved here (strip_zero_width_chars' job).
    assert_eq!(
        api::collapse_whitespace("hello\u{200B}world"),
        "hello\u{200B}world"
    );
}

#[test]
fn collapse_folds_line_controls_to_space() {
    // #433: CR folds to a space (was deleted → joined tokens).
    assert_eq!(api::collapse_whitespace("a\rb"), "a b");
    assert_eq!(api::collapse_whitespace("a\u{000B}b"), "a b"); // VT
    assert_eq!(api::collapse_whitespace("a\u{0085}b"), "a b"); // NEL
}

#[test]
fn collapse_folds_blank_render_set() {
    // #433: Braille blank + Hangul fillers fold to a space.
    assert_eq!(api::collapse_whitespace("a\u{2800}b"), "a b");
    assert_eq!(api::collapse_whitespace("a\u{3164}b"), "a b");
}

#[test]
fn collapse_empty() {
    assert_eq!(api::collapse_whitespace(""), "");
}

#[test]
fn collapse_only_whitespace() {
    assert_eq!(api::collapse_whitespace("   \t\n  "), "");
}

#[test]
fn strip_control_standalone() {
    assert_eq!(api::strip_control_chars("hello\x00\x01world"), "helloworld");
    // Preserves newline and tab
    assert_eq!(api::strip_control_chars("hello\nworld"), "hello\nworld");
    assert_eq!(api::strip_control_chars("hello\tworld"), "hello\tworld");
}

#[test]
fn strip_zero_width_standalone() {
    // ZWSP
    assert_eq!(
        api::strip_zero_width_chars("hello\u{200B}world"),
        "helloworld"
    );
    // BOM
    assert_eq!(api::strip_zero_width_chars("\u{FEFF}hello"), "hello");
    // Invisible math operators
    assert_eq!(api::strip_zero_width_chars("a\u{2061}b"), "ab");
    // Normal text unchanged
    assert_eq!(api::strip_zero_width_chars("hello world"), "hello world");
}

#[test]
fn strip_control_preserves_whitespace() {
    // Standalone strip_control does NOT collapse whitespace
    assert_eq!(api::strip_control_chars("hello   world"), "hello   world");
}

#[test]
fn all_zero_width_chars_stripped() {
    let all_zw = "\u{200B}\u{200C}\u{200D}\u{FEFF}\u{2060}\u{180E}\u{2061}\u{2062}\u{2063}\u{2064}";
    let input = format!("x{all_zw}y");
    assert_eq!(api::strip_zero_width_chars(&input), "xy");
}
