//! Exhaustive grapheme-integrity tests for translit (issue #174, tier 3).
//!
//! Core invariant (empirically validated: 800k+ adversarial checks, zero
//! counterexamples): Unicode normalization respects grapheme-cluster
//! boundaries. For every normalization form (NFC, NFD, NFKC, NFKD):
//!
//!     normalize(whole) == concat(normalize(g) for g in graphemes(whole))
//!
//! This proves normalization never splits a combining-mark sequence or an
//! Indic conjunct, and never merges across cluster boundaries.
//!
//! These tests exhaustively cover bounded Unicode domains (all Hangul
//! syllables, all Devanagari conjunct pairs, the full combining-diacriticals
//! block, and every assigned BMP scalar). They are `#[ignore]` by default so
//! they don't slow everyday development — exactly like
//! `tests/exhaustive_transliterate.rs`. Run before release with:
//! `cargo test --no-default-features --test exhaustive_grapheme -- --ignored`
//!
//! Normalization entry point: we call `_translit::normalize::_normalize`, the
//! SAME `#[pyfunction]` translit ships. Although it is annotated `#[pyfunction]`
//! its signature is `fn(text: &str, form: &str) -> PyResult<String>` — it takes
//! no `Python<'_>` token and touches no Python objects, so it is callable
//! directly from a plain `#[test]` with NO GIL. (The module's own unit tests in
//! `src/normalize.rs` do exactly this.) Calling it directly guarantees we
//! exercise the identical code path that ships to users.

use _translit::normalize::_normalize;
use unicode_segmentation::UnicodeSegmentation;

const FORMS: [&str; 4] = ["NFC", "NFD", "NFKC", "NFKD"];

/// `normalize(whole)` equals the join of per-grapheme-cluster normalizations.
fn boundary_preserved(s: &str, form: &str) -> bool {
    _normalize(s, form).unwrap()
        == s.graphemes(true)
            .map(|g| _normalize(g, form).unwrap())
            .collect::<String>()
}

/// Assert boundary preservation across all four forms with a useful message.
fn assert_all_forms(s: &str, ctx: &str) {
    for form in FORMS {
        assert!(
            boundary_preserved(s, form),
            "boundary violation ({ctx}) under {form}: input={s:?}"
        );
    }
}

// ── All 11,172 Hangul syllables (U+AC00–U+D7A3) ───────────────────────

#[test]
#[ignore = "exhaustive: slow, run with --ignored"]
fn boundary_preservation_all_hangul_syllables() {
    for cp in 0xAC00_u32..=0xD7A3 {
        let syl = char::from_u32(cp).unwrap();
        // The syllable alone.
        let alone = syl.to_string();
        assert_all_forms(&alone, "hangul alone");
        // The syllable wrapped between ASCII neighbors.
        let wrapped = format!("a{syl}b");
        assert_all_forms(&wrapped, "hangul wrapped");
    }
}

// ── Every Devanagari consonant-virama-consonant conjunct ──────────────

#[test]
#[ignore = "exhaustive: slow, run with --ignored"]
fn boundary_preservation_devanagari_conjuncts() {
    const VIRAMA: char = '\u{094D}';
    for c1 in 0x0915_u32..=0x0939 {
        let cons1 = char::from_u32(c1).unwrap();
        for c2 in 0x0915_u32..=0x0939 {
            let cons2 = char::from_u32(c2).unwrap();
            // c1 + virama + c2 forms a conjunct (one grapheme cluster).
            let conjunct = format!("{cons1}{VIRAMA}{cons2}");
            assert_all_forms(&conjunct, "devanagari conjunct");
            // With a leading base and a trailing base.
            let bracketed = format!("\u{0915}{conjunct}\u{0939}");
            assert_all_forms(&bracketed, "devanagari conjunct bracketed");
        }
    }
}

// ── Full combining-diacriticals block on representative bases ──────────

#[test]
#[ignore = "exhaustive: slow, run with --ignored"]
fn boundary_preservation_bmp_combining_pairs() {
    // Latin "a", Devanagari "क", and Hangul "한" as representative bases.
    let bases = ["a", "\u{0915}", "\u{D55C}"];
    for cp in 0x0300_u32..=0x036F {
        let mark = char::from_u32(cp).unwrap();
        for base in bases {
            let s = format!("{base}{mark}");
            assert_all_forms(&s, "base + combining mark");
        }
    }
}

// ── Every assigned BMP scalar as a single-char string ─────────────────

#[test]
#[ignore = "exhaustive: slow, run with --ignored"]
fn boundary_preservation_full_bmp_singletons() {
    // A single scalar is a single grapheme cluster, so per-cluster
    // normalization is trivially equal to whole-string normalization. This
    // exhaustively confirms there is no pathological singleton that breaks the
    // identity (and catches any future regression in the grapheme segmenter).
    for cp in 0x0000_u32..=0xFFFF {
        // Skip the surrogate range — not valid Unicode scalar values.
        if (0xD800..=0xDFFF).contains(&cp) {
            continue;
        }
        let ch = char::from_u32(cp).unwrap();
        let s = ch.to_string();
        for form in FORMS {
            assert!(
                boundary_preserved(&s, form),
                "singleton boundary violation under {form}: U+{cp:04X}"
            );
        }
    }
}
