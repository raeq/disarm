//! Shared input decoding for the disarm fuzz targets.
//!
//! # Input layout
//!
//! Every text target reads its input as `TEXT [0xFF OPTIONS]`:
//!
//! - **`TEXT`** is decoded with [`String::from_utf8_lossy`], so any valid UTF-8 file is a
//!   seed as it stands and a mutation that breaks the encoding still yields text. The
//!   byte `0xFE` followed by three bytes is an escape for one code point drawn from
//!   [`INTERESTING`] (bidi controls, invisibles, tags, selectors, combining marks,
//!   Hangul, Kirat Rai, …), which gives the mutator a three-byte route to the classes the
//!   library exists to handle rather than hoping to spell them out in UTF-8.
//! - **`OPTIONS`** follows the first `0xFF`, a byte that never occurs in UTF-8. The target's
//!   options are drawn from it with [`arbitrary`]. With no `0xFF` the options come from an
//!   empty buffer, which `arbitrary` turns into each type's first or zero value — the
//!   library's defaults, by the order the option enums are declared in.
//!
//! The byte target (`decode_bytes`) does not use this layout: its input is the bytes.

use arbitrary::{Arbitrary, Unstructured};

/// Separates the text from the options. Never valid in UTF-8.
pub const OPTIONS_MARKER: u8 = 0xFF;

/// Escape for one [`INTERESTING`] code point: `0xFE range hi lo`.
pub const ESCAPE: u8 = 0xFE;

/// Code point ranges (inclusive) that the escape draws from.
///
/// Chosen for what the library treats specially, not for coverage of Unicode as a whole:
/// every class `canonicalize` strips, every carrier `decode_smuggled` reads, the
/// characters the formal models' findings turned on (`formal/`), and a sample of each
/// script the transliteration tables and the confusable fold cover.
pub const INTERESTING: &[(u32, u32)] = &[
    (0x0000, 0x001F),     // C0 controls, incl. BS, TAB, LF, VT, FF, CR, ESC
    (0x007F, 0x009F),     // DEL, C1 controls, NEL
    (0x00A0, 0x00FF),     // NBSP, soft hyphen, Latin-1 letters
    (0x0100, 0x024F),     // Latin Extended-A and -B
    (0x0300, 0x036F),     // combining diacritics, CGJ U+034F
    (0x0370, 0x03FF),     // Greek
    (0x0400, 0x04FF),     // Cyrillic
    (0x0590, 0x05FF),     // Hebrew
    (0x0600, 0x06FF),     // Arabic, incl. the Prepend U+0600-0605 and ALM U+061C
    (0x0900, 0x097F),     // Devanagari
    (0x0E00, 0x0E7F),     // Thai
    (0x1100, 0x11FF),     // Hangul jamo, incl. the fillers U+115F-1160
    (0x17B4, 0x17B5),     // Khmer inherent vowels (default-ignorable)
    (0x180B, 0x180F),     // Mongolian free variation selectors
    (0x1AB0, 0x1AFF),     // combining diacritics extended
    (0x1E00, 0x1EFF),     // Latin Extended Additional
    (0x1F00, 0x1FFF),     // Greek Extended (U+1FEE, U+1FFD)
    (0x2000, 0x206F),     // spaces, ZW*, bidi marks and embeddings, LS/PS, isolates, U+206A-206F
    (0x20A0, 0x20FF),     // currency, combining marks for symbols, keycap U+20E3
    (0x2100, 0x218F),     // letterlike (KELVIN, OHM), number forms
    (0x2460, 0x24FF),     // enclosed alphanumerics (circled letters)
    (0x3000, 0x30FF),     // CJK punctuation, kana
    (0x3130, 0x318F),     // Hangul compatibility jamo, U+3164
    (0x3300, 0x33FF),     // CJK compatibility (U+337F)
    (0x4E00, 0x4FFF),     // CJK unified ideographs (sample)
    (0xAC00, 0xADFF),     // Hangul syllables (sample)
    (0xD7B0, 0xD7FF),     // Hangul jamo extended-B
    (0xE000, 0xE0FF),     // private use (sample)
    (0xF900, 0xFAFF),     // CJK compatibility ideographs
    (0xFB00, 0xFB4F),     // alphabetic presentation forms (ligatures)
    (0xFDD0, 0xFDEF),     // noncharacters
    (0xFE00, 0xFE0F),     // variation selectors
    (0xFE20, 0xFE2F),     // combining half marks
    (0xFE70, 0xFEFF),     // Arabic presentation forms-B, BOM
    (0xFF00, 0xFFEF),     // halfwidth and fullwidth forms, U+FFA0
    (0xFFF0, 0xFFFF),     // specials: interlinear annotation, U+FFFD, U+FFFE/FFFF
    (0x11080, 0x110CF),   // Kaithi (Prepend U+110BD, U+110CD)
    (0x16D40, 0x16D7F),   // Kirat Rai (the backward-composing starter U+16D67)
    (0x1BCA0, 0x1BCA3),   // shorthand format controls
    (0x1D173, 0x1D17A),   // musical symbol formats
    (0x1D400, 0x1D7FF),   // mathematical alphanumerics
    (0x1F100, 0x1F1FF),   // enclosed alphanumeric supplement, regional indicators
    (0x1F300, 0x1F64F),   // emoji, skin-tone modifiers U+1F3FB-1F3FF
    (0x1F900, 0x1F9FF),   // supplemental symbols and pictographs
    (0xE0000, 0xE007F),   // tags
    (0xE0100, 0xE01EF),   // variation selectors supplement
    (0x10FFFE, 0x10FFFF), // plane-16 noncharacters
];

/// The code point an escape names. Surrogates cannot be named: no range holds one.
fn interesting(range: u8, hi: u8, lo: u8) -> char {
    let (start, end) = INTERESTING[usize::from(range) % INTERESTING.len()];
    let offset = u32::from(u16::from_be_bytes([hi, lo])) % (end - start + 1);
    char::from_u32(start + offset).unwrap_or('\u{FFFD}')
}

/// Decode the text half of an input: lossy UTF-8 with the [`ESCAPE`] expansion.
pub fn decode_text(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len());
    let mut segments = bytes.split(|&b| b == ESCAPE);
    if let Some(first) = segments.next() {
        out.push_str(&String::from_utf8_lossy(first));
    }
    for seg in segments {
        if let [range, hi, lo, rest @ ..] = seg {
            out.push(interesting(*range, *hi, *lo));
            out.push_str(&String::from_utf8_lossy(rest));
        } else {
            out.push_str(&String::from_utf8_lossy(seg));
        }
    }
    out
}

/// Split an input into its text and its options, per the module docs.
///
/// The options are drawn from the bytes after the first [`OPTIONS_MARKER`]; `arbitrary`
/// never fails on a short buffer for the types the targets use, but a `None` here is
/// treated by every target as "skip this input" rather than as a finding.
pub fn text_and<'a, T: Arbitrary<'a>>(data: &'a [u8]) -> Option<(String, T)> {
    let (text, options) = match data.iter().position(|&b| b == OPTIONS_MARKER) {
        Some(i) => (&data[..i], &data[i + 1..]),
        None => (data, &[][..]),
    };
    let opts = T::arbitrary(&mut Unstructured::new(options)).ok()?;
    Some((decode_text(text), opts))
}

/// The largest index `<= i` that is a char boundary of `s` (stable replacement for the
/// nightly `str::floor_char_boundary`).
pub fn floor_boundary(s: &str, i: usize) -> usize {
    let mut i = i.min(s.len());
    while !s.is_char_boundary(i) {
        i -= 1;
    }
    i
}

/// Split `s` at a char boundary chosen by `at` (taken modulo `len + 1`).
pub fn split_at_choice(s: &str, at: u16) -> (&str, &str) {
    let i = floor_boundary(s, usize::from(at) % (s.len() + 1));
    s.split_at(i)
}

/// Whether `needle` is a subsequence of `hay`, by `char`.
pub fn is_subsequence(needle: &str, hay: &str) -> bool {
    let mut hay = hay.chars();
    needle.chars().all(|c| hay.any(|h| h == c))
}

/// A language code for the options: none, `"auto"`, one of the built-in codes, or an
/// arbitrary string that is almost never a valid code (which exercises the error path).
#[derive(Debug, Arbitrary)]
pub enum Lang {
    /// No language: the default tables.
    None,
    /// `"auto"`: script detection.
    Auto,
    /// The built-in code at this index into [`disarm::api::list_langs`], modulo its length.
    Known(u8),
    /// Anything else.
    Raw(String),
}

impl Lang {
    /// The code this names, as the API takes it.
    pub fn code(&self) -> Option<String> {
        match self {
            Lang::None => None,
            Lang::Auto => Some("auto".to_owned()),
            Lang::Known(i) => {
                let langs = disarm::api::list_langs();
                Some(langs[usize::from(*i) % langs.len()].clone())
            }
            Lang::Raw(s) => Some(s.clone()),
        }
    }
}

/// [`disarm::api::DigitPolicy`], drawable from the options. `Numeric` first: the default.
#[derive(Debug, Clone, Copy, Arbitrary)]
pub enum Policy {
    /// `DigitPolicy::Numeric`.
    Numeric,
    /// `DigitPolicy::Tr39`.
    Tr39,
    /// `DigitPolicy::Preserve`.
    Preserve,
}

impl From<Policy> for disarm::api::DigitPolicy {
    fn from(p: Policy) -> Self {
        match p {
            Policy::Numeric => Self::Numeric,
            Policy::Tr39 => Self::Tr39,
            Policy::Preserve => Self::Preserve,
        }
    }
}

/// NFC of `s`, through the library's own normalizer.
pub fn nfc(s: &str) -> String {
    disarm::api::normalize(s, disarm::api::NormalizationForm::Nfc)
}

/// NFD of `s`, through the library's own normalizer.
pub fn nfd(s: &str) -> String {
    disarm::api::normalize(s, disarm::api::NormalizationForm::Nfd)
}

/// Whether a locator's `(ch, offset)` points at `ch` in `s`, in the weak sense the
/// locators meet today: `offset` is a char boundary of `s`, and `ch` occurs at or after
/// it, as itself, in the NFC of the rest (a discontiguous composition: `n U+05BC U+0327`
/// composes to `U+0146`), or through its canonical decomposition. After, not at: a mark
/// is reported at the offset of its base, however long the run of marks between them.
///
/// The documented contract is stronger — "its byte offset in the input string", and for
/// `find_confusables` "the character as it appeared in the input" — and does not hold:
/// the confusable locators walk composed clusters and report every character of one at
/// the cluster's start, and a composed character that never appeared in the input (even
/// a composition exclusion such as U+FB49, which no normalization form produces), and
/// `find_untranslatable` reports a selector at the offset of its base. Found by this
/// fuzzer; see docs/contributing/testing.md, "Fuzzing". Tighten this to
/// `s[offset..].starts_with(ch)` once that is fixed.
pub fn located(s: &str, offset: usize, ch: char) -> bool {
    let Some(rest) = s.get(offset..) else {
        return false;
    };
    let decomposed = nfd(ch.encode_utf8(&mut [0; 4]));
    !rest.is_empty()
        && (rest.contains(ch) || nfc(rest).contains(ch) || nfd(rest).contains(&decomposed))
}
