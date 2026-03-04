use pyo3::prelude::*;
use std::borrow::Cow;
use std::collections::HashMap;

use crate::tables;

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

    // Pre-size the output buffer.  For Latin/Cyrillic, 1:1 is a good estimate
    // (most characters map to one ASCII char).  For CJK, each ideograph expands
    // to a multi-letter pinyin/romaji syllable plus a space separator — typically
    // 3–5× the UTF-8 byte length.  We sample the first non-ASCII codepoint to
    // pick a multiplier, avoiding reallocations for CJK-heavy input.
    let capacity_multiplier = text.chars().find(|c| !c.is_ascii()).map_or(1, |c| {
        let cp = c as u32;
        if (0x3000..=0x9FFF).contains(&cp)
            || (0xAC00..=0xD7AF).contains(&cp)
            || (0xF900..=0xFAFF).contains(&cp)
        {
            4 // CJK ideographs, Hangul, kana, CJK punctuation
        } else {
            1 // Latin/Cyrillic/Arabic/etc.
        }
    });
    let mut result = String::with_capacity(text.len() * capacity_multiplier);
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

        let char_class = if is_cjk_ideograph(ch) {
            1_u8
        } else if is_hangul(ch) {
            2
        } else if is_kana(ch) {
            3
        } else {
            5
        };
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
                // Insert a space at script transitions to prevent run-together
                // transliterations. Spaces are inserted:
                // - Between consecutive ideographs (each is a word): 北京 → "bei jing"
                // - Between consecutive Hangul syllables: 서울 → "seo ul"
                // - At ideograph↔kana boundaries: 東京タワー → "dong jing tawa-"
                // - At CJK↔Latin boundaries (handled above for ASCII)
                // NOT inserted between consecutive kana (they form words by concat).
                if is_cjk && !s.is_empty() && prev_class != 0 {
                    let needs_space = match (prev_class, char_class) {
                        // Ideograph→ideograph: always space (each char is a "word")
                        (1, 1) => true,
                        // Hangul→Hangul: always space (each syllable is distinct)
                        (2, 2) => true,
                        // Kana→kana: NO space (concatenate for words like ひらがな)
                        (3, 3) => false,
                        // Cross-script transitions: space
                        (1, 3) | (3, 1) => true, // ideograph↔kana
                        (1, 2) | (2, 1) => true, // ideograph↔hangul
                        (2, 3) | (3, 2) => true, // hangul↔kana
                        // From ASCII/Latin/other to CJK
                        (4, _) | (5, _) => true,
                        _ => false,
                    };
                    if needs_space {
                        if let Some(last) = last_appended {
                            if last.is_alphanumeric() {
                                result.push(' ');
                                last_appended = Some(' ');
                            }
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

/// Check if a character is a CJK Unified Ideograph (Han character).
#[inline]
fn is_cjk_ideograph(ch: char) -> bool {
    let cp = ch as u32;
    (0x4E00..=0x9FFF).contains(&cp)       // CJK Unified Ideographs
        || (0x3400..=0x4DBF).contains(&cp) // CJK Extension A
        || (0xF900..=0xFAFF).contains(&cp) // CJK Compatibility Ideographs
}

/// Check if a character is a Hangul syllable or jamo.
#[inline]
fn is_hangul(ch: char) -> bool {
    let cp = ch as u32;
    (0xAC00..=0xD7AF).contains(&cp)       // Hangul Syllables
        || (0x3131..=0x3163).contains(&cp) // Compatibility Jamo
}

/// Check if a character is Hiragana or Katakana.
/// Used for spacing: kanji→kana and kana→kanji transitions get spaces.
#[inline]
fn is_kana(ch: char) -> bool {
    let cp = ch as u32;
    (0x3040..=0x309F).contains(&cp)       // Hiragana
        || (0x30A0..=0x30FF).contains(&cp) // Katakana
        || (0xFF65..=0xFF9F).contains(&cp) // Half-width Katakana
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
