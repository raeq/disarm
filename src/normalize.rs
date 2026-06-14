//! Layer 1 (pure-Rust core): Unicode normalization (NFC/NFD/NFKC/NFKD). No pyo3.
//!
//! Shims in `src/py/normalize.rs`; crates.io surface is
//! `crate::api::{normalize, is_normalized}` (typed `NormalizationForm`).

use unicode_normalization::UnicodeNormalization;

// disarm does not cap input or output size — bounding untrusted input is the
// caller's responsibility (normalization is linear time/memory; see #80).

/// Validate normalization form string. Returns an error for invalid forms.
#[inline]
pub(crate) fn validate_form(form: &str) -> Result<(), crate::Error> {
    if !matches!(form, "NFC" | "NFD" | "NFKC" | "NFKD") {
        return Err(crate::Error::InvalidNormForm {
            got: form.to_owned(),
        });
    }
    Ok(())
}

/// Unicode normalization (NFC, NFD, NFKC, NFKD). Validates `form`.
pub(crate) fn normalize(text: &str, form: &str) -> Result<String, crate::Error> {
    let mut out = String::new();
    normalize_into(text, form, &mut out)?;
    Ok(out)
}

/// In-place form of [`normalize`] writing into `out` (cleared first), so the
/// pipeline can reuse one buffer across steps (#236 item 7).
pub(crate) fn normalize_into(text: &str, form: &str, out: &mut String) -> Result<(), crate::Error> {
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
pub(crate) fn is_normalized(text: &str, form: &str) -> Result<bool, crate::Error> {
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_nfc_roundtrip() {
        let text = "caf\u{0065}\u{0301}"; // e + combining accent
        let normalized = normalize(text, "NFC").unwrap();
        assert_eq!(normalized, "caf\u{00e9}"); // single é
    }

    #[test]
    fn test_normalize_accepts_input_without_size_cap() {
        // There is no input/output size cap (#80); normal and large inputs alike
        // normalize without error.
        assert!(normalize("Héllo wörld", "NFKD").is_ok());
        let large = "é".repeat(2 * 1024 * 1024); // ~4 MiB, formerly cap-relevant
        assert!(normalize(&large, "NFKD").is_ok());
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
                let once = normalize(&s, &form);
                if let Ok(once) = once {
                    let twice = normalize(&once, &form).unwrap();
                    prop_assert_eq!(&once, &twice);
                }
            }

            /// After normalizing, is_normalized must confirm the result.
            #[test]
            fn normalize_then_is_normalized(
                s in "\\PC*",
                form in prop_oneof!["NFC", "NFD", "NFKC", "NFKD"],
            ) {
                if let Ok(normalized) = normalize(&s, &form) {
                    prop_assert!(is_normalized(&normalized, &form).unwrap());
                }
            }

            /// NFKC output is always also valid NFC.
            #[test]
            fn nfkc_implies_nfc(s in "\\PC*") {
                if let Ok(nfkc) = normalize(&s, "NFKC") {
                    prop_assert!(is_normalized(&nfkc, "NFC").unwrap());
                }
            }

            /// NFKD output is always also valid NFD.
            #[test]
            fn nfkd_implies_nfd(s in "\\PC*") {
                if let Ok(nfkd) = normalize(&s, "NFKD") {
                    prop_assert!(is_normalized(&nfkd, "NFD").unwrap());
                }
            }
        }
    }
}
