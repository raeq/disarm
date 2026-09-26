//! Pure-Rust integration test for the `crate::api` surface (#38 / #42).
//!
//! This test links **only** against the default-feature crate — i.e. the pyo3-free
//! pure Rust core (`default = []`, no `extension-module`, no libpython). It exercises
//! every Layer-2 `api` category, so it is the executable proof that the extraction
//! produced a *usable standalone Rust dependency*: if any module had leaked pyo3
//! into Layer 1, this test would fail to compile under the default feature set.
//!
//! Build/run it with the default features (`cargo test`); it must NOT require
//! `extension-module`.

use disarm::api;

#[test]
fn confusables() {
    // Cyrillic 'а' (U+0430) folds to Latin 'a'.
    assert_eq!(
        api::normalize_confusables("\u{0430}pple", api::TargetScript::Latin),
        "apple"
    );
    assert!(api::is_confusable(
        "p\u{0430}ypal",
        api::TargetScript::Latin
    ));
}

#[test]
fn width_and_graphemes() {
    assert_eq!(api::terminal_width("世界", false), 4);
    assert_eq!(api::grapheme_width("a", false), 1);
    assert_eq!(api::grapheme_len("café"), 4);
    assert_eq!(api::grapheme_split("ab").len(), 2);
    assert_eq!(api::grapheme_truncate("hello", 3), "hel");
}

#[test]
fn text_cleanup() {
    assert_eq!(api::collapse_whitespace("a   b"), "a b");
    assert_eq!(api::collapse_whitespace("a\rb"), "a b"); // #433: CR folds, not deleted
    assert_eq!(api::strip_control_chars("a\x00b"), "ab"); // NUL (non-ws) removed
    assert_eq!(api::strip_control_chars("a\rb"), "a\rb"); // #433: CR preserved for fold
    assert_eq!(api::strip_zero_width_chars("a\u{200b}b"), "ab");
    assert!(!api::is_zalgo("hi", 3));
    assert_eq!(api::strip_zalgo("a", 2), "a");
    assert_eq!(api::fold_case("ß"), "ss");
    assert!(api::is_case_fold_stable("gross.txt"));
    assert!(!api::is_case_fold_stable("groß.txt"));
}

#[test]
fn normalization() {
    assert_eq!(
        api::normalize("cafe\u{0301}", api::NormalizationForm::Nfc),
        "café"
    );
    assert!(api::is_normalized("café", api::NormalizationForm::Nfc));
}

#[test]
fn encoders() {
    assert_eq!(api::escape_html("<a>"), "&lt;a&gt;");
    assert_eq!(
        api::percent_encode("a b", api::UrlComponent::Query),
        "a%20b"
    );
}

#[test]
fn reverse_and_scripts() {
    assert!(api::reverse_langs().iter().any(|l| l == "ru"));
    // Round-trips through the closed reverse-table set; exact output is data-driven.
    let _ = api::reverse_transliterate("privet", api::ReverseLang::Russian);
    assert!(api::detect_scripts("hello").contains(&"Latin"));
    assert!(!api::is_mixed_script("hello"));
    let _ = api::inspect_auto_lang("hello");
}

#[test]
fn filename_fallible() {
    // POSIX: only '/' and NUL are illegal, so '/' becomes the separator.
    assert_eq!(
        api::sanitize_filename("a/b", "_", 255, api::Platform::Posix, None, true).unwrap(),
        "a_b"
    );
    // The lang argument is the one fallible input — an unknown code is rejected.
    let err = api::sanitize_filename("x", "_", 255, api::Platform::Universal, Some("zzz"), true)
        .unwrap_err();
    assert_eq!(err.kind(), disarm::ErrorKind::InvalidArgument);
}

#[test]
fn log_injection_fallible() {
    assert_eq!(
        api::strip_log_injection("a\r\nb", "?", false).unwrap(),
        "a??b"
    );
    // A replacement that itself contains a neutralized character is rejected.
    assert!(api::strip_log_injection("x", "\r", false).is_err());
}

#[test]
fn encoding_fallible() {
    let decoded =
        api::decode_to_utf8(&[0x63, 0x61, 0x66, 0xE9], Some("ISO-8859-1"), 0.0, false).unwrap();
    assert_eq!(decoded.text, "café");
    assert!(api::decode_to_utf8(b"x", Some("FAKE-999"), 0.0, false).is_err());
    let det = api::detect_encoding(b"hello world");
    assert!(!det.label.is_empty() && det.confidence > 0.0);
}

#[test]
fn slugification() {
    assert_eq!(
        api::try_slugify("Héllo Wörld", &api::SlugConfig::default()).unwrap(),
        "hello-world"
    );
}

#[test]
fn transliteration() {
    use api::{OnUnknown, Scheme, Transliterate};
    // Free-function convenience (all defaults).
    assert_eq!(api::transliterate("hello"), "hello");
    // Builder with a scheme + replacement policy.
    let out = Transliterate::new()
        .scheme(Scheme::StrictIso9)
        .on_unknown(OnUnknown::Replace("?".into()))
        .try_run("Москва")
        .unwrap();
    assert!(out.is_ascii() && !out.is_empty());
    assert_eq!(api::strip_accents("café"), "cafe");
    assert!(api::is_ascii("hi") && !api::is_ascii("café"));
    assert!(api::list_langs().iter().any(|l| l == "ru"));
    assert!(Transliterate::new()
        .try_find_untranslatable("hi")
        .unwrap()
        .is_empty());
}

#[test]
fn presets_and_pipeline() {
    assert!(api::canonicalize("hello").is_ok());
    let _ = api::strip_format("hello");
    let _ = api::strip_bidi("hello");
    assert!(api::list_profiles().iter().all(|p| !p.is_empty()));
}

#[test]
#[allow(deprecated)]
fn deprecated_preset_aliases_forward_to_new_names() {
    use api::DisarmStr;

    // #430: the old names remain as deprecated aliases (removed in 1.0) and
    // must be byte-identical to the new names they forward to.
    let input = "p\u{0430}ypal\u{202e}";
    assert_eq!(
        api::security_clean(input).unwrap(),
        api::canonicalize(input).unwrap()
    );
    assert_eq!(api::display_clean(input), api::strip_format(input));
    assert_eq!(
        api::normalize_user_input(input).unwrap(),
        api::canonicalize_strict(input).unwrap()
    );
    // The DisarmStr method aliases forward too.
    assert_eq!(
        input.security_clean().unwrap(),
        input.canonicalize().unwrap()
    );
    assert_eq!(input.display_clean(), input.strip_format());
    assert_eq!(
        input.normalize_user_input().unwrap(),
        input.canonicalize_strict().unwrap()
    );
}

#[test]
fn hostname() {
    let analysis = api::is_suspicious_hostname("example.com");
    assert!(!analysis.suspicious);
    assert_eq!(analysis.canonical, "example.com");
    // A Cyrillic 'а' spoof in a Latin label is flagged.
    let spoof = api::is_suspicious_hostname("p\u{0430}ypal.com");
    assert!(spoof.suspicious);
}

#[test]
fn emoji() {
    // Built-in CLDR demojize (the custom Python provider is binding-only).
    assert_eq!(api::demojize("hi", false), "hi");
}

// ── #586: the Layer-2 surface must converge, like Python already does ────────────
//
// `confusables::normalize_confusables` (the String form the PyO3 shim calls) iterates
// to a fixed point (#522). `api::normalize_confusables_with` called the single-pass
// `_cow` form instead, and every non-Python binding — Node, Ruby, Java, Kotlin, the C
// ABI — reaches the API through it. So the security primitive answered differently
// depending on which language you called it from, and the non-Python answer could
// still be confusable with the target script.

/// A fold exposing a composition: `¥`+◌̀ folds to `Y`+◌̀, which composes to `Ỳ`.
#[test]
fn normalize_confusables_composes_what_a_fold_exposes() {
    assert_eq!(
        api::normalize_confusables("\u{00A5}\u{0300}", api::TargetScript::Latin),
        "\u{1EF2}"
    );
}

/// A composition exposing a fold: `Ҫ`+◌̧ composes to `Ç`, itself a confusable → `C`.
#[test]
fn normalize_confusables_folds_what_a_composition_exposes() {
    assert_eq!(
        api::normalize_confusables("\u{04AA}\u{0327}", api::TargetScript::Latin),
        "C"
    );
}

/// The property that makes the output usable as a comparison skeleton: whatever comes
/// back must not itself be confusable with the target script.
#[test]
fn normalize_confusables_output_is_never_confusable() {
    for input in ["\u{04AA}\u{0327}", "\u{00A5}\u{0300}", "p\u{0430}ypal"] {
        let folded = api::normalize_confusables(input, api::TargetScript::Latin);
        assert!(
            !api::is_confusable(&folded, api::TargetScript::Latin),
            "{input:?} folded to {folded:?}, which is still confusable"
        );
    }
}

/// Completeness is a property of `Numeric` and `Tr39`. `Preserve` keeps the digit rows
/// by design (#648), and `is_confusable` takes no policy, so it still flags them: the
/// guide said "never itself confusable" without the qualification until the Lean model of
/// the fold (`formal/lean/Confusables`, F2) measured 161 Latin code points like this one.
#[test]
fn preserve_keeps_what_is_confusable_flags() {
    let zero = "\u{0966}"; // DEVANAGARI DIGIT ZERO
    let kept =
        api::normalize_confusables_with(zero, api::TargetScript::Latin, api::DigitPolicy::Preserve);
    assert_eq!(kept, zero);
    assert!(api::is_confusable(&kept, api::TargetScript::Latin));
    for policy in [api::DigitPolicy::Numeric, api::DigitPolicy::Tr39] {
        let folded = api::normalize_confusables_with(zero, api::TargetScript::Latin, policy);
        assert!(
            !api::is_confusable(&folded, api::TargetScript::Latin),
            "{policy:?}"
        );
    }
}

/// The borrow contract as `normalize_confusables` documents it (F10). It used to say
/// "borrowed when the input is already NFC and nothing folds", which fails both ways.
#[test]
fn normalize_confusables_borrows_as_documented() {
    use std::borrow::Cow;
    let fold = |s| api::normalize_confusables(s, api::TargetScript::Latin);
    assert!(matches!(fold("paypal"), Cow::Borrowed(_)));
    // NFC, and nothing folds, but a mark could compose: owned, and equal to the input.
    let marked = fold("x\u{0301}");
    assert!(matches!(marked, Cow::Owned(_)));
    assert_eq!(marked, "x\u{0301}");
    // Not NFC (its NFC is U+03A9), but nothing could compose and nothing folds.
    assert!(matches!(fold("\u{2126}"), Cow::Borrowed(_)));
    assert!(matches!(fold("p\u{0430}ypal"), Cow::Owned(_)));
}

/// F4 (the Lean model in `formal/lean/Confusables`): the fold is invariant to the
/// input's normal form for the Unicode 16 compositions whose second element is a
/// starter, on the layer every non-Python binding calls. The NFD came back as it went in.
#[test]
fn normalize_confusables_composes_a_starter_pair() {
    for (nfc, nfd) in [
        ("\u{16D68}", "\u{16D67}\u{16D67}"),
        ("\u{16D69}", "\u{16D63}\u{16D67}"),
        ("\u{16D6A}", "\u{16D63}\u{16D67}\u{16D67}"),
    ] {
        for policy in [
            api::DigitPolicy::Numeric,
            api::DigitPolicy::Tr39,
            api::DigitPolicy::Preserve,
        ] {
            let fold = |s| api::normalize_confusables_with(s, api::TargetScript::Latin, policy);
            assert_eq!(fold(nfd), fold(nfc), "{nfd:?} under {policy:?}");
            assert_eq!(fold(nfd), nfc);
        }
        assert_eq!(
            api::skeleton_key(nfd, api::DigitPolicy::Numeric).unwrap(),
            nfc,
            "skeleton_key on {nfd:?}"
        );
    }
}

/// `f(f(x)) == f(x)` on the Layer-2 path, under both digit policies and both targets.
#[test]
fn normalize_confusables_is_idempotent() {
    for target in [api::TargetScript::Latin, api::TargetScript::Cyrillic] {
        for policy in [api::DigitPolicy::Numeric, api::DigitPolicy::Tr39] {
            for input in [
                "\u{04AA}\u{0327}",
                "\u{00A5}\u{0300}",
                "g\u{0966}\u{0966}gle",
            ] {
                let once = api::normalize_confusables_with(input, target, policy);
                let twice = api::normalize_confusables_with(&once, target, policy);
                assert_eq!(
                    once, twice,
                    "{input:?} not idempotent for {target:?}/{policy:?}"
                );
            }
        }
    }
}
