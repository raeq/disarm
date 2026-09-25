//! Both forms of a case pair transliterate to the same letters, differing at most in case
//! (#1052).
//!
//! `search_key` folds case *before* it transliterates, so a pair whose lowercase form has
//! no table entry leaves the key untransliterated even when the capital has one: `ȺBC`
//! keyed as `ⱥbc` and never met `ÀBC`. The other direction breaks `transliterate` itself,
//! which returned `[?]` for the Georgian Mtavruli capitals whose Mkhedruli lowercase maps.
//!
//! The pairs come from the crate's own `case_folding.tsv`, the table `fold_case` (and so
//! `search_key`) runs on, rather than from the running toolchain's Unicode version.

use disarm::api::{search_key, OnUnknown, Transliterate};

const CASE_FOLDING: &str = include_str!("../src/tables/data/case_folding.tsv");

/// `(capital, folded)` for every single-code-point fold of an uppercase letter.
///
/// The fold table also carries folds that are not case pairs: `µ` to `μ`, the combining
/// iota subscript to `ι`, the Cyrillic Extended-C variant lowercases to their plain
/// letters. Those map to different letters on purpose, so only an uppercase key counts.
/// `is_uppercase` only narrows the pinned table, so the toolchain's Unicode version can
/// drop a row but never add one.
fn case_pairs() -> Vec<(char, char)> {
    CASE_FOLDING
        .lines()
        .filter(|line| !line.starts_with('#') && !line.is_empty())
        .filter_map(|line| {
            let (hex, folded) = line.split_once('\t')?;
            let capital = char::from_u32(u32::from_str_radix(hex, 16).ok()?)?;
            if !capital.is_uppercase() {
                return None;
            }
            let mut chars = folded.chars();
            let first = chars.next()?;
            chars.next().is_none().then_some((capital, first))
        })
        .collect()
}

/// Transliterated, with an unknown character passed through, so an unmapped form is
/// visible as itself rather than as a sentinel both sides share.
fn translit(c: char) -> String {
    Transliterate::new()
        .on_unknown(OnUnknown::Preserve)
        .try_run(&c.to_string())
        .expect("no lang, so nothing to reject")
        .into_owned()
}

#[test]
fn the_case_folding_table_has_the_pairs_the_issue_names() {
    let pairs = case_pairs();
    assert!(pairs.len() > 1_000, "only {} pairs parsed", pairs.len());
    for pair in [('\u{023A}', '\u{2C65}'), ('\u{1CB1}', '\u{10F1}')] {
        assert!(
            pairs.contains(&pair),
            "{pair:?} missing from case_folding.tsv"
        );
    }
}

#[test]
fn both_forms_of_a_case_pair_transliterate_alike() {
    let mismatched: Vec<String> = case_pairs()
        .into_iter()
        .filter_map(|(capital, folded)| {
            let (upper, lower) = (translit(capital), translit(folded));
            (upper.to_lowercase() != lower.to_lowercase()).then(|| {
                format!(
                    "U+{:04X} {capital} -> {upper:?} / U+{:04X} {folded} -> {lower:?}",
                    u32::from(capital),
                    u32::from(folded)
                )
            })
        })
        .collect();
    assert!(
        mismatched.is_empty(),
        "{} case pairs transliterate differently:\n{}",
        mismatched.len(),
        mismatched.join("\n")
    );
}

#[test]
fn search_key_is_ascii_wherever_transliterate_is() {
    let leaked: Vec<String> = case_pairs()
        .into_iter()
        .filter(|&(capital, _)| translit(capital).is_ascii())
        .filter_map(|(capital, _)| {
            let text = capital.to_string();
            let key = search_key(&text, None).expect("no lang");
            (!key.is_ascii()).then(|| format!("U+{:04X} {capital} -> {key:?}", u32::from(capital)))
        })
        .collect();
    assert!(
        leaked.is_empty(),
        "search_key leaves non-ASCII where transliterate does not:\n{}",
        leaked.join("\n")
    );
}

#[test]
fn the_issue_reproduction() {
    assert_eq!(search_key("\u{023A}BC", None).unwrap(), "abc");
    assert_eq!(
        search_key("\u{023A}BC", None).unwrap(),
        search_key("\u{00C0}BC", None).unwrap()
    );
    assert_eq!(translit('\u{2C65}'), "a");
    assert_eq!(translit('\u{2C62}'), "L");
    assert_eq!(translit('\u{1CB1}'), "He");
}
