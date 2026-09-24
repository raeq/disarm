//! The documented properties the #1040 fuzz targets found false, reproduced through the
//! public API.
//!
//! Each section is one finding, and each finding's fuzz target (`fuzz/fuzz_targets/`)
//! asserts the full property again now that it holds. The inputs are the ones the
//! fuzzers reported, or the smallest reproduction of them; see
//! `docs/architecture/testing-guarantees.md` under *Fuzzing* for the list.

use disarm::api::{slugify, NormalizationForm, SlugConfig};

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
