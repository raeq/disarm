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
        api::slugify("Héllo Wörld", &api::SlugConfig::default()),
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
        .run("Москва");
    assert!(out.is_ascii() && !out.is_empty());
    assert_eq!(api::strip_accents("café"), "cafe");
    assert!(api::is_ascii("hi") && !api::is_ascii("café"));
    assert!(api::list_langs().iter().any(|l| l == "ru"));
    assert!(Transliterate::new().find_untranslatable("hi").is_empty());
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
