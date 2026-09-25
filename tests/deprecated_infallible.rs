//! The infallible `Transliterate::run`, `Transliterate::find_untranslatable`,
//! `api::slugify` and `DisarmStr::slugify` are deprecated since 0.17 in favour of their
//! `try_` forms, and removed in 1.0. Until then they keep doing what they did: an unknown
//! `lang` falls back to the default tables instead of failing, and with a valid `lang` or
//! none each returns what its `try_` form returns. This file pins that, so the
//! deprecation changes a warning and nothing else.
#![allow(deprecated)]

use disarm::api::{self, DisarmStr, SlugConfig, Transliterate};
use disarm::ErrorKind;

const KYIV: &str = "\u{41A}\u{438}\u{457}\u{432}";

#[test]
fn run_falls_back_on_an_unknown_lang_where_try_run_refuses() {
    let typo = Transliterate::new().lang("UK");
    assert_eq!(typo.run(KYIV), Transliterate::new().try_run(KYIV).unwrap());
    assert_eq!(
        typo.try_run(KYIV).unwrap_err().kind(),
        ErrorKind::InvalidArgument
    );
}

#[test]
fn run_matches_try_run_for_a_valid_lang() {
    for lang in ["uk", "ru", "de", "auto"] {
        let t = Transliterate::new().lang(lang);
        assert_eq!(t.run(KYIV), t.try_run(KYIV).unwrap(), "{lang}");
    }
}

#[test]
fn find_untranslatable_falls_back_and_otherwise_matches() {
    let text = "a\u{E000}\u{1F240}";
    let typo = Transliterate::new().lang("UK");
    let default = Transliterate::new().try_find_untranslatable(text).unwrap();
    assert_eq!(typo.find_untranslatable(text), default);
    assert!(typo.try_find_untranslatable(text).is_err());
    assert_eq!(Transliterate::new().find_untranslatable(text), default);
}

#[test]
fn slugify_falls_back_on_an_unknown_lang_and_otherwise_matches() {
    let typo = SlugConfig::default().with_lang("dee");
    let plain = SlugConfig::default();
    let text = "M\u{FC}nchen \u{41A}\u{438}\u{457}\u{432}";
    assert_eq!(
        api::slugify(text, &typo),
        api::try_slugify(text, &plain).unwrap()
    );
    assert!(api::try_slugify(text, &typo).is_err());
    let de = SlugConfig::default().with_lang("de");
    assert_eq!(
        api::slugify(text, &de),
        api::try_slugify(text, &de).unwrap()
    );
}

#[test]
fn the_extension_trait_follows_the_free_functions() {
    let text = "M\u{FC}nchen";
    let de = SlugConfig::default().with_lang("de");
    assert_eq!(text.slugify(&de), api::try_slugify(text, &de).unwrap());
    assert_eq!(text.try_slugify(&de).unwrap(), "muenchen");
    let typo = SlugConfig::default().with_lang("dee");
    assert_eq!(
        text.try_slugify(&typo).unwrap_err().kind(),
        ErrorKind::InvalidArgument
    );
}

#[test]
fn the_transliterate_shorthand_is_not_deprecated_and_is_the_tables_alone() {
    // No `lang` to get wrong, so it stays; it matches `try_run` whenever no replacement
    // is registered, which none is in this test binary.
    assert_eq!(
        api::transliterate(KYIV),
        Transliterate::new().try_run(KYIV).unwrap()
    );
}
