//! #561 — the digit-mapping policy switch, from the public Rust surface.

use disarm::api::{normalize_confusables, normalize_confusables_with, DigitPolicy, TargetScript};

const LATIN: TargetScript = TargetScript::Latin;

/// The two-argument entry point keeps the historical behaviour, so no existing caller
/// changes. That is why the policy is a separate function rather than a third parameter.
#[test]
fn the_two_arg_form_is_still_numeric() {
    assert_eq!(normalize_confusables("\u{0966}", LATIN), "0");
    assert_eq!(
        normalize_confusables("\u{0966}", LATIN),
        normalize_confusables_with("\u{0966}", LATIN, DigitPolicy::Numeric)
    );
}

#[test]
fn default_derives_the_numeric_policy() {
    assert_eq!(DigitPolicy::default(), DigitPolicy::Numeric);
    assert_eq!(DigitPolicy::Numeric.as_str(), "numeric");
    assert_eq!(DigitPolicy::Tr39.as_str(), "tr39");
}

#[test]
fn tr39_policy_uses_the_upstream_letter_targets() {
    for (source, numeric, tr39) in [
        ('\u{0966}', "0", "o"), // Devanagari zero
        ('\u{09E6}', "0", "o"), // Bengali zero
        ('\u{0CE6}', "0", "O"), // Kannada zero — capital O, not lowercase
        ('\u{0661}', "1", "l"), // Arabic-Indic one
        ('\u{0667}', "7", "V"), // Arabic-Indic seven
    ] {
        let s = source.to_string();
        assert_eq!(
            normalize_confusables_with(&s, LATIN, DigitPolicy::Numeric),
            numeric
        );
        assert_eq!(
            normalize_confusables_with(&s, LATIN, DigitPolicy::Tr39),
            tr39
        );
    }
}

/// The point of the policy: under TR39 a Devanagari zero and a Latin `o` collide, which is
/// what makes two confusable identifiers compare equal. Under numeric they do not — right
/// for prose, wrong for a skeleton benchmark.
#[test]
fn tr39_policy_makes_the_skeleton_collide() {
    let spoof = "g\u{0966}\u{0966}gle";
    assert_eq!(
        normalize_confusables_with(spoof, LATIN, DigitPolicy::Tr39),
        "google"
    );
    assert_eq!(
        normalize_confusables_with(spoof, LATIN, DigitPolicy::Numeric),
        "g00gle"
    );
}

/// The policy must be surgical: everything outside the 45 divergent rows is untouched.
#[test]
fn the_policy_touches_only_the_divergent_rows() {
    for text in [
        "p\u{0430}ypal",
        "\u{041D}\u{0435}llo W\u{043E}rld",
        "hello",
        "caf\u{00E9}",
        "",
        "0123456789",
    ] {
        assert_eq!(
            normalize_confusables_with(text, LATIN, DigitPolicy::Numeric),
            normalize_confusables_with(text, LATIN, DigitPolicy::Tr39),
            "policy changed something outside the digit rows for {text:?}"
        );
    }
}

/// Both policies must be fixed points — every preset is built on this fold.
#[test]
fn both_policies_are_idempotent() {
    for policy in [DigitPolicy::Numeric, DigitPolicy::Tr39] {
        for text in [
            "\u{0966}\u{09E6}\u{0CE6}",
            "g\u{0966}\u{0966}gle",
            "p\u{0430}ypal",
            "\u{0661}\u{0665}",
        ] {
            let once = normalize_confusables_with(text, LATIN, policy);
            let twice = normalize_confusables_with(&once, LATIN, policy);
            assert_eq!(twice, once, "{policy:?} not idempotent on {text:?}");
        }
    }
}

/// #590: `⁰` and `⁹` are the only two superscript digits upstream TR39 carries — it
/// lists visual lookalikes, and no letter resembles a superscript four. Under the
/// numeric reading they are exact twins, and #590 was an asymmetry there.
///
/// Under `tr39` they legitimately differ, and #587 is why: a divergence is recorded
/// only when upstream's target has an ASCII form. `⁰`'s does (`º` → `o`); `⁹`'s does
/// not (`ꝰ` U+A770 has no clear representative), so that row is dropped and `tr39`
/// falls back to numeric for it. The asymmetry is a stated consequence of the
/// contract now, not an accident of which block a target happened to live in.
#[test]
fn the_two_superscript_digits_agree_under_numeric() {
    assert_eq!(
        normalize_confusables_with("\u{2070}", LATIN, DigitPolicy::Numeric),
        "0"
    );
    assert_eq!(
        normalize_confusables_with("\u{2079}", LATIN, DigitPolicy::Numeric),
        "9"
    );
}

/// Hostname analysis deliberately stays numeric — selecting TR39 there would silently
/// change what `is_suspicious_hostname` flags, which is a security-behaviour change.
#[test]
fn hostname_analysis_is_unaffected() {
    let host = "g\u{0966}\u{0966}gle.com";
    let analysis = disarm::api::is_suspicious_hostname(host);
    // The canonical form is the numeric-policy skeleton, verbatim — not the TR39 one.
    assert_eq!(
        analysis.canonical,
        normalize_confusables_with(host, LATIN, DigitPolicy::Numeric)
    );
    assert_ne!(
        analysis.canonical,
        normalize_confusables_with(host, LATIN, DigitPolicy::Tr39)
    );
}

/// The override set holds TR39's *Latin* targets, so the policy is Latin-only: under any
/// other target it must be a no-op, not a source of Latin letters in a Cyrillic skeleton
/// (and not a fold for sources the Cyrillic table has no row for at all).
#[test]
fn the_policy_is_scoped_to_the_latin_target() {
    const CYRILLIC: TargetScript = TargetScript::Cyrillic;
    for text in [
        "\u{0966}",  // Devanagari zero — a Cyrillic row exists (→ "0")
        "\u{0668}",  // Arabic-Indic eight — a Cyrillic row exists (→ "8")
        "\u{0660}",  // Arabic-Indic zero — NO Cyrillic row; must pass through
        "\u{2079}",  // superscript nine — NO Cyrillic row; must pass through
        "\u{118E3}", // Warang Citi three — NO Cyrillic row; must pass through
        "hello",
    ] {
        assert_eq!(
            normalize_confusables_with(text, CYRILLIC, DigitPolicy::Numeric),
            normalize_confusables_with(text, CYRILLIC, DigitPolicy::Tr39),
            "digit policy changed the Cyrillic fold of {text:?}"
        );
    }
}

// ── #587: the override values honour the ASCII contract ──────────────────────
//
// `write_digit_tr39_overrides` took upstream's raw target with only `strip_combining`
// applied, bypassing the `ASCII_FOLD` pass every value in the main Latin table goes
// through. #341 made ASCII the contract for that table; the override set was written
// later and never joined it, so `digit_policy="tr39"` reintroduced exactly the
// non-ASCII residue #341 had removed.

/// TR39 routes the Arabic-Indic eights through `Ʌ` (U+0245), which the main pipeline
/// folds to `a`. The override set must agree — TR39 puts `٨ ۸ Λ Ꟛ` in one confusable
/// class, and a skeleton that returns a different string for each defeats its purpose.
#[test]
fn tr39_targets_are_ascii_folded_like_the_main_table() {
    for src in ["\u{0668}", "\u{06F8}"] {
        assert_eq!(
            normalize_confusables_with(src, LATIN, DigitPolicy::Tr39),
            "a"
        );
    }
    // U+2070 routes through `º` (U+00BA), which folds to `o`.
    assert_eq!(
        normalize_confusables_with("\u{2070}", LATIN, DigitPolicy::Tr39),
        "o"
    );
}

/// `ꝰ` (U+A770 MODIFIER LETTER US) has no clear ASCII representative, so the
/// divergence cannot be expressed under the contract. Rather than ship a non-ASCII
/// value, the row is dropped and `tr39` falls back to the numeric reading.
#[test]
fn a_divergence_with_no_ascii_form_falls_back_to_numeric() {
    assert_eq!(
        normalize_confusables_with("\u{2079}", LATIN, DigitPolicy::Tr39),
        "9"
    );
    assert_eq!(
        normalize_confusables_with("\u{2079}", LATIN, DigitPolicy::Numeric),
        "9"
    );
}
