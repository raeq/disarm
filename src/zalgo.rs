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
//!
//! Layer 1 (pure-Rust core): no pyo3. Shim in `src/py/zalgo.rs`; crates.io
//! surface is `crate::api::{is_zalgo, strip_zalgo}`.

use unicode_normalization::char::is_combining_mark;
use unicode_normalization::UnicodeNormalization;

/// Default threshold: a base character with more than this many combining marks
/// is considered zalgo.  Vietnamese `ệ` has 2 combining marks in NFD, so 3
/// is a safe default that catches abuse while preserving all real-world text.
pub(crate) const DEFAULT_THRESHOLD: usize = 3;

/// Default cap for `strip_zalgo`: keep at most this many combining marks per
/// base character.
///
/// **Equal to [`DEFAULT_THRESHOLD`] on purpose (#788).** It was 2 while the threshold
/// was 3, so the library stripped from text it had just declined to call suspicious:
/// `is_zalgo("\u05d0\u05b8\u05c1\u0591")` is `false` — pointed and cantillated
/// Hebrew routinely puts a vowel, a dot and an accent on one consonant — and
/// `strip_zalgo` removed the accent anyway.
///
/// The two constants must move together, and the direction is forced. Lowering the
/// threshold to 2 would make `is_zalgo` call ordinary Torah text zalgo; raising the cap
/// to 3 makes the transform act only on what the predicate flags. #429 set the cap to
/// preserve legitimate diacritics, and 3-mark Hebrew is legitimate — so this serves
/// that decision rather than reversing it.
///
/// `tests/test_zalgo_cap.py` holds the invariant, stated as **marks preserved** rather
/// than string equality: for every `s` where `is_zalgo(s)` is false,
/// `strip_zalgo(s)` loses no combining mark. Byte equality is the wrong claim — this
/// function recomposes to NFC, so a decomposed input legitimately comes back spelled
/// differently, and an earlier draft of that test reported 750 "violations" that were
/// all recomposition.
pub(crate) const DEFAULT_MAX_MARKS: usize = DEFAULT_THRESHOLD;

/// Streaming check: does any base character carry **more than** `threshold`
/// consecutive combining marks in NFD form?
///
/// Returns the instant the first run exceeds `threshold`, so a short zalgo burst
/// at the front of a long benign tail settles in `O(burst)`, not `O(len)` — no
/// full NFD walk once the verdict is decided (review H-P2/H-P3).
fn exceeds_combining_run(text: &str, threshold: usize) -> bool {
    let mut run: usize = 0;
    for ch in text.nfd() {
        if is_combining_mark(ch) {
            run += 1;
            if run > threshold {
                return true;
            }
        } else {
            run = 0;
        }
    }
    false
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
pub(crate) fn is_zalgo(text: &str, threshold: usize) -> bool {
    // Fast path: pure ASCII has no combining marks.
    if text.is_ascii() {
        return false;
    }
    exceeds_combining_run(text, threshold)
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
pub(crate) fn strip_zalgo(text: &str, max_marks: usize) -> String {
    let mut out = String::new();
    strip_zalgo_into(text, max_marks, &mut out);
    out
}

/// In-place form of [`strip_zalgo`] writing the final NFC result into `out`
/// (cleared first), so the pipeline can reuse one buffer across steps
/// (#236 item 7). The NFD/NFC two-pass still needs one internal temporary.
pub(crate) fn strip_zalgo_into(text: &str, max_marks: usize, out: &mut String) {
    out.clear();
    // Fast path: pure ASCII has no combining marks.
    if text.is_ascii() {
        out.push_str(text);
        return;
    }

    // Fast path (H-P3): if no base exceeds `max_marks`, the mark-filtering step
    // is a no-op, so skip the intermediate `filtered` buffer and just normalize
    // to NFC (`NFC(NFD(x)) == NFC(x)`), preserving the documented NFC output
    // contract without the per-char copy. Most non-ASCII text has no zalgo.
    if !exceeds_combining_run(text, max_marks) {
        out.extend(text.nfc());
        return;
    }

    let mut filtered = String::with_capacity(text.len());
    let mut mark_count: usize = 0;

    // The cap is counted over the *NFD (decomposed)* sequence, so it bounds the
    // number of combining marks per base in decomposed space — a precomposed
    // accented letter (e.g. `é` = one mark in NFD) costs one toward the cap, and a
    // base carrying N stacked marks is capped to `max_marks` of them. The final NFC
    // recompose may then re-attach kept marks into precomposed forms; the count is
    // deliberately taken *before* that recompose so stacking is measured uniformly
    // regardless of the input's composition.
    let mut base: Option<char> = None;
    let mut negation_kept = false;
    for ch in text.nfd() {
        if crate::transliterate::is_negation_of(ch, base) && !negation_kept {
            // #749: not a diacritic. On a symbol, `U+0338` and `U+20D2` are the stroke
            // through a relation, so dropping one leaves the *positive* operator — `≠`
            // became `=`. The first one does not count toward the cap: a negated symbol
            // is one mark by construction and can never be the stacking this bounds.
            //
            // Exactly one per base. A relation carries a single stroke; a *run* of them
            // is stacking whatever the base is, and exempting the whole run let
            // `"=" + "\u{0338}" * 1000` through `Zalgo(0)` intact. Overlays after the
            // first fall to the branch below and are counted like any other mark.
            //
            // On a *letter* the same code point is strikethrough obfuscation, which this
            // preset exists to remove, so `is_negation_of` asks about the base.
            negation_kept = true;
            filtered.push(ch);
        } else if is_combining_mark(ch) {
            mark_count += 1;
            if mark_count <= max_marks {
                filtered.push(ch);
            }
            // else: drop the excess combining mark
        } else {
            mark_count = 0;
            negation_kept = false;
            base = Some(ch);
            filtered.push(ch);
        }
    }

    // Recompose to NFC for consistency with the rest of the library.
    out.extend(filtered.nfc());
}

/// Remove a combining mark whose own script is a *specific* script differing from the
/// script of the base it attaches to (#615, CVE-2017-7833).
///
/// The CVE is domain spoofing "through the combination of Arabic and Indic vowel marker
/// characters with Latin characters", which "can obscure non-Latin characters in domain
/// names, making them invisible to most users while avoiding punycode encoding".
///
/// `strip_zalgo`'s cap cannot reach it. That is a **count**, and by count one Arabic
/// shadda is indistinguishable from one acute accent, so no threshold removes the spoof
/// and keeps `café`. The discriminator the count lacks is already in disarm's script
/// data:
///
/// | mark | `detect_char_script` | |
/// |---|---|---|
/// | `U+0301` COMBINING ACUTE | `Inherited` | a legitimate diacritic — kept |
/// | `U+0651` ARABIC SHADDA | `Arabic` | the CVE's vector — stripped off a Latin base |
/// | `U+0E31` THAI MAI HAN AKAT | `Thai` | likewise |
///
/// This is UTS #39's mixed-script reasoning applied at the grapheme level rather than
/// across the whole string. A mark whose script is `Inherited` attaches to anything and
/// is never touched, which is why `café`, `naïve`, `Việt Nam` and Arabic *with* its own
/// vowel marks all pass through unchanged.
///
/// Deliberately **not** in `canonicalize`, and not public. Scholarly transliteration, IPA
/// and linguistic transcription legitimately place marks from one script on bases of
/// another, and a strip that fires on those would be destructive in exactly the corpus
/// least able to notice. `canonicalize_strict` is where a caller has already accepted a
/// stricter contract.
///
/// Only the in-place form exists: the preset runner reuses one scratch buffer across
/// steps (#236 item 7), so an owned wrapper would have no caller.
pub(crate) fn strip_cross_script_marks_into(text: &str, out: &mut String) {
    out.clear();
    out.reserve(text.len());
    // The script of the most recent non-mark character — what a mark attaches to.
    let mut base_script: Option<&'static str> = None;
    for ch in text.chars() {
        if is_combining_mark(ch) {
            let mark_script = crate::scripts::detect_char_script(ch);
            // `Inherited` means "takes the script of its base", so it can never
            // conflict. `Common` marks (rare) are treated the same way.
            let specific = mark_script != "Inherited" && mark_script != "Common";
            if specific && base_script.is_some_and(|b| b != mark_script) {
                continue; // cross-script mark on a foreign base — the CVE's shape
            }
            out.push(ch);
            continue;
        }
        base_script = match crate::scripts::detect_char_script(ch) {
            // Punctuation, digits and whitespace do not re-anchor the base script.
            "Common" | "Inherited" => base_script,
            s => Some(s),
        };
        out.push(ch);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_zalgo_clean_text() {
        assert!(!is_zalgo("hello world", 3));
        assert!(!is_zalgo("café résumé", 3));
        assert!(!is_zalgo("", 3));
    }

    #[test]
    fn test_is_zalgo_ascii_fast_path() {
        assert!(!is_zalgo("just ascii text 12345!@#$%", 3));
    }

    #[test]
    fn test_is_zalgo_vietnamese() {
        // Vietnamese ệ = e + combining circumflex + combining dot below (2 marks)
        assert!(!is_zalgo("Việt Nam", 3));
        assert!(!is_zalgo("ệ", 2));
    }

    #[test]
    fn test_is_zalgo_detects_stacking() {
        // Build zalgo: 'a' + 10 combining marks
        let mut zalgo = String::from("a");
        for _ in 0..10 {
            zalgo.push('\u{0300}'); // combining grave accent
        }
        assert!(is_zalgo(&zalgo, 3));
    }

    #[test]
    fn test_is_zalgo_threshold_boundary() {
        // Exactly at threshold: not zalgo
        let mut text = String::from("a");
        for _ in 0..3 {
            text.push('\u{0300}');
        }
        assert!(!is_zalgo(&text, 3));

        // One above threshold: zalgo
        text.push('\u{0300}');
        assert!(is_zalgo(&text, 3));
    }

    #[test]
    fn test_strip_zalgo_clean_text_unchanged() {
        assert_eq!(strip_zalgo("hello world", 2), "hello world");
        assert_eq!(strip_zalgo("café", 2), "café");
    }

    #[test]
    fn test_strip_zalgo_preserves_legitimate_diacritics() {
        // Vietnamese ệ has 2 combining marks — should be preserved with max_marks=2
        let input = "Việt Nam";
        assert_eq!(strip_zalgo(input, 2), input);

        // French accents — 1 combining mark each
        assert_eq!(strip_zalgo("résumé", 2), "résumé");
    }

    #[test]
    fn test_strip_zalgo_removes_excess() {
        // 'a' + 10 combining graves → should keep only max_marks
        let mut zalgo = String::from("a");
        for _ in 0..10 {
            zalgo.push('\u{0300}'); // combining grave accent
        }
        let result = strip_zalgo(&zalgo, 2);
        // Result should be 'a' with exactly 2 combining graves (in NFC: à + 1 extra grave)
        // NFD: a + grave + grave, NFC: à + grave (combining grave after precomposed à)
        // The key assertion: no more than 2 combining marks survived
        assert!(result.chars().count() <= 3); // base + at most 2 marks after NFC
        assert!(result.starts_with('à'));
    }

    #[test]
    fn test_strip_zalgo_max_marks_zero_strips_all() {
        assert_eq!(strip_zalgo("café", 0), "cafe");
        assert_eq!(strip_zalgo("résumé", 0), "resume");
    }

    #[test]
    fn test_strip_zalgo_ascii_fast_path() {
        let input = "just ascii";
        assert_eq!(strip_zalgo(input, 2), input);
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
        let result = strip_zalgo(&zalgo, 2);
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
    fn test_exceeds_combining_run() {
        assert!(!exceeds_combining_run("hello", 0));
        assert!(!exceeds_combining_run("café", 1)); // 1 mark, threshold 1
        assert!(!exceeds_combining_run("", 0));

        let mut text = String::from("a");
        for _ in 0..5 {
            text.push('\u{0300}');
        }
        assert!(exceeds_combining_run(&text, 2)); // 5 marks > 2
        assert!(!exceeds_combining_run(&text, 5)); // 5 marks, threshold 5
    }

    proptest::proptest! {
        /// H-P3: `strip_zalgo` always returns NFC — the fast path that skips the
        /// filter must still normalize.
        #[test]
        fn strip_zalgo_output_is_nfc(s in "\\PC*", max in 0usize..4) {
            let out = strip_zalgo(&s, max);
            proptest::prop_assert!(unicode_normalization::is_nfc(&out));
        }

        /// The fast path (no excess marks) must produce the same bytes as the
        /// full filter path would on the same input.
        #[test]
        fn strip_zalgo_fast_path_matches_filter(s in "\\PC*") {
            // With a high cap, no run is ever excess, so the fast path is taken;
            // it must equal a plain NFC normalization.
            let out = strip_zalgo(&s, 1000);
            let nfc: String = s.nfc().collect();
            proptest::prop_assert_eq!(out, nfc);
        }
    }
}
