//! The documented properties the #1040 fuzz targets found false, reproduced through the
//! public API.
//!
//! Each section is one finding, and each finding's fuzz target (`fuzz/fuzz_targets/`)
//! asserts the full property again now that it holds. The inputs are the ones the
//! fuzzers reported, or the smallest reproduction of them; see
//! `docs/architecture/testing-guarantees.md` under *Fuzzing* for the list.

use disarm::api::{
    catalog_key, catalog_key_with, find_confusables, find_unmapped_confusables, is_confusable,
    normalize_confusables, normalize_confusables_with, sanitize_filename, search_key,
    search_key_with, sort_key_with, try_slugify, DigitPolicy, NormalizationForm, OnUnknown,
    Platform, SlugConfig, TargetScript, Transliterate,
};

/// `try_slugify` for the configs these tests build, every one with a valid `lang` (or
/// none): the slug it returns is the one the deprecated infallible `slugify` returned.
fn slugify(text: &str, config: &SlugConfig) -> String {
    try_slugify(text, config).expect("a valid lang")
}

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
        for u in t.try_find_untranslatable(text).unwrap() {
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
    let found = Transliterate::new()
        .try_find_untranslatable("x\u{FE0F}")
        .unwrap();
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
    assert_eq!(t.try_run("\u{1F240}").unwrap(), "[?]ben[?]");
    let found = t.try_find_untranslatable("x\u{1F240}y").unwrap();
    assert_eq!(found.len(), 1, "{found:?}");
    assert_eq!((found[0].ch, found[0].offset), ('\u{1F240}', 1));
    // Reported exactly when the policies disagree on it.
    let ignore = t
        .clone()
        .on_unknown(OnUnknown::Ignore)
        .try_run("\u{1F240}")
        .unwrap();
    let preserve = t
        .clone()
        .on_unknown(OnUnknown::Preserve)
        .try_run("\u{1F240}")
        .unwrap();
    assert_ne!(ignore, preserve);
    // A compatibility character recovered whole is still not reported.
    assert!(t
        .try_find_untranslatable("\u{FB01}\u{1D400}\u{337F}")
        .unwrap()
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
        if !t.try_find_untranslatable(&s).unwrap().is_empty() {
            continue;
        }
        let ignore = t.clone().on_unknown(OnUnknown::Ignore).try_run(&s).unwrap();
        let preserve = t
            .clone()
            .on_unknown(OnUnknown::Preserve)
            .try_run(&s)
            .unwrap();
        let replace = t
            .clone()
            .on_unknown(OnUnknown::Replace("\u{1}".into()))
            .try_run(&s)
            .unwrap();
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

// -- 5. slugify: `allow_unicode` with an empty separator composes across words ------
//
// Joining the words with nothing can put two characters that compose side by side after
// the composing step has run: `"\u{1100} \u{1161}"` gave the two conjoining jamo, whose
// slug is U+AC00, and Kirat Rai U+16D67 does the same with itself.

#[test]
fn an_empty_separator_slug_is_its_own_slug() {
    let config = SlugConfig::new()
        .with_allow_unicode(true)
        .with_separator("");
    assert_eq!(slugify("\u{1100} \u{1161}", &config), "\u{AC00}");
    assert_eq!(slugify("\u{16D67},\u{16D67}", &config), "\u{16D68}");
    assert_eq!(slugify("\u{16D63}!\u{16D67}", &config), "\u{16D69}");
    for s in [
        "\u{1100} \u{1161}",
        "\u{1100}\u{1161} \u{11A8} x",
        "\u{16D67},\u{16D67},\u{16D67}",
        "a \u{301}b",
        "\u{915} \u{94D}\u{937}",
        "e! \u{302}\u{301}",
    ] {
        for lowercase in [true, false] {
            let config = SlugConfig::new()
                .with_allow_unicode(true)
                .with_separator("")
                .with_lowercase(lowercase);
            let once = slugify(s, &config);
            assert_eq!(slugify(&once, &config), once, "{s:?}");
        }
    }
    // A separator keeps the words apart, as it always did.
    let dashed = SlugConfig::new().with_allow_unicode(true);
    assert_eq!(slugify("\u{1100} \u{1161}", &dashed), "\u{1100}-\u{1161}");
}

// -- 8. slugify: an enclosed Latin letter comes from the separator, not the text -----
//
// The fuzz crash's options: `allow_unicode`, `max_length` 62, `save_order`, one empty
// stopword, entities decoded, and a separator of NULs, a slash, U+24B6 and `d`. The
// U+24B6 in the slug is the separator's, inserted as given between `m` and `p`; the text
// never contributes one, which is the property `allow_unicode` documents (#1028).

#[test]
fn an_enclosed_latin_letter_in_the_slug_is_the_separators() {
    let sep = "\0\0\0\0/\0\0\0\0\0\0\0\0\0\0\0\u{24B6}d";
    let config = || {
        SlugConfig::new()
            .with_separator(sep)
            .with_max_length(62)
            .with_save_order(true)
            .with_stopwords([""])
            .with_allow_unicode(true)
    };
    assert_eq!(slugify("\u{FFFD}!M\0p\0", &config()), format!("m{sep}p"));
    // The text's own U+24B6 is dropped under the same options: no word of the slug
    // carries one.
    let out = slugify("\u{24B6}dmin \u{24B6} x\u{24B6}y", &config());
    for word in out.split(sep) {
        assert!(!word.contains('\u{24B6}'), "{word:?} in {out:?}");
    }
    assert_eq!(out, format!("dmin{sep}x{sep}y"));
}

// -- 7. The key builders end in NFC ------------------------------------------------
//
// `catalog_key` and `search_key` strip controls after the last step that composes, so a
// control between two characters that compose left them apart until the next call:
// Kirat Rai U+16D67 U+0016 U+16D67 keyed as the two vowel signs, and the key of that is
// U+16D68. The fuzz crash was `U+FFFD U+FFFD U+16D67 U+0016 U+16D67` with no options,
// so under the default policy; every policy failed the same way.

#[test]
fn a_key_is_its_own_key_across_a_stripped_control() {
    type Key = fn(&str, DigitPolicy) -> String;
    let keys: [(&str, Key); 4] = [
        ("catalog_key", |s, p| {
            catalog_key_with(s, None, false, p).unwrap().into_owned()
        }),
        ("catalog_key strict_iso9", |s, p| {
            catalog_key_with(s, None, true, p).unwrap().into_owned()
        }),
        ("search_key", |s, p| {
            search_key_with(s, None, p).unwrap().into_owned()
        }),
        ("sort_key", |s, p| {
            sort_key_with(s, None, p).unwrap().into_owned()
        }),
    ];
    let crash = "\u{FFFD}\u{FFFD}\u{16D67}\u{16}\u{16D67}";
    for (name, key) in keys {
        for policy in [
            DigitPolicy::Numeric,
            DigitPolicy::Tr39,
            DigitPolicy::Preserve,
        ] {
            for s in [
                crash,
                "\u{16D67}\0\u{16D67}",
                "\u{16D63}\u{1}\u{16D67}",
                "\u{16D69}\u{7F}\u{16D67}",
                "x\u{16D67}\u{200B}\u{16D67}y",
            ] {
                let once = key(s, policy);
                assert_eq!(key(&once, policy), once, "{name} ({policy}) on {s:?}");
            }
            assert_eq!(
                key(crash, policy),
                "\u{FFFD}\u{FFFD}\u{16D68}",
                "{name} ({policy})"
            );
        }
    }
    // The public defaults are the `Numeric` builders, byte for byte.
    assert_eq!(
        catalog_key("\u{16D63}\u{1}\u{16D67}", None, false).unwrap(),
        "\u{16D69}"
    );
    assert_eq!(
        search_key("\u{16D67}\0\u{16D67}", None).unwrap(),
        "\u{16D68}"
    );
}

// -- 9. normalize_confusables: a fold cycle outlasted the pass cap -------------------

/// Found on 2026-09-26. `C` + U+0327 composes to `Ç`, which folds back to `C`, so each
/// pass takes one cedilla, and the loop stopped after eight. Nine cedillas tripped its
/// debug assertion; from ten, the fold was not idempotent and what it returned was still
/// confusable. The `c` and `i` + U+0309 cycles are the other two the tables hold.
#[test]
fn a_fold_cycle_takes_every_mark_however_many() {
    for (base, mark) in [("C", "\u{327}"), ("c", "\u{327}"), ("i", "\u{309}")] {
        for n in [9, 10, 64, 10_000] {
            let text = format!("{base}{}", mark.repeat(n));
            for policy in [
                DigitPolicy::Numeric,
                DigitPolicy::Tr39,
                DigitPolicy::Preserve,
            ] {
                let once = normalize_confusables_with(&text, TargetScript::Latin, policy);
                assert_eq!(once, base, "{base} + {n} marks ({policy})");
            }
            assert!(!is_confusable(
                &normalize_confusables(&text, TargetScript::Latin),
                TargetScript::Latin
            ));
        }
    }
    // The reported input, with a mark of another class after the run.
    let crash = "A. \u{FFFD}\u{FFFD}\u{3AA}\u{4AA}\u{327}\u{32A}\u{327}\u{327}\u{327}\
                 \u{327}\u{32A}\u{327}\u{327}\u{327}\u{32C}\u{FFFD}\u{F37C}\u{FFFD}\
                 \u{FFFD}\u{F37C}\u{FFFD}\u{FFFD}";
    let once = normalize_confusables(crash, TargetScript::Latin);
    assert_eq!(normalize_confusables(&once, TargetScript::Latin), once);
    assert!(once.contains("C\u{32A}\u{32A}\u{32C}"), "{once:?}");
}

/// The same cycles in the presets' and the pipeline's own fold loops, which iterate the
/// fold and NFC (or NFKC, with a case fold in `skeleton_key`) under the same cap: the
/// nightly run's input made `canonicalize_strict` return `Ç` and then `C`, and
/// `skeleton_key` return `ç` and then `c`.
#[test]
fn every_preset_takes_every_mark_of_a_fold_cycle() {
    use disarm::api as d;
    let crash = "A. \u{FFFD}\u{FFFD}\u{3AA}\u{4AA}\u{327}\u{32A}\u{327}\u{327}\u{327}\
                 \u{327}\u{32A}\u{327}\u{327}\u{327}\u{32C}\u{FFFD}\u{F37C}\u{FFFD}\
                 \u{FFFD}\u{F37C}\u{FFFD}\u{FFFD}";
    let mut inputs = vec![crash.to_owned()];
    for (base, mark) in [("C", "\u{327}"), ("c", "\u{327}"), ("i", "\u{309}")] {
        for n in [9, 10, 64, 2_000] {
            inputs.push(format!("{base}{}", mark.repeat(n)));
        }
    }
    let profiles = d::list_profiles();
    for s in &inputs {
        let head: String = s.chars().take(12).collect();
        for policy in [
            DigitPolicy::Numeric,
            DigitPolicy::Tr39,
            DigitPolicy::Preserve,
        ] {
            let builders: [(&str, &dyn Fn(&str) -> String); 7] = [
                ("canonicalize", &|t| {
                    d::canonicalize_with(t, policy).unwrap().into_owned()
                }),
                ("canonicalize_strict", &|t| {
                    d::canonicalize_strict_with(t, policy).unwrap().into_owned()
                }),
                ("strip_obfuscation", &|t| {
                    d::strip_obfuscation_with(t, policy).unwrap().into_owned()
                }),
                ("catalog_key", &|t| {
                    catalog_key_with(t, None, false, policy)
                        .unwrap()
                        .into_owned()
                }),
                ("search_key", &|t| {
                    search_key_with(t, None, policy).unwrap().into_owned()
                }),
                ("sort_key", &|t| {
                    sort_key_with(t, None, policy).unwrap().into_owned()
                }),
                ("skeleton_key", &|t| {
                    d::skeleton_key(t, policy).unwrap().into_owned()
                }),
            ];
            for (name, f) in builders {
                let once = f(s);
                assert_eq!(f(&once), once, "{name} ({policy}) on {head:?}...");
            }
        }
        for profile in &profiles {
            let pipe = d::get_pipeline(profile).unwrap();
            let once = pipe.process(s).unwrap();
            assert_eq!(
                pipe.process(&once).unwrap(),
                once,
                "{profile} on {head:?}..."
            );
        }
    }
}

// -- 10. canonicalize: the fold moves a mark past the cap ------------------------------

/// Found on 2026-09-26 by the `presets` target. The cap (three marks of one class on a
/// base) ran before the confusable fold, and the fold turned `ģ` (a cedilla, below) into
/// `ġ` (a dot, above): `ǧ` + U+0327 with three marks above kept all three, and then the
/// `g` carried four above, which the next call cut. Only `numeric`: the other policies
/// fold before the cap as well.
#[test]
fn canonicalize_caps_a_mark_the_fold_moved() {
    use disarm::api::canonicalize_with;
    let found = "\u{1E7}\u{327}\u{367}\u{327}\u{327}\u{327}\u{303}";
    for policy in [
        DigitPolicy::Numeric,
        DigitPolicy::Tr39,
        DigitPolicy::Preserve,
    ] {
        let once = canonicalize_with(found, policy).unwrap().into_owned();
        assert_eq!(once, "\u{121}\u{30C}\u{367}", "{policy}");
        assert_eq!(canonicalize_with(&once, policy).unwrap(), once, "{policy}");
    }
}
