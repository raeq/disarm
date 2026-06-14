//! Shared proptest strategies for the split integration-transliterate test crates.
//!
//! Rust integration tests are separate crates, so these helpers cannot be shared
//! via `use` across the `integration_transliterate*` files directly. Following the
//! standard cargo pattern, they live in `tests/common/mod.rs` (which is NOT itself
//! compiled as a test crate) and each split file does `mod common;` then
//! `use common::*;`.
//!
//! Each split test crate uses a different subset of these strategies, so unused
//! ones are expected per-crate — hence the module-level `allow(dead_code)`.
#![allow(dead_code)]

use proptest::prelude::*;

/// Generate a random string from a Unicode range.
pub fn chars_in_range(start: u32, end: u32) -> BoxedStrategy<String> {
    let chars: Vec<char> = (start..=end).filter_map(char::from_u32).collect();
    proptest::collection::vec(proptest::sample::select(chars), 1..=30)
        .prop_map(|v| v.into_iter().collect::<String>())
        .boxed()
}

/// Generate Devanagari text (U+0900-U+097F).
pub fn devanagari_text() -> BoxedStrategy<String> {
    chars_in_range(0x0900, 0x097F)
}

/// Generate Bengali text (U+0980-U+09FF).
pub fn bengali_text() -> BoxedStrategy<String> {
    chars_in_range(0x0980, 0x09FF)
}

/// Generate Tamil text (U+0B80-U+0BFF).
pub fn tamil_text() -> BoxedStrategy<String> {
    chars_in_range(0x0B80, 0x0BFF)
}

/// Generate text from any of the 10 Indic blocks (U+0900-U+0DFF, includes Sinhala).
pub fn any_indic_text() -> BoxedStrategy<String> {
    chars_in_range(0x0900, 0x0DFF)
}

/// Generate Hebrew text (U+0590-U+05FF).
pub fn hebrew_text() -> BoxedStrategy<String> {
    chars_in_range(0x0590, 0x05FF)
}

/// Generate Hebrew presentation forms (U+FB1D-U+FB4F).
pub fn hebrew_presentation_text() -> BoxedStrategy<String> {
    chars_in_range(0xFB1D, 0xFB4F)
}

/// Generate Sinhala text (U+0D80-U+0DFF).
pub fn sinhala_text() -> BoxedStrategy<String> {
    chars_in_range(0x0D80, 0x0DFF)
}

/// Generate Georgian text (U+10D0-U+10F0 Mkhedruli).
pub fn georgian_text() -> BoxedStrategy<String> {
    chars_in_range(0x10D0, 0x10F0)
}

/// Generate Armenian text (U+0530-U+058F).
pub fn armenian_text() -> BoxedStrategy<String> {
    chars_in_range(0x0531, 0x0587)
}

/// Generate Thai text (U+0E01-U+0E4B, consonants + vowels + tone marks).
pub fn thai_text() -> BoxedStrategy<String> {
    chars_in_range(0x0E01, 0x0E4B)
}

/// Generate Thai consonants only (U+0E01-U+0E2E).
pub fn thai_consonants_strat() -> BoxedStrategy<String> {
    chars_in_range(0x0E01, 0x0E2E)
}

/// Generate Thai digits only (U+0E50-U+0E59).
pub fn thai_digits_strat() -> BoxedStrategy<String> {
    chars_in_range(0x0E50, 0x0E59)
}

/// Generate Lao text (U+0E81-U+0ECD).
pub fn lao_text() -> BoxedStrategy<String> {
    chars_in_range(0x0E81, 0x0ECD)
}

/// Generate any Tai text (Thai or Lao).
pub fn any_tai_text() -> BoxedStrategy<String> {
    proptest::strategy::Union::new(vec![thai_text(), lao_text()]).boxed()
}

/// Generate extended Latin text (U+00C0-U+024F).
pub fn extended_latin_text() -> BoxedStrategy<String> {
    chars_in_range(0x00C0, 0x024F)
}

/// Generate Cyrillic text (U+0400-U+04FF).
pub fn cyrillic_text() -> BoxedStrategy<String> {
    chars_in_range(0x0400, 0x04FF)
}

/// Generate CJK text (U+4E00-U+50FF).
pub fn cjk_text() -> BoxedStrategy<String> {
    chars_in_range(0x4E00, 0x50FF)
}

/// Generate Hangul text (U+AC00-U+ACFF).
pub fn hangul_text() -> BoxedStrategy<String> {
    chars_in_range(0xAC00, 0xACFF)
}

/// Devanagari consonants only (U+0915-U+0939).
pub fn devanagari_consonants() -> BoxedStrategy<String> {
    chars_in_range(0x0915, 0x0939)
}

pub fn ethiopic_text() -> BoxedStrategy<String> {
    let chars: Vec<char> = (0x1200u32..=0x1357)
        .filter(|cp| {
            let block_offset = cp & 0x07;
            block_offset < 7 // skip labialized gap at offset 7
        })
        .filter_map(char::from_u32)
        .collect();
    proptest::collection::vec(proptest::sample::select(chars), 1..=20)
        .prop_map(|v| v.into_iter().collect::<String>())
        .boxed()
}

pub fn myanmar_text() -> BoxedStrategy<String> {
    let chars: Vec<char> = (0x1000u32..=0x104B).filter_map(char::from_u32).collect();
    proptest::collection::vec(proptest::sample::select(chars), 1..=20)
        .prop_map(|v| v.into_iter().collect::<String>())
        .boxed()
}

pub fn khmer_text() -> BoxedStrategy<String> {
    let chars: Vec<char> = (0x1780u32..=0x17E9).filter_map(char::from_u32).collect();
    proptest::collection::vec(proptest::sample::select(chars), 1..=20)
        .prop_map(|v| v.into_iter().collect::<String>())
        .boxed()
}

pub fn tibetan_text() -> BoxedStrategy<String> {
    let chars: Vec<char> = (0x0F00u32..=0x0F6A)
        .chain(0x0F71..=0x0F84)
        .chain(0x0F90..=0x0FBC)
        .filter_map(char::from_u32)
        .filter(|c| c.is_alphanumeric() || !c.is_control())
        .collect();
    proptest::collection::vec(proptest::sample::select(chars), 1..=20)
        .prop_map(|v| v.into_iter().collect::<String>())
        .boxed()
}

/// Generate Arabic text (U+0621-U+064A).
pub fn arabic_text() -> BoxedStrategy<String> {
    chars_in_range(0x0621, 0x064A)
}

/// Generate Arabic Presentation Forms-B (U+FE70-U+FEFF).
pub fn arabic_presentation_text() -> BoxedStrategy<String> {
    chars_in_range(0xFE70, 0xFEFC)
}

/// Generate Syriac text (U+0710-U+0740).
pub fn syriac_text() -> BoxedStrategy<String> {
    chars_in_range(0x0710, 0x073F)
}

/// Generate Thaana text (U+0780-U+07B0).
pub fn thaana_text() -> BoxedStrategy<String> {
    chars_in_range(0x0780, 0x07B0)
}

/// Generate N'Ko text (U+07C0-U+07F9).
pub fn nko_text() -> BoxedStrategy<String> {
    chars_in_range(0x07C0, 0x07E7)
}

/// Generate Coptic text (U+2C80-U+2CC1).
pub fn coptic_text() -> BoxedStrategy<String> {
    chars_in_range(0x2C80, 0x2CC1)
}

/// Generate Cherokee text (U+13A0-U+13F5).
pub fn cherokee_text() -> BoxedStrategy<String> {
    chars_in_range(0x13A0, 0x13F5)
}

/// Generate Canadian Aboriginal Syllabics text (U+1401-U+1676).
pub fn canadian_text() -> BoxedStrategy<String> {
    chars_in_range(0x1401, 0x1676)
}

/// Generate Vai text (U+A500-U+A62B).
pub fn vai_text() -> BoxedStrategy<String> {
    chars_in_range(0xA500, 0xA62B)
}

/// Generate Mongolian text (U+1820-U+1878).
pub fn mongolian_text() -> BoxedStrategy<String> {
    chars_in_range(0x1820, 0x1878)
}

/// Generate Runic text (U+16A0-U+16EA).
pub fn runic_text() -> BoxedStrategy<String> {
    chars_in_range(0x16A0, 0x16EA)
}

/// Generate Ogham text (U+1681-U+169A).
pub fn ogham_text() -> BoxedStrategy<String> {
    chars_in_range(0x1681, 0x169A)
}

/// Generate Balinese text (U+1B05-U+1B59).
pub fn balinese_text() -> BoxedStrategy<String> {
    chars_in_range(0x1B05, 0x1B44)
}

/// Generate Balinese consonants (U+1B13-U+1B33).
pub fn balinese_consonants() -> BoxedStrategy<String> {
    chars_in_range(0x1B13, 0x1B33)
}

/// Generate Javanese text (U+A984-U+A9C0).
pub fn javanese_text() -> BoxedStrategy<String> {
    chars_in_range(0xA984, 0xA9C0)
}

/// Generate Javanese consonants (U+A990-U+A9B2).
pub fn javanese_consonants() -> BoxedStrategy<String> {
    chars_in_range(0xA990, 0xA9B2)
}

/// Generate Tai Le text (U+1950-U+196D).
pub fn tai_le_text() -> BoxedStrategy<String> {
    chars_in_range(0x1950, 0x196D)
}

/// Generate New Tai Lue text (U+1980-U+19C9).
pub fn new_tai_lue_text() -> BoxedStrategy<String> {
    chars_in_range(0x1980, 0x19C9)
}

// ── #352: positional shims over the new `Transliterate` builder ────────────────
// The per-script conformance tables call transliterate ~220 times with positional
// args. Rather than rewrite each to the builder, these helpers keep the old call
// shape on top of the new API. Use `common::transliterate(...)` in the tests.

fn scheme_of(strict_iso9: bool, gost7034: bool) -> disarm::api::Scheme {
    use disarm::api::Scheme;
    if strict_iso9 {
        Scheme::StrictIso9
    } else if gost7034 {
        Scheme::GostR7034
    } else {
        Scheme::Default
    }
}

fn on_unknown_of(error_mode: disarm::ErrorMode, replacement: &str) -> disarm::api::OnUnknown {
    use disarm::api::OnUnknown;
    match error_mode {
        disarm::ErrorMode::Replace => OnUnknown::Replace(replacement.to_owned()),
        disarm::ErrorMode::Ignore => OnUnknown::Ignore,
        disarm::ErrorMode::Preserve => OnUnknown::Preserve,
    }
}

/// Positional transliterate matching the pre-#352 `api::transliterate` signature.
pub fn transliterate<'a>(
    text: &'a str,
    lang: Option<&str>,
    error_mode: disarm::ErrorMode,
    replacement: &str,
    tones: bool,
    strict_iso9: bool,
    gost7034: bool,
) -> std::borrow::Cow<'a, str> {
    let mut b = disarm::api::Transliterate::new()
        .scheme(scheme_of(strict_iso9, gost7034))
        .on_unknown(on_unknown_of(error_mode, replacement))
        .tones(tones);
    if let Some(l) = lang {
        b = b.lang(l);
    }
    b.run(text)
}

/// Positional `find_untranslatable` matching the pre-#352 signature.
pub fn find_untranslatable(
    text: &str,
    lang: Option<&str>,
    tones: bool,
    strict_iso9: bool,
    gost7034: bool,
) -> Vec<(char, usize)> {
    let mut b = disarm::api::Transliterate::new()
        .scheme(scheme_of(strict_iso9, gost7034))
        .tones(tones);
    if let Some(l) = lang {
        b = b.lang(l);
    }
    b.find_untranslatable(text)
}
