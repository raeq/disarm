//! Idiomatic-Rust surface added in #352: the `Transliterate` builder,
//! `Scheme`/`OnUnknown` enums, `Cow`-returning transforms, the `graphemes()`
//! iterator, the `DisarmStr` extension trait, `SlugConfig` builder methods, and
//! `FromStr`/`Display` on the public enums.

use std::borrow::Cow;
use std::str::FromStr;

use disarm::api::{self, OnUnknown, Scheme, SlugConfig, TargetScript, Transliterate};
use disarm::{DisarmStr, ErrorMode};

#[test]
fn transliterate_convenience_equals_default_builder() {
    assert_eq!(
        api::transliterate("Москва"),
        Transliterate::new().run("Москва")
    );
    assert_eq!(api::transliterate("Москва"), "Moskva");
    assert_eq!(api::transliterate("hello"), "hello");
}

#[test]
fn scheme_is_plumbed() {
    // Each scheme builds and runs; ISO 9 differs from the default for Cyrillic.
    let default = Transliterate::new().scheme(Scheme::Default).run("я");
    let iso9 = Transliterate::new().scheme(Scheme::StrictIso9).run("я");
    let gost = Transliterate::new().scheme(Scheme::GostR7034).run("я");
    assert_ne!(default, iso9);
    assert!(!default.is_empty() && !iso9.is_empty() && !gost.is_empty());
}

#[test]
fn on_unknown_policies() {
    // U+1F600 has no romanization.
    let s = "a\u{1F600}b";
    assert_eq!(
        Transliterate::new().on_unknown(OnUnknown::Ignore).run(s),
        "ab"
    );
    assert_eq!(
        Transliterate::new()
            .on_unknown(OnUnknown::Replace("_".into()))
            .run(s),
        "a_b"
    );
    assert!(Transliterate::new()
        .on_unknown(OnUnknown::Preserve)
        .run(s)
        .contains('\u{1F600}'));
}

#[test]
fn cow_borrows_on_noop() {
    // No-op inputs borrow (zero allocation).
    assert!(matches!(api::strip_accents("hello"), Cow::Borrowed(_)));
    assert!(matches!(api::strip_accents("日本語"), Cow::Borrowed(_)));
    assert!(matches!(api::fold_case("hello"), Cow::Borrowed(_)));
    assert!(matches!(
        api::normalize_confusables("hello", TargetScript::Latin),
        Cow::Borrowed(_)
    ));
    // Changed inputs allocate.
    assert!(matches!(api::strip_accents("café"), Cow::Owned(_)));
    assert!(matches!(api::fold_case("HELLO"), Cow::Owned(_)));
    assert!(matches!(
        api::normalize_confusables("p\u{0430}ypal", TargetScript::Latin),
        Cow::Owned(_)
    ));
}

#[test]
fn graphemes_iterator() {
    let g: Vec<&str> = api::graphemes("a\u{2764}\u{FE0F}b").collect();
    assert_eq!(g, ["a", "\u{2764}\u{FE0F}", "b"]);
    assert_eq!(api::graphemes("café").count(), 4);
}

#[test]
fn disarm_str_extension_trait() {
    assert_eq!(
        "раypal".normalize_confusables(TargetScript::Latin),
        "paypal"
    );
    assert_eq!("café".strip_accents(), "cafe");
    assert_eq!("HELLO".fold_case(), "hello");
    assert_eq!("Москва".transliterate(), "Moskva");
    assert!("p\u{0430}ypal.com".is_suspicious_hostname().0);
    assert!("hello".strip_obfuscation().is_ok());
    // Works on String too (blanket AsRef<str> impl).
    let owned = String::from("café");
    assert_eq!(owned.strip_accents(), "cafe");
}

#[test]
fn slugconfig_builder_methods() {
    let cfg = SlugConfig::default()
        .with_separator("_")
        .with_lowercase(true);
    assert_eq!(api::slugify("Héllo Wörld", &cfg), "hello_world");
}

#[test]
fn fromstr_display_roundtrip() {
    for m in [ErrorMode::Replace, ErrorMode::Ignore, ErrorMode::Preserve] {
        assert_eq!(ErrorMode::from_str(&m.to_string()).unwrap(), m);
    }
    for t in [TargetScript::Latin, TargetScript::Cyrillic] {
        assert_eq!(TargetScript::from_str(&t.to_string()).unwrap(), t);
    }
    for sc in [Scheme::Default, Scheme::StrictIso9, Scheme::GostR7034] {
        assert_eq!(Scheme::from_str(&sc.to_string()).unwrap(), sc);
    }
    assert!(ErrorMode::from_str("nonsense").is_err());
    assert!(TargetScript::from_str("greek").is_err());
    assert!(Scheme::from_str("nonsense").is_err());
}
