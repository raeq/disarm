//! Zalgo text detection and stripping.
//!
//! Zalgo text abuses Unicode combining marks by stacking dozens of diacriticals
//! on a single base character, producing visually disruptive "glitchy" text.
//! Legitimate text rarely exceeds 2–3 combining marks per base character
//! (e.g. Vietnamese `ệ` = e + combining circumflex + combining dot below).
//!
//! This module provides:
//! - `is_zalgo()` — detect whether text contains excessive combining marks
//! - `strip_zalgo()` — cap combining marks per base character, preserving
//!   legitimate diacritics while removing the stacked abuse

use pyo3::prelude::*;
use unicode_normalization::char::is_combining_mark;
use unicode_normalization::UnicodeNormalization;

/// Default threshold: a base character with more than this many combining marks
/// is considered zalgo.  Vietnamese `ệ` has 2 combining marks in NFD, so 3
/// is a safe default that catches abuse while preserving all real-world text.
const DEFAULT_THRESHOLD: usize = 3;

/// Default cap for `strip_zalgo`: keep at most this many combining marks per
/// base character.  Set to 2 to preserve all legitimate diacritics (including
/// Vietnamese double-stacked marks) while stripping anything beyond that.
const DEFAULT_MAX_MARKS: usize = 2;

/// Count consecutive combining marks after each base character in NFD form.
/// Returns the maximum count found.
fn max_combining_run(text: &str) -> usize {
    let mut max_run: usize = 0;
    let mut current_run: usize = 0;

    for ch in text.nfd() {
        if is_combining_mark(ch) {
            current_run += 1;
            if current_run > max_run {
                max_run = current_run;
            }
        } else {
            current_run = 0;
        }
    }
    max_run
}

/// Detect whether text contains zalgo-style combining mark abuse.
///
/// Returns `True` if any base character has more than `threshold` consecutive
/// combining marks in NFD decomposition.
///
/// # Parameters
/// - `threshold`: Maximum allowed combining marks per base character (default: 3).
///   Vietnamese `ệ` has 2 marks in NFD — the default of 3 is safe for all
///   legitimate scripts.
#[pyfunction]
#[pyo3(signature = (text, *, threshold=DEFAULT_THRESHOLD))]
pub fn _is_zalgo(text: &str, threshold: usize) -> bool {
    // Fast path: pure ASCII has no combining marks.
    if text.is_ascii() {
        return false;
    }
    max_combining_run(text) > threshold
}

/// Strip excessive combining marks, keeping at most `max_marks` per base
/// character.  Operates in NFD (decomposed) space and recomposes to NFC.
///
/// This preserves legitimate diacritics (é, ñ, ệ) while removing zalgo
/// stacking abuse.
///
/// # Parameters
/// - `max_marks`: Maximum combining marks to keep per base character (default: 2).
///   Set to 0 to strip all combining marks (equivalent to `strip_accents`).
#[pyfunction]
#[pyo3(signature = (text, *, max_marks=DEFAULT_MAX_MARKS))]
pub fn _strip_zalgo(text: &str, max_marks: usize) -> String {
    // Fast path: pure ASCII has no combining marks.
    if text.is_ascii() {
        return text.to_owned();
    }

    let mut result = String::with_capacity(text.len());
    let mut mark_count: usize = 0;

    for ch in text.nfd() {
        if is_combining_mark(ch) {
            mark_count += 1;
            if mark_count <= max_marks {
                result.push(ch);
            }
            // else: drop the excess combining mark
        } else {
            mark_count = 0;
            result.push(ch);
        }
    }

    // Recompose to NFC for consistency with the rest of the library.
    result.nfc().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_zalgo_clean_text() {
        assert!(!_is_zalgo("hello world", 3));
        assert!(!_is_zalgo("café résumé", 3));
        assert!(!_is_zalgo("", 3));
    }

    #[test]
    fn test_is_zalgo_ascii_fast_path() {
        assert!(!_is_zalgo("just ascii text 12345!@#$%", 3));
    }

    #[test]
    fn test_is_zalgo_vietnamese() {
        // Vietnamese ệ = e + combining circumflex + combining dot below (2 marks)
        assert!(!_is_zalgo("Việt Nam", 3));
        assert!(!_is_zalgo("ệ", 2));
    }

    #[test]
    fn test_is_zalgo_detects_stacking() {
        // Build zalgo: 'a' + 10 combining marks
        let mut zalgo = String::from("a");
        for _ in 0..10 {
            zalgo.push('\u{0300}'); // combining grave accent
        }
        assert!(_is_zalgo(&zalgo, 3));
    }

    #[test]
    fn test_is_zalgo_threshold_boundary() {
        // Exactly at threshold: not zalgo
        let mut text = String::from("a");
        for _ in 0..3 {
            text.push('\u{0300}');
        }
        assert!(!_is_zalgo(&text, 3));

        // One above threshold: zalgo
        text.push('\u{0300}');
        assert!(_is_zalgo(&text, 3));
    }

    #[test]
    fn test_strip_zalgo_clean_text_unchanged() {
        assert_eq!(_strip_zalgo("hello world", 2), "hello world");
        assert_eq!(_strip_zalgo("café", 2), "café");
    }

    #[test]
    fn test_strip_zalgo_preserves_legitimate_diacritics() {
        // Vietnamese ệ has 2 combining marks — should be preserved with max_marks=2
        let input = "Việt Nam";
        assert_eq!(_strip_zalgo(input, 2), input);

        // French accents — 1 combining mark each
        assert_eq!(_strip_zalgo("résumé", 2), "résumé");
    }

    #[test]
    fn test_strip_zalgo_removes_excess() {
        // 'a' + 10 combining graves → should keep only max_marks
        let mut zalgo = String::from("a");
        for _ in 0..10 {
            zalgo.push('\u{0300}'); // combining grave accent
        }
        let result = _strip_zalgo(&zalgo, 2);
        // Result should be 'a' with exactly 2 combining graves (in NFC: à + 1 extra grave)
        // NFD: a + grave + grave, NFC: à + grave (combining grave after precomposed à)
        // The key assertion: no more than 2 combining marks survived
        assert!(result.chars().count() <= 3); // base + at most 2 marks after NFC
        assert!(result.starts_with('à'));
    }

    #[test]
    fn test_strip_zalgo_max_marks_zero_strips_all() {
        assert_eq!(_strip_zalgo("café", 0), "cafe");
        assert_eq!(_strip_zalgo("résumé", 0), "resume");
    }

    #[test]
    fn test_strip_zalgo_ascii_fast_path() {
        let input = "just ascii";
        assert_eq!(_strip_zalgo(input, 2), input);
    }

    #[test]
    fn test_strip_zalgo_multiple_base_chars() {
        // Multiple base chars each with excessive stacking
        let mut zalgo = String::new();
        for base in ['H', 'i'] {
            zalgo.push(base);
            for _ in 0..8 {
                zalgo.push('\u{0300}');
                zalgo.push('\u{0301}');
                zalgo.push('\u{0302}');
            }
        }
        let result = _strip_zalgo(&zalgo, 2);
        // Each base char should have at most 2 combining marks
        let mut mark_count = 0;
        for ch in result.nfd() {
            if is_combining_mark(ch) {
                mark_count += 1;
                assert!(mark_count <= 2, "Too many combining marks in output");
            } else {
                mark_count = 0;
            }
        }
    }

    #[test]
    fn test_max_combining_run() {
        assert_eq!(max_combining_run("hello"), 0);
        assert_eq!(max_combining_run("café"), 1);
        assert_eq!(max_combining_run(""), 0);

        let mut text = String::from("a");
        for _ in 0..5 {
            text.push('\u{0300}');
        }
        assert_eq!(max_combining_run(&text), 5);
    }
}
