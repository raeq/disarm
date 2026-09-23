//! Regression tests for the slug findings of the Lean model of the output sanitizers
//! (`formal/lean/Sanitizers/README.md`), on the Layer-2 API the bindings call.
//!
//! Each test names its finding. Finding 9 (`UniqueSlugifier`) is a binding-layer type; its
//! candidate builder is in the core and is tested beside it in `src/slugify.rs`.

use disarm::api::{slugify, SlugConfig};

fn unicode() -> SlugConfig {
    SlugConfig::new().with_allow_unicode(true)
}

// -- Finding 4: `allow_unicode` kept 130 `Other_Alphabetic` symbols ----------------------

#[test]
fn finding_4_circled_letters_are_symbols_not_letters() {
    // U+24B6 CIRCLED LATIN CAPITAL LETTER A: `So`, and `Alphabetic` through
    // `Other_Alphabetic`. It lowercased to U+24D0 and stayed.
    assert_eq!(slugify("\u{24B6}dmin", &unicode()), "dmin");
    assert_eq!(slugify("x\u{24B6}y", &unicode()), "x-y");
}

#[test]
fn finding_4_every_alphabetic_symbol_is_a_separator() {
    let ranges = [
        0x24B6..=0x24E9,
        0x1F130..=0x1F149,
        0x1F150..=0x1F169,
        0x1F170..=0x1F189,
    ];
    let mut count = 0;
    for cp in ranges.into_iter().flatten() {
        let ch = char::from_u32(cp).unwrap();
        // The premise: `char::is_alphanumeric` accepts every one of them.
        assert!(ch.is_alphanumeric(), "U+{cp:04X} premise");
        let text = format!("a{ch}b");
        assert_eq!(slugify(&text, &unicode()), "a-b", "U+{cp:04X}");
        assert_eq!(
            slugify(&text, &unicode().with_lowercase(false)),
            "a-b",
            "U+{cp:04X}, lowercase = false"
        );
        count += 1;
    }
    assert_eq!(count, 130);
}

#[test]
fn finding_4_letters_digits_and_marks_are_still_kept() {
    // Neighbours of the excluded ranges that are letters or digits stay.
    assert_eq!(slugify("\u{2460}", &unicode()), "\u{2460}"); // CIRCLED DIGIT ONE, No
    assert_eq!(slugify("\u{2170}", &unicode()), "\u{2170}"); // SMALL ROMAN NUMERAL ONE, Nl
    assert_eq!(slugify("caf\u{E9}", &unicode()), "caf\u{E9}");
    assert_eq!(slugify("\u{915}\u{93F}", &unicode()), "\u{915}\u{93F}"); // Devanagari ki
}

// -- Finding 13: a truncated `allow_unicode` slug could end in a joiner ------------------

#[test]
fn finding_13_plain_cut_never_ends_in_a_joiner() {
    let cfg = unicode().with_max_length(4);
    assert_eq!(slugify("a\u{200D}b", &cfg), "a");
    assert_eq!(slugify("a\u{200C}b", &cfg), "a");
}

#[test]
fn finding_13_word_boundary_cut_never_ends_in_a_joiner() {
    let cfg = unicode().with_max_length(4).with_word_boundary(true);
    assert_eq!(slugify("a\u{200C}b", &cfg), "a");
    assert_eq!(slugify("a\u{200D}b", &cfg), "a");
    // With no separator there are no words, and the cut is cleaned the same way.
    let cfg = cfg.with_separator("");
    assert_eq!(slugify("a\u{200D}b", &cfg), "a");
}

#[test]
fn finding_13_no_cut_ends_in_a_joiner() {
    let texts = [
        "a\u{200D}b c\u{200C}d",
        "\u{915}\u{94D}\u{200D}\u{937} x",
        "\u{645}\u{6CC}\u{200C}\u{631}\u{648}\u{645}",
        "\u{1F468}\u{200D}\u{1F469}\u{200D}\u{1F467} a\u{200D}b",
    ];
    for text in texts {
        for word_boundary in [false, true] {
            for max in 1..=text.len() + 1 {
                let cfg = unicode()
                    .with_max_length(max)
                    .with_word_boundary(word_boundary);
                let slug = slugify(text, &cfg);
                assert!(slug.len() <= max);
                assert!(
                    !slug.ends_with(['\u{200C}', '\u{200D}']),
                    "{text:?} max {max} wb {word_boundary}: {slug:?}"
                );
                assert!(!slug.ends_with('-'), "{text:?} max {max}: {slug:?}");
            }
        }
    }
}

// -- Finding 10: composition ran before lowercasing -------------------------------------

#[test]
fn finding_10_lowercasing_then_composing_is_nfc() {
    // `T` + U+0308 has no precomposed form; `t` + U+0308 composes to U+1E97.
    assert_eq!(slugify("T\u{308}", &unicode()), "\u{1E97}");
    assert_eq!(slugify("\u{1E97}", &unicode()), "\u{1E97}");
    assert_eq!(slugify("t\u{308}", &unicode()), "\u{1E97}");
    // Idempotent.
    let once = slugify("T\u{308}", &unicode());
    assert_eq!(slugify(&once, &unicode()), once);
    // Without lowercasing nothing composes, and nothing changes.
    let cfg = unicode().with_lowercase(false);
    assert_eq!(slugify("T\u{308}", &cfg), "T\u{308}");
}

// -- Finding 5: plain truncation left a partial multi-character separator ---------------

#[test]
fn finding_5_plain_cut_strips_a_partial_separator() {
    let cfg = SlugConfig::new().with_separator("-_").with_max_length(2);
    assert_eq!(slugify("a b", &cfg), "a");
    // The word-boundary branch already did.
    assert_eq!(slugify("a b", &cfg.with_word_boundary(true)), "a");
    // A whole separator is still stripped.
    let cfg = SlugConfig::new().with_separator("-_").with_max_length(3);
    assert_eq!(slugify("a b", &cfg), "a");
    let cfg = SlugConfig::new().with_separator("--").with_max_length(4);
    assert_eq!(slugify("ab cd", &cfg), "ab");
}

// -- Finding 6: `word_boundary` dropped a whole word it had room for -------------------

#[test]
fn finding_6_a_cut_on_a_word_end_keeps_the_word() {
    let cfg = SlugConfig::new()
        .with_max_length(9)
        .with_word_boundary(true);
    assert_eq!(slugify("very long title here", &cfg), "very-long");
    // The documented examples are unchanged.
    let cfg = SlugConfig::new()
        .with_max_length(10)
        .with_word_boundary(true);
    assert_eq!(slugify("Very Long Title Here", &cfg), "very-long");
    assert_eq!(slugify("a very long title here", &cfg), "a-very");
    // A multi-character separator.
    let cfg = SlugConfig::new()
        .with_separator("--")
        .with_max_length(4)
        .with_word_boundary(true);
    assert_eq!(slugify("abcd ef", &cfg), "abcd");
    // Under `allow_unicode` the cut is a cluster boundary, and the rule is the same.
    let cfg = unicode().with_max_length(6).with_word_boundary(true);
    assert_eq!(
        slugify("\u{D55C}\u{AD6D} \u{C5B4}", &cfg),
        "\u{D55C}\u{AD6D}"
    );
}

// -- Finding 7: stopwords were not case-insensitive -------------------------------------

#[test]
fn finding_7_stopwords_are_case_insensitive() {
    let cfg = SlugConfig::new().with_stopwords(["The"]);
    assert_eq!(slugify("The Fox", &cfg), "fox");
    let cfg = SlugConfig::new().with_stopwords(["THE", "fOX"]);
    assert_eq!(slugify("the quick fox", &cfg), "quick");
    // With `lowercase = false` the slug keeps its case and the match still ignores it.
    let cfg = SlugConfig::new()
        .with_lowercase(false)
        .with_stopwords(["the"]);
    assert_eq!(slugify("The Fox", &cfg), "Fox");
    let cfg = SlugConfig::new()
        .with_lowercase(false)
        .with_stopwords(["THE"]);
    assert_eq!(slugify("the Fox", &cfg), "Fox");
    // `save_order` too.
    let cfg = SlugConfig::new()
        .with_save_order(true)
        .with_stopwords(["The"]);
    assert_eq!(slugify("The Fox the Hen The", &cfg), "fox-the-hen");
    // Non-ASCII.
    let cfg = unicode().with_stopwords(["\u{C4}RGER"]);
    assert_eq!(slugify("\u{C4}rger im B\u{FC}ro", &cfg), "im-b\u{FC}ro");
    let cfg = unicode()
        .with_lowercase(false)
        .with_stopwords(["\u{E4}rger"]);
    assert_eq!(slugify("\u{C4}rger im B\u{FC}ro", &cfg), "im-B\u{FC}ro");
}

// -- Finding 8: an empty separator filtered stopwords character by character ------------

#[test]
fn finding_8_an_empty_separator_has_no_words_to_filter() {
    let cfg = SlugConfig::new().with_separator("").with_stopwords(["b"]);
    assert_eq!(slugify("abc", &cfg), "abc");
    assert_eq!(slugify("a b c", &cfg), "abc");
    let cfg = cfg.with_save_order(true);
    assert_eq!(slugify("bab", &cfg), "bab");
}

// -- Finding 11: the mark cap counts a precomposed base's own marks ---------------------

#[test]
fn finding_11_a_precomposed_base_keeps_its_own_marks_and_gains_none() {
    use unicode_normalization::char::is_combining_mark;
    use unicode_normalization::UnicodeNormalization;
    let marks = |s: &str| s.nfd().filter(|c| is_combining_mark(*c)).count();
    // U+1F82: alpha with psili, varia and ypogegrammeni, three marks in its NFD.
    let slug = slugify("\u{1F82}", &unicode());
    assert_eq!(slug, "\u{1F82}");
    assert_eq!(marks(&slug), 3);
    // A fourth mark is not added to it.
    assert_eq!(slugify("\u{1F82}\u{301}", &unicode()), "\u{1F82}");
    // A base with fewer is capped at two, counted over its decomposition.
    assert_eq!(marks(&slugify("a\u{301}\u{302}\u{303}", &unicode())), 2);
    assert_eq!(marks(&slugify("\u{E0}\u{301}\u{302}", &unicode())), 2);
}
