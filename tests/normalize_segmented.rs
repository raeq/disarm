//! `api::normalize` writes exactly what `unicode_normalization` writes for the whole string.
//!
//! `normalize` splits the text at normalization boundaries and normalizes only the
//! segments that need it, copying the rest. A boundary sits before a character that is a
//! starter (combining class 0) and passes the form's quick check: it never composes with
//! what precedes it, and a class-0 character stops canonical reordering, so what comes
//! before it normalizes independently of what comes after. If that reasoning is wrong for
//! any character, these tests say which.
//!
//! The oracle is the crate's own full-string iterator, which the segmented path used to be.

use disarm::api::{normalize, NormalizationForm};
use unicode_normalization::char::canonical_combining_class;
use unicode_normalization::UnicodeNormalization;

const FORMS: [NormalizationForm; 4] = [
    NormalizationForm::Nfc,
    NormalizationForm::Nfd,
    NormalizationForm::Nfkc,
    NormalizationForm::Nfkd,
];

fn oracle(text: &str, form: NormalizationForm) -> String {
    match form {
        NormalizationForm::Nfc => text.nfc().collect(),
        NormalizationForm::Nfd => text.nfd().collect(),
        NormalizationForm::Nfkc => text.nfkc().collect(),
        NormalizationForm::Nfkd => text.nfkd().collect(),
        other => unreachable!("a form this test does not know: {other:?}"),
    }
}

fn check(text: &str) {
    for form in FORMS {
        assert_eq!(
            normalize(text, form),
            oracle(text, form),
            "{form:?} of {:?}",
            text.chars()
                .map(|c| format!("U+{:04X}", u32::from(c)))
                .collect::<Vec<_>>()
        );
    }
}

/// Neighbours that exercise every way two characters interact under normalization:
/// composing bases, marks of different classes (reordering), Hangul L / V / T and a
/// precomposed LV syllable, an Indic two-part vowel, a Tibetan subjoined letter, and a
/// compatibility character.
const CONTEXTS: [char; 14] = [
    'a', 'e', '\u{1100}', // HANGUL CHOSEONG KIYEOK (L)
    '\u{1161}', // HANGUL JUNGSEONG A (V)
    '\u{11A8}', // HANGUL JONGSEONG KIYEOK (T)
    '\u{AC00}', // HANGUL SYLLABLE GA (LV)
    '\u{0B47}', // ORIYA VOWEL SIGN E, first of a two-part vowel
    '\u{0B3E}', // ORIYA VOWEL SIGN AA, composes backward with U+0B47
    '\u{0301}', // COMBINING ACUTE ACCENT, ccc 230
    '\u{0327}', // COMBINING CEDILLA, ccc 202
    '\u{0345}', // COMBINING GREEK YPOGEGRAMMENI, ccc 240
    '\u{05B0}', // HEBREW POINT SHEVA, ccc 10
    '\u{0FB2}', // TIBETAN SUBJOINED LETTER RA
    '\u{FB01}', // LATIN SMALL LIGATURE FI, compatibility
];

fn scalars() -> impl Iterator<Item = char> {
    (0u32..0x11_0000).filter_map(char::from_u32)
}

/// Every scalar normalization can touch: a combining class, a decomposition, a quick
/// check other than Yes in any form, or Hangul.
fn interesting() -> Vec<char> {
    scalars()
        .filter(|&c| {
            let s = c.to_string();
            !c.is_ascii()
                && (canonical_combining_class(c) != 0
                    || s.nfd().ne(s.chars())
                    || s.nfkd().ne(s.chars())
                    || s.nfc().ne(s.chars())
                    || [
                        unicode_normalization::is_nfc_quick(s.chars()),
                        unicode_normalization::is_nfd_quick(s.chars()),
                        unicode_normalization::is_nfkc_quick(s.chars()),
                        unicode_normalization::is_nfkd_quick(s.chars()),
                    ]
                    .into_iter()
                    .any(|quick| quick != unicode_normalization::IsNormalized::Yes)
                    || matches!(u32::from(c), 0x1100..=0x11FF | 0xAC00..=0xD7A3))
        })
        .collect()
}

#[test]
fn every_interesting_scalar_between_every_context() {
    let set = interesting();
    assert!(set.len() > 15_000, "only {} interesting scalars", set.len());
    for &c in &set {
        check(&c.to_string());
        for &x in &CONTEXTS {
            check(&format!("{x}{c}"));
            check(&format!("{c}{x}"));
        }
        // A starter run on either side, as in real text.
        check(&format!("ab{c}\u{301}cd"));
    }
}

#[test]
fn random_strings_over_the_interesting_alphabet() {
    let set = interesting();
    let mut state: u64 = 0x2545_F491_4F6C_DD1D;
    let mut next = move || {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        state
    };
    for _ in 0..20_000 {
        let len = (next() % 24) as usize;
        let text: String = (0..len)
            .map(|_| match next() % 5 {
                0 => char::from(b' ' + (next() % 95) as u8),
                1 => CONTEXTS[(next() % CONTEXTS.len() as u64) as usize],
                _ => set[(next() % set.len() as u64) as usize],
            })
            .collect();
        check(&text);
    }
}

#[test]
fn a_document_that_is_mostly_normalized() {
    // The shape the fast path is for: long starter runs, a few characters that change.
    let text = "Pricing \u{2014} \u{201C}smart quotes\u{201D}, cafe\u{301}\u{A9} and \
                nai\u{308}ve\u{2122} users pay \u{20AC}9.99 \u{2026} \u{FB01}ne \u{1100}\u{1161}\u{11A8} "
        .repeat(50);
    check(&text);
}

/// Every scalar, alone and between an `a` and a combining acute. Minutes in debug.
#[test]
#[ignore = "exhaustive: every Unicode scalar; run with --release -- --ignored"]
fn every_scalar_alone_and_in_context() {
    for c in scalars() {
        check(&c.to_string());
        check(&format!("a{c}"));
        check(&format!("{c}\u{301}"));
        check(&format!("\u{1100}{c}\u{11A8}"));
    }
}
