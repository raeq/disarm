//! Layer 1 (pure-Rust core): UAX #29 grapheme segmentation. No pyo3.
//!
//! Shims in `src/py/grapheme.rs`; crates.io surface is
//! `crate::api::{grapheme_len, grapheme_split, grapheme_truncate}`.

use unicode_segmentation::UnicodeSegmentation;

/// Iterate the extended grapheme clusters (UAX #29) of `text`.
///
/// The single in-crate choke point for grapheme segmentation: every other
/// grapheme/width operation goes through this, so swapping the segmenter (the
/// in-house UAX #29 implementation tracked in #226) touches only this function.
pub(crate) fn clusters(text: &str) -> impl Iterator<Item = &str> {
    text.graphemes(true)
}

/// Count the number of user-perceived characters (extended grapheme clusters).
///
/// This is the correct answer to "how many characters does the user see?"
/// A single grapheme cluster may span multiple codepoints (e.g., flag emoji,
/// skin-toned emoji, Hangul syllables with combining jamo, Zalgo text).
///
/// Examples:
///   grapheme_len("café")  → 4  (not 5 if NFD-decomposed)
///   grapheme_len("🏳️‍🌈")   → 1  (rainbow flag: 4 codepoints, 1 grapheme)
///   grapheme_len("👩‍👩‍👧‍👦")  → 1  (family emoji: 7 codepoints, 1 grapheme)
pub(crate) fn grapheme_len(text: &str) -> usize {
    clusters(text).count()
}

/// Split text into a list of extended grapheme clusters.
///
/// Each element is a user-perceived character. This is the correct way
/// to iterate over "characters" in Unicode text.
pub(crate) fn grapheme_split(text: &str) -> Vec<String> {
    clusters(text).map(std::borrow::ToOwned::to_owned).collect()
}

/// Truncate `text` to at most `max_graphemes` clusters. The core of
/// `crate::api::grapheme_truncate`, split out so callers with a known-good `usize`
/// (tests, internal callers) skip the boundary conversion.
pub(crate) fn truncate_to_graphemes(text: &str, max_graphemes: usize) -> String {
    // Reserve for the *result*, not the whole input (review M-P4): keeping a few
    // graphemes from a huge string shouldn't allocate the full input length.
    // ~4 bytes/grapheme covers typical clusters; rare large emoji ZWJ sequences
    // just trigger an amortized realloc. Capped at the input length.
    let cap = text.len().min(max_graphemes.saturating_mul(4));
    let mut result = String::with_capacity(cap);
    for (count, g) in clusters(text).enumerate() {
        if count >= max_graphemes {
            break;
        }
        result.push_str(g);
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_grapheme_len_ascii() {
        assert_eq!(grapheme_len("hello"), 5);
    }

    #[test]
    fn test_grapheme_len_cafe_nfc() {
        assert_eq!(grapheme_len("caf\u{00E9}"), 4); // NFC é
    }

    #[test]
    fn test_grapheme_len_cafe_nfd() {
        assert_eq!(grapheme_len("cafe\u{0301}"), 4); // NFD e + combining accent = 1 grapheme
    }

    #[test]
    fn test_grapheme_len_family_emoji() {
        // 👩‍👩‍👧‍👦 = 4 person codepoints + 3 ZWJ = 7 codepoints, 1 grapheme
        assert_eq!(grapheme_len("👩\u{200D}👩\u{200D}👧\u{200D}👦"), 1);
    }

    #[test]
    fn test_grapheme_len_flag() {
        // 🇬🇧 = 2 regional indicators, 1 grapheme
        assert_eq!(grapheme_len("🇬🇧"), 1);
    }

    #[test]
    fn test_grapheme_len_hangul() {
        // 한 = 1 precomposed Hangul syllable
        assert_eq!(grapheme_len("한"), 1);
    }

    #[test]
    fn test_grapheme_split_basic() {
        let parts = grapheme_split("café");
        assert_eq!(parts, vec!["c", "a", "f", "é"]);
    }

    #[test]
    fn test_grapheme_split_nfd() {
        let parts = grapheme_split("cafe\u{0301}");
        assert_eq!(parts.len(), 4); // e + combining accent is one grapheme
        assert_eq!(parts[3], "e\u{0301}");
    }

    #[test]
    fn test_grapheme_truncate_basic() {
        assert_eq!(truncate_to_graphemes("hello world", 5), "hello");
    }

    #[test]
    fn test_grapheme_truncate_emoji() {
        let family = "👩\u{200D}👩\u{200D}👧\u{200D}👦 family";
        let truncated = truncate_to_graphemes(family, 1);
        assert_eq!(truncated, "👩\u{200D}👩\u{200D}👧\u{200D}👦");
    }

    #[test]
    fn test_grapheme_truncate_nfd() {
        let text = "cafe\u{0301}s"; // 5 graphemes: c, a, f, e+accent, s
        let truncated = truncate_to_graphemes(text, 4);
        assert_eq!(truncated, "cafe\u{0301}"); // keeps the combining accent with e
    }

    #[test]
    fn test_grapheme_truncate_within_limit() {
        assert_eq!(truncate_to_graphemes("hi", 10), "hi");
    }

    #[test]
    fn test_grapheme_truncate_rejects_negative() {
        // #231: the non-negative contract is enforced in the core.
        let err = crate::error::checked_max_graphemes(-1).unwrap_err();
        assert!(err
            .to_string()
            .contains("max_graphemes must be non-negative, got -1"));
        assert_eq!(crate::error::checked_max_graphemes(0).unwrap(), 0);
    }

    mod proptest_properties {
        use super::*;
        use proptest::prelude::*;

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            /// len(grapheme_split(s)) == grapheme_len(s).
            #[test]
            fn split_len_consistent(s in "\\PC*") {
                let parts = grapheme_split(&s);
                let len = grapheme_len(&s);
                prop_assert_eq!(parts.len(), len);
            }

            /// Joining grapheme_split recovers the original string (lossless partition).
            #[test]
            fn split_roundtrip(s in "\\PC*") {
                let parts = grapheme_split(&s);
                let joined: String = parts.concat();
                prop_assert_eq!(&joined, &s);
            }

            /// grapheme_truncate never exceeds the requested count.
            #[test]
            fn truncate_respects_limit(s in "\\PC*", n in 0..200usize) {
                let result = truncate_to_graphemes(&s, n);
                prop_assert!(grapheme_len(&result) <= n);
            }

            /// grapheme_truncate returns a byte-prefix of the original.
            #[test]
            fn truncate_is_prefix(s in "\\PC*", n in 0..200usize) {
                let result = truncate_to_graphemes(&s, n);
                prop_assert!(s.starts_with(&result));
            }

            /// Truncating at grapheme_len(s) returns the string unchanged.
            #[test]
            fn truncate_at_full_length_is_identity(s in "\\PC*") {
                let len = grapheme_len(&s);
                let result = truncate_to_graphemes(&s, len);
                prop_assert_eq!(&result, &s);
            }
        }
    }
}
