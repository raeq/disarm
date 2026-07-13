//! Layer 1 (pure-Rust core): Unicode whitespace normalization. No pyo3.
//!
//! The PyO3 shim lives in `src/py/whitespace.rs`; the crates.io surface is
//! `crate::api::collapse_whitespace`.

/// Fold Unicode whitespace runs to single ASCII spaces, trimming the ends.
///
/// This **folds whitespace only** (#433): every code point in the explicit
/// [`is_fold_whitespace`] set (the line controls TAB/LF/VT/FF/CR, the
/// information separators FS/GS/RS/US, NEL, and the `Zs`/`Zl`/`Zp` spaces) and
/// the [`is_blank_render`] set (Braille blank, the Hangul fillers) becomes a
/// single space; runs collapse and leading/trailing spaces are trimmed.
///
/// It does **not** delete control or zero-width characters — those are the job
/// of the separate [`strip_control_chars`] / [`strip_zero_width_chars`] steps.
/// Folding (not deleting) the line controls means `a\rb` → `a b`, not `ab`, so
/// an invisible line break can no longer silently join two tokens.
///
/// Ordering contract (review D-8): the three whitespace functions are **not**
/// order-commutative. `collapse_whitespace` is the *terminal* whitespace step —
/// it trims leading/trailing runs that an earlier strip may expose. The presets
/// always run it last; a [`crate::pipeline::Pipeline`] built by hand that
/// sequences a `COLLAPSE_WS` step *before* a later strip can leave untrimmed
/// leading/trailing space. Run collapse after every strip that can expose one.
pub(crate) fn collapse_whitespace(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    collapse_whitespace_into(text, &mut out);
    out
}

/// In-place form of [`collapse_whitespace`] writing into `result` (cleared
/// first). Lets the pipeline reuse one buffer across steps (#236 item 7).
pub(crate) fn collapse_whitespace_into(text: &str, result: &mut String) {
    result.clear();
    result.reserve(text.len());
    let mut prev_was_space = false;
    // Track whether we've seen any non-whitespace yet to skip leading spaces.
    let mut seen_non_ws = false;

    for ch in text.chars() {
        if is_fold_whitespace(ch) || is_blank_render(ch) {
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
}

/// The explicit whitespace-fold set (#433).
///
/// Defined here in the core (not inherited from an engine's `\s`) so every
/// binding folds an identical set. It is the union of the Unicode `White_Space`
/// property and the four information separators `U+001C..U+001F`: the engines
/// disagree on those (Python `re`/`str.isspace()` treat them as whitespace; the
/// Unicode property, the Rust `regex` crate, JS, and .NET do not), and deleting
/// them is the same invisible-join hazard as deleting CR, so disarm folds them.
pub(crate) fn is_fold_whitespace(ch: char) -> bool {
    let cp = ch as u32;
    matches!(cp,
        0x0009..=0x000D   // TAB, LF, VT, FF, CR
        | 0x001C..=0x001F // FS, GS, RS, US (information separators)
        | 0x0085          // NEL
        | 0x0020          // SPACE
        | 0x00A0          // NBSP
        | 0x1680          // OGHAM SPACE MARK
        | 0x2000..=0x200A // EN QUAD … HAIR SPACE
        | 0x2028          // LINE SEPARATOR
        | 0x2029          // PARAGRAPH SEPARATOR
        | 0x202F          // NARROW NO-BREAK SPACE
        | 0x205F          // MEDIUM MATHEMATICAL SPACE
        | 0x3000          // IDEOGRAPHIC SPACE
    )
}

/// Code points that render as a blank cell but are **not** in any space
/// category, so category detection cannot reach them (#433). Folded to a space
/// (not deleted) so the result keeps a separator and cannot itself become an
/// invisible-join vector:
/// - `U+2800` BRAILLE PATTERN BLANK (category `So`) — invisible padding /
///   length-check evasion (originally #413; genuine Braille blanks fold to a
///   space, which is acceptable for the canonicalize/comparison presets).
/// - `U+115F`/`U+1160` HANGUL CHOSEONG/JUNGSEONG FILLER, `U+3164` HANGUL FILLER,
///   `U+FFA0` HALFWIDTH HANGUL FILLER (category `Lo`) — blank-rendering jamo
///   placeholders; isolated fillers in normalized text are padding abuse.
///
/// Maintained as an explicit, documented list; audit against future Unicode
/// versions for other blank-rendering additions.
pub(crate) fn is_blank_render(ch: char) -> bool {
    matches!(ch as u32, 0x2800 | 0x115F | 0x1160 | 0x3164 | 0xFFA0)
}

/// Strip control characters that are **not** whitespace (#433).
///
/// Controls in the [`is_fold_whitespace`] set — TAB, LF, VT, FF, CR, the
/// information separators `U+001C..U+001F`, and NEL — are preserved here so
/// [`collapse_whitespace`] can fold them to a space; deleting them would join
/// the surrounding tokens. Every other C0/C1 control (NUL, DEL, the C1 block,
/// etc.) is removed.
pub(crate) fn strip_control_chars(text: &str) -> String {
    let mut out = String::new();
    strip_control_chars_into(text, &mut out);
    out
}

/// In-place form of [`strip_control_chars`] (#236 item 7).
pub(crate) fn strip_control_chars_into(text: &str, out: &mut String) {
    out.clear();
    // The filter's `size_hint` lower bound is 0, so `extend` cannot pre-size the
    // buffer; reserve up front (review M-P5). A mandatory stage in every key path.
    out.reserve(text.len());
    out.extend(
        text.chars()
            .filter(|&ch| !ch.is_control() || is_fold_whitespace(ch)),
    );
}

/// Strip zero-width and invisible characters from text.
pub(crate) fn strip_zero_width_chars(text: &str) -> String {
    let mut out = String::new();
    strip_zero_width_chars_into(text, &mut out);
    out
}

/// In-place form of [`strip_zero_width_chars`] (#236 item 7).
pub(crate) fn strip_zero_width_chars_into(text: &str, out: &mut String) {
    out.clear();
    // `is_zero_width` matches no ASCII code point, so pure-ASCII input is copied
    // unchanged (#252 O6.2). Premise guarded by `is_zero_width_has_no_ascii`.
    if text.is_ascii() {
        out.push_str(text);
        return;
    }
    out.reserve(text.len()); // filter's size_hint lower bound is 0 (review M-P5)
    out.extend(text.chars().filter(|&ch| !is_zero_width(ch)));
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
        assert_eq!(collapse_whitespace("hello   world"), "hello world");
    }

    #[test]
    fn test_line_controls_fold_not_delete() {
        // #433: every line control folds to a single space (no token join).
        // Previously VT/FF/CR/NEL/FS–US were *deleted*, joining "a"+"b" → "ab".
        for sep in [
            '\u{0009}', '\u{000A}', '\u{000B}', '\u{000C}', '\u{000D}', // TAB,LF,VT,FF,CR
            '\u{001C}', '\u{001D}', '\u{001E}', '\u{001F}', // FS,GS,RS,US
            '\u{0085}', // NEL
        ] {
            assert_eq!(
                collapse_whitespace(&format!("a{sep}b")),
                "a b",
                "{:#06x} should fold to a space",
                sep as u32
            );
        }
    }

    #[test]
    fn test_blank_render_set_folds_to_space() {
        // #433: blank-rendering code points outside the space categories fold to
        // a space (Braille blank + the Hangul fillers).
        for blank in ['\u{2800}', '\u{115F}', '\u{1160}', '\u{3164}', '\u{FFA0}'] {
            assert_eq!(
                collapse_whitespace(&format!("a{blank}b")),
                "a b",
                "{:#06x} should fold to a space",
                blank as u32
            );
        }
    }

    #[test]
    fn test_fold_only_preserves_zero_width_and_nonws_control() {
        // #433: collapse folds whitespace ONLY. Zero-width chars and non-whitespace
        // controls (NUL) are NOT deleted here — that is strip_zero_width_chars /
        // strip_control_chars' job. They pass through unchanged.
        assert_eq!(collapse_whitespace("he\u{200B}llo"), "he\u{200B}llo");
        assert_eq!(collapse_whitespace("a\u{2061}b"), "a\u{2061}b"); // function application
        assert_eq!(collapse_whitespace("a\x00b"), "a\x00b"); // NUL preserved
    }

    #[test]
    fn test_strip_control_preserves_fold_whitespace() {
        // #433: strip_control_chars removes non-whitespace controls but PRESERVES
        // the line controls so collapse can fold them (no join).
        assert_eq!(strip_control_chars("a\x00b"), "ab"); // NUL removed
        assert_eq!(strip_control_chars("a\u{0007}b"), "ab"); // BEL removed
        assert_eq!(strip_control_chars("a\rb"), "a\rb"); // CR preserved (whitespace)
        assert_eq!(strip_control_chars("a\u{000B}b"), "a\u{000B}b"); // VT preserved
        assert_eq!(strip_control_chars("a\u{0085}b"), "a\u{0085}b"); // NEL preserved
        assert_eq!(strip_control_chars("a\tb\nc"), "a\tb\nc"); // TAB/LF preserved
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
    fn fold_sets_are_disjoint_from_zero_width() {
        // The sets must not overlap, or a char's fate would depend on step order.
        // (Zero-width is deleted; fold-whitespace / blank-render become a space.)
        for cp in 0u32..=0x1_0000 {
            let Some(ch) = char::from_u32(cp) else {
                continue;
            };
            if is_fold_whitespace(ch) || is_blank_render(ch) {
                assert!(
                    !is_zero_width(ch),
                    "{cp:#06x} is both a fold char and zero-width"
                );
            }
        }
    }

    /// Tier-3 exhaustive gate for the whitespace-collapse invariants (#433).
    ///
    /// `collapse_whitespace` treats every whitespace code point *uniformly* (any run of
    /// fold-whitespace / blank-render collapses to one space, the ends are trimmed), so
    /// its state machine turns on the whitespace-vs-not *pattern*. Two exhaustive sweeps
    /// together pin it where the `\PC*` proptests only sample: (1) every code point in a
    /// run context (`x␟c␟c␟y c z`), proving each is classified so runs collapse
    /// idempotently with no `"  "` and trimmed ends; and (2) every pattern over {two
    /// distinct whitespace chars, a non-ws letter} up to length 7, proving the
    /// collapse/trim state machine on mixed runs and boundaries. `#[ignore]` (Tier 3);
    /// run via `--lib -- --ignored`.
    #[test]
    #[ignore = "exhaustive: whitespace-collapse over every code point + patterns; Tier 3"]
    fn exhaustive_collapse_whitespace() {
        let check = |s: &str| {
            let once = collapse_whitespace(s);
            assert_eq!(once, collapse_whitespace(&once), "not idempotent on {s:?}");
            assert!(!once.contains("  "), "double space from {s:?} → {once:?}");
            if !once.is_empty() {
                assert_ne!(once.as_bytes()[0], b' ', "leading space from {s:?}");
                assert_ne!(
                    *once.as_bytes().last().unwrap(),
                    b' ',
                    "trailing space {s:?}"
                );
            }
        };
        // (1) every code point in a collapsing run context.
        for cp in 0u32..=0x0010_FFFF {
            let Some(c) = char::from_u32(cp) else {
                continue;
            };
            check(&format!("x{c}{c}y{c}z"));
        }
        // (2) every pattern over {SPACE, NBSP, 'x'} up to length 7 (uniform ws handling
        //     means two distinct ws chars suffice to exercise mixed runs).
        let alphabet = [' ', '\u{00A0}', 'x'];
        let mut stack = vec![String::new()];
        while let Some(s) = stack.pop() {
            check(&s);
            if s.chars().count() < 7 {
                for &a in &alphabet {
                    let mut n = s.clone();
                    n.push(a);
                    stack.push(n);
                }
            }
        }
    }

    mod proptest_properties {
        use super::*;
        use proptest::prelude::*;

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            /// Collapsing whitespace is idempotent.
            #[test]
            fn collapse_whitespace_idempotent(s in "\\PC*") {
                let once = collapse_whitespace(&s);
                let twice = collapse_whitespace(&once);
                prop_assert_eq!(&once, &twice);
            }

            /// Result has no leading or trailing whitespace.
            #[test]
            fn no_leading_trailing_whitespace(s in "\\PC*") {
                let result = collapse_whitespace(&s);
                if !result.is_empty() {
                    prop_assert_ne!(result.as_bytes()[0], b' ');
                    prop_assert_ne!(result.as_bytes()[result.len() - 1], b' ');
                }
            }

            /// Result never contains consecutive spaces.
            #[test]
            fn no_consecutive_spaces(s in "\\PC*") {
                let result = collapse_whitespace(&s);
                prop_assert!(!result.contains("  "), "double space in: {result:?}");
            }

            /// Pure alphanumeric ASCII passes through unchanged.
            #[test]
            fn alphanumeric_passthrough(s in "[a-zA-Z0-9]{1,50}") {
                let result = collapse_whitespace(&s);
                prop_assert_eq!(&result, &s);
            }

            /// Idempotent over a mix of letters, every fold-whitespace char, and
            /// the blank-render set (#433 acceptance: f(f(x)) == f(x)).
            #[test]
            fn idempotent_over_ws_and_blank_sets(
                s in r"[ab\x09\x0a\x0b\x0c\x0d\x1c\x1d\x1e\x1f\u{0085}\u{00a0}\u{2000}\u{2028}\u{3000}\u{2800}\u{115f}\u{1160}\u{3164}\u{ffa0}]{0,32}"
            ) {
                let once = collapse_whitespace(&s);
                let twice = collapse_whitespace(&once);
                prop_assert_eq!(&once, &twice);
            }
        }
    }
}
