//! Regression tests for the core half of the bindings harness findings
//! (`formal/bindings/README.md`). Each binding's own suite covers its half; these pin
//! what every binding now inherits from the core.

use disarm::api::{self, OnUnknown, SlugConfig, Transliterate};
use disarm::ErrorKind;

/// S1: `strip_accents` is per character. A character with a singleton canonical
/// decomposition folds whether or not an unrelated accent occurs elsewhere.
#[test]
fn s1_strip_accents_folds_a_singleton_alone_and_in_company() {
    for (ch, folded) in [
        ("\u{037E}", ";"),        // GREEK QUESTION MARK
        ("\u{2126}", "\u{03A9}"), // OHM SIGN
        ("\u{F900}", "\u{8C48}"), // CJK COMPATIBILITY IDEOGRAPH
        ("\u{212B}", "A"),        // ANGSTROM SIGN: singleton to A-ring, then stripped
    ] {
        assert_eq!(api::strip_accents(ch), folded, "{ch:?} alone");
        let with_mark = format!("{ch}e\u{0301}");
        assert_eq!(
            api::strip_accents(&with_mark),
            format!("{folded}e"),
            "{ch:?} beside a combining mark"
        );
    }
    // The borrowing fast path still borrows text that is NFC and carries no mark.
    assert!(matches!(
        api::strip_accents("\u{041C}\u{043E}\u{0441}\u{043A}\u{0432}\u{0430}"),
        std::borrow::Cow::Borrowed(_)
    ));
}

/// B2: an unknown `lang` is rejected by the fallible transliteration entry points and
/// by `try_slugify`, with the same InvalidArgument the key builders give.
#[test]
fn b2_unknown_lang_is_invalid_argument() {
    let kyiv = "\u{41A}\u{438}\u{457}\u{432}";
    for bad in ["UK", "russian", "xx", ""] {
        let t = Transliterate::new().lang(bad);
        assert_eq!(
            t.try_run(kyiv).unwrap_err().kind(),
            ErrorKind::InvalidArgument,
            "{bad:?}"
        );
        assert_eq!(
            t.try_find_untranslatable(kyiv).unwrap_err().kind(),
            ErrorKind::InvalidArgument
        );
        assert_eq!(
            api::try_slugify(kyiv, &SlugConfig::default().with_lang(bad))
                .unwrap_err()
                .kind(),
            ErrorKind::InvalidArgument
        );
        assert_eq!(
            api::validate_lang(bad).unwrap_err().kind(),
            ErrorKind::InvalidArgument
        );
        // The same message the key builders have always given.
        assert_eq!(
            t.try_run(kyiv).unwrap_err().to_string(),
            api::search_key(kyiv, Some(bad)).unwrap_err().to_string()
        );
    }
    assert_eq!(
        Transliterate::new().lang("uk").try_run(kyiv).unwrap(),
        "Kyiv"
    );
    for good in ["auto", "nb", "nn", "da", "de", "uk"] {
        assert!(api::validate_lang(good).is_ok(), "{good}");
    }
    assert_eq!(
        api::try_slugify("M\u{fc}nchen", &SlugConfig::default().with_lang("de")).unwrap(),
        "muenchen"
    );
    // No lang, nothing to reject.
    assert!(Transliterate::new().try_run(kyiv).is_ok());
    assert!(api::try_slugify(kyiv, &SlugConfig::default()).is_ok());
}

/// E1: the replacements `register_replacements` records are applied by the public
/// Rust API's fallible transliteration, as the docs say, and as Python does.
#[test]
fn e1_registered_replacements_reach_try_run() {
    let key = "zqxformalone";
    api::register_replacements([(key.to_owned(), "bar".to_owned())].into())
        .expect("registration is not sealed in this binary");
    let text = format!("a {key} b");
    assert_eq!(Transliterate::new().try_run(&text).unwrap(), "a bar b");
    // The finder sees the same post-replacement text.
    let found = Transliterate::new()
        .try_find_untranslatable(&format!("{key}\u{E000}"))
        .unwrap();
    assert_eq!(found.len(), 1);
    assert_eq!(found[0].offset, 3, "offset into the replaced text");
    // The infallible form is the tables alone, as documented. `run` is deprecated
    // (removed in 1.0); until then this pins what it does.
    #[allow(deprecated)]
    let tables_alone = Transliterate::new().run(&text);
    assert_eq!(tables_alone, text);
    assert!(api::remove_replacement(key).unwrap());
    assert_eq!(Transliterate::new().try_run(&text).unwrap(), text);
    // Nothing changed, so the result borrows the input.
    assert!(matches!(
        Transliterate::new().try_run("plain ascii").unwrap(),
        std::borrow::Cow::Borrowed(_)
    ));
}

/// D1: an emoji CLDR cannot name becomes the `[?]` sentinel, Python's documented
/// default, and `demojize_with` picks the policy.
#[test]
fn d1_unnameable_emoji_takes_the_sentinel() {
    let lone_ri = "\u{1F1E6}";
    assert_eq!(api::demojize(lone_ri, false), "[?]");
    assert_eq!(api::demojize_with(lone_ri, false, &OnUnknown::Ignore), "");
    assert_eq!(
        api::demojize_with(lone_ri, false, &OnUnknown::Preserve),
        lone_ri
    );
    assert_eq!(
        api::demojize_with(lone_ri, false, &OnUnknown::Replace("<?>".into())),
        "<?>"
    );
    // A lone tag character is the other bundled class.
    assert_eq!(api::demojize("\u{E0041}", false), "[?]");
    // Named emoji are unchanged.
    assert_eq!(api::demojize("\u{1F600}", false), "grinning face");
}

/// B1: the zalgo defaults every binding reads are the core's, and equal (#788).
#[test]
fn b1_zalgo_defaults_come_from_the_core() {
    assert_eq!(api::DEFAULT_ZALGO_THRESHOLD, 3);
    assert_eq!(api::DEFAULT_ZALGO_MAX_MARKS, api::DEFAULT_ZALGO_THRESHOLD);
    let three = "a\u{0316}\u{0317}\u{0318}";
    assert!(!api::is_zalgo(three, api::DEFAULT_ZALGO_THRESHOLD));
    assert_eq!(api::strip_zalgo(three, api::DEFAULT_ZALGO_MAX_MARKS), three);
}
