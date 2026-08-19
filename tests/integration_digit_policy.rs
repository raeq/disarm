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

/// The policy must be surgical: everything outside the ~45 divergent rows is untouched.
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

/// Hostname analysis deliberately stays numeric — selecting TR39 there would silently
/// change what `is_suspicious_hostname` flags, which is a security-behaviour change.
#[test]
fn hostname_analysis_is_unaffected() {
    let analysis = disarm::api::is_suspicious_hostname("g\u{0966}\u{0966}gle.com");
    // Whatever the verdict, it must match the numeric-policy skeleton, not the TR39 one.
    assert!(!analysis.canonical.contains("google"));
}
