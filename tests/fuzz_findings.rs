//! The documented properties the #1040 fuzz targets found false, reproduced through the
//! public API.
//!
//! Each section is one finding, and each finding's fuzz target (`fuzz/fuzz_targets/`)
//! asserts the full property again now that it holds. The inputs are the ones the
//! fuzzers reported, or the smallest reproduction of them; see
//! `docs/architecture/testing-guarantees.md` under *Fuzzing* for the list.

use disarm::api::{
    find_confusables, find_unmapped_confusables, normalize_confusables, sanitize_filename, slugify,
    NormalizationForm, OnUnknown, Platform, SlugConfig, TargetScript, Transliterate,
};

fn nfc(s: &str) -> String {
    disarm::api::normalize(s, NormalizationForm::Nfc)
}

fn nfd(s: &str) -> String {
    disarm::api::normalize(s, NormalizationForm::Nfd)
}

// -- 1. slugify: a numeric entity that fails to decode --------------------------------
//
// It was skipped together with up to 14 bytes of the ASCII after it, stopping at the
// first non-ASCII byte. Now `&#` with no digit after it is text, as in HTML, and a run
// of digits that names no allowed character is dropped without what follows it.

#[test]
fn text_after_an_undecodable_entity_survives() {
    let config = SlugConfig::new();
    assert_eq!(slugify("Q&#A session", &config), "q-a-session");
    assert_eq!(slugify("Tom &#and Jerry", &config), "tom-and-jerry");
    // `&#12` is a control character, refused: the entity goes, the words stay.
    assert_eq!(slugify("issue &#12 fixed", &config), "issue-fixed");
    assert_eq!(slugify("a &#x; b", &config), "a-x-b");
    // A digit run too long for a scalar is dropped whole, not in part.
    let long = format!("a &#{} b", "9".repeat(40));
    assert_eq!(slugify(&long, &config), "a-b");
}

#[test]
fn entities_that_decode_still_decode() {
    let config = SlugConfig::new();
    assert_eq!(slugify("caf&#233;", &config), "cafe");
    assert_eq!(slugify("caf&#xe9;", &config), "cafe");
    assert_eq!(slugify("&#65;BC", &config), "abc");
    assert_eq!(slugify("&#X41;bc", &config), "abc");
    // Without the `;` the digit run still ends the entity.
    assert_eq!(slugify("caf&#233 au lait", &config), "cafe-au-lait");
    assert_eq!(slugify(&format!("&#{}66;c", "0".repeat(20)), &config), "bc");
}

/// Both spellings of the text around an entity give one slug (#477), which the skip
/// broke: it stopped at a composed letter and ran through its decomposition.
#[test]
fn an_entity_reads_the_same_in_both_normal_forms() {
    let config = SlugConfig::new().with_allow_unicode(true);
    for s in [
        "&#a\u{301}",
        "&#\u{e1}",
        "&#xa\u{301}",
        "&#x4a\u{301}b",
        "&#x\u{307}41;",
        "Q&#A\u{301} session",
        "&#12\u{301}",
    ] {
        assert_eq!(
            slugify(&nfc(s), &config),
            slugify(&nfd(s), &config),
            "NFC and NFD of {s:?}"
        );
    }
    assert_eq!(slugify("&#a\u{301}", &config), "\u{e1}");
    assert_eq!(slugify("&#x4a\u{301}b", &config), "\u{e1}b");
}

// -- 2. The locators report a character of the input, at its own offset -------------
//
// `find_unmapped_confusables`, `find_confusables` and `find_untranslatable` walk the
// composed clusters the fold and the engine look up, and reported every character of a
// cluster at the cluster's start, including a composed one the input did not contain.

/// Every report points at its character: `ch` starts `text[offset..]`.
fn assert_located(text: &str) {
    for &target in TargetScript::ALL {
        for m in find_confusables(text, target) {
            let rest = &text[m.offset..];
            assert!(rest.starts_with(m.ch), "{m:?} in {text:?} ({target})");
        }
        for u in find_unmapped_confusables(text, target) {
            let rest = &text[u.offset..];
            assert!(rest.starts_with(u.ch), "{u:?} in {text:?} ({target})");
        }
    }
    for t in [Transliterate::new(), Transliterate::new().lang("ru")] {
        for u in t.find_untranslatable(text) {
            let rest = &text[u.offset..];
            assert!(rest.starts_with(u.ch), "{u:?} in {text:?}");
        }
    }
}

#[test]
fn a_mark_that_composes_with_nothing_is_at_its_own_offset() {
    // U+04AA does not compose with U+0327: the cedilla is at 2, where it is.
    let found = find_unmapped_confusables("\u{4AA}\u{327}", TargetScript::Latin);
    assert!(
        found.iter().any(|u| (u.ch, u.offset) == ('\u{327}', 2)),
        "{found:?}"
    );
    // A variation selector is at its own offset, not its base's.
    let found = Transliterate::new().find_untranslatable("x\u{FE0F}");
    assert_eq!(found.len(), 1, "{found:?}");
    assert_eq!((found[0].ch, found[0].offset), ('\u{FE0F}', 1));
}

#[test]
fn a_decomposed_homoglyph_is_reported_as_written() {
    // U+0456 + U+0308 is looked up as U+0457, which the input does not contain: the
    // report is the base as written, with the composed character's fold as its target.
    let found = find_confusables("a\u{456}\u{308}", TargetScript::Latin);
    assert_eq!(found.len(), 1, "{found:?}");
    assert_eq!((found[0].ch, found[0].offset), ('\u{456}', 1));
    assert_eq!(
        found[0].target,
        normalize_confusables("\u{457}", TargetScript::Latin)
    );
}

#[test]
fn every_report_points_at_its_character() {
    for s in [
        "\u{4AA}\u{327}",
        "x\u{FE0F}",
        "\u{456}\u{308}",
        "\u{456}\u{308}\u{327}",
        // Shin + dagesh, whose composition U+FB49 is excluded from every normal form.
        "\u{5E9}\u{5BC}",
        "\u{5E9}\u{5BC}\u{5C1}",
        "n\u{5BC}\u{327}",
        "a\u{301}\u{323}",
        "\u{E1}\u{323}",
        "\u{915}\u{93C}\u{903}",
        "\u{9A1}\u{9BC}\u{983}",
        "\u{F40}\u{F72}\u{F71}",
        "\u{1100}\u{1161}\u{11A8}\u{301}",
        "\u{16D63}\u{16D67}\u{16D67}\u{16D67}",
        "c\u{327}\u{301}\u{FE00}",
    ] {
        assert_located(s);
        assert_located(&format!("x{s}y{s}"));
    }
    // A long run of marks stays linear and still located.
    assert_located(&format!("a{}", "\u{301}\u{323}\u{FE0F}".repeat(2000)));
}

// -- 3. find_untranslatable: a compatibility character recovered only in part -------
//
// U+1F240 is NFKC `\u{3014}\u{672C}\u{3015}`. The ideograph romanizes and the brackets
// do not, so `run` replaces the brackets, while `find_untranslatable` counted the
// character as recovered and reported nothing.

#[test]
fn a_partial_compatibility_recovery_is_reported() {
    let t = Transliterate::new();
    assert_eq!(t.run("\u{1F240}"), "[?]ben[?]");
    let found = t.find_untranslatable("x\u{1F240}y");
    assert_eq!(found.len(), 1, "{found:?}");
    assert_eq!((found[0].ch, found[0].offset), ('\u{1F240}', 1));
    // Reported exactly when the policies disagree on it.
    let ignore = t.clone().on_unknown(OnUnknown::Ignore).run("\u{1F240}");
    let preserve = t.clone().on_unknown(OnUnknown::Preserve).run("\u{1F240}");
    assert_ne!(ignore, preserve);
    // A compatibility character recovered whole is still not reported.
    assert!(t
        .find_untranslatable("\u{FB01}\u{1D400}\u{337F}")
        .is_empty());
}

/// The fuzz target's "nothing reported, so the three policies agree" check, which was
/// limited to input NFKC leaves alone, over the enclosed and squared CJK blocks.
#[test]
fn nothing_reported_means_the_policies_agree() {
    let t = Transliterate::new();
    for cp in (0x1F200..=0x1F2FF)
        .chain(0x3200..=0x33FF)
        .chain(0xFF00..=0xFFEF)
    {
        let Some(c) = char::from_u32(cp) else {
            continue;
        };
        let s = c.to_string();
        if !t.find_untranslatable(&s).is_empty() {
            continue;
        }
        let ignore = t.clone().on_unknown(OnUnknown::Ignore).run(&s);
        let preserve = t.clone().on_unknown(OnUnknown::Preserve).run(&s);
        let replace = t
            .clone()
            .on_unknown(OnUnknown::Replace("\u{1}".into()))
            .run(&s);
        assert_eq!(ignore, preserve, "U+{cp:04X}");
        assert_eq!(ignore, replace, "U+{cp:04X}");
    }
}

// -- 4. sanitize_filename: a fixed point, however many passes it takes ---------------
//
// Each pass stripped trailing separators and then trailing dots, once each, so a stem
// ending in separators and dots by turns lost one layer per pass, and the pass loop
// stops at eight: `"a" + ".*" * 9` gave `a._`, which sanitizes to `a`.

#[test]
fn a_run_of_empty_extensions_settles_in_one_call() {
    let sf = |s: &str, sep: &str, max: usize, platform: Platform, keep_ext: bool| {
        sanitize_filename(s, sep, max, platform, None, keep_ext).unwrap()
    };
    let nine = format!("a{}", ".*".repeat(9));
    assert_eq!(sf(&nine, "_", 255, Platform::Universal, false), "a");
    for n in [1, 7, 8, 9, 10, 64, 300] {
        for unit in [".*", ". ", ".?.", "*.", ". *", ".\u{2026}*"] {
            let s = format!("a{}b{}", unit.repeat(n), unit.repeat(n));
            for sep in ["_", "", "-", "--", "._"] {
                for platform in [Platform::Universal, Platform::Windows, Platform::Posix] {
                    for max in [0, 5, 255] {
                        for keep_ext in [false, true] {
                            let once = sf(&s, sep, max, platform, keep_ext);
                            let twice = sf(&once, sep, max, platform, keep_ext);
                            assert_eq!(twice, once, "{s:?} sep={sep:?} max={max} {keep_ext}");
                        }
                    }
                }
            }
        }
    }
}
