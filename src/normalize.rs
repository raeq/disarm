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
// input-size check cannot foresee, so the preset runners refuse a step that leaves the text
// more than `MAX_NORMALIZE_OUTPUT_BYTES` longer than the preset's input (#768,
// `presets::check_growth`). This comment claimed there was no cap until #768; the cap sat
// on the `Nfkc` arm alone until the Lean model in `formal/lean/Presets` found the steps
// after it growing unchecked.

// `UNICODE_VERSION`: the UCD release `unicode-normalization` implements. Emitted by
// build.rs from the crate's own const, so it cannot drift from the tables it names — the
// same discipline `CONFUSABLES_VERSION` uses. The doc comment lives on the generated item
// (a doc comment cannot attach to an `include!`). Re-exported as
// `crate::api::UNICODE_VERSION` (#642, #645).
include!(concat!(env!("OUT_DIR"), "/unicode_version.rs"));

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
    let form = match form {
        "NFC" => Form::Nfc,
        "NFD" => Form::Nfd,
        "NFKC" => Form::Nfkc,
        "NFKD" => Form::Nfkd,
        _ => unreachable!("validate_form guarantees a known normalization form"),
    };
    normalize_segmented(text, form, out);
    Ok(())
}

#[derive(Clone, Copy)]
enum Form {
    Nfc,
    Nfd,
    Nfkc,
    Nfkd,
}

// `NFC_BOUNDARY`, `NFD_BOUNDARY`, `NFKC_BOUNDARY`, `NFKD_BOUNDARY`: one bit per BMP code
// point, set where `is_boundary_lookup` is true (codegen/norm_boundary.rs).
include!(concat!(env!("OUT_DIR"), "/norm_boundary.rs"));

/// Whether a normalization boundary sits before `c` (see [`is_boundary_lookup`]).
///
/// A bit test for the BMP, generated at build time from the same rule; the two table
/// lookups the rule costs made the check dearer than normalizing on scripts where almost
/// every character is non-ASCII and unchanged (`search_key` on Cyrillic, +10%).
#[inline]
fn is_boundary(c: char, form: Form) -> bool {
    let cp = u32::from(c);
    if cp > 0xFFFF {
        return is_boundary_lookup(c, form);
    }
    let table = match form {
        Form::Nfc => &NFC_BOUNDARY,
        Form::Nfd => &NFD_BOUNDARY,
        Form::Nfkc => &NFKC_BOUNDARY,
        Form::Nfkd => &NFKD_BOUNDARY,
    };
    table[(cp >> 6) as usize] >> (cp & 63) & 1 == 1
}

/// Whether a normalization boundary sits before `c`: a starter that passes `form`'s quick
/// check.
///
/// Quick check Yes means `c` is already in `form` and, for the composing forms, never
/// composes with what precedes it (a character that can is `Maybe`). Combining class 0
/// means canonical reordering cannot move a mark across it. So the text before `c`
/// normalizes the same whether or not anything follows it, and `c` itself is left as it
/// is: normalizing the pieces between boundaries and concatenating them is normalizing
/// the whole. `tests/normalize_segmented.rs` holds the two equal.
fn is_boundary_lookup(c: char, form: Form) -> bool {
    use unicode_normalization::{
        char::canonical_combining_class, is_nfc_quick, is_nfd_quick, is_nfkc_quick, is_nfkd_quick,
        IsNormalized,
    };
    if canonical_combining_class(c) != 0 {
        return false;
    }
    let one = std::iter::once(c);
    let quick = match form {
        Form::Nfc => is_nfc_quick(one),
        Form::Nfd => is_nfd_quick(one),
        Form::Nfkc => is_nfkc_quick(one),
        Form::Nfkd => is_nfkd_quick(one),
    };
    quick == IsNormalized::Yes
}

fn append_normalized(segment: &str, form: Form, out: &mut String) {
    match form {
        Form::Nfc => out.extend(segment.nfc()),
        Form::Nfd => out.extend(segment.nfd()),
        Form::Nfkc => out.extend(segment.nfkc()),
        Form::Nfkd => out.extend(segment.nfkd()),
    }
}

/// Normalize `text` into `out`, running the normalizer only over the segments that need
/// it and copying everything else.
///
/// The full-string iterator decomposed and recomposed every character, although in
/// ordinary text almost every one is a boundary that normalization leaves alone: mixed
/// web text changes at a quote, an ellipsis or a trademark sign. A segment runs from one
/// boundary to the next; a segment holding only its boundary is copied, any other is
/// normalized on its own. ASCII bytes are boundaries in every form and are never decoded.
fn normalize_segmented(text: &str, form: Form, out: &mut String) {
    let bytes = text.as_bytes();
    out.reserve(text.len());
    let mut copied = 0; // text[..copied] is in `out`
    let mut segment = 0; // start of the segment being read: a boundary, or 0
    let mut dirty = false; // text[segment..i] needs the normalizer
    let mut i = 0;
    while i < bytes.len() {
        let (boundary, len) = if bytes[i] < 0x80 {
            (true, 1)
        } else {
            let c = text[i..].chars().next().expect("`i` is a char boundary");
            (is_boundary(c, form), c.len_utf8())
        };
        if boundary {
            if dirty {
                out.push_str(&text[copied..segment]);
                append_normalized(&text[segment..i], form, out);
                copied = i;
                dirty = false;
            }
            segment = i;
        } else {
            dirty = true;
        }
        i += len;
    }
    if dirty {
        out.push_str(&text[copied..segment]);
        append_normalized(&text[segment..], form, out);
    } else {
        out.push_str(&text[copied..]);
    }
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
/// - Not a size bound on the presets. `MAX_NORMALIZE_OUTPUT_BYTES` (#768) bounds how far
///   a preset may grow its input, and it already applies.
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

    /// The build-time bitmaps say what the rule says, for every BMP scalar and form. This
    /// is also what catches a build-dependency copy of `unicode-normalization` that
    /// disagrees with the runtime one.
    #[test]
    fn boundary_bitmaps_match_the_lookup() {
        for form in [Form::Nfc, Form::Nfd, Form::Nfkc, Form::Nfkd] {
            for c in (0u32..0x1_0000).filter_map(char::from_u32) {
                assert_eq!(
                    is_boundary(c, form),
                    is_boundary_lookup(c, form),
                    "U+{:04X}",
                    u32::from(c)
                );
            }
        }
    }

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
