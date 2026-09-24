//! The documented properties the #1040 fuzz targets found false, reproduced through the
//! public API.
//!
//! Each section is one finding, and each finding's fuzz target (`fuzz/fuzz_targets/`)
//! asserts the full property again now that it holds. The inputs are the ones the
//! fuzzers reported, or the smallest reproduction of them; see
//! `docs/architecture/testing-guarantees.md` under *Fuzzing* for the list.

use disarm::api::{
    find_confusables, find_unmapped_confusables, normalize_confusables, slugify, NormalizationForm,
    SlugConfig, TargetScript, Transliterate,
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
