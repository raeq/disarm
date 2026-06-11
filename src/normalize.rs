use pyo3::prelude::*;
use unicode_normalization::UnicodeNormalization;

// disarm does not cap input or output size — bounding untrusted input is the
// caller's responsibility (normalization is linear time/memory; see #80).

/// Validate normalization form string. Returns an error for invalid forms.
#[inline]
fn validate_form(form: &str) -> Result<(), crate::Error> {
    if !matches!(form, "NFC" | "NFD" | "NFKC" | "NFKD") {
        return Err(crate::Error::InvalidNormForm {
            got: form.to_owned(),
        });
    }
    Ok(())
}

/// Unicode normalization (NFC, NFD, NFKC, NFKD).
#[pyfunction]
#[pyo3(signature = (text, *, form="NFC"))]
pub fn _normalize(text: &str, form: &str) -> PyResult<String> {
    let mut out = String::new();
    normalize_into(text, form, &mut out)?;
    Ok(out)
}

/// In-place form of [`_normalize`] writing into `out` (cleared first), so the
/// pipeline can reuse one buffer across steps (#236 item 7).
pub fn normalize_into(text: &str, form: &str, out: &mut String) -> PyResult<()> {
    validate_form(form)?;
    out.clear();
    // ASCII is invariant under all four normalization forms (no decomposition,
    // no composition), so skip the normalizer for pure-ASCII input. This fast
    // path moved down from the Python wrapper (#185) so that `form` is still
    // validated above on every call — the wrapper's version sat *before* its own
    // validation and would have accepted a typo'd form on ASCII input.
    if text.is_ascii() {
        out.push_str(text);
        return Ok(());
    }
    match form {
        "NFC" => out.extend(text.nfc()),
        "NFD" => out.extend(text.nfd()),
        "NFKC" => out.extend(text.nfkc()),
        "NFKD" => out.extend(text.nfkd()),
        _ => unreachable!(),
    }
    Ok(())
}

/// Check if text is already in the specified normalization form.
///
/// Uses the `unicode-normalization` quick-check first.  If the quick-check
/// returns `false` we fall back to a full normalize-and-compare, because the
/// crate's quick-check tables can be stricter than the normalizer itself for
/// certain unassigned codepoints (e.g. U+1CCD6 in Unicode 15/16 gaps).
#[pyfunction]
#[pyo3(signature = (text, *, form="NFC"))]
pub fn _is_normalized(text: &str, form: &str) -> PyResult<bool> {
    validate_form(form)?;
    let quick = match form {
        "NFC" => unicode_normalization::is_nfc(text),
        "NFD" => unicode_normalization::is_nfd(text),
        "NFKC" => unicode_normalization::is_nfkc(text),
        "NFKD" => unicode_normalization::is_nfkd(text),
        _ => unreachable!(),
    };
    if quick {
        return Ok(true);
    }
    // Quick-check said no — verify with a full normalization pass.
    // If normalizing produces the same bytes, the text is already normalized
    // and the quick-check gave a false negative (Unicode version gap).
    let normalized: String = match form {
        "NFC" => text.nfc().collect(),
        "NFD" => text.nfd().collect(),
        "NFKC" => text.nfkc().collect(),
        "NFKD" => text.nfkd().collect(),
        _ => unreachable!(),
    };
    Ok(normalized == text)
}

/// Batch normalization: process a list of strings in a single PyO3 boundary crossing.
#[pyfunction]
#[pyo3(signature = (texts, *, form="NFC"))]
pub fn _normalize_batch(py: Python<'_>, texts: Vec<String>, form: &str) -> PyResult<Vec<String>> {
    validate_form(form)?;
    if texts.len() > crate::MAX_BATCH_SIZE {
        return Err(crate::Error::BatchTooLarge {
            len: texts.len(),
            max: crate::MAX_BATCH_SIZE,
        }
        .into());
    }
    // Pick the normalizer once (form is validated), then run the pure-Rust loop
    // with the GIL released (#70): the closure touches no Python objects, so
    // other Python threads run in parallel during a large batch.
    let normalize_one: fn(&str) -> String = match form {
        "NFC" => |t| t.nfc().collect(),
        "NFD" => |t| t.nfd().collect(),
        "NFKC" => |t| t.nfkc().collect(),
        "NFKD" => |t| t.nfkd().collect(),
        _ => unreachable!(),
    };
    Ok(py.allow_threads(move || texts.iter().map(|t| normalize_one(t)).collect()))
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
    fn test_normalize_accepts_input_without_size_cap() {
        // There is no input/output size cap (#80); normal and large inputs alike
        // normalize without error.
        assert!(_normalize("Héllo wörld", "NFKD").is_ok());
        let large = "é".repeat(2 * 1024 * 1024); // ~4 MiB, formerly cap-relevant
        assert!(_normalize(&large, "NFKD").is_ok());
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
