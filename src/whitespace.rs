use pyo3::prelude::*;

/// Normalize Unicode whitespace to single ASCII spaces.
/// Optionally strip control characters and zero-width characters.
#[pyfunction]
#[pyo3(signature = (text, *, strip_control=true, strip_zero_width=true))]
pub fn _collapse_whitespace(text: &str, strip_control: bool, strip_zero_width: bool) -> String {
    let mut result = String::with_capacity(text.len());
    let mut prev_was_space = false;

    for ch in text.chars() {
        if is_zero_width(ch) {
            if !strip_zero_width {
                result.push(ch);
            }
            continue;
        }

        if ch.is_control() && ch != '\n' && ch != '\t' {
            if !strip_control {
                result.push(ch);
            }
            continue;
        }

        if ch.is_whitespace() {
            if !prev_was_space {
                result.push(' ');
                prev_was_space = true;
            }
        } else {
            result.push(ch);
            prev_was_space = false;
        }
    }

    // Trim leading/trailing whitespace
    result.trim().to_owned()
}

/// Check if a character is invisible/zero-width and should be stripped.
///
/// Covers zero-width joiners/spaces, the word joiner family, and the
/// invisible math operators (U+2061–2064) which render identically to
/// zero-width characters and can be abused for text spoofing.
fn is_zero_width(ch: char) -> bool {
    matches!(
        ch,
        // ── Zero-width spaces / joiners ─────────────────
        '\u{200B}'   // ZWSP  Zero-Width Space
        | '\u{200C}' // ZWNJ  Zero-Width Non-Joiner
        | '\u{200D}' // ZWJ   Zero-Width Joiner
        | '\u{FEFF}' // BOM   Byte Order Mark / Zero-Width No-Break Space
        // ── Word joiners ────────────────────────────────
        | '\u{2060}' // WJ    Word Joiner
        | '\u{180E}' // MVS   Mongolian Vowel Separator
        // ── Invisible math operators (General_Category=Cf) ──
        // Added in Unicode 3.2; render as zero-width in all contexts
        // outside mathematical typesetting. Frequently found in
        // copy-pasted text from equation editors.
        | '\u{2061}' // Function Application
        | '\u{2062}' // Invisible Times
        | '\u{2063}' // Invisible Separator
        | '\u{2064}' // Invisible Plus
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_collapse_whitespace() {
        assert_eq!(
            _collapse_whitespace("hello   world", true, true),
            "hello world"
        );
    }

    #[test]
    fn test_strip_zero_width() {
        assert_eq!(_collapse_whitespace("he\u{200B}llo", true, true), "hello");
    }

    #[test]
    fn test_strip_invisible_math_operators() {
        // U+2061–U+2064: invisible math operators that render as zero-width.
        // Common in text copy-pasted from equation editors.
        assert_eq!(_collapse_whitespace("a\u{2061}b", true, true), "ab"); // Function Application
        assert_eq!(_collapse_whitespace("a\u{2062}b", true, true), "ab"); // Invisible Times
        assert_eq!(_collapse_whitespace("a\u{2063}b", true, true), "ab"); // Invisible Separator
        assert_eq!(_collapse_whitespace("a\u{2064}b", true, true), "ab"); // Invisible Plus
    }

    #[test]
    fn test_strip_all_zero_width_chars() {
        // Exhaustive: every character in is_zero_width in a single string.
        // If a new char is added to is_zero_width, add it here too.
        let all_zw = "\u{200B}\u{200C}\u{200D}\u{FEFF}\u{2060}\u{180E}\
                      \u{2061}\u{2062}\u{2063}\u{2064}";
        assert_eq!(
            _collapse_whitespace(&format!("x{all_zw}y"), true, true),
            "xy"
        );
        // Verify count: 10 zero-width characters
        assert_eq!(all_zw.chars().count(), 10);
    }

    #[test]
    fn test_nul_stripped_with_control() {
        // NUL (U+0000) is a C0 control character — stripped when strip_control=true.
        assert_eq!(_collapse_whitespace("a\x00b", true, true), "ab");
    }

    #[test]
    fn test_nul_preserved_without_control() {
        // With strip_control=false, NUL passes through.
        assert_eq!(_collapse_whitespace("a\x00b", false, true), "a\x00b");
    }

    #[test]
    fn test_zero_width_preserved_when_disabled() {
        // With strip_zero_width=false, invisible chars should pass through.
        assert_eq!(
            _collapse_whitespace("a\u{2061}b", true, false),
            "a\u{2061}b"
        );
    }

    mod proptest_properties {
        use super::*;
        use proptest::prelude::*;

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            /// Collapsing whitespace is idempotent.
            #[test]
            fn collapse_whitespace_idempotent(s in "\\PC*") {
                let once = _collapse_whitespace(&s, true, true);
                let twice = _collapse_whitespace(&once, true, true);
                prop_assert_eq!(&once, &twice);
            }

            /// Result has no leading or trailing whitespace.
            #[test]
            fn no_leading_trailing_whitespace(s in "\\PC*") {
                let result = _collapse_whitespace(&s, true, true);
                if !result.is_empty() {
                    prop_assert_ne!(result.as_bytes()[0], b' ');
                    prop_assert_ne!(result.as_bytes()[result.len() - 1], b' ');
                }
            }

            /// Result never contains consecutive spaces.
            #[test]
            fn no_consecutive_spaces(s in "\\PC*") {
                let result = _collapse_whitespace(&s, true, true);
                prop_assert!(!result.contains("  "), "double space in: {result:?}");
            }

            /// Pure alphanumeric ASCII passes through unchanged.
            #[test]
            fn alphanumeric_passthrough(s in "[a-zA-Z0-9]{1,50}") {
                let result = _collapse_whitespace(&s, true, true);
                prop_assert_eq!(&result, &s);
            }
        }
    }
}
