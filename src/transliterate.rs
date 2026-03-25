use pyo3::prelude::*;
use std::borrow::Cow;
use std::collections::HashMap;

use crate::tables;
use crate::unicode_ranges as ur;
use crate::ErrorMode;

/// Maximum input size for transliteration, in bytes.
///
/// Transliteration may expand CJK characters to multi-word ASCII (e.g.
/// 你→"ni "), so worst-case output can be several times larger than input.
/// This cap prevents excessive allocation on adversarial input.
const MAX_TRANSLITERATE_INPUT_BYTES: usize = 10 * 1024 * 1024; // 10 MiB

/// Script class for tracking inter-script word spacing.
///
/// Used to determine whether a space separator should be inserted between
/// adjacent transliterated characters (e.g. between consecutive CJK ideographs,
/// but not between consecutive kana).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ScriptClass {
    /// Start-of-string or no character yet.
    None,
    /// CJK Unified Ideograph (Han character).
    Ideograph,
    /// Hangul syllable or jamo.
    Hangul,
    /// Hiragana or Katakana.
    Kana,
    /// ASCII / Latin character.
    Latin,
    /// Indic Brahmic scripts (Devanagari, Bengali, Tamil, etc.).
    Indic,
    /// Any other script (Cyrillic, Arabic, etc.).
    Other,
}

/// Core transliteration: Unicode → ASCII.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None, errors="replace", replace_with="[?]", strict_iso9=false, gost7034=false))]
pub fn _transliterate(
    text: &str,
    lang: Option<&str>,
    errors: &str,
    replace_with: &str,
    strict_iso9: bool,
    gost7034: bool,
) -> PyResult<String> {
    if strict_iso9 && gost7034 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "strict_iso9 and gost7034 are mutually exclusive",
        ));
    }
    if text.len() > MAX_TRANSLITERATE_INPUT_BYTES {
        return translit_err!(
            "input too large ({} bytes); maximum for transliterate() is {} bytes",
            text.len(),
            MAX_TRANSLITERATE_INPUT_BYTES
        );
    }
    let error_mode = ErrorMode::from_str(errors)?;
    Ok(
        transliterate_impl(text, lang, error_mode, replace_with, strict_iso9, gost7034)
            .into_owned(),
    )
}

/// Internal transliteration implementation.
///
/// Returns `Cow::Borrowed` when the input is pure ASCII (zero allocation),
/// `Cow::Owned` otherwise.
pub fn transliterate_impl<'a>(
    text: &'a str,
    lang: Option<&str>,
    error_mode: ErrorMode,
    replace_with: &str,
    strict_iso9: bool,
    gost7034: bool,
) -> Cow<'a, str> {
    // Fast path: pure ASCII input needs no transliteration.
    // `str::is_ascii()` is a single SIMD-friendly scan — sub-nanosecond for
    // short strings, and it lets us skip all per-character work + allocation.
    if text.is_ascii() {
        return Cow::Borrowed(text);
    }

    let mut result = String::with_capacity(estimate_capacity(text));
    let mut prev_class = ScriptClass::None;
    // Track last char appended to `result` — avoids O(n) `result.chars().last()` scan.
    let mut last_appended: Option<char> = None;
    // Indic virama/mātrā context: when the previous character was an Indic
    // consonant (whose table entry includes the inherent "a"), a following
    // virama or dependent vowel must strip that trailing "a" first.
    let mut last_was_indic_consonant = false;

    for ch in text.chars() {
        if ch.is_ascii() {
            last_was_indic_consonant = false;
            // Insert space when transitioning from ideograph/Hangul to ASCII alnum
            if matches!(prev_class, ScriptClass::Ideograph | ScriptClass::Hangul)
                && ch.is_alphanumeric()
            {
                if let Some(last) = last_appended {
                    if last.is_alphanumeric() {
                        result.push(' ');
                    }
                }
            }
            result.push(ch);
            last_appended = Some(ch);
            prev_class = ScriptClass::Latin;
            continue;
        }

        let char_class = classify_char(ch);
        let is_cjk = matches!(
            char_class,
            ScriptClass::Ideograph | ScriptClass::Hangul | ScriptClass::Kana
        );

        // Lookup priority:
        // 1. If strict_iso9: ISO 9 table → default table (lang overrides ignored)
        // 2. If gost7034: GOST 7.0.34 table → default table (lang overrides ignored)
        // 3. Otherwise: lang override → default table
        let mapped: Option<Cow<'static, str>> = if strict_iso9 {
            tables::lookup_iso9(ch)
                .map(Cow::Borrowed)
                .or_else(|| tables::lookup_default(ch).map(Cow::Borrowed))
        } else if gost7034 {
            tables::lookup_gost7034(ch)
                .map(Cow::Borrowed)
                .or_else(|| tables::lookup_default(ch).map(Cow::Borrowed))
        } else {
            lang.and_then(|l| tables::lookup_lang(l, ch))
                .or_else(|| tables::lookup_default(ch).map(Cow::Borrowed))
        };

        if let Some(s) = mapped.as_deref() {
            if is_cjk
                && !s.is_empty()
                && prev_class != ScriptClass::None
                && needs_cjk_space(prev_class, char_class)
            {
                if let Some(last) = last_appended {
                    if last.is_alphanumeric() {
                        result.push(' ');
                        last_appended = Some(' ');
                    }
                }
            }
            // Indic virama/mātrā handling: strip the inherent "a" from
            // the previous consonant when followed by virama or a dependent
            // vowel sign.
            if char_class == ScriptClass::Indic {
                let role = indic_char_role(ch as u32);
                match role {
                    IndicRole::Virama | IndicRole::DependentVowel if last_was_indic_consonant => {
                        // Pop the trailing inherent 'a' from the previous consonant
                        if result.ends_with('a') {
                            result.pop();
                        }
                        last_was_indic_consonant = false;
                    }
                    IndicRole::Consonant => {
                        last_was_indic_consonant = true;
                    }
                    _ => {
                        last_was_indic_consonant = false;
                    }
                }
            } else {
                last_was_indic_consonant = false;
            }
            result.push_str(s);
            // Track last char of the appended transliteration string
            if let Some(c) = s.chars().next_back() {
                last_appended = Some(c);
            }
            prev_class = char_class;
        } else {
            last_was_indic_consonant = false;
            match error_mode {
                ErrorMode::Replace => {
                    // An empty replace_with is intentionally equivalent to
                    // ErrorMode::Ignore — the char is silently dropped.
                    // This matches Unidecode's default behaviour and is
                    // used by the unidecode() compat shim.
                    result.push_str(replace_with);
                    last_appended = replace_with.chars().next_back();
                }
                ErrorMode::Ignore => {}
                ErrorMode::Preserve => {
                    result.push(ch);
                    last_appended = Some(ch);
                }
            }
            prev_class = ScriptClass::Other;
        }
    }

    Cow::Owned(result)
}

/// Estimate the output buffer capacity based on a sample of the input.
///
/// For Latin/Cyrillic/Arabic, a 1:1 ratio is typical.
/// For CJK, each ideograph expands to a multi-letter pinyin/romaji syllable
/// plus a space separator — typically 3–5× the UTF-8 byte length.
/// We sample the first 5 non-ASCII codepoints and use the maximum multiplier
/// seen, so mixed-script strings like "Hello 北京" pick up the CJK 4×
/// multiplier rather than defaulting to 1× from the leading Latin characters.
/// The result is capped at 256 MiB: a larger `with_capacity` hint is never
/// useful and avoids attempting massive pre-allocations on adversarial input.
const MAX_CAPACITY_HINT: usize = 256 * 1024 * 1024; // 256 MiB

fn estimate_capacity(text: &str) -> usize {
    let multiplier = text
        .chars()
        .filter(|c| !c.is_ascii())
        .take(5)
        .fold(1usize, |max_m, c| {
            let cp = c as u32;
            let m = if ur::CJK_CAPACITY_RANGE.contains(&cp)
                || ur::HANGUL_SYLLABLES.contains(&cp)
                || ur::CJK_COMPAT.contains(&cp)
            {
                4
            } else {
                1
            };
            max_m.max(m)
        });
    text.len().saturating_mul(multiplier).min(MAX_CAPACITY_HINT)
}

/// Classify a non-ASCII character into a script class for spacing decisions.
#[inline]
fn classify_char(ch: char) -> ScriptClass {
    if is_cjk_ideograph(ch) {
        ScriptClass::Ideograph
    } else if is_hangul(ch) {
        ScriptClass::Hangul
    } else if is_kana(ch) {
        ScriptClass::Kana
    } else if is_indic(ch) {
        ScriptClass::Indic
    } else {
        ScriptClass::Other
    }
}

/// Determine whether a space should be inserted between two adjacent CJK
/// transliterations, given their script classes.
///
/// Spaces are inserted:
/// - Between consecutive ideographs (each is a word): 北京 → "bei jing"
/// - Between consecutive Hangul syllables: 서울 → "seo ul"
/// - At ideograph↔kana boundaries: 東京タワー → "dong jing tawa-"
/// - After Latin/Other before any CJK: "hello東京" → "hello dong jing"
///
/// NOT inserted between consecutive kana (they concatenate to form words).
///
/// Note: this function is only called when `curr` is a CJK class
/// (Ideograph | Hangul | Kana), guarded by the `is_cjk` check at the
/// call site. The last arm is explicitly enumerated to match that
/// constraint rather than using a wildcard.
#[inline]
fn needs_cjk_space(prev: ScriptClass, curr: ScriptClass) -> bool {
    use ScriptClass::{Hangul, Ideograph, Indic, Kana, Latin, Other};
    matches!(
        (prev, curr),
        (Ideograph | Kana | Hangul, Ideograph | Hangul)
            | (Ideograph | Hangul, Kana)
            | (Latin | Other | Indic, Ideograph | Hangul | Kana)
    )
}

/// Check if a character is a CJK Unified Ideograph (Han character).
#[inline]
fn is_cjk_ideograph(ch: char) -> bool {
    let cp = ch as u32;
    ur::CJK_UNIFIED.contains(&cp) || ur::CJK_EXT_A.contains(&cp) || ur::CJK_COMPAT.contains(&cp)
}

/// Check if a character is a Hangul syllable or jamo.
#[inline]
fn is_hangul(ch: char) -> bool {
    let cp = ch as u32;
    ur::HANGUL_SYLLABLES.contains(&cp) || ur::HANGUL_COMPAT_JAMO.contains(&cp)
}

/// Check if a character is in any Brahmic abugida range (Indic, Tibetan, Myanmar, Khmer).
#[inline]
fn is_indic(ch: char) -> bool {
    let cp = ch as u32;
    ur::INDIC.contains(&cp)
        || ur::TIBETAN.contains(&cp)
        || ur::MYANMAR.contains(&cp)
        || ur::KHMER.contains(&cp)
        || ur::BALINESE.contains(&cp)
        || ur::JAVANESE.contains(&cp)
}

/// Role of an Indic character for virama/mātrā context handling.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum IndicRole {
    /// Not a special Indic role (independent vowel, modifier, digit, etc.)
    None,
    /// Consonant (carries inherent "a" in the transliteration table).
    Consonant,
    /// Dependent vowel sign (mātrā) — replaces the inherent "a".
    DependentVowel,
    /// Virama (halant) — suppresses the inherent "a".
    Virama,
}

/// Classify a Brahmic codepoint's role based on its offset within the script block.
///
/// All core Indic scripts share a common structural layout at consistent Unicode
/// offsets (modulo 0x80), so a single function handles the 9 core scripts.
/// Sinhala, Tibetan, Myanmar, and Khmer use different offsets and are handled
/// by dedicated sub-functions.
#[inline]
fn indic_char_role(cp: u32) -> IndicRole {
    if (0x0D80..=0x0DFF).contains(&cp) {
        return sinhala_char_role(cp);
    }
    if (0x0F00..=0x0FFF).contains(&cp) {
        return tibetan_char_role(cp);
    }
    if (0x1000..=0x109F).contains(&cp) {
        return myanmar_char_role(cp);
    }
    if (0x1780..=0x17FF).contains(&cp) {
        return khmer_char_role(cp);
    }
    if (0x1B00..=0x1B7F).contains(&cp) {
        return balinese_char_role(cp);
    }
    if (0xA980..=0xA9DF).contains(&cp) {
        return javanese_char_role(cp);
    }
    if !(0x0900..=0x0D7F).contains(&cp) {
        return IndicRole::None;
    }
    let offset = cp & 0x7F;
    match offset {
        0x15..=0x39 | 0x58..=0x5F => IndicRole::Consonant,
        0x3E..=0x4C => IndicRole::DependentVowel,
        0x4D => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Sinhala codepoint's role. Sinhala consonants, dependent vowels,
/// and virama (al-lakuna) occupy different offsets from the other Indic scripts.
#[inline]
fn sinhala_char_role(cp: u32) -> IndicRole {
    match cp {
        0x0D9A..=0x0DC6 => IndicRole::Consonant,
        0x0DCF..=0x0DDF | 0x0DF2..=0x0DF3 => IndicRole::DependentVowel,
        0x0DCA => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Tibetan codepoint's role.
///
/// Tibetan consonants (U+0F40–U+0F69) and subjoined consonants (U+0F90–U+0FBC)
/// carry an inherent 'a'. Vowel signs (U+0F71–U+0F7D) replace it.
/// The halanta mark (U+0F84) suppresses it.
#[inline]
fn tibetan_char_role(cp: u32) -> IndicRole {
    match cp {
        0x0F40..=0x0F69 | 0x0F90..=0x0FBC => IndicRole::Consonant,
        0x0F71..=0x0F7D => IndicRole::DependentVowel,
        0x0F84 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Myanmar codepoint's role.
///
/// Myanmar consonants (U+1000–U+1021) carry an inherent 'a'.
/// Dependent vowels (U+102B–U+1035) and medial consonants (U+103B–U+103E) replace it.
/// Virama (U+1039) and asat (U+103A) suppress it.
#[inline]
fn myanmar_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1000..=0x1021 => IndicRole::Consonant,
        0x102B..=0x1035 | 0x103B..=0x103E => IndicRole::DependentVowel,
        0x1039 | 0x103A => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Khmer codepoint's role.
///
/// Khmer consonants (U+1780–U+17A2) carry an inherent vowel.
/// Dependent vowels (U+17B6–U+17C5) replace it.
/// The coeng mark (U+17D2) stacks consonants (virama equivalent).
#[inline]
fn khmer_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1780..=0x17A2 => IndicRole::Consonant,
        0x17B6..=0x17C5 => IndicRole::DependentVowel,
        0x17D2 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Balinese codepoint's role. Balinese is a Brahmic abugida with
/// consonants carrying inherent 'a', dependent vowels, and adeg-adeg (virama).
#[inline]
fn balinese_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1B13..=0x1B33 => IndicRole::Consonant,
        0x1B35..=0x1B43 => IndicRole::DependentVowel,
        0x1B44 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Javanese codepoint's role. Javanese is a Brahmic abugida with
/// consonants carrying inherent 'a', dependent vowels, and pangkon (virama).
#[inline]
fn javanese_char_role(cp: u32) -> IndicRole {
    match cp {
        0xA990..=0xA9B2 => IndicRole::Consonant,
        0xA9B4..=0xA9BC => IndicRole::DependentVowel,
        0xA9C0 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Check if a character is Hiragana or Katakana.
/// Used for spacing: kanji→kana and kana→kanji transitions get spaces.
#[inline]
fn is_kana(ch: char) -> bool {
    let cp = ch as u32;
    ur::HIRAGANA.contains(&cp) || ur::KATAKANA.contains(&cp) || ur::KATAKANA_HALFWIDTH.contains(&cp)
}

/// Remove diacritical marks while preserving base characters.
/// NFD decompose → strip combining marks → NFC recompose.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _strip_accents(text: &str) -> String {
    use unicode_normalization::UnicodeNormalization;

    text.nfd()
        .filter(|c| !unicode_normalization::char::is_combining_mark(*c))
        .nfc()
        .collect()
}

/// True if all characters are ASCII (U+0000–U+007F).
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _is_ascii(text: &str) -> bool {
    text.is_ascii()
}

/// Return available language codes for transliteration.
#[pyfunction]
#[pyo3(signature = ())]
pub fn _list_langs() -> Vec<String> {
    tables::list_langs()
}

/// Register or override a transliteration mapping for a language code.
#[pyfunction]
#[pyo3(signature = (code, mappings))]
pub fn _register_lang(code: &str, mappings: HashMap<String, String>) -> PyResult<()> {
    // Guard against unbounded growth of the global language table.
    let current = tables::registered_lang_count();
    if current >= tables::MAX_REGISTERED_LANGS {
        // Re-registering an existing code is always allowed (overwrite, not grow).
        if !tables::has_registered_lang(code) {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "register_lang(): maximum of {} registered languages reached; \
                 re-registering an existing code is still allowed",
                tables::MAX_REGISTERED_LANGS
            )));
        }
    }
    tables::register_lang(code, mappings).map_err(|bad_keys| {
        pyo3::exceptions::PyValueError::new_err(format!(
            "register_lang(): mapping keys must be exactly one Unicode character; \
             invalid keys: {}",
            bad_keys
                .iter()
                .map(|k| format!("{k:?}"))
                .collect::<Vec<_>>()
                .join(", ")
        ))
    })
}

/// Register global pre-transliteration replacements.
#[pyfunction]
#[pyo3(signature = (replacements,))]
pub fn _register_replacements(replacements: HashMap<String, String>) -> PyResult<()> {
    tables::register_replacements(replacements).map_err(|projected| {
        pyo3::exceptions::PyValueError::new_err(format!(
            "register_replacements(): table would exceed the maximum of {} entries \
             (projected size: {}); call clear_replacements() first",
            tables::MAX_REPLACEMENTS,
            projected
        ))
    })
}

/// Remove a single global pre-transliteration replacement by key.
///
/// Returns True if the key was present, False otherwise.
#[pyfunction]
#[pyo3(signature = (key,))]
pub fn _remove_replacement(key: &str) -> PyResult<bool> {
    Ok(tables::remove_replacement(key))
}

/// Clear all global pre-transliteration replacements.
#[pyfunction]
#[pyo3(signature = ())]
pub fn _clear_replacements() -> PyResult<()> {
    tables::clear_replacements();
    Ok(())
}

/// Batch transliteration: process a list of strings in a single PyO3 boundary crossing.
#[pyfunction]
#[pyo3(signature = (texts, *, lang=None, errors="replace", replace_with="[?]", strict_iso9=false, gost7034=false))]
pub fn _transliterate_batch(
    texts: Vec<String>,
    lang: Option<&str>,
    errors: &str,
    replace_with: &str,
    strict_iso9: bool,
    gost7034: bool,
) -> PyResult<Vec<String>> {
    if strict_iso9 && gost7034 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "strict_iso9 and gost7034 are mutually exclusive",
        ));
    }
    if texts.len() > crate::MAX_BATCH_SIZE {
        return translit_err!(
            "batch too large ({} items); maximum is {} items",
            texts.len(),
            crate::MAX_BATCH_SIZE
        );
    }
    let error_mode = ErrorMode::from_str(errors)?;
    Ok(texts
        .iter()
        .map(|text| {
            transliterate_impl(text, lang, error_mode, replace_with, strict_iso9, gost7034)
                .into_owned()
        })
        .collect())
}

/// Batch accent stripping: process a list of strings in a single PyO3 boundary crossing.
#[pyfunction]
#[pyo3(signature = (texts,))]
pub fn _strip_accents_batch(texts: Vec<String>) -> PyResult<Vec<String>> {
    use unicode_normalization::UnicodeNormalization;
    if texts.len() > crate::MAX_BATCH_SIZE {
        return translit_err!(
            "batch too large ({} items); maximum is {} items",
            texts.len(),
            crate::MAX_BATCH_SIZE
        );
    }
    Ok(texts
        .into_iter()
        .map(|text| {
            if text.is_ascii() {
                text // move, no clone — Vec is consumed by into_iter()
            } else {
                text.nfd()
                    .filter(|c| !unicode_normalization::char::is_combining_mark(*c))
                    .nfc()
                    .collect()
            }
        })
        .collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ascii_passthrough() {
        let result = transliterate_impl("hello", None, ErrorMode::Replace, "[?]", false, false);
        assert_eq!(result, "hello");
    }

    #[test]
    fn test_is_ascii() {
        assert!(_is_ascii("hello"));
        assert!(!_is_ascii("héllo"));
    }

    mod proptest_properties {
        use super::*;
        use proptest::prelude::*;

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            /// With ErrorMode::Ignore, output is always pure ASCII.
            #[test]
            fn transliterate_ignore_is_ascii(s in "\\PC*") {
                let result = transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false);
                prop_assert!(
                    result.is_ascii(),
                    "Non-ASCII in Ignore output: {:?}",
                    result.chars().filter(|c: &char| !c.is_ascii()).collect::<Vec<_>>()
                );
            }

            /// With ErrorMode::Preserve, non-empty printable input produces
            /// non-empty output (every char either maps or is kept verbatim).
            #[test]
            fn transliterate_preserve_nonempty(s in "[^\\s]{1,50}") {
                let result = transliterate_impl(&s, None, ErrorMode::Preserve, "", false, false);
                prop_assert!(!result.is_empty());
            }

            /// strip_accents is idempotent.
            #[test]
            fn strip_accents_idempotent(s in "\\PC*") {
                let once = _strip_accents(&s);
                let twice = _strip_accents(&once);
                prop_assert_eq!(&once, &twice);
            }

            /// strip_accents output is always NFC (docstring: NFD → filter → NFC).
            #[test]
            fn strip_accents_output_is_nfc(s in "\\PC*") {
                let result = _strip_accents(&s);
                prop_assert!(
                    unicode_normalization::is_nfc(&result),
                    "strip_accents output not NFC"
                );
            }

            /// ASCII input passes through transliterate unchanged.
            #[test]
            fn transliterate_ascii_passthrough(s in "[a-zA-Z0-9 ]{0,100}") {
                let result = transliterate_impl(&s, None, ErrorMode::Replace, "[?]", false, false);
                prop_assert_eq!(&result, &s);
            }
        }
    }
}
