//! Layer 1 (pure-Rust core): full Unicode case folding. No pyo3.
//!
//! Shim in `src/py/case_fold.rs`; crates.io surface is `crate::api::fold_case`.

use crate::tables::case_folding_data;

// disarm does not cap input size — bounding untrusted input is the caller's
// responsibility (case folding is linear time/memory; see #80).

/// Full Unicode case folding per CaseFolding.txt (status C + F).
///
/// Unlike `str.lower()` / `char::to_lowercase()`, this performs *full* case
/// folding: ß→ss, İ→i̇, ﬁ→fi, µ→μ, ſ→s, ς→σ, and ~1,500 other mappings
/// including Cherokee, Adlam, and all ligature expansions.
///
/// Fast paths:
/// 1. Pure-ASCII bypass — if the entire string is ASCII, use branchless
///    bitwise lowercasing with no PHF lookup.
/// 2. Per-character ASCII check — uppercase A-Z are lowered inline.
/// 3. PHF lookup — O(1) for all 1,557 Unicode case folding entries.
/// 4. Identity fallback — characters not in the table map to themselves.
pub(crate) fn fold_case_impl(text: &str) -> String {
    let mut out = String::new();
    fold_case_into(text, &mut out);
    out
}

/// Borrowing form of [`fold_case_impl`] (#352): returns `Cow::Borrowed` when
/// `text` is already fully case-folded (no ASCII uppercase and no character with
/// a folding-table entry), so the no-op case never allocates.
///
/// Single pass with lazy allocation (review H-P1): each character is probed in
/// the folding table **once** — the buffer is created (and the unchanged prefix
/// copied) only at the first character that actually folds. The old form scanned
/// to detect a change and then scanned again to fold, doubling the PHF probes on
/// the most expensive (all-foldable) inputs.
pub(crate) fn fold_case_cow(text: &str) -> std::borrow::Cow<'_, str> {
    use std::borrow::Cow;

    // Pure-ASCII: one cheap byte scan; allocate only if an uppercase is present.
    if text.is_ascii() {
        if text.bytes().any(|b| b.is_ascii_uppercase()) {
            let mut out = text.to_owned();
            out.make_ascii_lowercase();
            return Cow::Owned(out);
        }
        return Cow::Borrowed(text);
    }

    let mut out: Option<String> = None;
    let start_owned = |i: usize| {
        let mut s = String::with_capacity(text.len() + text.len() / 10);
        s.push_str(&text[..i]);
        s
    };
    for (i, ch) in text.char_indices() {
        if ch.is_ascii_uppercase() {
            out.get_or_insert_with(|| start_owned(i))
                .push(ch.to_ascii_lowercase());
        } else if !ch.is_ascii() {
            if let Some(folded) = case_folding_data::lookup(ch) {
                out.get_or_insert_with(|| start_owned(i)).push_str(folded);
            } else if let Some(buf) = out.as_mut() {
                buf.push(ch);
            }
        } else if let Some(buf) = out.as_mut() {
            buf.push(ch);
        }
    }
    out.map_or(Cow::Borrowed(text), Cow::Owned)
}

/// In-place form of [`fold_case_impl`] writing into `result` (cleared first),
/// so the pipeline can reuse one buffer across steps (#236 item 7).
pub(crate) fn fold_case_into(text: &str, result: &mut String) {
    result.clear();
    // Fast path: pure ASCII — branchless bulk lowering, no heap probe.
    if text.is_ascii() {
        result.push_str(text);
        result.make_ascii_lowercase();
        return;
    }

    // Over-allocate by 10% to reduce reallocations when expanding chars
    // are present (e.g. ß→ss, ﬃ→ffi).  For pure non-expanding input the
    // excess is negligible; for expansion-heavy input it avoids 1–2 reallocs.
    result.reserve(text.len() + text.len() / 10);

    for ch in text.chars() {
        if ch.is_ascii() {
            // ASCII lowercase — no PHF lookup needed.
            result.push(ch.to_ascii_lowercase());
        } else if let Some(folded) = case_folding_data::lookup(ch) {
            result.push_str(folded);
        } else {
            // Not in case folding table → maps to itself.
            result.push(ch);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── ASCII fast path ─────────────────────────────────────────────

    #[test]
    fn test_fold_case_basic() {
        assert_eq!(fold_case_impl("Hello"), "hello");
        assert_eq!(fold_case_impl("Straße"), "strasse");
    }

    #[test]
    fn test_fold_case_ascii_fast_path() {
        assert_eq!(fold_case_impl("HELLO WORLD"), "hello world");
        assert_eq!(fold_case_impl("already lowercase"), "already lowercase");
        assert_eq!(fold_case_impl("MiXeD CaSe 123!"), "mixed case 123!");
    }

    #[test]
    fn test_fold_case_pure_ascii_digits_and_punctuation() {
        // Digits and punctuation pass through unchanged.
        assert_eq!(fold_case_impl("12345!@#$%"), "12345!@#$%");
        assert_eq!(fold_case_impl("foo_bar-baz.qux"), "foo_bar-baz.qux");
    }

    #[test]
    fn test_fold_case_empty_string() {
        assert_eq!(fold_case_impl(""), "");
    }

    #[test]
    fn test_fold_case_single_ascii_char() {
        assert_eq!(fold_case_impl("A"), "a");
        assert_eq!(fold_case_impl("z"), "z");
        assert_eq!(fold_case_impl("7"), "7");
    }

    // ── Latin ligatures ─────────────────────────────────────────────

    #[test]
    fn test_fold_case_ligatures() {
        assert_eq!(fold_case_impl("ﬁnd ﬂat ﬀ ﬃ ﬄ"), "find flat ff ffi ffl");
        assert_eq!(fold_case_impl("ﬅop ﬆop"), "stop stop");
    }

    // ── Latin Extended: characters where fold != lower ────────────

    #[test]
    fn test_fold_case_micro_sign_to_greek_mu() {
        // µ (U+00B5 micro sign) → μ (U+03BC Greek small mu)
        assert_eq!(fold_case_impl("\u{00B5}"), "\u{03BC}");
    }

    #[test]
    fn test_fold_case_long_s_to_s() {
        // ſ (U+017F long s) → s
        assert_eq!(fold_case_impl("\u{017F}"), "s");
    }

    #[test]
    fn test_fold_case_eszett() {
        // ß (U+00DF) → ss
        assert_eq!(fold_case_impl("ß"), "ss");
        // ẞ (U+1E9E capital eszett) → ss
        assert_eq!(fold_case_impl("ẞ"), "ss");
    }

    #[test]
    fn test_fold_case_dotted_i() {
        // İ (U+0130) → i + combining dot above (U+0307)
        assert_eq!(fold_case_impl("\u{0130}"), "i\u{0307}");
    }

    // ── Greek ────────────────────────────────────────────────────────

    #[test]
    fn test_fold_case_greek_uppercase() {
        assert_eq!(fold_case_impl("ΑΒΓΔ"), "αβγδ");
        assert_eq!(fold_case_impl("ΩΨΧΦ"), "ωψχφ");
    }

    #[test]
    fn test_fold_case_greek_final_sigma() {
        // ς (U+03C2 final sigma) → σ (U+03C3)
        assert_eq!(fold_case_impl("\u{03C2}"), "\u{03C3}");
    }

    #[test]
    fn test_fold_case_greek_variant_forms() {
        // ϐ (U+03D0 beta symbol) → β
        assert_eq!(fold_case_impl("\u{03D0}"), "\u{03B2}");
        // ϑ (U+03D1 theta symbol) → θ
        assert_eq!(fold_case_impl("\u{03D1}"), "\u{03B8}");
        // ϕ (U+03D5 phi symbol) → φ
        assert_eq!(fold_case_impl("\u{03D5}"), "\u{03C6}");
        // ϖ (U+03D6 pi symbol) → π
        assert_eq!(fold_case_impl("\u{03D6}"), "\u{03C0}");
        // ϰ (U+03F0 kappa symbol) → κ
        assert_eq!(fold_case_impl("\u{03F0}"), "\u{03BA}");
        // ϱ (U+03F1 rho symbol) → ρ
        assert_eq!(fold_case_impl("\u{03F1}"), "\u{03C1}");
    }

    #[test]
    fn test_fold_case_greek_with_tonos() {
        // ΐ (U+0390) → ΐ decomposed: ι + combining diaeresis + combining acute
        assert_eq!(fold_case_impl("\u{0390}"), "\u{03B9}\u{0308}\u{0301}");
    }

    // ── Cyrillic ─────────────────────────────────────────────────────

    #[test]
    fn test_fold_case_cyrillic_uppercase() {
        assert_eq!(fold_case_impl("АБВГД"), "абвгд");
        assert_eq!(fold_case_impl("ЭЮЯЪ"), "эюяъ");
    }

    #[test]
    fn test_fold_case_cyrillic_mixed() {
        assert_eq!(fold_case_impl("Москва"), "москва");
        assert_eq!(fold_case_impl("КИЇВ"), "київ");
    }

    // ── Armenian ─────────────────────────────────────────────────────

    #[test]
    fn test_fold_case_armenian() {
        // Ա (U+0531) → ա (U+0561)
        assert_eq!(fold_case_impl("\u{0531}"), "\u{0561}");
        // Armenian ligature և (U+0587) → եւ
        assert_eq!(fold_case_impl("\u{0587}"), "\u{0565}\u{0582}");
    }

    // ── Georgian ─────────────────────────────────────────────────────

    #[test]
    fn test_fold_case_georgian_mtavruli() {
        // Mtavruli Ა (U+1C90) → ა (U+10D0)
        assert_eq!(fold_case_impl("\u{1C90}"), "\u{10D0}");
    }

    // ── Cherokee ─────────────────────────────────────────────────────

    #[test]
    fn test_fold_case_cherokee() {
        // Cherokee is unusual: CaseFolding.txt maps the *small* forms
        // (U+AB70–U+ABBF) to the original uppercase forms (U+13A0–U+13EF).
        // The uppercase forms themselves have no folding entry → identity.
        assert_eq!(fold_case_impl("\u{13A0}"), "\u{13A0}"); // Ꭰ stays Ꭰ
                                                            // Small ꭰ (U+AB70) folds to Ꭰ (U+13A0)
        assert_eq!(fold_case_impl("\u{AB70}"), "\u{13A0}");
        assert_eq!(fold_case_impl("\u{AB71}"), "\u{13A1}");
    }

    // ── Adlam ────────────────────────────────────────────────────────

    #[test]
    fn test_fold_case_adlam() {
        // Adlam capital 𞤀 (U+1E900) → small 𞤢 (U+1E922)
        assert_eq!(fold_case_impl("\u{1E900}"), "\u{1E922}");
        // Adlam capital 𞤁 (U+1E901) → small 𞤣 (U+1E923)
        assert_eq!(fold_case_impl("\u{1E901}"), "\u{1E923}");
    }

    // ── Fullwidth Latin ──────────────────────────────────────────────

    #[test]
    fn test_fold_case_fullwidth_latin() {
        // Ａ (U+FF21) → ａ (U+FF41)
        assert_eq!(fold_case_impl("\u{FF21}"), "\u{FF41}");
        // Ｚ (U+FF3A) → ｚ (U+FF5A)
        assert_eq!(fold_case_impl("\u{FF3A}"), "\u{FF5A}");
    }

    // ── Mixed-script strings ─────────────────────────────────────────

    #[test]
    fn test_fold_case_mixed_scripts() {
        assert_eq!(fold_case_impl("Café ΣΟΦΙΑ"), "café σοφια");
    }

    #[test]
    fn test_fold_case_mixed_ascii_and_non_ascii() {
        // ASCII uppercase + non-ASCII uppercase in one string.
        assert_eq!(fold_case_impl("ABC Straße ÄÖÜ"), "abc strasse äöü");
    }

    #[test]
    fn test_fold_case_mixed_cjk_and_latin() {
        // CJK passes through; Latin folds.
        assert_eq!(fold_case_impl("Hello 你好 WORLD"), "hello 你好 world");
    }

    // ── Identity / passthrough ───────────────────────────────────────

    #[test]
    fn test_fold_case_identity_cjk() {
        assert_eq!(fold_case_impl("你好世界"), "你好世界");
    }

    #[test]
    fn test_fold_case_identity_emoji() {
        assert_eq!(fold_case_impl("🎉🚀💡"), "🎉🚀💡");
    }

    #[test]
    fn test_fold_case_identity_already_folded() {
        // Already-folded non-ASCII should pass through unchanged.
        assert_eq!(fold_case_impl("café résumé naïve"), "café résumé naïve");
    }

    // ── Edge cases ───────────────────────────────────────────────────

    #[test]
    fn test_fold_case_string_length_grows() {
        // ß→ss doubles the char; verify the output length is correct.
        assert_eq!(fold_case_impl("ßßß"), "ssssss");
        assert_eq!(fold_case_impl("ßßß").len(), 6);
    }

    #[test]
    fn test_fold_case_combining_characters_preserved() {
        // Combining marks that are not in CaseFolding.txt pass through.
        // é as e + combining acute accent
        let input = "e\u{0301}";
        assert_eq!(fold_case_impl(input), input);
    }

    #[test]
    fn test_fold_case_null_byte() {
        // Null byte is valid in the middle of a Rust &str.
        assert_eq!(fold_case_impl("A\0B"), "a\0b");
    }

    #[test]
    fn test_fold_case_surrogate_boundary() {
        // Characters near the BMP boundary.
        // U+FFFF is not a case-folding entry → identity.
        assert_eq!(fold_case_impl("\u{FFFF}"), "\u{FFFF}");
        // U+10000 (𐀀 Linear B Syllable B008 A) → identity.
        assert_eq!(fold_case_impl("\u{10000}"), "\u{10000}");
    }

    #[test]
    fn test_fold_case_deseret() {
        // Deseret capital 𐐀 (U+10400) → small 𐐨 (U+10428)
        assert_eq!(fold_case_impl("\u{10400}"), "\u{10428}");
    }

    #[test]
    fn test_fold_case_osage() {
        // Osage capital 𐒰 (U+104B0) → small 𐓘 (U+104D8)
        assert_eq!(fold_case_impl("\u{104B0}"), "\u{104D8}");
    }

    #[test]
    fn test_fold_case_warang_citi() {
        // Warang Citi capital 𑢠 (U+118A0) → small 𑣀 (U+118C0)
        assert_eq!(fold_case_impl("\u{118A0}"), "\u{118C0}");
    }

    #[test]
    fn test_fold_case_agrees_with_casefolding_txt() {
        // Spot-check a handful of entries across the full range
        // to verify the PHF data matches CaseFolding.txt expectations.
        let cases: &[(char, &str)] = &[
            ('A', "a"),
            ('Z', "z"),
            ('À', "à"),                       // U+00C0 → U+00E0
            ('Ð', "ð"),                       // U+00D0 → U+00F0
            ('Ø', "ø"),                       // U+00D8 → U+00F8
            ('Ʃ', "ʃ"),                       // U+01A9 → U+0283
            ('Ω', "ω"),                       // U+03A9 → U+03C9
            ('Ж', "ж"),                       // U+0416 → U+0436
            ('\u{0587}', "\u{0565}\u{0582}"), // Armenian և → եւ
        ];
        for &(input, expected) in cases {
            let got = fold_case_impl(&input.to_string());
            assert_eq!(
                got, expected,
                "fold_case(U+{:04X} {:?}) = {:?}, expected {:?}",
                input as u32, input, got, expected
            );
        }
    }

    // ── Property-based tests ─────────────────────────────────────────

    mod proptest_properties {
        use super::*;
        use proptest::prelude::*;

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            /// Case folding is idempotent: fold(fold(x)) == fold(x).
            #[test]
            fn fold_case_idempotent(s in "\\PC*") {
                let once = fold_case_impl(&s);
                let twice = fold_case_impl(&once);
                prop_assert_eq!(&once, &twice);
            }

            /// After folding, no ASCII uppercase letters remain.
            #[test]
            fn fold_case_no_ascii_uppercase(s in "\\PC*") {
                let result = fold_case_impl(&s);
                for ch in result.chars() {
                    if ch.is_ascii() {
                        prop_assert!(
                            !ch.is_ascii_uppercase(),
                            "uppercase {ch:?} in fold output: {result:?}"
                        );
                    }
                }
            }

            /// Output char count ≥ input char count (folding never drops characters,
            /// though byte length may shrink for ligatures like ﬅ → st).
            #[test]
            fn fold_case_never_drops_chars(s in "\\PC*") {
                let result = fold_case_impl(&s);
                prop_assert!(
                    result.chars().count() >= s.chars().count(),
                    "fold_case dropped chars: {} → {}",
                    s.chars().count(),
                    result.chars().count()
                );
            }

            /// Pure ASCII input stays pure ASCII after folding.
            #[test]
            fn fold_case_ascii_stays_ascii(s in "[\\x00-\\x7f]*") {
                let result = fold_case_impl(&s);
                prop_assert!(
                    result.is_ascii(),
                    "non-ASCII in fold of ASCII input: {result:?}"
                );
            }
        }
    }
}
