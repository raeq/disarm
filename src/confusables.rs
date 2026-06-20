//! Layer 1 (pure-Rust core): TR39 confusable folding. No pyo3.
//!
//! The PyO3 shims for these functions live in `src/py/confusables.rs`; the
//! idiomatic crates.io surface is `crate::api::{normalize_confusables,
//! is_confusable}`. This module is the algorithm, returning the native
//! [`crate::ErrorRepr`] (never a `PyErr`).
//!
//! These fns are `pub(crate)` while [`crate::ErrorRepr`] is `pub(crate)` (avoiding a
//! private-in-public leak). They are promoted to `pub` together with the opaque
//! public `Error` in the first fallible-module extraction sub-PR (#38).

use crate::tables;

/// Validate the `target_script` parameter.
///
/// Supported values: `"latin"`, `"cyrillic"`.
fn validate_target_script(target_script: &str) -> Result<(), crate::ErrorRepr> {
    match target_script {
        "latin" | "cyrillic" => Ok(()),
        _ => Err(crate::ErrorRepr::InvalidTargetScript {
            got: target_script.to_owned(),
        }),
    }
}

/// Canonically recompose `text` to NFC (#475), borrowing when it is already NFC.
///
/// Replace Unicode confusable homoglyphs with target-script equivalents.
///
/// The public fold/detect entrypoints compose each base + combining-mark cluster at
/// lookup time (#475/#477, see [`crate::compose`]) so a *decomposed* homoglyph (`і`
/// U+0456 + combining diaeresis U+0308) reaches the bundled table's *precomposed*
/// entry (`ї` U+0457 → `i`) instead of mapping only the base and leaving the mark —
/// otherwise the recovery is evadable, and detection flips, by sending the decomposed
/// form. Compose-only (never decompose), so a composition-excluded presentation form
/// (`שׂ` U+FB2B) keeps its own table entry, and the result is invariant to the input's
/// normal form. The preset-internal `normalize_confusables_into` stays pure — the
/// presets canonicalize their own input upstream.
///
/// # NFKC interaction warning
/// This function applies **NFC** (canonical) but **not NFKC** (compatibility)
/// normalization. NFKC must not be added as a pre-processing step: ~31 codepoints in
/// the TR39 confusables table conflict with NFKC mappings (e.g. ſ U+017F: TR39→f but
/// NFKC→s). NFC is safe because it never applies a compatibility mapping. If NFKC is
/// ever needed, `gen_confusables.py` must filter entries where the TR39 target
/// differs from `unicodedata.normalize('NFKC', chr(cp))`.
/// See: <https://paultendo.github.io/posts/unicode-confusables-nfkc-conflict/>
///
/// # Valid `target_script` values
/// `"latin"` or `"cyrillic"`. Any other value returns [`crate::ErrorRepr`].
pub(crate) fn normalize_confusables(
    text: &str,
    target_script: &str,
) -> Result<String, crate::ErrorRepr> {
    validate_target_script(target_script)?;
    let map = tables::resolve_confusable_map(target_script);
    let mut out = String::with_capacity(text.len());
    for (ch, _) in crate::compose::composed(text) {
        match map.and_then(|m| m.get(&ch).copied()) {
            Some(replacement) => out.push_str(replacement),
            None => out.push(ch),
        }
    }
    Ok(out)
}

/// Borrowing form of [`normalize_confusables`] (#352): returns `Cow::Borrowed`
/// when `text` contains no confusable for the target (the common case), so a
/// no-op never allocates. A single pass — it only starts building an owned
/// string at the first character that actually folds.
pub(crate) fn normalize_confusables_cow<'a>(
    text: &'a str,
    target_script: &str,
) -> Result<std::borrow::Cow<'a, str>, crate::ErrorRepr> {
    use std::borrow::Cow;

    validate_target_script(target_script)?;
    let map = tables::resolve_confusable_map(target_script);

    // #475/#477: a base + combining-mark cluster must fold as its precomposed form.
    // Compose-at-lookup can only change something when a combining mark is present, so
    // gate on that: mark-bearing input is folded into an owned buffer, while mark-free
    // input (the common case — ASCII, CJK, precomposed letters) falls through to the
    // single-pass borrow-on-no-op path, which never allocates on a no-op.
    if crate::compose::has_combining_mark(text) {
        let mut out = String::with_capacity(text.len());
        for (ch, _) in crate::compose::composed(text) {
            match map.and_then(|m| m.get(&ch).copied()) {
                Some(replacement) => out.push_str(replacement),
                None => out.push(ch),
            }
        }
        return Ok(Cow::Owned(out));
    }

    for (i, ch) in text.char_indices() {
        if let Some(replacement) = map.and_then(|m| m.get(&ch).copied()) {
            // First fold found: copy the borrowed prefix, then fold the rest.
            let mut out = String::with_capacity(text.len());
            out.push_str(&text[..i]);
            out.push_str(replacement);
            for ch in text[i + ch.len_utf8()..].chars() {
                match map.and_then(|m| m.get(&ch).copied()) {
                    Some(replacement) => out.push_str(replacement),
                    None => out.push(ch),
                }
            }
            return Ok(Cow::Owned(out));
        }
    }
    Ok(Cow::Borrowed(text))
}

/// In-place form of [`normalize_confusables`] writing into `out` (cleared
/// first), so the pipeline can reuse one buffer across steps (#236 item 7).
pub(crate) fn normalize_confusables_into(
    text: &str,
    target_script: &str,
    out: &mut String,
) -> Result<(), crate::ErrorRepr> {
    validate_target_script(target_script)?;
    out.clear();
    out.reserve(text.len());

    // Resolve the confusables map once (#236 / #233 review item) instead of
    // re-dispatching `target_script` for every character. `validate_target_script`
    // above guarantees `Some`. There is deliberately no ASCII fast path: the
    // latin table maps ASCII source code points (U+007C `|`→`l`, U+0022 `"`→`''`,
    // U+0060 `` ` ``→`'`), so ASCII input is not identity even for `target="latin"`.
    let map = tables::resolve_confusable_map(target_script);

    for ch in text.chars() {
        match map.and_then(|m| m.get(&ch).copied()) {
            Some(replacement) => out.push_str(replacement),
            None => out.push(ch),
        }
    }

    Ok(())
}

/// True if text contains any characters confusable with target-script characters.
///
/// # Valid `target_script` values
/// `"latin"` or `"cyrillic"`. Any other value returns [`crate::ErrorRepr`].
pub(crate) fn is_confusable(text: &str, target_script: &str) -> Result<bool, crate::ErrorRepr> {
    validate_target_script(target_script)?;

    // #475/#477: detect on the compose-at-lookup form so a decomposed homoglyph can't
    // evade detection (a composed `ç` is confusable; its decomposed `c`+cedilla
    // otherwise is not). See [`crate::compose`].
    let map = tables::resolve_confusable_map(target_script);
    for (ch, _) in crate::compose::composed(text) {
        if map.is_some_and(|m| m.contains_key(&ch)) {
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
        let result = normalize_confusables("\u{0430}", "latin").unwrap();
        assert_eq!(result, "a");
    }

    #[test]
    fn test_normalize_confusables_passthrough() {
        let result = normalize_confusables("hello", "latin").unwrap();
        assert_eq!(result, "hello");
    }

    #[test]
    fn test_normalize_confusables_empty() {
        let result = normalize_confusables("", "latin").unwrap();
        assert_eq!(result, "");
    }

    #[test]
    fn test_is_confusable_true() {
        // Cyrillic 'а' is confusable with Latin 'a'
        assert!(is_confusable("\u{0430}", "latin").unwrap());
    }

    #[test]
    fn test_is_confusable_false() {
        assert!(!is_confusable("hello", "latin").unwrap());
    }

    #[test]
    fn test_is_confusable_empty() {
        assert!(!is_confusable("", "latin").unwrap());
    }

    #[test]
    fn fold_and_detect_are_form_invariant() {
        // #475/#477: compose-at-lookup, so a decomposed homoglyph folds/detects the
        // same as its precomposed form. `ї` (U+0457) → "i"; NFD is `і` + U+0308.
        use unicode_normalization::UnicodeNormalization;
        for ch in ['\u{0457}', '\u{00E7}', '\u{03AF}', '\u{0625}'] {
            let nfc: String = std::iter::once(ch).collect();
            let nfd: String = std::iter::once(ch).nfd().collect();
            assert_ne!(nfc, nfd, "{ch:?} must actually decompose for this test");
            assert_eq!(
                normalize_confusables(&nfc, "latin").unwrap(),
                normalize_confusables(&nfd, "latin").unwrap(),
                "fold not form-invariant on {ch:?}"
            );
            assert_eq!(
                is_confusable(&nfc, "latin").unwrap(),
                is_confusable(&nfd, "latin").unwrap(),
                "detection not form-invariant on {ch:?}"
            );
        }
    }

    #[test]
    fn nfc_form_preserves_existing_output() {
        // Already-NFC / ASCII input is unchanged by compose-at-lookup (mark-free gate).
        assert_eq!(normalize_confusables("\u{0430}ll", "latin").unwrap(), "all");
        assert_eq!(normalize_confusables("hello", "latin").unwrap(), "hello");
    }

    #[test]
    fn composition_excluded_presentation_form_is_untouched() {
        // #477: compose-only must never *decompose*. The Hebrew presentation form `שׂ`
        // (U+FB2B) is composition-excluded; an NFC-first fix would decompose it and
        // change its output. Compose-at-lookup leaves a lone starter alone, and leaves
        // an excluded base+mark pair (`ש` U+05E9 + sin dot U+05C2) decomposed — neither
        // is a Latin confusable, so both pass through unchanged, and the two forms agree.
        assert_eq!(
            normalize_confusables("\u{FB2B}", "latin").unwrap(),
            "\u{FB2B}"
        );
        assert_eq!(
            normalize_confusables("\u{05E9}\u{05C2}", "latin").unwrap(),
            "\u{05E9}\u{05C2}"
        );
    }

    #[test]
    fn test_validate_target_script_latin_ok() {
        assert!(validate_target_script("latin").is_ok());
    }

    #[test]
    fn test_validate_target_script_cyrillic_ok() {
        assert!(validate_target_script("cyrillic").is_ok());
    }

    #[test]
    fn test_validate_target_script_invalid() {
        assert!(validate_target_script("greek").is_err());
        assert!(validate_target_script("").is_err());
        assert!(validate_target_script("Latin").is_err()); // case-sensitive
        assert!(validate_target_script("Cyrillic").is_err()); // case-sensitive
    }

    #[test]
    fn test_normalize_confusables_mixed_long() {
        // String with confusable Cyrillic chars interspersed with ASCII
        let input = "h\u{0435}ll\u{043E} w\u{043E}rld"; // Cyrillic е and о
        let result = normalize_confusables(input, "latin").unwrap();
        // Cyrillic е→e, о→o
        assert_eq!(result, "hello world");
    }

    #[test]
    fn test_normalize_confusables_nfc_vs_nfd() {
        // Confusable lookup operates on individual codepoints; NFC and NFD
        // should both work (combining marks aren't confusable targets).
        let nfc = "\u{00e9}"; // é as single codepoint
        let result = normalize_confusables(nfc, "latin").unwrap();
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
                let once = normalize_confusables(&s, "latin").unwrap();
                let twice = normalize_confusables(&once, "latin").unwrap();
                prop_assert_eq!(&once, &twice,
                    "normalize_confusables is not idempotent on: {:?}", s);
            }

            /// After normalizing confusables, is_confusable must return false.
            /// This is the completeness invariant: if the table is self-consistent,
            /// no confusable characters survive normalization.
            #[test]
            fn normalized_is_not_confusable(s in "\\PC*") {
                let normalized = normalize_confusables(&s, "latin").unwrap();
                let still_confusable = is_confusable(&normalized, "latin").unwrap();
                prop_assert!(!still_confusable,
                    "is_confusable returned true after normalize_confusables on: {:?} → {:?}",
                    s, normalized);
            }

            /// The *fold* never drops characters — every table value is non-empty, so
            /// each looked-up code point yields at least one output char. The count is
            /// measured against the compose-at-lookup stream, not the raw input:
            /// composing a base + combining-mark cluster (`і`+◌̈ → `ї`, #475/#477)
            /// legitimately reduces the count by one grapheme before the fold, which is
            /// exactly the form-invariant behaviour the dedicated tests assert. What
            /// must never happen is the *fold* deleting content.
            #[test]
            fn fold_never_drops_chars(s in "\\PC*") {
                let result = normalize_confusables(&s, "latin").unwrap();
                let composed = crate::compose::composed(&s).count();
                prop_assert!(
                    result.chars().count() >= composed,
                    "fold dropped chars: {:?} ({} composed) → {:?} ({} chars)",
                    s, composed, result, result.chars().count()
                );
            }

            /// normalize_confusables output is always valid UTF-8 (trivially
            /// true since we return String, but this catches memory corruption).
            #[test]
            fn normalize_confusables_valid_utf8(s in "\\PC*") {
                let result = normalize_confusables(&s, "latin").unwrap();
                // If this compiles and doesn't panic, the result is valid UTF-8.
                let _ = result.len(); // forces evaluation
            }
        }
    }
}
