//! Integration tests for whitespace, control char, and zero-width stripping.

use _disarm::whitespace;

#[test]
fn collapse_basic() {
    assert_eq!(
        whitespace::_collapse_whitespace("hello   world", true, true),
        "hello world"
    );
}

#[test]
fn collapse_strips_leading_trailing() {
    assert_eq!(
        whitespace::_collapse_whitespace("  hello  ", true, true),
        "hello"
    );
}

#[test]
fn collapse_with_control_chars() {
    assert_eq!(
        whitespace::_collapse_whitespace("hello\x00world", true, true),
        "helloworld"
    );
}

#[test]
fn collapse_preserves_control_when_disabled() {
    assert_eq!(
        whitespace::_collapse_whitespace("hello\x00world", false, true),
        "hello\x00world"
    );
}

#[test]
fn collapse_strips_zero_width() {
    assert_eq!(
        whitespace::_collapse_whitespace("hello\u{200B}world", true, true),
        "helloworld"
    );
}

#[test]
fn collapse_preserves_zero_width_when_disabled() {
    assert_eq!(
        whitespace::_collapse_whitespace("hello\u{200B}world", true, false),
        "hello\u{200B}world"
    );
}

#[test]
fn collapse_empty() {
    assert_eq!(whitespace::_collapse_whitespace("", true, true), "");
}

#[test]
fn collapse_only_whitespace() {
    assert_eq!(
        whitespace::_collapse_whitespace("   \t\n  ", true, true),
        ""
    );
}

#[test]
fn strip_control_standalone() {
    assert_eq!(
        whitespace::strip_control_chars("hello\x00\x01world"),
        "helloworld"
    );
    // Preserves newline and tab
    assert_eq!(
        whitespace::strip_control_chars("hello\nworld"),
        "hello\nworld"
    );
    assert_eq!(
        whitespace::strip_control_chars("hello\tworld"),
        "hello\tworld"
    );
}

#[test]
fn strip_zero_width_standalone() {
    // ZWSP
    assert_eq!(
        whitespace::strip_zero_width_chars("hello\u{200B}world"),
        "helloworld"
    );
    // BOM
    assert_eq!(whitespace::strip_zero_width_chars("\u{FEFF}hello"), "hello");
    // Invisible math operators
    assert_eq!(whitespace::strip_zero_width_chars("a\u{2061}b"), "ab");
    // Normal text unchanged
    assert_eq!(
        whitespace::strip_zero_width_chars("hello world"),
        "hello world"
    );
}

#[test]
fn strip_control_preserves_whitespace() {
    // Standalone strip_control does NOT collapse whitespace
    assert_eq!(
        whitespace::strip_control_chars("hello   world"),
        "hello   world"
    );
}

#[test]
fn all_zero_width_chars_stripped() {
    let all_zw = "\u{200B}\u{200C}\u{200D}\u{FEFF}\u{2060}\u{180E}\u{2061}\u{2062}\u{2063}\u{2064}";
    let input = format!("x{all_zw}y");
    assert_eq!(whitespace::strip_zero_width_chars(&input), "xy");
}
