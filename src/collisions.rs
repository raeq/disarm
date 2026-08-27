//! Layer 1 (pure-Rust core): which values in a set reduce to the same identity
//! key (#620). No pyo3.
//!
//! Every other disarm detector is a single-string predicate, and a collision is
//! not a property of a single string — `groß.txt` is an ordinary German filename.
//! The question is only answerable about a *set*: given these names, which of
//! them are the same name? That is the question node-tar's `PathReservations`
//! guard failed to ask (CVE-2026-23950), and the one a registry has to ask before
//! accepting a second `аdmin` (CVE-2013-7236).
//!
//! Shim in `src/py/collisions.rs`; crates.io surface is
//! `crate::api::find_key_collisions`, which owns the [`crate::api::KeyForm`] enum
//! and passes its token down here.

use std::borrow::Cow;
use std::collections::HashMap;

use crate::ErrorRepr;

/// One group of distinct inputs that reduce to the same key.
///
/// A group is a collision only when it holds **two or more distinct inputs**. The
/// same string appearing twice is the same name twice, which a reservation table
/// already handles; the hazard the collision CVEs describe is two names that
/// *differ* and occupy one slot.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct KeyCollision {
    /// The reduced form every member of the group shares.
    pub key: String,
    /// The distinct inputs that reduce to it, in order of first appearance.
    pub values: Vec<String>,
    /// Every position in the input list that belongs to this group, ascending.
    ///
    /// Not parallel to [`values`](Self::values): a value repeated verbatim
    /// contributes one entry there and one index per occurrence here. Both are
    /// present because both uses are real — a registry wants the names, an
    /// extractor wants to know which entries to refuse.
    pub indices: Vec<usize>,
}

/// Apply the reducer named by `key` to one value.
///
/// The token set is [`crate::api::KeyForm`]'s; Layer 2 holds the enum and can
/// only produce a valid token, so the error arm is reachable from a hand-written
/// string alone (the C ABI and the dynamic bindings).
fn reduce<'a>(value: &'a str, key: &str, lang: Option<&str>) -> Result<Cow<'a, str>, ErrorRepr> {
    match key {
        "fold_case" => Ok(crate::case_fold::fold_case_cow(value)),
        "search_key" => crate::presets::search_key(value, lang),
        "catalog_key" => crate::presets::catalog_key(value, lang, false),
        "canonicalize" => crate::presets::canonicalize(value),
        "canonicalize_strict" => crate::presets::canonicalize_strict(value),
        "normalize_confusables" => Ok(crate::confusables::normalize_confusables_fixed_cow(
            value, "latin", "numeric",
        )?),
        _ => Err(ErrorRepr::InvalidKeyForm {
            got: key.to_owned(),
        }),
    }
}

/// Group `values` by their reduction under `key` and return only the groups that
/// hold more than one distinct input (#620).
///
/// Reducing and grouping happen in one pass over one reducer, so the report
/// cannot disagree with the collapse it describes — which is the property worth
/// having, and the one a caller re-implementing this by hand has to get right.
///
/// Groups come back in order of the first index that participates, so the output
/// is deterministic for a given input rather than dependent on hash iteration.
pub(crate) fn find_key_collisions(
    values: &[&str],
    key: &str,
    lang: Option<&str>,
) -> Result<Vec<KeyCollision>, ErrorRepr> {
    if values.len() > crate::MAX_BATCH_SIZE {
        return Err(ErrorRepr::BatchTooLarge {
            len: values.len(),
            max: crate::MAX_BATCH_SIZE,
        });
    }

    // Groups live in a Vec, so first-appearance order is the storage order and
    // needs no second pass to recover; the map only remembers which slot a key
    // owns. Looking the slot up by value (a `usize`) also ends the borrow on the
    // map immediately, which is what lets the miss arm allocate the key — the
    // reduction is only turned into an owned `String` for a key that is new.
    let mut groups: Vec<KeyCollision> = Vec::new();
    let mut slot_of: HashMap<String, usize> = HashMap::new();

    for (index, value) in values.iter().enumerate() {
        let reduced = reduce(value, key, lang)?;
        if let Some(&slot) = slot_of.get(reduced.as_ref()) {
            let group = &mut groups[slot];
            if !group.values.iter().any(|seen| seen == value) {
                group.values.push((*value).to_owned());
            }
            group.indices.push(index);
        } else {
            let reduced = reduced.into_owned();
            slot_of.insert(reduced.clone(), groups.len());
            groups.push(KeyCollision {
                key: reduced,
                values: vec![(*value).to_owned()],
                indices: vec![index],
            });
        }
    }

    // A group of one is a name that collides with nothing.
    groups.retain(|group| group.values.len() > 1);
    Ok(groups)
}

#[cfg(test)]
mod tests {
    use super::*;

    const FOLD: &str = "fold_case";

    fn collide(values: &[&str], key: &str) -> Vec<KeyCollision> {
        find_key_collisions(values, key, None).expect("valid key form")
    }

    // ── The CVE the function exists for ─────────────────────────────

    #[test]
    fn the_node_tar_pair_is_reported() {
        let found = collide(&["groß.txt", "gross.txt", "other.txt"], FOLD);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].key, "gross.txt");
        assert_eq!(found[0].values, ["groß.txt", "gross.txt"]);
        assert_eq!(found[0].indices, [0, 1]);
    }

    #[test]
    fn a_clean_set_reports_nothing() {
        assert!(collide(&["a.txt", "b.txt", "c.txt"], FOLD).is_empty());
        assert!(collide(&[], FOLD).is_empty());
    }

    // ── What counts as a collision ──────────────────────────────────

    #[test]
    fn one_name_twice_is_not_a_collision() {
        // Two entries, one name. A reservation table already handles this; the
        // hazard is two names that DIFFER and share a slot.
        assert!(collide(&["a.txt", "a.txt"], FOLD).is_empty());
    }

    #[test]
    fn a_repeat_inside_a_real_collision_keeps_its_index() {
        let found = collide(&["groß.txt", "gross.txt", "gross.txt"], FOLD);
        assert_eq!(found.len(), 1);
        // Distinct values, but every position.
        assert_eq!(found[0].values, ["groß.txt", "gross.txt"]);
        assert_eq!(found[0].indices, [0, 1, 2]);
    }

    #[test]
    fn three_spellings_land_in_one_group() {
        let found = collide(&["groß.txt", "gross.txt", "GROSS.TXT"], FOLD);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].values, ["groß.txt", "gross.txt", "GROSS.TXT"]);
    }

    // ── Order ───────────────────────────────────────────────────────

    #[test]
    fn groups_come_back_in_first_appearance_order() {
        // `zeta` collides at index 0, `alpha` at index 1; a HashMap would be free
        // to return them either way round, so the order is asserted rather than
        // observed.
        let found = collide(&["zetaß", "alphaß", "zetass", "alphass"], FOLD);
        assert_eq!(found.len(), 2);
        assert_eq!(found[0].key, "zetass");
        assert_eq!(found[1].key, "alphass");
    }

    #[test]
    fn indices_are_ascending() {
        let found = collide(&["groß", "x", "gross", "y", "GROSS"], FOLD);
        assert_eq!(found[0].indices, [0, 2, 4]);
    }

    // ── The reducer is the policy ───────────────────────────────────

    #[test]
    fn the_reducer_decides_what_collides() {
        // Measured, and the reason the caller has to choose: `fold_case` sees the
        // eszett and not the Cyrillic homoglyph; `canonicalize` sees the reverse.
        let names = &["groß", "gross", "admin", "аdmin"];
        let folded = collide(names, FOLD);
        assert_eq!(folded.len(), 1);
        assert_eq!(folded[0].values, ["groß", "gross"]);

        let canonical = collide(names, "canonicalize");
        assert_eq!(canonical.len(), 1);
        assert_eq!(canonical[0].values, ["admin", "аdmin"]);

        // `search_key` is the one that sees both.
        let searched = collide(names, "search_key");
        assert_eq!(searched.len(), 2);
    }

    #[test]
    fn every_key_form_token_resolves() {
        for key in [
            "fold_case",
            "search_key",
            "catalog_key",
            "canonicalize",
            "canonicalize_strict",
            "normalize_confusables",
        ] {
            find_key_collisions(&["a"], key, None)
                .unwrap_or_else(|e| panic!("{key} rejected: {e}"));
        }
    }

    #[test]
    fn an_unknown_key_form_is_an_error_not_a_silent_default() {
        let err = find_key_collisions(&["a"], "lower", None).unwrap_err();
        assert!(matches!(err, ErrorRepr::InvalidKeyForm { .. }), "{err:?}");
    }

    #[test]
    fn a_batch_over_the_cap_is_refused() {
        let big = vec!["a"; crate::MAX_BATCH_SIZE + 1];
        let err = find_key_collisions(&big, FOLD, None).unwrap_err();
        assert!(matches!(err, ErrorRepr::BatchTooLarge { .. }), "{err:?}");
    }

    // ── The property the issue asks for ─────────────────────────────

    #[test]
    fn reporting_agrees_with_collapsing() {
        // The guarantee: anything reported as one group really does reduce to one
        // value, and nothing outside a group shares a key with it. Checked against
        // the reducer directly rather than against the function's own bookkeeping.
        let names = &["groß.txt", "gross.txt", "GROSS.TXT", "other.txt", "andere"];
        let found = collide(names, FOLD);
        for group in &found {
            for value in &group.values {
                assert_eq!(reduce(value, FOLD, None).unwrap(), group.key);
            }
        }
        let grouped: Vec<&str> = found
            .iter()
            .flat_map(|g| g.values.iter().map(String::as_str))
            .collect();
        for name in names {
            if grouped.contains(name) {
                continue;
            }
            let key = reduce(name, FOLD, None).unwrap();
            assert!(
                !found.iter().any(|g| g.key == key),
                "{name:?} shares a key with a reported group but was left out"
            );
        }
    }

    #[test]
    fn lang_reaches_the_reducers_that_take_one() {
        // German transliteration turns ö into oe, so `Müller` and `Mueller`
        // collide under a de search key and do not under the default.
        let names = &["Müller", "Mueller"];
        assert!(
            find_key_collisions(names, "search_key", Some("de"))
                .unwrap()
                .len()
                == 1
        );
        assert!(find_key_collisions(names, "search_key", None)
            .unwrap()
            .is_empty());
    }
}
