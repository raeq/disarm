use pyo3::prelude::*;
use std::borrow::Cow;
use std::collections::HashMap;

use crate::tables;
use crate::unicode_ranges as ur;

/// Error handling mode for untransliterable characters.
#[derive(Debug, Clone, Copy)]
pub enum ErrorMode {
    Replace,
    Ignore,
    Preserve,
}

impl ErrorMode {
    pub fn from_str(s: &str) -> PyResult<Self> {
        match s {
            "replace" => Ok(Self::Replace),
            "ignore" => Ok(Self::Ignore),
            "preserve" => Ok(Self::Preserve),
            _ => Err(crate::TranslitError::new_err(format!(
                "errors must be 'replace', 'ignore', or 'preserve', got '{s}'"
            ))),
        }
    }
}

/// Core transliteration: Unicode → ASCII.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None, errors="replace", replace_with="[?]", strict_iso9=false))]
pub fn _transliterate(
    text: &str,
    lang: Option<&str>,
    errors: &str,
    replace_with: &str,
    strict_iso9: bool,
) -> PyResult<String> {
    let error_mode = ErrorMode::from_str(errors)?;
    Ok(transliterate_impl(text, lang, error_mode, replace_with, strict_iso9).into_owned())
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
) -> Cow<'a, str> {
    // Fast path: pure ASCII input needs no transliteration.
    // `str::is_ascii()` is a single SIMD-friendly scan — sub-nanosecond for
    // short strings, and it lets us skip all per-character work + allocation.
    if text.is_ascii() {
        return Cow::Borrowed(text);
    }

    let mut result = String::with_capacity(estimate_capacity(text));
    // Track the script class of the previous character for space insertion.
    // 0 = none/start, 1 = ideograph (Han), 2 = Hangul, 3 = kana, 4 = ASCII/Latin, 5 = other
    let mut prev_class: u8 = 0;
    // Track last char appended to `result` — avoids O(n) `result.chars().last()` scan.
    let mut last_appended: Option<char> = None;

    for ch in text.chars() {
        if ch.is_ascii() {
            // Insert space when transitioning from ideograph/Hangul to ASCII alnum
            if (prev_class == 1 || prev_class == 2) && ch.is_alphanumeric() {
                if let Some(last) = last_appended {
                    if last.is_alphanumeric() {
                        result.push(' ');
                    }
                }
            }
            result.push(ch);
            last_appended = Some(ch);
            prev_class = 4;
            continue;
        }

        let char_class = classify_char(ch);
        let is_cjk = char_class <= 3; // ideograph, hangul, or kana

        // Lookup priority:
        // 1. If strict_iso9: ISO 9 table → default table (lang overrides ignored)
        // 2. Otherwise: lang override → default table
        let mapped = if strict_iso9 {
            tables::lookup_iso9(ch).or_else(|| tables::lookup_default(ch))
        } else {
            lang.and_then(|l| tables::lookup_lang(l, ch))
                .or_else(|| tables::lookup_default(ch))
        };

        match mapped {
            Some(s) => {
                if is_cjk
                    && !s.is_empty()
                    && prev_class != 0
                    && needs_cjk_space(prev_class, char_class)
                {
                    if let Some(last) = last_appended {
                        if last.is_alphanumeric() {
                            result.push(' ');
                            last_appended = Some(' ');
                        }
                    }
                }
                result.push_str(s);
                // Track last char of the appended transliteration string
                if let Some(c) = s.chars().next_back() {
                    last_appended = Some(c);
                }
                prev_class = char_class;
            }
            None => {
                match error_mode {
                    ErrorMode::Replace => {
                        result.push_str(replace_with);
                        last_appended = replace_with.chars().next_back();
                    }
                    ErrorMode::Ignore => {}
                    ErrorMode::Preserve => {
                        result.push(ch);
                        last_appended = Some(ch);
                    }
                }
                prev_class = 5;
            }
        }
    }

    Cow::Owned(result)
}

/// Estimate the output buffer capacity based on a sample of the input.
///
/// For Latin/Cyrillic/Arabic, a 1:1 ratio is typical.
/// For CJK, each ideograph expands to a multi-letter pinyin/romaji syllable
/// plus a space separator — typically 3–5× the UTF-8 byte length.
/// We sample the first non-ASCII codepoint to pick a multiplier, avoiding
/// reallocations for CJK-heavy input without scanning the whole string.
fn estimate_capacity(text: &str) -> usize {
    let multiplier = text.chars().find(|c| !c.is_ascii()).map_or(1, |c| {
        let cp = c as u32;
        if ur::CJK_CAPACITY_RANGE.contains(&cp)
            || ur::HANGUL_SYLLABLES.contains(&cp)
            || ur::CJK_COMPAT.contains(&cp)
        {
            4
        } else {
            1
        }
    });
    text.len() * multiplier
}

/// Classify a non-ASCII character into a script class:
/// 1 = CJK ideograph, 2 = Hangul, 3 = kana, 5 = other
#[inline]
fn classify_char(ch: char) -> u8 {
    if is_cjk_ideograph(ch) {
        1
    } else if is_hangul(ch) {
        2
    } else if is_kana(ch) {
        3
    } else {
        5
    }
}

/// Determine whether a space should be inserted between two adjacent CJK
/// transliterations, given their script classes.
///
/// Spaces are inserted:
/// - Between consecutive ideographs (each is a word): 北京 → "bei jing"
/// - Between consecutive Hangul syllables: 서울 → "seo ul"
/// - At ideograph↔kana boundaries: 東京タワー → "dong jing tawa-"
/// - At CJK↔Latin boundaries (handled separately for ASCII)
///
/// NOT inserted between consecutive kana (they concatenate to form words).
#[inline]
fn needs_cjk_space(prev_class: u8, char_class: u8) -> bool {
    match (prev_class, char_class) {
        (1, 1) => true,          // ideograph→ideograph
        (2, 2) => true,          // Hangul→Hangul
        (3, 3) => false,         // kana→kana (no space)
        (1, 3) | (3, 1) => true, // ideograph↔kana
        (1, 2) | (2, 1) => true, // ideograph↔Hangul
        (2, 3) | (3, 2) => true, // Hangul↔kana
        (4, _) | (5, _) => true, // ASCII/other → CJK
        _ => false,
    }
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
    tables::register_lang(code, mappings);
    Ok(())
}

/// Register global pre-transliteration replacements.
#[pyfunction]
#[pyo3(signature = (replacements,))]
pub fn _register_replacements(replacements: HashMap<String, String>) -> PyResult<()> {
    tables::register_replacements(replacements);
    Ok(())
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
#[pyo3(signature = (texts, *, lang=None, errors="replace", replace_with="[?]", strict_iso9=false))]
pub fn _transliterate_batch(
    texts: Vec<String>,
    lang: Option<&str>,
    errors: &str,
    replace_with: &str,
    strict_iso9: bool,
) -> PyResult<Vec<String>> {
    let error_mode = ErrorMode::from_str(errors)?;
    Ok(texts
        .iter()
        .map(|text| {
            transliterate_impl(text, lang, error_mode, replace_with, strict_iso9).into_owned()
        })
        .collect())
}

/// Batch accent stripping: process a list of strings in a single PyO3 boundary crossing.
#[pyfunction]
#[pyo3(signature = (texts,))]
pub fn _strip_accents_batch(texts: Vec<String>) -> Vec<String> {
    use unicode_normalization::UnicodeNormalization;
    texts
        .iter()
        .map(|text| {
            if text.is_ascii() {
                text.clone()
            } else {
                text.nfd()
                    .filter(|c| !unicode_normalization::char::is_combining_mark(*c))
                    .nfc()
                    .collect()
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ascii_passthrough() {
        let result = transliterate_impl("hello", None, ErrorMode::Replace, "[?]", false);
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
                let result = transliterate_impl(&s, None, ErrorMode::Ignore, "", false);
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
                let result = transliterate_impl(&s, None, ErrorMode::Preserve, "", false);
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
                let result = transliterate_impl(&s, None, ErrorMode::Replace, "[?]", false);
                prop_assert_eq!(&result, &s);
            }
        }
    }
}
