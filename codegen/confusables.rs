//! Build-time checks and fixes for the confusable fold tables: which non-ASCII
//! targets the Latin table may hold, and the canonical-singleton rows (#481, #831).

use std::collections::BTreeMap;
use std::path::Path;

use super::readers::read_str_str_tsv;

/// Non-ASCII targets that are not Latin letters and are allowed anyway.
///
/// `Script=Common` characters belong to no script, so the "stay inside the script this
/// table folds toward" rule has nothing to say about them; they are neither the Greek nor
/// the Cyrillic target the assert exists to reject. The list is explicit and short so that
/// admitting one is a decision with a name on it, rather than a side effect of a block
/// range — U+00F7 was reachable only because it sits inside Latin-1 Supplement, which is
/// not all letters (#847 review).
///
/// Each entry is also checked against the source set below: a target that is itself a
/// source would chain the fold whatever its script.
pub(crate) const COMMON_SCRIPT_TARGETS: &[char] = &[
    // U+2797 HEAVY DIVISION SIGN folds here. Both are `Sm`, neither is a letter, and
    // there is no ASCII division sign to prefer — `/` is a solidus and means something
    // else.
    '\u{00F7}',
];

/// True for a Latin **letter** (#831).
///
/// `build.rs` has no script property and no dependency that supplies one, so this is a
/// block-range list. It is deliberately STRICTER than `Script=Latin`: a Latin letter in a
/// block not listed here fails the build rather than passing quietly, which is the safe
/// direction for an assert whose job is to keep a Greek or Cyrillic target out of a table
/// that folds toward Latin. Widen it when a row needs it, and look at the row.
pub(crate) fn is_latin_letter(ch: char) -> bool {
    let cp = ch as u32;
    // `is_alphabetic` is what makes this a *letter* test rather than a block test. The
    // Latin-1 Supplement range below is not all letters: U+00D7 MULTIPLICATION SIGN and
    // U+00F7 DIVISION SIGN sit inside it and are `Sm`, so a block test alone would admit
    // a mathematical operator as a fold target and weaken the assert this exists to make.
    ch.is_ascii()
        || (ch.is_alphabetic()
            && ((0x00C0..=0x024F).contains(&cp)  // Latin-1 Supplement letters, Extended-A/B
            || (0x0250..=0x02AF).contains(&cp)  // IPA Extensions
            || (0x1D00..=0x1DBF).contains(&cp)  // Phonetic Extensions (+ Supplement)
            || (0x1E00..=0x1EFF).contains(&cp)  // Latin Extended Additional
            || (0x2C60..=0x2C7F).contains(&cp)  // Latin Extended-C
            || (0xA720..=0xA7FF).contains(&cp)  // Latin Extended-D
            || (0xAB30..=0xAB6F).contains(&cp))) // Latin Extended-E
}

/// #481: inject "real" canonical-singleton rows into a char→str fold table. For each
/// singleton `s → g` (from `canonical_singletons.tsv`), give `s` the same value as `g`
/// **only when `g` already folds** (has an entry). That is the real recovery gap — the
/// raw singleton should fold exactly as its canonical target (U+1F77 GREEK IOTA WITH
/// OXIA → "i", like its tonos form U+03AF). When `g` does not fold, `s` is a benign
/// passthrough re-encoding (same non-target letter, two encodings); a row there would
/// put a foreign-script value in the table and turn the fold into a partial normalizer,
/// so it is skipped (carved out in the form-invariance oracle instead). Never overrides
/// a curated row.
pub(crate) fn inject_folding_singleton_rows(
    singletons_path: &Path,
    entries: &mut BTreeMap<u32, String>,
) {
    for (s_hex, g_hex) in read_str_str_tsv(singletons_path) {
        let s = u32::from_str_radix(s_hex.trim(), 16)
            .unwrap_or_else(|e| panic!("bad singleton hex '{s_hex}': {e}"));
        let g = u32::from_str_radix(g_hex.trim(), 16)
            .unwrap_or_else(|e| panic!("bad singleton hex '{g_hex}': {e}"));
        if entries.contains_key(&s) {
            continue;
        }
        if let Some(value) = entries.get(&g).cloned() {
            entries.insert(s, value);
        }
    }
}
