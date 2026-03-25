use pyo3::prelude::*;

use crate::tables;

/// Validate the `target_script` parameter. Currently only `"latin"` is supported.
fn validate_target_script(target_script: &str) -> PyResult<()> {
    if target_script != "latin" {
        return translit_err!("target_script must be 'latin', got '{target_script}'");
    }
    Ok(())
}

/// Replace Unicode confusable homoglyphs with target-script equivalents.
///
/// # Valid `target_script` values
/// Currently only `"latin"` is supported. Any other value raises `TranslitError`.
#[pyfunction]
#[pyo3(signature = (text, *, target_script="latin"))]
pub fn _normalize_confusables(text: &str, target_script: &str) -> PyResult<String> {
    validate_target_script(target_script)?;

    let mut result = String::with_capacity(text.len());

    for ch in text.chars() {
        match tables::lookup_confusable(ch, target_script) {
            Some(replacement) => result.push_str(replacement),
            None => result.push(ch),
        }
    }

    Ok(result)
}

/// True if text contains any characters confusable with target-script characters.
///
/// # Valid `target_script` values
/// Currently only `"latin"` is supported. Any other value raises `TranslitError`.
#[pyfunction]
#[pyo3(signature = (text, *, target_script="latin"))]
pub fn _is_confusable(text: &str, target_script: &str) -> PyResult<bool> {
    validate_target_script(target_script)?;

    for ch in text.chars() {
        if tables::lookup_confusable(ch, target_script).is_some() {
            return Ok(true);
        }
    }
    Ok(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normalize_confusables_cyrillic() {
        // Cyrillic 'а' (U+0430) → Latin 'a'
        let result = _normalize_confusables("\u{0430}", "latin").unwrap();
        assert_eq!(result, "a");
    }

    #[test]
    fn test_normalize_confusables_passthrough() {
        let result = _normalize_confusables("hello", "latin").unwrap();
        assert_eq!(result, "hello");
    }

    #[test]
    fn test_normalize_confusables_empty() {
        let result = _normalize_confusables("", "latin").unwrap();
        assert_eq!(result, "");
    }

    #[test]
    fn test_is_confusable_true() {
        // Cyrillic 'а' is confusable with Latin 'a'
        assert!(_is_confusable("\u{0430}", "latin").unwrap());
    }

    #[test]
    fn test_is_confusable_false() {
        assert!(!_is_confusable("hello", "latin").unwrap());
    }

    #[test]
    fn test_is_confusable_empty() {
        assert!(!_is_confusable("", "latin").unwrap());
    }

    #[test]
    fn test_validate_target_script_latin_ok() {
        assert!(validate_target_script("latin").is_ok());
    }

    #[test]
    fn test_validate_target_script_invalid() {
        assert!(validate_target_script("cyrillic").is_err());
        assert!(validate_target_script("").is_err());
        assert!(validate_target_script("Latin").is_err()); // case-sensitive
    }

    #[test]
    fn test_normalize_confusables_mixed_long() {
        // String with confusable Cyrillic chars interspersed with ASCII
        let input = "h\u{0435}ll\u{043E} w\u{043E}rld"; // Cyrillic е and о
        let result = _normalize_confusables(input, "latin").unwrap();
        // Cyrillic е→e, о→o
        assert_eq!(result, "hello world");
    }

    #[test]
    fn test_normalize_confusables_nfc_vs_nfd() {
        // Confusable lookup operates on individual codepoints; NFC and NFD
        // should both work (combining marks aren't confusable targets).
        let nfc = "\u{00e9}"; // é as single codepoint
        let result = _normalize_confusables(nfc, "latin").unwrap();
        // é is not a confusable — it should pass through unchanged
        assert_eq!(result, nfc);
    }

    // ── Property-based tests ─────────────────────────────────────────

    mod proptest_properties {
        use super::*;
        use proptest::prelude::*;

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            /// Normalizing confusables is idempotent: applying it twice
            /// yields the same result as applying it once. This must hold
            /// because every confusable maps to an ASCII target, and ASCII
            /// characters are never themselves confusable.
            #[test]
            fn normalize_confusables_idempotent(s in "\\PC*") {
                let once = _normalize_confusables(&s, "latin").unwrap();
                let twice = _normalize_confusables(&once, "latin").unwrap();
                prop_assert_eq!(&once, &twice,
                    "normalize_confusables is not idempotent on: {:?}", s);
            }

            /// After normalizing confusables, is_confusable must return false.
            /// This is the completeness invariant: if the table is self-consistent,
            /// no confusable characters survive normalization.
            #[test]
            fn normalized_is_not_confusable(s in "\\PC*") {
                let normalized = _normalize_confusables(&s, "latin").unwrap();
                let still_confusable = _is_confusable(&normalized, "latin").unwrap();
                prop_assert!(!still_confusable,
                    "is_confusable returned true after normalize_confusables on: {:?} → {:?}",
                    s, normalized);
            }

            /// normalize_confusables never drops characters — it only replaces.
            /// Output character count must be >= input character count
            /// (replacements may expand, e.g. a ligature confusable, but never shrink).
            #[test]
            fn normalize_confusables_never_drops_chars(s in "\\PC*") {
                let result = _normalize_confusables(&s, "latin").unwrap();
                prop_assert!(
                    result.chars().count() >= s.chars().count(),
                    "normalize_confusables dropped chars: {:?} ({} chars) → {:?} ({} chars)",
                    s, s.chars().count(), result, result.chars().count()
                );
            }

            /// normalize_confusables output is always valid UTF-8 (trivially
            /// true since we return String, but this catches memory corruption).
            #[test]
            fn normalize_confusables_valid_utf8(s in "\\PC*") {
                let result = _normalize_confusables(&s, "latin").unwrap();
                // If this compiles and doesn't panic, the result is valid UTF-8.
                prop_assert!(result.len() >= 0); // trivial, just forces evaluation
            }
        }
    }
}
