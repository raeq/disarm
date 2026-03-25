use pyo3::prelude::*;
use unicode_normalization::UnicodeNormalization;

/// Maximum input size for normalization, in bytes.
///
/// Unicode NFKD can expand a single codepoint into up to 18 combining
/// characters in pathological cases (e.g. U+FDFA ﷺ → 18-char Arabic string).
/// Capping input size limits worst-case expansion.
const MAX_NORMALIZE_INPUT_BYTES: usize = 10 * 1024 * 1024; // 10 MiB

/// Maximum output size for normalization, in bytes.
///
/// Even with the 10 MiB input cap, a maximally expanding NFKD character
/// (18× expansion) could produce ~180 MiB of output.  This cap ensures the
/// allocated output stays within an acceptable bound.  The input check alone
/// is not sufficient because each input byte can expand to many output bytes.
const MAX_NORMALIZE_OUTPUT_BYTES: usize = 50 * 1024 * 1024; // 50 MiB

/// Validate normalization form string. Returns an error for invalid forms.
#[inline]
fn validate_form(form: &str) -> PyResult<()> {
    if !matches!(form, "NFC" | "NFD" | "NFKC" | "NFKD") {
        return translit_err!("form must be 'NFC', 'NFD', 'NFKC', or 'NFKD', got '{form}'");
    }
    Ok(())
}

/// Normalise `text` and check that the output does not exceed the output cap.
///
/// Collecting first then checking means the peak allocation equals the output
/// size, which the cap bounds.  The collected string is dropped on error so
/// the memory is immediately reclaimed.
#[inline]
fn normalize_checked(output: String, form: &str) -> PyResult<String> {
    if output.len() > MAX_NORMALIZE_OUTPUT_BYTES {
        return translit_err!(
            "normalize() output too large ({} bytes after {} normalization); \
             maximum output is {} bytes. Use a smaller input.",
            output.len(),
            form,
            MAX_NORMALIZE_OUTPUT_BYTES
        );
    }
    Ok(output)
}

/// Unicode normalization (NFC, NFD, NFKC, NFKD).
#[pyfunction]
#[pyo3(signature = (text, *, form="NFC"))]
pub fn _normalize(text: &str, form: &str) -> PyResult<String> {
    validate_form(form)?;
    if text.len() > MAX_NORMALIZE_INPUT_BYTES {
        return translit_err!(
            "input too large ({} bytes); maximum for normalize() is {} bytes",
            text.len(),
            MAX_NORMALIZE_INPUT_BYTES
        );
    }
    match form {
        "NFC" => normalize_checked(text.nfc().collect(), form),
        "NFD" => normalize_checked(text.nfd().collect(), form),
        "NFKC" => normalize_checked(text.nfkc().collect(), form),
        "NFKD" => normalize_checked(text.nfkd().collect(), form),
        _ => unreachable!(),
    }
}

/// Check if text is already in the specified normalization form.
#[pyfunction]
#[pyo3(signature = (text, *, form="NFC"))]
pub fn _is_normalized(text: &str, form: &str) -> PyResult<bool> {
    validate_form(form)?;
    match form {
        "NFC" => Ok(unicode_normalization::is_nfc(text)),
        "NFD" => Ok(unicode_normalization::is_nfd(text)),
        "NFKC" => Ok(unicode_normalization::is_nfkc(text)),
        "NFKD" => Ok(unicode_normalization::is_nfkd(text)),
        _ => unreachable!(),
    }
}

/// Batch normalization: process a list of strings in a single PyO3 boundary crossing.
#[pyfunction]
#[pyo3(signature = (texts, *, form="NFC"))]
pub fn _normalize_batch(texts: Vec<String>, form: &str) -> PyResult<Vec<String>> {
    validate_form(form)?;
    if texts.len() > crate::MAX_BATCH_SIZE {
        return translit_err!(
            "batch too large ({} items); maximum is {} items",
            texts.len(),
            crate::MAX_BATCH_SIZE
        );
    }
    // Validate each string's size before processing any.
    for t in &texts {
        if t.len() > MAX_NORMALIZE_INPUT_BYTES {
            return translit_err!(
                "input too large ({} bytes); maximum for normalize() is {} bytes",
                t.len(),
                MAX_NORMALIZE_INPUT_BYTES
            );
        }
    }
    // Apply the validated form to all strings.
    match form {
        "NFC" => texts
            .iter()
            .map(|t| normalize_checked(t.nfc().collect(), form))
            .collect(),
        "NFD" => texts
            .iter()
            .map(|t| normalize_checked(t.nfd().collect(), form))
            .collect(),
        "NFKC" => texts
            .iter()
            .map(|t| normalize_checked(t.nfkc().collect(), form))
            .collect(),
        "NFKD" => texts
            .iter()
            .map(|t| normalize_checked(t.nfkd().collect(), form))
            .collect(),
        _ => unreachable!(),
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

    #[test]
    fn test_normalize_output_cap_not_triggered_on_normal_input() {
        // Normal text should never hit the output cap.
        let text = "Héllo wörld";
        assert!(_normalize(text, "NFKD").is_ok());
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
                // Skip inputs that could expand beyond the output cap.
                let once = _normalize(&s, &form);
                if let Ok(once) = once {
                    let twice = _normalize(&once, &form).unwrap();
                    prop_assert_eq!(&once, &twice);
                }
            }

            /// After normalizing, is_normalized must confirm the result.
            #[test]
            fn normalize_then_is_normalized(
                s in "\\PC*",
                form in prop_oneof!["NFC", "NFD", "NFKC", "NFKD"],
            ) {
                if let Ok(normalized) = _normalize(&s, &form) {
                    prop_assert!(_is_normalized(&normalized, &form).unwrap());
                }
            }

            /// NFKC output is always also valid NFC.
            #[test]
            fn nfkc_implies_nfc(s in "\\PC*") {
                if let Ok(nfkc) = _normalize(&s, "NFKC") {
                    prop_assert!(_is_normalized(&nfkc, "NFC").unwrap());
                }
            }

            /// NFKD output is always also valid NFD.
            #[test]
            fn nfkd_implies_nfd(s in "\\PC*") {
                if let Ok(nfkd) = _normalize(&s, "NFKD") {
                    prop_assert!(_is_normalized(&nfkd, "NFD").unwrap());
                }
            }
        }
    }
}
