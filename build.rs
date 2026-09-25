//! Build script: generates PHF (perfect hash function) maps from data files.
//!
//! This avoids proc-macro overhead (`phf_macros`) by running the PHF
//! computation once during `build.rs`, writing the generated Rust code
//! to `$OUT_DIR`. Source files then `include!()` the output.
//!
//! Data files live in `src/tables/data/` as simple TSV (tab-separated):
//!   - char→str maps: `HEXCODEPOINT\tvalue`
//!   - str→str maps:  `key\tvalue`
//!   - char sets:      `HEXCODEPOINT`

use std::cmp::Ordering;
use std::collections::BTreeSet;
use std::env;
use std::fmt::Write as _;
use std::fs;
use std::path::{Path, PathBuf};

#[path = "codegen/arrays.rs"]
mod arrays;
#[path = "codegen/confusables.rs"]
mod confusables;
#[path = "codegen/norm_boundary.rs"]
mod norm_boundary;
#[path = "codegen/phf_tables.rs"]
mod phf_tables;
#[path = "codegen/ranges.rs"]
mod ranges;
#[path = "codegen/readers.rs"]
mod readers;

use arrays::{build_dense_interned_array, generate_emoji_trie, generate_translit_flat_array};
use confusables::{inject_folding_singleton_rows, is_latin_letter, COMMON_SCRIPT_TARGETS};
use phf_tables::{
    build_char_str_map, escape_str, generate_char_set, generate_char_str_map,
    generate_excluded_compositions_map, generate_str_str_map,
};
use ranges::{
    generate_bidi_strong_ranges, generate_decimal_digit_zeros, generate_prototype_census,
    generate_range_set, generate_width_ranges,
};
use readers::{
    read_char_set_tsv, read_char_str_tsv, read_confusables_version, read_range_tsv,
    read_str_str_tsv,
};

/// Every bundled confusables table: `(script token, TSV file name, generated ident)`.
///
/// One list, because there were three before this: the Latin and Cyrillic tables were
/// built by hand-written blocks, Arabic and Hebrew by a loop, and the upstream-version
/// agreement check compared only the first two. #792 added two tables and the check did
/// not notice (#849 review). Adding a target here now reaches the version check for free.
const CONFUSABLE_TABLES: [(&str, &str, &str); 4] = [
    ("latin", "confusables_to_latin.tsv", "TO_LATIN"),
    ("cyrillic", "confusables_to_cyrillic.tsv", "TO_CYRILLIC"),
    ("arabic", "confusables_to_arabic.tsv", "TO_ARABIC"),
    ("hebrew", "confusables_to_hebrew.tsv", "TO_HEBREW"),
];

fn main() {
    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    let data_dir = Path::new("src/tables/data");

    // Tell Cargo to re-run only when data files change
    println!("cargo:rerun-if-changed=src/tables/data");
    println!("cargo:rerun-if-changed=build.rs");

    // --- Hanzi Pinyin ---
    {
        let entries = read_char_str_tsv(&data_dir.join("hanzi_pinyin.tsv"));
        assert!(
            entries.len() >= 20_000,
            "hanzi_pinyin.tsv: expected ≥20,000 entries, got {}",
            entries.len()
        );
        for (&cp, value) in &entries {
            assert!(
                value.is_ascii(),
                "hanzi_pinyin.tsv: non-ASCII value {value:?} for U+{cp:04X}"
            );
            assert!(
                (0x4E00..=0x9FFF).contains(&cp),
                "hanzi_pinyin.tsv: U+{cp:04X} outside the CJK Unified block; \
                 the dense table (#237 item 2) covers only U+4E00–U+9FFF"
            );
        }
        // #237 item 2: the toneless table is ~99.7% dense over U+4E00–U+9FFF
        // (20,924 of 20,992 cps), so a flat interned id array beats a PHF on both
        // size (~50 KB vs ~600 KB) and lookup cost (no hashing). The sparse toned
        // table below stays a PHF.
        let code = build_dense_interned_array(
            &entries,
            0x4E00,
            0x9FFF - 0x4E00 + 1,
            "HANZI_PINYIN",
            "pub",
        );
        fs::write(out_dir.join("hanzi_pinyin_phf.rs"), code).unwrap();
    }

    // --- Hanzi Pinyin (toned) ---
    generate_char_str_map(
        &data_dir.join("hanzi_pinyin_toned.tsv"),
        &out_dir.join("hanzi_pinyin_toned_phf.rs"),
        "HANZI_PINYIN_TONED",
        "pub",
    );

    // --- Confusables (Latin target) ---
    // H1 invariant (#38): `api::normalize_confusables` / `api::is_confusable` are
    // infallible because every `TargetScript` variant maps to a populated table.
    // build.rs is a separate compilation unit and cannot call the crate's
    // `resolve_confusable_map`, so the guarantee is encoded here: these two blocks
    // assert the source TSVs backing the Latin and Cyrillic maps are non-empty. If
    // either were ever dropped, this build fails rather than the Layer-2 `.expect()`
    // panicking at runtime.
    {
        let mut entries = read_char_str_tsv(&data_dir.join("confusables_to_latin.tsv"));
        // #481: a canonical singleton resolves as its target. Add the row only when the
        // target itself folds (is already a confusable) — that is the real recovery gap
        // (U+1F77 GREEK IOTA WITH OXIA should fold like its tonos form U+03AF). When the
        // target does NOT fold, the singleton is a benign passthrough re-encoding (two
        // encodings of the same non-Latin letter); minting a row there would put a
        // non-Latin value in the to-Latin table and make the fold a partial normalizer.
        inject_folding_singleton_rows(&data_dir.join("canonical_singletons.tsv"), &mut entries);
        assert!(
            entries.len() >= 1_000,
            "confusables_to_latin.tsv: expected ≥1,000 entries, got {}",
            entries.len()
        );
        // #831: a non-ASCII VALUE is now permitted in this table, and only under two
        // conditions. Every row was ASCII before — 2,220 of 2,220, unasserted — and the
        // LGR rows cannot be: folding `\u{17c}` ż to `z` merges it with the bare letter,
        // which that registry does not block, and is the over-collapse `search_key`
        // already commits.
        //
        // The two conditions are what make it safe, so they are checked rather than
        // trusted. A non-ASCII target must be a Latin LETTER — the table maps onto Latin,
        // and a Greek or Cyrillic target would make the fold a partial transliterator —
        // and it must not itself be a source, or the fold takes more than one step and
        // the fixed-point loop has work to do that it should not.
        for (&cp, value) in &entries {
            if value.is_ascii() {
                continue;
            }
            for ch in value.chars() {
                assert!(
                    is_latin_letter(ch) || COMMON_SCRIPT_TARGETS.contains(&ch),
                    "confusables_to_latin.tsv: U+{cp:04X} maps to {value:?}, which is not \
                     Latin. A non-ASCII target must stay inside the script this table \
                     folds toward, or be listed in COMMON_SCRIPT_TARGETS (#831)."
                );
            }
            let target: Vec<char> = value.chars().collect();
            // EVERY character of the target, not just a single-character one (#723).
            //
            // The `len() == 1` form let `044B` -> `\u{0185}i` through: the target is two
            // characters, and `0185` is itself a source that folds to `b`. So the
            // iterating entry points reached `bi` and the single-pass ones stopped at
            // `\u{0185}i` — `strip_obfuscation` was not a fixed point, and the exhaustive
            // idempotence gate tested only the function that iterates.
            //
            // A multi-character target is not exempt from the rule; it was exempt from
            // the check.
            for (i, &ch) in target.iter().enumerate() {
                assert!(
                    !entries.contains_key(&(ch as u32)),
                    "confusables_to_latin.tsv: U+{cp:04X} maps to {value:?}, whose \
                     character {i} (U+{:04X}) is itself a source. That chains the fold, \
                     so a single-pass caller stops one step short of the fixed point the \
                     iterating ones reach (#831, #723).",
                    ch as u32
                );
            }
        }

        let code = build_char_str_map(&entries, "TO_LATIN", "");
        fs::write(out_dir.join("confusables_phf.rs"), code).unwrap();

        // ASCII confusable sources for the preset fast-path guard (#458). The
        // guard skips the whole pipeline on benign input that no step can change;
        // it must therefore know which ASCII bytes the confusable fold rewrites
        // (today 0x22 `"`→`''`, 0x60 `` ` ``→`'`, 0x7C `|`→`l`). Derive that set
        // from the data here, as a `[bool; 128]`, so it can never silently rot if
        // the table gains or drops an ASCII source — the guard stays pure byte
        // arithmetic at runtime while staying in lockstep with the PHF data.
        let mut ascii = [false; 128];
        for (&cp, value) in &entries {
            if cp < 128 && *value != char::from_u32(cp).unwrap().to_string() {
                ascii[cp as usize] = true;
            }
        }
        let flags: String = ascii
            .iter()
            .map(|b| if *b { "true," } else { "false," })
            .collect();
        fs::write(
            out_dir.join("ascii_confusable_latin.rs"),
            format!(
                "// Generated by build.rs (#458). ASCII codepoints (0x00–0x7F) the\n\
                 // confusables→latin map rewrites; used by the preset fast-path guard.\n\
                 pub(crate) static ASCII_CONFUSABLE_LATIN: [bool; 128] = [{flags}];\n"
            ),
        )
        .unwrap();
    }

    // --- Confusables (Cyrillic target) ---
    {
        let mut entries = read_char_str_tsv(&data_dir.join("confusables_to_cyrillic.tsv"));
        inject_folding_singleton_rows(&data_dir.join("canonical_singletons.tsv"), &mut entries);
        assert!(
            !entries.is_empty(),
            "confusables_to_cyrillic.tsv: expected ≥1 entries, got 0",
        );
        let code = build_char_str_map(&entries, "TO_CYRILLIC", "");
        fs::write(out_dir.join("confusables_to_cyrillic_phf.rs"), code).unwrap();
    }

    // --- Confusables (Arabic and Hebrew targets, #792) ---
    // The RTL targets. 948 of TR39's 1,007 strong-RTL sources were unmapped under both
    // existing targets (#791), because generation drops a class entirely when no member
    // belongs to the target script — so a class whose members are all Arabic survived
    // into neither table. No `inject_folding_singleton_rows` here: that pass (#481) is
    // about a canonical singleton resolving as its target, and both of these tables are
    // generated from classes whose target is already the script's own letter.
    for &(script, table, ident) in &CONFUSABLE_TABLES[2..] {
        let entries = read_char_str_tsv(&data_dir.join(table));
        assert!(!entries.is_empty(), "{table}: expected ≥1 entries, got 0");
        let code = build_char_str_map(&entries, ident, "");
        fs::write(
            out_dir.join(format!("confusables_to_{script}_phf.rs")),
            code,
        )
        .unwrap();
    }

    // --- Bundled confusables.txt version (#560) ---
    // The upstream version is already written in the TSV header line that
    // `read_char_str_tsv` skips as a comment. Parse it here and emit it as a const so a
    // running program can answer "am I stale?" without inferring it from behaviour.
    // `read_confusables_version` panics unless the header still matches the expected
    // shape, which is the build-time assertion the acceptance criteria ask for: the
    // constant cannot silently go stale, and the version is never typed a second time.
    {
        // Every bundled confusables table, not just the first two. #792 added Arabic and
        // Hebrew, and this check kept comparing Latin against Cyrillic — so a mixed
        // upstream release would have shipped with one CONFUSABLES_VERSION describing
        // four tables it no longer described (#849 review). Derived from the table list
        // above rather than written out again, so the next target is covered by adding it
        // in one place.
        let versions: Vec<(&str, String)> = CONFUSABLE_TABLES
            .iter()
            .map(|(script, table, _)| (*script, read_confusables_version(&data_dir.join(table))))
            .collect();
        let (first_script, first) = &versions[0];
        for (script, version) in &versions[1..] {
            assert_eq!(
                first, version,
                "confusables tables disagree on the upstream version ({first_script} \
                 {first}, {script} {version}); all are generated from one confusables.txt \
                 release, so a single CONFUSABLES_VERSION const no longer covers them. \
                 Either regenerate them all from the same release, or split the const per \
                 table."
            );
        }
        let latin = first.clone();
        fs::write(
            out_dir.join("confusables_version.rs"),
            format!(
                "// Generated by build.rs (#560) from the confusables TSV header line.\n\
                 pub const CONFUSABLES_VERSION: &str = {latin:?};\n"
            ),
        )
        .unwrap();
    }

    // --- Normalization UCD version (#642, #645) ---
    // Same discipline as CONFUSABLES_VERSION above: read from the thing it describes, never
    // typed twice. `unicode-normalization` publishes the value as a `(u64, u64, u64)`, and
    // the public surface is a `&str` to match `CONFUSABLES_VERSION`, so the formatting
    // happens here rather than needing a const-format dependency at runtime.
    {
        let (major, minor, patch) = unicode_normalization::UNICODE_VERSION;
        let version = format!("{major}.{minor}.{patch}");
        fs::write(
            out_dir.join("unicode_version.rs"),
            format!(
                "// Generated by build.rs (#645) from `unicode_normalization::UNICODE_VERSION`.\n\
                 /// The UCD release the normalizer implements, as `\"major.minor.patch\"`.\n\
                 ///\n\
                 /// Read from the crate that does the normalizing rather than typed a second\n\
                 /// time, so it cannot drift from the tables it names. Re-exported publicly as\n\
                 /// [`crate::api::UNICODE_VERSION`].\n\
                 pub(crate) const UNICODE_VERSION: &str = {version:?};\n"
            ),
        )
        .unwrap();
    }

    // --- Normalization-boundary bitmaps ---
    // Which BMP characters the normalizer can skip, per form, from the same crate that
    // normalizes (see codegen/norm_boundary.rs and src/normalize.rs).
    norm_boundary::generate(&out_dir);

    // --- Digit-policy overrides (#561) ---
    // The rows where disarm folds a non-Latin digit to the ASCII DIGIT and TR39 folds it
    // to a letter. An override SET, not a second table: the two policies agree on every
    // other row, so shipping one table plus ~45 overrides makes it impossible for them to
    // drift where they agree.
    {
        let entries = read_char_str_tsv(&data_dir.join("confusables_digit_tr39.tsv"));
        assert!(
            !entries.is_empty(),
            "confusables_digit_tr39.tsv: expected ≥1 override, got 0 — \
             regenerate with scripts/gen_confusables.py"
        );
        for (&cp, value) in &entries {
            assert!(
                !value.is_empty(),
                "confusables_digit_tr39.tsv: empty target for U+{cp:04X}"
            );
            // #587: this set was written after #341 made ASCII the contract for the
            // Latin tables, and never joined it — TR39's raw targets put `Ʌ` (U+0245)
            // and `º` (U+00BA) straight back. The generator now runs each override
            // through ASCII_FOLD and drops any row whose divergence has no ASCII form,
            // so the invariant is real and worth asserting rather than assumed.
            assert!(
                value.is_ascii(),
                "confusables_digit_tr39.tsv: non-ASCII target {value:?} for \
                 U+{cp:04X}; the override set is ASCII only (#341/#587). Regenerate \
                 with scripts/gen_confusables.py, which folds or drops such a row."
            );
        }
        let code = build_char_str_map(&entries, "DIGIT_TR39", "");
        fs::write(out_dir.join("confusables_digit_tr39_phf.rs"), code).unwrap();
    }

    // --- Contraction rules (#562) ---
    // Multi-codepoint SOURCE -> single-codepoint target, the inverse of the expansion
    // rows the confusable tables already carry. Emitted as a sorted slice rather than a
    // PHF: the set is tiny and the consumer builds one Aho-Corasick automaton over it,
    // so a hash map would buy nothing.
    {
        let entries = read_str_str_tsv(&data_dir.join("confusables_contractions.tsv"));
        assert!(
            !entries.is_empty(),
            "confusables_contractions.tsv: expected at least one rule, got 0"
        );
        for (source, target) in &entries {
            assert!(
                source.chars().count() >= 2,
                "contraction source {source:?} is not multi-codepoint - it belongs in \
                 confusables_to_latin.tsv, not here"
            );
            assert!(
                target.chars().count() == 1,
                "contraction target {target:?} must be a single character"
            );
            assert!(
                source.is_ascii() && target.is_ascii(),
                "contraction rules are ASCII digraph to ASCII letter: {source:?} -> {target:?}"
            );
        }
        // Idempotence precondition: no rule OUTPUT may appear inside any rule INPUT, or
        // one pass could expose a fresh match and the transform would not be a fixed
        // point. Checked here so a future data edit fails the build rather than silently
        // making the hostname canonical form depend on how many times it was run.
        for (_, target) in &entries {
            for (source, _) in &entries {
                assert!(
                    !source.contains(target.as_str()),
                    "contraction output {target:?} occurs inside source {source:?}; \
                     that chains and breaks idempotence"
                );
            }
        }
        let mut sorted = entries;
        sorted.sort();
        let mut rows = String::new();
        for (source, target) in &sorted {
            writeln!(rows, "    ({source:?}, {target:?}),").unwrap();
        }
        fs::write(
            out_dir.join("confusables_contractions.rs"),
            format!(
                "// Generated by build.rs (#562) from confusables_contractions.tsv.\n\
                 pub static CONTRACTIONS: &[(&str, &str)] = &[\n{rows}];\n"
            ),
        )
        .unwrap();
    }

    // --- Upstream confusable sources (coverage introspection, #563) ---
    // Every SOURCE codepoint in the bundled upstream `confusables.txt` — the
    // denominator for "which confusables does disarm not fold?". Not a mapping: the
    // answer is derived at runtime as `these sources MINUS the target table's keys`,
    // so it stays correct when either table gains a row and there is no second
    // artifact to keep in sync.
    {
        let sources = read_char_set_tsv(&data_dir.join("confusables_upstream_sources.tsv"));
        // The bundled 17.0.0 file has 6,565 sources. Guard the order of magnitude so a
        // truncated or half-written regeneration fails the build rather than silently
        // shrinking reported exposure — an under-reported gap is worse than no gap
        // report at all, because it reads as coverage.
        assert!(
            sources.len() >= 5_000,
            "confusables_upstream_sources.tsv: expected ≥5,000 sources, got {}",
            sources.len()
        );
        generate_char_set(
            &data_dir.join("confusables_upstream_sources.tsv"),
            &out_dir.join("confusables_upstream_sources_phf.rs"),
            "UPSTREAM_CONFUSABLE_SOURCES",
            "",
        );
    }

    // --- Excluded compositions (compose-at-lookup widening, #481) ---
    // Base+mark composition exclusions (KA+nukta → QA, shin+sin-dot → U+FB2B) that
    // canonical NFC does not recompose, so #479's compose-at-lookup misses them. Consulted
    // in `compose.rs` after NFC of a cluster. Shared by confusables and transliterate.
    generate_excluded_compositions_map(
        &data_dir.join("excluded_compositions.tsv"),
        &out_dir.join("excluded_compositions_phf.rs"),
        "EXCLUDED_COMPOSITIONS",
        "pub(crate)",
    );

    // --- Emoji ---
    generate_char_str_map(
        &data_dir.join("emoji_single.tsv"),
        &out_dir.join("emoji_single_phf.rs"),
        "EMOJI_SINGLE",
        "pub",
    );
    // --- Emoji rows the TR39 confusable table also claims (#614) ---
    // 49 code points appear in BOTH emoji_single.tsv and confusables_to_latin.tsv, and
    // they are mostly not emoji at all: typographic punctuation (`2010 hyphen`, the
    // apostrophes and quotes, `2026 ellipsis`), currency (`20AC euro`), math operators
    // and the CJK tortoise-shell brackets. They reach the emoji table from CLDR
    // `annotationsDerived`, which names non-emoji characters.
    //
    // Both entries are legitimate. `demojize("I ❤ €5")` -> "I red heart euro 5" is
    // exactly what that function is for. What is wrong is which table wins inside a
    // COMPARISON preset: `strip_obfuscation("€xample.com")` named the euro sign instead
    // of folding it, so the spoof and the genuine string stopped being equal rather than
    // becoming equal, and CVE-2017-5383 survived a preset documented as maximum-strength
    // deobfuscation.
    //
    // Derived as an INTERSECTION rather than read from a curated file, so it cannot drift
    // out of date the way a hand-written override list would. The count is asserted: a
    // future emoji-table refresh that claims another confusable source fails the build
    // with this message instead of silently widening the gap.
    {
        let emoji = read_char_str_tsv(&data_dir.join("emoji_single.tsv"));
        let confusable = read_char_str_tsv(&data_dir.join("confusables_to_latin.tsv"));
        let overlap: BTreeSet<u32> = emoji
            .keys()
            .filter(|cp| confusable.contains_key(cp))
            .copied()
            .collect();
        assert_eq!(
            overlap.len(),
            54,
            "emoji_single.tsv ∩ confusables_to_latin.tsv changed: expected the 54 rows \
             reviewed in #614, #801 and #815, found {}. A new row means a confusable source is \
             now named instead of folded inside strip_obfuscation. Review it, then update \
             this count.",
            overlap.len()
        );
        let mut code = String::from(
            "/// Code points claimed by BOTH the emoji name table and the TR39 confusable\n\
             /// table (#614). Skipped by `demojize` inside comparison presets so the fold\n\
             /// wins; standalone `demojize` still names them.\n\
             pub(crate) static EMOJI_ROWS_TR39_ALSO_CLAIMS: phf::Set<u32> = ",
        );
        let mut set = phf_codegen::Set::new();
        for cp in &overlap {
            set.entry(*cp);
        }
        code.push_str(&set.build().to_string());
        code.push_str(";\n");
        fs::write(out_dir.join("emoji_tr39_overlap_phf.rs"), code).unwrap();
    }

    // --- Emoji rows that name a code point with no emoji property (#757) ---
    // CLDR `annotationsDerived` names characters that are not emoji by any Unicode
    // property: typographic punctuation, currency, math operators, brackets. #614 caught
    // the 49 of them the TR39 confusable table also claims; the rest were still named,
    // and `ml_normalize` — the preset documented for tokenizers — ran the name table with
    // no suppression at all. `film’s` came back as `film right apostrophe s`: one token
    // to four, and the possessive gone. That is the spurious-token-insertion mechanism
    // `docs/security/adversarial-defense.md` disqualifies `unidecode` for.
    //
    // Derived as a SET DIFFERENCE against the UCD property, not a curated list, so a CLDR
    // refresh that annotates more punctuation lands in the set instead of slipping past
    // it. The count is asserted for the opposite reason to #614's: there the gate guards
    // a gap that should not widen, here it guards a suppression list that should not grow
    // without review — a new row means a preset stopped naming something it used to name.
    {
        let emoji = read_char_str_tsv(&data_dir.join("emoji_single.tsv"));
        let property = read_range_tsv(&data_dir.join("emoji_property.tsv"));
        let has_property = |cp: u32| {
            property
                .binary_search_by(|&(lo, hi)| {
                    if cp < lo {
                        Ordering::Greater
                    } else if cp > hi {
                        Ordering::Less
                    } else {
                        Ordering::Equal
                    }
                })
                .is_ok()
        };
        let non_emoji: BTreeSet<u32> = emoji
            .keys()
            .filter(|cp| !has_property(**cp))
            .copied()
            .collect();
        assert_eq!(
            non_emoji.len(),
            326,
            "emoji_single.tsv rows carrying neither Emoji nor Extended_Pictographic \
             changed: expected the 326 reviewed in #757, found {}. A new row means a \
             preset now passes through a character it used to name. Review it, then \
             update this count.",
            non_emoji.len()
        );
        let mut code = String::from(
            "/// Code points the CLDR name table annotates that carry neither the Unicode\n\
             /// `Emoji` nor the `Extended_Pictographic` property (#757). Skipped by\n\
             /// `demojize` inside presets; standalone `demojize` still names them.\n\
             pub(crate) static EMOJI_ROWS_WITHOUT_EMOJI_PROPERTY: phf::Set<u32> = ",
        );
        let mut set = phf_codegen::Set::new();
        for cp in &non_emoji {
            set.entry(*cp);
        }
        code.push_str(&set.build().to_string());
        code.push_str(";\n");
        fs::write(out_dir.join("emoji_non_emoji_phf.rs"), code).unwrap();
    }

    // Production matcher (#242 item 4): compact code-point trie.
    generate_emoji_trie(
        &data_dir.join("emoji_multi.tsv"),
        &out_dir.join("emoji_multi_trie.rs"),
        "EMOJI_MULTI_TRIE",
    );
    // The hex-key PHF is retained as the test-only equivalence oracle (it is
    // `#[cfg(test)]`-gated at the include site, so it is not in the shipped
    // binary — that is the table-size win).
    generate_str_str_map(
        &data_dir.join("emoji_multi.tsv"),
        &out_dir.join("emoji_multi_phf.rs"),
        "EMOJI_MULTI",
        "pub",
    );
    generate_char_set(
        &data_dir.join("emoji_starters.tsv"),
        &out_dir.join("emoji_starters_phf.rs"),
        "EMOJI_MULTI_STARTERS",
        "pub",
    );

    // --- Case Folding (full Unicode CaseFolding.txt) ---
    generate_char_str_map(
        &data_dir.join("case_folding.tsv"),
        &out_dir.join("case_folding_phf.rs"),
        "CASE_FOLD",
        "pub",
    );

    // --- Transliteration: default table (flat BMP array) ---
    {
        let default_entries = read_char_str_tsv(&data_dir.join("translit_default.tsv"));
        assert!(
            default_entries.len() >= 5_000,
            "translit_default.tsv: expected ≥5,000 entries, got {}",
            default_entries.len()
        );
        for (&cp, value) in &default_entries {
            assert!(
                value.is_ascii(),
                "translit_default.tsv: non-ASCII value {value:?} for U+{cp:04X}"
            );
        }
    }
    generate_translit_flat_array(
        &data_dir.join("translit_default.tsv"),
        &out_dir.join("translit_default_flat.rs"),
    );

    // --- Transliteration: SMP default table (ancient/historic scripts above U+FFFF) ---
    {
        let smp_entries = read_char_str_tsv(&data_dir.join("translit_default_smp.tsv"));
        for (&cp, value) in &smp_entries {
            assert!(
                value.is_ascii(),
                "translit_default_smp.tsv: non-ASCII value {value:?} for U+{cp:04X}"
            );
        }
    }
    generate_char_str_map(
        &data_dir.join("translit_default_smp.tsv"),
        &out_dir.join("translit_default_smp_phf.rs"),
        "DEFAULT_SMP",
        "",
    );

    // --- Transliteration: language-specific tables ---
    // Auto-discover language override tables by scanning the data dir, so adding a
    // language is just dropping in a `translit_lang_<code>.tsv` file — no hand-edit of a
    // hardcoded list that could silently drop a language (#74). The const name is the
    // file stem upper-cased (`lang_de` → `LANG_DE`), matching the names the dispatch in
    // `src/tables/transliteration.rs` references. The two romanization *standards*
    // (iso9, gost7034) are not languages, so they stay explicit.
    let mut lang_tables: Vec<(String, String)> = Vec::new();
    for entry in fs::read_dir(data_dir).expect("read src/tables/data") {
        let name = entry
            .expect("data dir entry")
            .file_name()
            .to_string_lossy()
            .into_owned();
        if let Some(code) = name
            .strip_prefix("translit_lang_")
            .and_then(|s| s.strip_suffix(".tsv"))
        {
            let file_stem = format!("lang_{code}");
            let const_name = file_stem.to_uppercase();
            lang_tables.push((file_stem, const_name));
        }
    }
    assert!(
        lang_tables.len() >= 20,
        "expected ≥20 translit_lang_*.tsv override tables, found {} — wrong data dir?",
        lang_tables.len()
    );
    lang_tables.push(("iso9".to_string(), "ISO9".to_string()));
    lang_tables.push(("gost7034".to_string(), "GOST7034".to_string()));
    // Deterministic order → reproducible generated output.
    lang_tables.sort();

    // Generate each language table to its own file, then combine
    let mut all_lang_code = String::new();
    for (file_stem, const_name) in &lang_tables {
        let tsv_path = data_dir.join(format!("translit_{file_stem}.tsv"));
        let entries = read_char_str_tsv(&tsv_path);
        for (&cp, value) in &entries {
            assert!(
                value.is_ascii(),
                "translit_{file_stem}.tsv: non-ASCII value {value:?} for U+{cp:04X}"
            );
        }
        all_lang_code.push_str(&build_char_str_map(&entries, const_name, ""));
        all_lang_code.push('\n');
    }

    let lang_out = out_dir.join("translit_langs_phf.rs");
    fs::write(&lang_out, all_lang_code).unwrap_or_else(|e| {
        panic!("Failed to write {}: {e}", lang_out.display());
    });

    // --- Reverse transliteration tables ---
    let reverse_tables = [
        ("reverse_ru", "REVERSE_RU"),
        ("reverse_uk", "REVERSE_UK"),
        ("reverse_el", "REVERSE_EL"),
    ];

    let mut all_reverse_code = String::new();
    for (file_stem, const_name) in &reverse_tables {
        let tsv_path = data_dir.join(format!("{file_stem}.tsv"));
        let entries = read_str_str_tsv(&tsv_path);
        // phf_codegen 0.13 retains the borrowed value until build(), so the formatted
        // literals must outlive the builder — collect them first.
        let formatted: Vec<(&str, String)> = entries
            .iter()
            .map(|(key, value)| (key.as_str(), format!("\"{}\"", escape_str(value))))
            .collect();
        let mut builder = phf_codegen::Map::<&str>::new();
        for (key, v) in &formatted {
            builder.entry(*key, v);
        }
        write!(
            all_reverse_code,
            "static {const_name}: phf::Map<&'static str, &'static str> = {};\n\n",
            builder.build()
        )
        .unwrap();
    }

    let reverse_out = out_dir.join("reverse_translit_phf.rs");
    fs::write(&reverse_out, all_reverse_code).unwrap_or_else(|e| {
        panic!("Failed to write {}: {e}", reverse_out.display());
    });

    // --- Terminal-width tables (#224): sorted, binary-searched range tables ---
    generate_width_ranges(
        &data_dir.join("char_width.tsv"),
        &out_dir.join("char_width_ranges.rs"),
    );
    generate_range_set(
        &data_dir.join("emoji_presentation.tsv"),
        &out_dir.join("emoji_presentation_ranges.rs"),
        "EMOJI_PRESENTATION_RANGES",
    );
    // #972: `Emoji=Yes`. The presentation table above answers "renders as emoji by
    // default"; this one answers "can render as emoji at all", which is the half a
    // `U+FE0F` turns on. `demojize`'s replacement mode needs both, and neither of them
    // needs the CLDR name table — that separation is what keeps a replace-only build
    // from linking 182 KB of names it will not read.
    generate_range_set(
        &data_dir.join("emoji_property.tsv"),
        &out_dir.join("emoji_property_ranges.rs"),
        "EMOJI_PROPERTY_RANGES",
    );
    // #992: `Emoji=Yes` alone, the base UTS #51 defines an emoji presentation sequence
    // for. The table above adds `Extended_Pictographic`, which reserves whole blocks, so
    // a selector after U+2605 BLACK STAR or an unassigned U+1FC00 opened a sequence there.
    generate_range_set(
        &data_dir.join("emoji_yes.tsv"),
        &out_dir.join("emoji_yes_ranges.rs"),
        "EMOJI_YES_RANGES",
    );
    // #774: the assigned-ness gate in front of the block-range script table.
    generate_range_set(
        &data_dir.join("assigned_ranges.tsv"),
        &out_dir.join("assigned_ranges.rs"),
        "ASSIGNED_RANGES",
    );
    // Finding 5 of the Lean detection model: the code points the block-range script
    // table would give a script and the UCD gives `Script=Common`. Generated from the
    // vendored `data/Scripts.txt` by `scripts/gen_script_common_carveouts.py`.
    generate_range_set(
        &data_dir.join("script_common_carveouts.tsv"),
        &out_dir.join("script_common_carveouts.rs"),
        "SCRIPT_COMMON_CARVEOUTS",
    );
    // #963: the per-script confusable denominator, so a script with no bundled table
    // reports `0 of N` rather than a number determined by that table's absence.
    generate_prototype_census(
        &data_dir.join("confusable_prototype_census.tsv"),
        &out_dir.join("confusable_prototype_census.rs"),
    );
    // #777: UTS #39 §5.3 Mixed Numbers — the zero of each decimal numbering system.
    generate_decimal_digit_zeros(
        &data_dir.join("decimal_digit_zeros.tsv"),
        &out_dir.join("decimal_digit_zeros.rs"),
    );
    // #750: the within-word joiners `seg_word` splits on.
    generate_char_set(
        &data_dir.join("word_joiners.tsv"),
        &out_dir.join("word_joiners_phf.rs"),
        "WORD_JOINERS",
        "pub(crate)",
    );

    // #773: UAX #9 strong direction, replacing a five-name script list.
    generate_bidi_strong_ranges(
        &data_dir.join("bidi_strong_ranges.tsv"),
        &out_dir.join("bidi_strong_ranges.rs"),
    );
}
