use pyo3::prelude::*;

/// Normalize Unicode whitespace to single ASCII spaces.
/// Optionally strip control characters and zero-width characters.
///
/// When `strip_control` is true, `\r` (carriage return) is stripped as a
/// control character, so Windows-style `\r\n` line endings become `\n`.
#[pyfunction]
#[pyo3(signature = (text, *, strip_control=true, strip_zero_width=true))]
pub fn _collapse_whitespace(text: &str, strip_control: bool, strip_zero_width: bool) -> String {
    let mut result = String::with_capacity(text.len());
    let mut prev_was_space = false;
    // Track whether we've seen any non-whitespace yet to skip leading spaces.
    let mut seen_non_ws = false;

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
            if seen_non_ws && !prev_was_space {
                result.push(' ');
                prev_was_space = true;
            }
        } else {
            result.push(ch);
            prev_was_space = false;
            seen_non_ws = true;
        }
    }

    // Strip trailing whitespace in-place (at most one trailing space from
    // the collapsing logic above).
    if result.ends_with(' ') {
        result.truncate(result.len() - 1);
    }

    result
}

/// Strip control characters from text (excluding newline and tab).
/// Note: `\r` (carriage return) is stripped, so `\r\n` becomes `\n`.
pub fn strip_control_chars(text: &str) -> String {
    text.chars()
        .filter(|&ch| !ch.is_control() || ch == '\n' || ch == '\t')
        .collect()
}

/// Strip zero-width and invisible characters from text.
pub fn strip_zero_width_chars(text: &str) -> String {
    // `is_zero_width` matches no ASCII code point, so pure-ASCII input is
    // returned unchanged — skip the filter+collect (and its allocation) on the
    // common ASCII case (#252 O6.2). Premise guarded by `is_zero_width_has_no_ascii`.
    if text.is_ascii() {
        return text.to_owned();
    }
    text.chars().filter(|&ch| !is_zero_width(ch)).collect()
}

/// Check if a character is invisible/zero-width and should be stripped.
///
/// Covers zero-width joiners/spaces, the word joiner family, and the
/// invisible math operators (U+2061–2064) which render identically to
/// zero-width characters and can be abused for text spoofing.
pub(crate) fn is_zero_width(ch: char) -> bool {
    // The ten code points form two consecutive runs plus two singletons, so a
    // pair of `wrapping_sub` range checks (predicated, no per-arm branch)
    // replaces the scattered compare chain (#235 item 9). Equivalent to the
    // former `matches!`; guarded by `test_strip_all_zero_width_chars`.
    //
    // Runs: ZWSP/ZWNJ/ZWJ (U+200B–U+200D); WJ + invisible math operators
    // U+2061–U+2064 (General_Category=Cf, render zero-width outside math
    // typesetting) which sit contiguously at U+2060–U+2064.
    // Singletons: BOM / ZW no-break space (U+FEFF), Mongolian Vowel Separator
    // (U+180E).
    let cp = ch as u32;
    cp.wrapping_sub(0x200B) <= 2 || cp.wrapping_sub(0x2060) <= 4 || cp == 0xFEFF || cp == 0x180E
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
    fn is_zero_width_has_no_ascii() {
        // strip_zero_width_chars's ASCII fast path is correct only because no
        // ASCII code point is zero-width (#252 O6.2). Guard that premise.
        for c in 0u8..0x80 {
            assert!(
                !is_zero_width(c as char),
                "ASCII {c:#04x} must not be zero-width"
            );
        }
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
