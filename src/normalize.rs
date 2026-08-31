//! Layer 1 (pure-Rust core): Unicode normalization (NFC/NFD/NFKC/NFKD). No pyo3.
//!
//! Shims in `src/py/normalize.rs`; crates.io surface is
//! `crate::api::{normalize, is_normalized}` (typed `NormalizationForm`).

use unicode_normalization::UnicodeNormalization;

// disarm does not cap input size — bounding untrusted input is the caller's
// responsibility (normalization is linear time/memory; see #80). The functions in this
// module are unbounded in output too: `normalize(text, form)` is a caller naming the
// expansion they want.
//
// The preset path is not. NFKC widens `U+FDFA` by 18×, which is an amplification an
// input-size check cannot foresee, so the `Step::Nfkc` arm of `presets::apply_into` caps
// produced output at `MAX_NORMALIZE_OUTPUT_BYTES` (#768). This comment claimed otherwise
// until then.

/// Validate normalization form string. Returns an error for invalid forms.
#[inline]
pub(crate) fn validate_form(form: &str) -> Result<(), crate::ErrorRepr> {
    if !matches!(form, "NFC" | "NFD" | "NFKC" | "NFKD") {
        return Err(crate::ErrorRepr::InvalidNormForm {
            got: form.to_owned(),
        });
    }
    Ok(())
}

/// Unicode normalization (NFC, NFD, NFKC, NFKD). Validates `form`.
pub(crate) fn normalize(text: &str, form: &str) -> Result<String, crate::ErrorRepr> {
    let mut out = String::new();
    normalize_into(text, form, &mut out)?;
    Ok(out)
}

/// In-place form of [`normalize`] writing into `out` (cleared first), so the
/// pipeline can reuse one buffer across steps (#236 item 7).
pub(crate) fn normalize_into(
    text: &str,
    form: &str,
    out: &mut String,
) -> Result<(), crate::ErrorRepr> {
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
        _ => unreachable!("validate_form guarantees a known normalization form"),
    }
    Ok(())
}

/// Check if text is already in the specified normalization form.
///
/// Uses the `unicode-normalization` quick-check first.  If the quick-check
/// returns `false` we fall back to a full normalize-and-compare, because the
/// crate's quick-check tables can be stricter than the normalizer itself for
/// certain unassigned codepoints (e.g. U+1CCD6 in Unicode 15/16 gaps).
pub(crate) fn is_normalized(text: &str, form: &str) -> Result<bool, crate::ErrorRepr> {
    validate_form(form)?;
    let quick = match form {
        "NFC" => unicode_normalization::is_nfc(text),
        "NFD" => unicode_normalization::is_nfd(text),
        "NFKC" => unicode_normalization::is_nfkc(text),
        "NFKD" => unicode_normalization::is_nfkd(text),
        _ => unreachable!("validate_form guarantees a known normalization form"),
    };
    if quick {
        return Ok(true);
    }
    // Quick-check said no — verify with a full normalization pass. Compare the
    // normalizer's char stream against the input's element-wise (`Iterator::eq`)
    // rather than collecting a whole `String`: this allocates nothing and exits
    // on the first differing char (O6). Char-sequence equality is equivalent to
    // the former byte equality for valid UTF-8.
    let already_normalized = match form {
        "NFC" => text.nfc().eq(text.chars()),
        "NFD" => text.nfd().eq(text.chars()),
        "NFKC" => text.nfkc().eq(text.chars()),
        "NFKD" => text.nfkd().eq(text.chars()),
        _ => unreachable!("validate_form guarantees a known normalization form"),
    };
    Ok(already_normalized)
}

/// Apply the Unicode Stream-Safe Text Format (UAX #15).
///
/// Inserts `U+034F COMBINING GRAPHEME JOINER` to break any run of more than 30
/// non-starters, which is the bound the standard defines so an implementation can process
/// text in fixed-size buffers without a normalization boundary falling inside one.
///
/// This is an **interop** bound, and it is worth being plain about what it is not:
///
/// - Not canonically equivalent. It inserts a character, so `stream_safe(s) != s` and
///   `NFC(stream_safe(s)) != NFC(s)`. Never use it on a comparison key.
/// - Not a zalgo control. [`crate::zalgo`] answers that question, with a different bound
///   and a different purpose; 30 non-starters is far above anything a reader would call
///   stacking abuse.
/// - Not a size bound on the presets. `MAX_NORMALIZE_OUTPUT_BYTES` (#768) is that, and it
///   already applies.
pub(crate) fn stream_safe(text: &str) -> String {
    use unicode_normalization::UnicodeNormalization;
    text.chars().stream_safe().collect()
}

/// True if `text` is **both** in normalization form `form` **and** Stream-Safe.
///
/// The upstream predicate is a conjunction — its own doc says "is Stream-Safe NFC" — and
/// the name here says so rather than leaving a reader to discover it. A string can be
/// stream-safe and not normalized; this returns `false` for it.
///
/// `NFKC`/`NFKD` are answered by their canonical counterparts, since compatibility folding
/// does not change how long a non-starter run is.
pub(crate) fn is_normalized_stream_safe(text: &str, form: &str) -> Result<bool, crate::ErrorRepr> {
    match form {
        "NFC" | "NFKC" => Ok(unicode_normalization::is_nfc_stream_safe(text)),
        "NFD" | "NFKD" => Ok(unicode_normalization::is_nfd_stream_safe(text)),
        _ => Err(crate::ErrorRepr::InvalidNormForm {
            got: form.to_owned(),
        }),
    }
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
