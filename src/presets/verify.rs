//! `is_canonical`: whether a text is already a preset's fixed point.

use std::borrow::Cow;

use super::keys::{catalog_key, search_key, skeleton_key, sort_key};
use super::text::{
    canonicalize, canonicalize_strict, ml_normalize, strip_format, strip_obfuscation,
};

/// Layer-1 core for `is_canonical` (#730) — the verification-path predicate.
///
/// Every other preset here is generation path: text in, normalized text out. This answers
/// the question a caller has about bytes that arrived already bound, where recomputing the
/// canonical form silently defends the comparison and leaves the stored value alone.
///
/// It is not [`crate::anomalies::has_anomalies`]. Over every assigned code point, 142,760
/// of them (5,292 outside the Private Use Area) are clean to the detector and are not
/// their own canonical form; none go the other way. CJK compatibility ideographs, Arabic
/// presentation forms and fullwidth Latin are in that set, and they belong there — `ＮＨＫ`
/// is ordinary Japanese text, so teaching the detector to fire on it would undo #633.
///
/// Defined as `preset(text) == text`, but it avoids materialising the normalized copy
/// whenever the pipeline's `Guard::Inert` classification hands back a borrow.
///
/// `preset` accepts the nine preset names, the three deprecated 0.11 aliases that
/// `PRESETS` still documents, and any policy-profile name. `skeleton_key` answers under
/// its default `digit_policy`, `"numeric"`, as every other preset here does.
pub(crate) fn is_canonical(text: &str, preset: &str) -> Result<bool, crate::ErrorRepr> {
    // A borrowed `Cow` proves no step touched the input. An owned one only proves a buffer
    // was allocated — several steps build one and write the input back unchanged — so it
    // still has to be compared.
    fn settled(out: Cow<'_, str>, text: &str) -> bool {
        match out {
            Cow::Borrowed(_) => true,
            Cow::Owned(s) => s == text,
        }
    }
    let out = match preset {
        // The second name in each of the first three arms is a 0.11 rename that `PRESETS`
        // still documents as a valid key, so the string dispatch has to accept it or the
        // registry claim is false. No deprecation warning fires here: the deprecation is
        // on the *function*, and this is a lookup key.
        "canonicalize" | "security_clean" => canonicalize(text)?,
        "canonicalize_strict" | "normalize_user_input" => canonicalize_strict(text)?,
        "strip_format" | "display_clean" => strip_format(text),
        "strip_obfuscation" => strip_obfuscation(text)?,
        "search_key" => search_key(text, None)?,
        "catalog_key" => catalog_key(text, None, false)?,
        "sort_key" => sort_key(text, None)?,
        "ml_normalize" => ml_normalize(text, None, "cldr", true)?,
        // Since `PRESETS` lists it (Finding 5 of the Lean model in `formal/lean/Presets`):
        // the registry the docstring names is the one this dispatch has to accept.
        "skeleton_key" => skeleton_key(text, "numeric")?,
        // Profiles are the other half of the registry. A pipeline returns an owned String,
        // so the borrow fast path is unavailable, but the comparison is still the answer.
        other => match crate::pipeline::get_pipeline(other)? {
            Some(p) => return Ok(p.process(text)? == text),
            None => {
                return Err(crate::ErrorRepr::UnknownProfile {
                    got: other.to_owned(),
                    available: crate::pipeline::profile_names().join(", "),
                })
            }
        },
    };
    Ok(settled(out, text))
}

#[cfg(test)]
mod is_canonical_tests {
    use super::*;

    /// The predicate is defined as `preset(text) == text` and must not drift from it.
    #[test]
    fn agrees_with_the_expression_it_replaces() {
        for text in [
            "abc",
            "",
            "paypal.com",
            "\u{FF21}\u{FF22}\u{FF23}", // ＡＢＣ
            "\u{216B}",                 // Ⅻ
            "a\"b",
            "caf\u{E9}",
            "e\u{301}", // decomposed — NFC changes it
        ] {
            let expected = canonicalize(text).unwrap() == text;
            assert_eq!(
                is_canonical(text, "canonicalize").unwrap(),
                expected,
                "{text:?}"
            );
        }
    }

    /// #730's premise: the detector stays silent on text that is not canonical. If this
    /// ever starts failing, `has_anomalies` has become a canonicity predicate and
    /// `is_canonical` is redundant — that is a decision, not a passing test.
    #[test]
    fn the_detector_is_silent_on_the_gap() {
        for text in ["\u{FF21}\u{FF22}\u{FF23}", "\u{FF4E}\u{FF48}\u{FF4B}"] {
            assert!(!crate::anomalies::has_anomalies(
                text,
                &std::collections::HashSet::new()
            ));
            assert!(!is_canonical(text, "canonicalize").unwrap());
        }
    }

    #[test]
    fn every_preset_name_dispatches() {
        // Plain ASCII is a fixed point of all nine.
        for preset in [
            "canonicalize",
            "canonicalize_strict",
            "strip_obfuscation",
            "strip_format",
            "search_key",
            "catalog_key",
            "sort_key",
            "ml_normalize",
            "skeleton_key",
        ] {
            assert!(
                is_canonical("abc", preset).unwrap(),
                "{preset} on plain ASCII"
            );
        }
        // Fullwidth separates them, which is the point of taking a preset argument at
        // all: `strip_format` has no NFKC step, so ＡＢＣ *is* its own canonical form
        // there while the other eight fold it to ABC.
        let fullwidth = "\u{FF21}\u{FF22}\u{FF23}";
        assert!(is_canonical(fullwidth, "strip_format").unwrap());
        for preset in [
            "canonicalize",
            "canonicalize_strict",
            "strip_obfuscation",
            "search_key",
            "catalog_key",
            "sort_key",
            "ml_normalize",
            "skeleton_key",
        ] {
            assert!(
                !is_canonical(fullwidth, preset).unwrap(),
                "{preset} on fullwidth"
            );
        }
    }

    /// `PRESETS` documents the 0.11 aliases as valid keys, so the string dispatch must
    /// accept them. Before this test they fell through to the profile lookup and came
    /// back as `UnknownProfile`, which made the registry claim in the docs false.
    #[test]
    fn the_deprecated_aliases_still_resolve() {
        let fullwidth = "\u{FF21}\u{FF22}\u{FF23}";
        for (alias, target) in [
            ("security_clean", "canonicalize"),
            ("display_clean", "strip_format"),
            ("normalize_user_input", "canonicalize_strict"),
        ] {
            for text in ["abc", fullwidth, "caf\u{E9}"] {
                assert_eq!(
                    is_canonical(text, alias).unwrap(),
                    is_canonical(text, target).unwrap(),
                    "{alias} disagrees with {target} on {text:?}"
                );
            }
        }
    }

    #[test]
    fn a_profile_name_dispatches_too() {
        for profile in crate::pipeline::profile_names() {
            let pipeline = crate::pipeline::get_pipeline(&profile).unwrap().unwrap();
            let expected =
                pipeline.process("\u{FF21}\u{FF22}\u{FF23}").unwrap() == "\u{FF21}\u{FF22}\u{FF23}";
            assert_eq!(
                is_canonical("\u{FF21}\u{FF22}\u{FF23}", &profile).unwrap(),
                expected,
                "{profile}"
            );
        }
    }

    #[test]
    fn an_unknown_name_is_an_error() {
        let err = is_canonical("abc", "not_a_preset").unwrap_err();
        assert!(format!("{err}").contains("not_a_preset"), "{err}");
    }

    /// The `Guard::Inert` fast path returns a borrow; the predicate must read that as
    /// "unchanged" rather than falling through to a comparison that was never needed.
    #[test]
    fn the_inert_fast_path_answers_true() {
        assert!(matches!(canonicalize("abc").unwrap(), Cow::Borrowed(_)));
        assert!(is_canonical("abc", "canonicalize").unwrap());
    }
}
