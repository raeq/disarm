use pyo3::prelude::*;
use unicode_normalization::UnicodeNormalization;

/// Maximum input size for normalization, in bytes.
///
/// Unicode NFKD can expand a single codepoint into up to 18 combining
/// characters in pathological cases.  Capping input size bounds worst-case
/// output size and prevents out-of-memory conditions on adversarial input.
const MAX_NORMALIZE_INPUT_BYTES: usize = 10 * 1024 * 1024; // 10 MiB

/// Unicode normalization (NFC, NFD, NFKC, NFKD).
#[pyfunction]
#[pyo3(signature = (text, *, form="NFC"))]
pub fn _normalize(text: &str, form: &str) -> PyResult<String> {
    if text.len() > MAX_NORMALIZE_INPUT_BYTES {
        return Err(crate::TranslitError::new_err(format!(
            "input too large ({} bytes); maximum for normalize() is {} bytes",
            text.len(),
            MAX_NORMALIZE_INPUT_BYTES
        )));
    }
    match form {
        "NFC" => Ok(text.nfc().collect()),
        "NFD" => Ok(text.nfd().collect()),
        "NFKC" => Ok(text.nfkc().collect()),
        "NFKD" => Ok(text.nfkd().collect()),
        _ => Err(crate::TranslitError::new_err(format!(
            "form must be 'NFC', 'NFD', 'NFKC', or 'NFKD', got '{form}'"
        ))),
    }
}

/// Check if text is already in the specified normalization form.
#[pyfunction]
#[pyo3(signature = (text, *, form="NFC"))]
pub fn _is_normalized(text: &str, form: &str) -> PyResult<bool> {
    match form {
        "NFC" => Ok(unicode_normalization::is_nfc(text)),
        "NFD" => Ok(unicode_normalization::is_nfd(text)),
        "NFKC" => Ok(unicode_normalization::is_nfkc(text)),
        "NFKD" => Ok(unicode_normalization::is_nfkd(text)),
        _ => Err(crate::TranslitError::new_err(format!(
            "form must be 'NFC', 'NFD', 'NFKC', or 'NFKD', got '{form}'"
        ))),
    }
}

/// Batch normalization: process a list of strings in a single PyO3 boundary crossing.
#[pyfunction]
#[pyo3(signature = (texts, *, form="NFC"))]
pub fn _normalize_batch(texts: Vec<String>, form: &str) -> PyResult<Vec<String>> {
    // Validate each string's size before processing any.
    for t in &texts {
        if t.len() > MAX_NORMALIZE_INPUT_BYTES {
            return Err(crate::TranslitError::new_err(format!(
                "input too large ({} bytes); maximum for normalize() is {} bytes",
                t.len(),
                MAX_NORMALIZE_INPUT_BYTES
            )));
        }
    }
    // Validate form once, then apply to all strings.
    match form {
        "NFC" => Ok(texts.iter().map(|t| t.nfc().collect()).collect()),
        "NFD" => Ok(texts.iter().map(|t| t.nfd().collect()).collect()),
        "NFKC" => Ok(texts.iter().map(|t| t.nfkc().collect()).collect()),
        "NFKD" => Ok(texts.iter().map(|t| t.nfkd().collect()).collect()),
        _ => Err(crate::TranslitError::new_err(format!(
            "form must be 'NFC', 'NFD', 'NFKC', or 'NFKD', got '{form}'"
        ))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_nfc_roundtrip() {
        let text = "caf\u{0065}\u{0301}"; // e + combining accent
        let normalized = _normalize(text, "NFC").unwrap();
        assert_eq!(normalized, "caf\u{00e9}"); // single é
    }

    mod proptest_properties {
        use super::*;
        use proptest::prelude::*;

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            /// Normalizing twice in any form gives the same result as once.
            #[test]
            fn normalize_idempotent(
                s in "\\PC*",
                form in prop_oneof!["NFC", "NFD", "NFKC", "NFKD"],
            ) {
                let once = _normalize(&s, &form).unwrap();
                let twice = _normalize(&once, &form).unwrap();
                prop_assert_eq!(&once, &twice);
            }

            /// After normalizing, is_normalized must confirm the result.
            #[test]
            fn normalize_then_is_normalized(
                s in "\\PC*",
                form in prop_oneof!["NFC", "NFD", "NFKC", "NFKD"],
            ) {
                let normalized = _normalize(&s, &form).unwrap();
                prop_assert!(_is_normalized(&normalized, &form).unwrap());
            }

            /// NFKC output is always also valid NFC.
            #[test]
            fn nfkc_implies_nfc(s in "\\PC*") {
                let nfkc = _normalize(&s, "NFKC").unwrap();
                prop_assert!(_is_normalized(&nfkc, "NFC").unwrap());
            }

            /// NFKD output is always also valid NFD.
            #[test]
            fn nfkd_implies_nfd(s in "\\PC*") {
                let nfkd = _normalize(&s, "NFKD").unwrap();
                prop_assert!(_is_normalized(&nfkd, "NFD").unwrap());
            }
        }
    }
}
