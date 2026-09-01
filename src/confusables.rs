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

/// Validate the `digit_policy` parameter (#561).
///
/// `"numeric"` (default) keeps disarm's reading: a non-Latin digit folds to the ASCII
/// digit, so a number in running prose stays a number. `"tr39"` selects upstream's, which
/// folds most of them to a Latin letter (Devanagari zero → `o`) — correct for an
/// identifier skeleton, where the only job is to make two confusable identifiers collide.
/// Three of the 45 divergent rows do not land on a letter: `٠` and `۰` fold to `.`, and
/// `𑣣` folds to the two characters `rn`. A skeleton feeding a label- or path-shaped key
/// has to allow for that extra `.`.
/// Safety bound on the confusables fixed-point loop, shared by the owned and borrowing
/// forms. Far above the observed maximum; the `debug_assert` on the way out catches any
/// future table change that regresses convergence.
const MAX_CONFUSABLE_PASSES: usize = 8;

fn validate_digit_policy(digit_policy: &str) -> Result<(), crate::ErrorRepr> {
    match digit_policy {
        "numeric" | "tr39" | "preserve" => Ok(()),
        _ => Err(crate::ErrorRepr::InvalidDigitPolicy {
            got: digit_policy.to_owned(),
        }),
    }
}

/// Resolve one character under the chosen digit policy (#561).
///
/// `tr39_digits` is `digit_policy == "tr39" && target_script == "latin"`: the override set
/// is generated from the **Latin** table and its values are TR39's Latin targets, so it is
/// meaningless — and actively wrong — for any other target. Consulting it under
/// `target_script = "cyrillic"` would emit a Latin letter into a Cyrillic skeleton, and
/// would invent folds for sources the Cyrillic table deliberately has no row for.
///
/// The override map is consulted only when that flag is set. The numeric path therefore
/// costs one predictable, loop-invariant `bool` test per lookup and never touches the
/// override map — not literally free, but the branch predicts perfectly and the map probe
/// (the part that would actually cost something) is skipped entirely. Splitting the fold
/// into two loops to remove the test was considered and rejected: it duplicates the
/// borrow-on-no-op logic for a branch that is already free in practice.
///
/// `preserve_digits` is the third policy (#648) and needs no table of its own. "The digit
/// rows" are exactly the rows whose target is one ASCII digit, which the bundled map
/// already states, so the set is read off the live table instead of duplicated beside it
/// — and therefore cannot drift from it. The two tables disagree about which sources
/// those are (157 rows in the Latin map, 66 in the Cyrillic, neither a subset of the
/// other), so a separate file would have had to be per-target as well.
#[inline]
fn lookup_with_policy(
    map: Option<&'static phf::Map<char, &'static str>>,
    ch: char,
    tr39_digits: bool,
    preserve_digits: bool,
) -> Option<&'static str> {
    if tr39_digits {
        if let Some(over) = crate::tables::confusable_digit_tr39_override(ch) {
            return Some(over);
        }
    }
    let hit = map.and_then(|m| m.get(&ch).copied())?;
    if preserve_digits && hit.len() == 1 && hit.as_bytes()[0].is_ascii_digit() {
        return None;
    }
    Some(hit)
}

/// Validate the `target_script` parameter.
///
/// Supported values: `"latin"`, `"cyrillic"`.
fn validate_target_script(target_script: &str) -> Result<(), crate::ErrorRepr> {
    match target_script {
        "latin" | "cyrillic" | "arabic" | "hebrew" => Ok(()),
        _ => Err(crate::ErrorRepr::InvalidTargetScript {
            got: target_script.to_owned(),
        }),
    }
}

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
/// Compose-at-lookup applies only **canonical** composition, never **NFKC**
/// (compatibility) mappings. NFKC must not be added: ~31 codepoints in the TR39
/// confusables table conflict with NFKC mappings (e.g. ſ U+017F: TR39→f but NFKC→s).
/// Canonical composition is safe because it never applies a compatibility mapping. If
/// NFKC is ever needed, `gen_confusables.py` must filter entries where the TR39 target
/// differs from `unicodedata.normalize('NFKC', chr(cp))`.
/// See: <https://paultendo.github.io/posts/unicode-confusables-nfkc-conflict/>
///
/// # Valid `target_script` values
/// `"latin"` or `"cyrillic"`. Any other value returns [`crate::ErrorRepr`].
pub(crate) fn normalize_confusables(
    text: &str,
    target_script: &str,
    digit_policy: &str,
) -> Result<String, crate::ErrorRepr> {
    // Owned wrapper over the borrowing fixed-point form, which is where the loop and its
    // rationale live. `_fixed_cow` borrows on a no-op (#352), so pure-ASCII or
    // already-folded input never allocates a rebuilt string — only this final owned
    // conversion copies a borrow.
    Ok(normalize_confusables_fixed_cow(text, target_script, digit_policy)?.into_owned())
}

/// Borrowing form of [`normalize_confusables`] (#352): returns `Cow::Borrowed`
/// when `text` contains no confusable for the target (the common case), so a
/// no-op never allocates. A single pass — it only starts building an owned
/// string at the first character that actually folds.
pub(crate) fn normalize_confusables_cow<'a>(
    text: &'a str,
    target_script: &str,
    digit_policy: &str,
) -> Result<std::borrow::Cow<'a, str>, crate::ErrorRepr> {
    use std::borrow::Cow;

    validate_target_script(target_script)?;
    validate_digit_policy(digit_policy)?;
    let map = tables::resolve_confusable_map(target_script);
    // Resolved once, not per character: the default path must not pay for the option.
    // Latin-only: the override set carries TR39's *Latin* targets, so it must never be
    // consulted for another target script (see `lookup_with_policy`).
    let tr39_digits = digit_policy == "tr39" && target_script == "latin";
    // Unlike `tr39`, this is target-agnostic: it declines to fold a digit at all, so
    // there is no Latin-target restriction to honour.
    let preserve_digits = digit_policy == "preserve";

    // #475/#477: a base + combining-mark cluster (or a conjoining Hangul jamo run, #483)
    // must fold as its precomposed form. Compose-at-lookup can only change something when
    // such input is present, so gate on that: it is folded into an owned buffer, while
    // input with neither (the common case — ASCII, CJK, precomposed letters) falls
    // through to the single-pass borrow-on-no-op path, which never allocates on a no-op.
    // ASCII can carry neither a combining mark nor a conjoining jamo, so skip the
    // `needs_composition` char-decode scan on it entirely (M-3) — `is_ascii` is a cheap
    // byte scan that short-circuits on the first non-ASCII byte, so non-ASCII pays ~nothing
    // extra, but pure-ASCII input no longer runs a second full trie-lookup pass.
    if !text.is_ascii() && crate::compose::needs_composition(text) {
        let mut out = String::with_capacity(text.len());
        for (ch, _) in crate::compose::composed(text) {
            match lookup_with_policy(map, ch, tr39_digits, preserve_digits) {
                Some(replacement) => out.push_str(replacement),
                None => out.push(ch),
            }
        }
        return Ok(Cow::Owned(out));
    }

    for (i, ch) in text.char_indices() {
        if let Some(replacement) = lookup_with_policy(map, ch, tr39_digits, preserve_digits) {
            // First fold found: copy the borrowed prefix, then fold the rest.
            let mut out = String::with_capacity(text.len());
            out.push_str(&text[..i]);
            out.push_str(replacement);
            for ch in text[i + ch.len_utf8()..].chars() {
                match lookup_with_policy(map, ch, tr39_digits, preserve_digits) {
                    Some(replacement) => out.push_str(replacement),
                    None => out.push(ch),
                }
            }
            return Ok(Cow::Owned(out));
        }
    }
    Ok(Cow::Borrowed(text))
}

/// [`normalize_confusables_cow`] iterated to a fixed point (#522) — the borrowing form
/// of [`normalize_confusables`], and the one every public surface must call.
///
/// Confusable folding and canonical composition expose work for each other in *both*
/// directions, so one pass is not stable:
///   * a fold can expose a composition — `¥`+◌̀ folds to `Y`+◌̀, which composes to `Ỳ`;
///   * a composition can expose a *new* fold — `Ҫ`+◌̧ composes to `Ç`, itself a
///     confusable that folds to `C`.
///
/// Re-running `_cow` (which composes-at-lookup on its input each pass) until the output
/// stops changing makes the result idempotent by construction, and complete: the loop can
/// only exit once no char folds, i.e. `is_confusable` is false. That completeness is the
/// point — #586 was the Layer-2 API calling the single-pass form, so `normalize` returned
/// strings that `is_confusable` still flagged, and the five non-Python bindings all
/// inherited it.
///
/// It converges in a few passes: every fold moves toward the ASCII-ish target script and
/// composition only shrinks length, so no cycle is possible, and the exhaustive
/// (confusable × mark) idempotency test bounds the pass count.
///
/// Borrows on a no-op exactly as `_cow` does (#352): input with nothing to fold is
/// already a fixed point, so the common case still never allocates.
pub(crate) fn normalize_confusables_fixed_cow<'a>(
    text: &'a str,
    target_script: &str,
    digit_policy: &str,
) -> Result<std::borrow::Cow<'a, str>, crate::ErrorRepr> {
    let mut cur = match normalize_confusables_cow(text, target_script, digit_policy)? {
        // Borrowed ⇒ nothing folded ⇒ the input is already a fixed point (the common case).
        std::borrow::Cow::Borrowed(s) => return Ok(std::borrow::Cow::Borrowed(s)),
        std::borrow::Cow::Owned(s) => s,
    };
    for _ in 0..MAX_CONFUSABLE_PASSES {
        match normalize_confusables_cow(&cur, target_script, digit_policy)? {
            std::borrow::Cow::Borrowed(_) => return Ok(std::borrow::Cow::Owned(cur)),
            std::borrow::Cow::Owned(next) if next == cur => {
                return Ok(std::borrow::Cow::Owned(cur));
            }
            std::borrow::Cow::Owned(next) => cur = next,
        }
    }
    debug_assert!(
        false,
        "normalize_confusables did not converge in {MAX_CONFUSABLE_PASSES} passes: {cur:?}"
    );
    Ok(std::borrow::Cow::Owned(cur))
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

// ── Coverage introspection (#563) ────────────────────────────────────────────────
//
// `find_untranslatable` has existed for transliteration since #184; there was no
// confusables analogue, so the only way to ask "which sources go uncovered?" was to
// rebuild the capability outside the library against a cached copy of the upstream
// file. A defender needs the answer because that set is precisely where an adaptive
// attacker moves: a tool at 0.949 per-source coverage is not 95% safe, it is one query
// away from the other 5%.

/// Every upstream confusable source the bundled `target_script` table does not map,
/// sorted by codepoint.
///
/// # Valid `target_script` values
/// `"latin"` or `"cyrillic"`. Any other value returns [`crate::ErrorRepr`].
pub(crate) fn unmapped_confusables(target_script: &str) -> Result<Vec<char>, crate::ErrorRepr> {
    validate_target_script(target_script)?;
    Ok(tables::unmapped_confusable_sources(target_script))
}

/// Scan `text` for characters upstream marks as confusable that the bundled
/// `target_script` table does **not** fold, as `(char, byte_offset)` in order of
/// appearance — the confusables analogue of `find_untranslatable`.
///
/// Composes at lookup exactly as the fold does (#475/#477/#483), so a decomposed
/// homoglyph whose *precomposed* form is mapped is correctly reported as covered
/// rather than as a gap. Offsets are anchored in the caller's `text`, never in the
/// composed intermediate; a multi-mark cluster reports the cluster's start.
///
/// # Valid `target_script` values
/// `"latin"` or `"cyrillic"`. Any other value returns [`crate::ErrorRepr`].
pub(crate) fn find_unmapped_confusables(
    text: &str,
    target_script: &str,
) -> Result<Vec<(char, usize)>, crate::ErrorRepr> {
    validate_target_script(target_script)?;
    let map = tables::resolve_confusable_map(target_script);

    let mut out = Vec::new();
    // Always iterate through `composed`: it is identity on input with nothing to
    // compose, and going through one path keeps this scan and the fold in lockstep by
    // construction. A character is a gap iff the fold would leave it alone AND upstream
    // considers it confusable — the second half is what separates "disarm does not
    // touch this" from "disarm cannot neutralize this".
    for (ch, offset) in crate::compose::composed(text) {
        let mapped = map.is_some_and(|m| m.contains_key(&ch));
        if !mapped && tables::is_upstream_confusable_source(ch) {
            out.push((ch, offset));
        }
    }
    Ok(out)
}

/// Every **mapped** confusable in `text`, with its byte offset and its fold target (#737).
///
/// The mirror of [`find_unmapped_confusables`]: the two read the same table from opposite
/// sides. That one answers *"what would survive the fold?"* — exposure. This one answers
/// *"what did the fold change, and to what?"* — evidence.
///
/// `is_confusable` returns a bare `bool` and `normalize_confusables` returns the folded
/// string; neither says **where**. A caller that wants to highlight the impersonated
/// character, or log which one it was, had to diff the two strings and hope the fold was
/// length-preserving, which it is not (`ﬁ` -> `fi`).
///
/// Offsets are anchored in the caller's `text`, and iterate through `composed` for the
/// same reason the sibling does: one path keeps this scan and the fold in lockstep by
/// construction.
///
/// # Valid `target_script` values
/// `"latin"` or `"cyrillic"`. Any other value returns [`crate::ErrorRepr`].
pub(crate) fn find_confusables(
    text: &str,
    target_script: &str,
) -> Result<Vec<(char, usize, &'static str)>, crate::ErrorRepr> {
    validate_target_script(target_script)?;
    let map = tables::resolve_confusable_map(target_script);

    let mut out = Vec::new();
    for (ch, offset) in crate::compose::composed(text) {
        if let Some(target) = map.and_then(|m| m.get(&ch)) {
            out.push((ch, offset, *target));
        }
    }
    Ok(out)
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

    /// Tier-3 exhaustive gate for the fold/compose idempotency invariant (#522).
    ///
    /// The `\PC*` proptest below is a *random* walk, so the specific two-code-point
    /// adjacency that breaks idempotency — a confusable base immediately followed by a
    /// combining mark that composes with the *folded* base — is astronomically unlikely
    /// to be generated, and indeed slipped through 1000-case runs until one unlucky CI
    /// seed hit `¥\u{340}`. The bug class is *local* (base + mark), so it is bounded and
    /// deterministically enumerable: cross every confusable source code point with every
    /// combining mark and assert both invariants hold for every pair. This caught 61
    /// residual failures that the one-shot recompose missed. `#[ignore]` (Tier 3): ~9M
    /// pairs, a few seconds in release — too slow for per-PR CI, run pre-release.
    #[test]
    #[ignore = "exhaustive: ~9M (confusable × mark) pairs; run in Tier 3 / pre-release"]
    fn exhaustive_fold_compose_idempotent_and_complete() {
        use unicode_normalization::char::is_combining_mark;
        let marks: Vec<char> = (0u32..=0x0010_FFFF)
            .filter_map(char::from_u32)
            .filter(|&c| is_combining_mark(c))
            .collect();
        for script in ["latin", "cyrillic"] {
            let map = tables::resolve_confusable_map(script).unwrap();
            for &base in map.keys() {
                for &m in &marks {
                    let s: String = [base, m].iter().collect();
                    let once = normalize_confusables(&s, script, "numeric").unwrap();
                    let twice = normalize_confusables(&once, script, "numeric").unwrap();
                    assert_eq!(
                        once, twice,
                        "not idempotent: base U+{:04X} + mark U+{:04X} ({script})",
                        base as u32, m as u32
                    );
                    assert!(
                        !is_confusable(&once, script).unwrap(),
                        "residual confusable after normalize: base U+{:04X} + mark U+{:04X} ({script}) → {once:?}",
                        base as u32, m as u32
                    );
                }
            }
        }
    }
    use super::*;

    #[test]
    fn test_normalize_confusables_cyrillic() {
        // Cyrillic 'а' (U+0430) → Latin 'a'
        let result = normalize_confusables("\u{0430}", "latin", "numeric").unwrap();
        assert_eq!(result, "a");
    }

    #[test]
    fn test_normalize_confusables_passthrough() {
        let result = normalize_confusables("hello", "latin", "numeric").unwrap();
        assert_eq!(result, "hello");
    }

    #[test]
    fn test_normalize_confusables_empty() {
        let result = normalize_confusables("", "latin", "numeric").unwrap();
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
                normalize_confusables(&nfc, "latin", "numeric").unwrap(),
                normalize_confusables(&nfd, "latin", "numeric").unwrap(),
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
        assert_eq!(
            normalize_confusables("\u{0430}ll", "latin", "numeric").unwrap(),
            "all"
        );
        assert_eq!(
            normalize_confusables("hello", "latin", "numeric").unwrap(),
            "hello"
        );
    }

    #[test]
    fn composition_excluded_presentation_form_is_form_invariant() {
        // #477/#481: the input is never decomposed (the #478 regression class), so a bare
        // presentation form `שׂ` U+FB2B passes through unchanged. Its decomposition `ש`
        // U+05E9 + sin dot U+05C2 now *composes* to U+FB2B via the widening map (#481)
        // rather than staying split, so both forms agree on U+FB2B — form-invariant, and
        // neither is a Latin confusable, so both pass through to the same scalar.
        assert_eq!(
            normalize_confusables("\u{FB2B}", "latin", "numeric").unwrap(),
            "\u{FB2B}"
        );
        assert_eq!(
            normalize_confusables("\u{05E9}\u{05C2}", "latin", "numeric").unwrap(),
            "\u{FB2B}"
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
        let result = normalize_confusables(input, "latin", "numeric").unwrap();
        // Cyrillic е→e, о→o
        assert_eq!(result, "hello world");
    }

    #[test]
    fn test_normalize_confusables_nfc_vs_nfd() {
        // Confusable lookup operates on individual codepoints; NFC and NFD
        // should both work (combining marks aren't confusable targets).
        let nfc = "\u{00e9}"; // é as single codepoint
        let result = normalize_confusables(nfc, "latin", "numeric").unwrap();
        // é is not a confusable — it should pass through unchanged
        assert_eq!(result, nfc);
    }

    #[test]
    fn normalize_confusables_idempotent_when_fold_and_compose_interact() {
        // #522 regression, both interaction directions.
        //
        // (a) a fold exposes a composition. `¥` (U+00A5) folds to `Y`, carrying a combining
        //     grave (U+0340, which canonically decomposes to U+0300). The cluster composes
        //     to `¥`+U+0300 (yen has no precomposed grave); folding `¥`→`Y` leaves `Y`+U+0300,
        //     which composes to `Ỳ` (U+1EF2) — a non-confusable, so that is the fixed point.
        let once = normalize_confusables("\u{a5}\u{340}", "latin", "numeric").unwrap();
        assert_eq!(once, "\u{1ef2}"); // Ỳ
        assert_eq!(
            normalize_confusables(&once, "latin", "numeric").unwrap(),
            once
        );

        // (b) a composition exposes a *new* fold. `Ҫ` (U+04AA) folds to `C`, carrying a
        //     combining cedilla (U+0327); `C`+cedilla composes to `Ç` (U+00C7) — which is
        //     *itself* a confusable that folds to `C`. Only iterating to a fixed point
        //     reaches `C`; a single recompose would stop at the still-confusable `Ç`.
        let once = normalize_confusables("\u{04AA}\u{0327}", "latin", "numeric").unwrap();
        assert_eq!(once, "C");
        assert_eq!(
            normalize_confusables(&once, "latin", "numeric").unwrap(),
            once
        );
        assert!(!is_confusable(&once, "latin").unwrap());
    }

    #[test]
    fn confusable_table_values_are_non_empty() {
        // The fold never deletes content because every table value is non-empty — a
        // lookup always yields at least one output char. Asserted directly over the
        // tables (deterministic), replacing the former char-count proptest which no
        // longer holds once fold∘compose iterates to a fixed point (#522).
        for script in ["latin", "cyrillic"] {
            let map = tables::resolve_confusable_map(script).unwrap();
            for (&key, &value) in map.entries() {
                assert!(
                    !value.is_empty(),
                    "empty confusable mapping for U+{:04X} ({script})",
                    key as u32
                );
            }
        }
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
                let once = normalize_confusables(&s, "latin", "numeric").unwrap();
                let twice = normalize_confusables(&once, "latin", "numeric").unwrap();
                prop_assert_eq!(&once, &twice,
                    "normalize_confusables is not idempotent on: {:?}", s);
            }

            /// After normalizing confusables, is_confusable must return false.
            /// This is the completeness invariant: if the table is self-consistent,
            /// no confusable characters survive normalization.
            #[test]
            fn normalized_is_not_confusable(s in "\\PC*") {
                let normalized = normalize_confusables(&s, "latin", "numeric").unwrap();
                let still_confusable = is_confusable(&normalized, "latin").unwrap();
                prop_assert!(!still_confusable,
                    "is_confusable returned true after normalize_confusables on: {:?} → {:?}",
                    s, normalized);
            }

            /// The fold never *annihilates* content: non-empty input yields non-empty
            /// output. A stronger char-count guarantee (`result >= composed input`) no
            /// longer holds since #522 — iterating fold∘compose to a fixed point can
            /// legitimately shorten the string (`Ҫ`+◌̧ → `Ç` → `C`, the cedilla absorbed
            /// then discarded because completeness forces the confusable `Ç` to fold to
            /// `C`). The "no table value is empty" guarantee that underpinned the old
            /// count check is asserted directly and deterministically by
            /// [`confusable_table_values_are_non_empty`].
            #[test]
            fn fold_never_annihilates_content(s in "\\PC+") {
                let result = normalize_confusables(&s, "latin", "numeric").unwrap();
                prop_assert!(!result.is_empty(),
                    "non-empty input {:?} normalized to empty", s);
            }

            /// normalize_confusables output is always valid UTF-8 (trivially
            /// true since we return String, but this catches memory corruption).
            #[test]
            fn normalize_confusables_valid_utf8(s in "\\PC*") {
                let result = normalize_confusables(&s, "latin", "numeric").unwrap();
                // If this compiles and doesn't panic, the result is valid UTF-8.
                let _ = result.len(); // forces evaluation
            }
        }
    }
}
