//! Layer 2 (part of [`crate::api`]) — metadata introspection over the curated
//! language/script tables (#404, phase 3).
//!
//! Read-only accessors that expose disarm's bundled per-language and per-script
//! metadata: which scripts it knows, which languages have context-aware
//! transliteration, and the descriptive details of a single language or script.

use crate::Error;

/// Metadata for one language — returned by [`lang_info`].
#[derive(Clone, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub struct LangMeta {
    /// Human-readable language name (e.g. `"German"`).
    pub name: &'static str,
    /// The dominant script for this language (e.g. `"Latin"`).
    pub script: &'static str,
    /// Broad geographic region (e.g. `"European"`).
    pub region: &'static str,
    /// Context-aware transliteration support: `"none"`, `"partial"`, or `"full"`.
    pub context: &'static str,
}

/// Per-script confusable coverage — returned by [`confusable_coverage`] (#963).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub struct ConfusableCoverage {
    /// The script the figures are about, in disarm's own spelling.
    pub script: &'static str,
    /// TR39 single-code-point sources whose prototype is in this script.
    pub sources: u32,
    /// How many of those `sources` some bundled fold table reaches.
    pub folded: u32,
}

/// Metadata for one script — returned by [`script_info`].
#[derive(Clone, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub struct ScriptMeta {
    /// Human-readable script name (e.g. `"Coptic"`).
    pub name: &'static str,
    /// The default language code for this script, if one is defined.
    pub default_lang: Option<&'static str>,
    /// A short example string in the script.
    pub example: &'static str,
    /// Whether disarm offers context-aware transliteration for this script.
    pub context_aware: bool,
}

/// The Unicode `confusables.txt` release the bundled confusable tables were folded
/// from (#560), e.g. `"17.0.0"`.
///
/// Distinct from the crate version: this is the *data* vintage, and it moves
/// independently of disarm's own semver. A confusables fold is only as current as its
/// table, so a caller comparing disarm against another tool — or auditing its own
/// exposure — needs this number rather than the release number.
///
/// The value is parsed out of the TSV header by `build.rs`, so it cannot drift from the
/// data it describes; the build fails if that header stops naming a version. Both
/// bundled tables (`latin` and `cyrillic` targets) are generated from the same upstream
/// release, so one constant covers both, and `build.rs` asserts they agree.
///
/// Note the tables also carry disarm's own cross-script additions (#336), so they are a
/// superset of the named release rather than a verbatim snapshot — see
/// `docs/provenance.md`.
///
/// ```
/// let v = disarm::api::CONFUSABLES_VERSION;
/// assert!(v.split('.').all(|part: &str| part.parse::<u32>().is_ok()));
/// ```
pub const CONFUSABLES_VERSION: &str = crate::tables::CONFUSABLES_VERSION;

/// The bundled `confusables.txt` release, as a function (#560).
///
/// Identical to [`CONFUSABLES_VERSION`]; the const is there for `const` contexts, this
/// is the op every other binding mirrors (`confusablesVersion()` in Node/Java/Kotlin,
/// `Disarm.confusables_version` in Ruby, `disarm_confusables_version()` in the C ABI),
/// so the cross-binding parity matrix has one name to match on.
#[must_use]
pub fn confusables_version() -> &'static str {
    CONFUSABLES_VERSION
}

/// The UCD release disarm's normalizer implements (#642, #645).
///
/// The question this answers is not "what Unicode does disarm target" — the bundled
/// tables track several releases and `docs/provenance.md` is the census. It is the
/// narrower and more useful one: **will my keys agree with `unicodedata`?** Every NFC and
/// NFKC step in the library, including the ones inside the presets, runs through
/// `unicode-normalization`, and that crate carries its own UCD independent of both the
/// bundled tables and disarm's semver.
///
/// It matters because the answer is usually *no*. disarm tracks a newer UCD than most
/// shipped CPythons, so `disarm.normalize` and `unicodedata.normalize` disagree on code
/// points assigned in between. A pipeline that canonicalizes with one and validates with
/// the other is where that becomes a vulnerability rather than a curiosity; see
/// `docs/security/cve-validation.md` → *Normalization cost*.
///
/// Read from the crate rather than restated, so it cannot drift from the data it names.
/// `tests/normalization_ucd_drift.rs` additionally holds the documentation to it.
///
/// ```
/// let v = disarm::api::UNICODE_VERSION;
/// assert!(v.split('.').all(|part: &str| part.parse::<u32>().is_ok()));
/// ```
pub const UNICODE_VERSION: &str = crate::normalize::UNICODE_VERSION;

/// The UCD release disarm's normalizer implements, as a function (#645).
///
/// Identical to [`UNICODE_VERSION`]; the const is there for `const` contexts, this is the
/// op every binding mirrors, so the parity matrix has one name to match on.
#[must_use]
pub fn unicode_version() -> &'static str {
    UNICODE_VERSION
}

/// Whether a key stored under an earlier release still compares equal (#644, #645).
///
/// **Not a Unicode version.** It is a monotonic counter, bumped whenever the output of a
/// key-producing function moves. Two artifacts reporting the same value produce the same
/// key for the same input; two reporting different values may not, and a consumer holding
/// stored keys should reindex across the boundary.
///
/// The value is meaningless in isolation and that is deliberate — the question a key
/// consumer has is a comparison, not a lookup. Pre-0.15 releases expose no constant at
/// all, so "unknown" and "different" are the same answer there.
///
/// It covers every function `tests/fixtures/key_stability/golden_keys.tsv.gz` tracks, not
/// only the three named "key builders": `search_key`, `catalog_key`, `sort_key`,
/// `fold_case`, `canonicalize`, `canonicalize_strict`, `strip_obfuscation` and
/// `normalize_confusables`. A stored `canonicalize` value is as much a key as a stored
/// `search_key` one, and 0.15 moved four of those eight while leaving the other four
/// byte-identical (#801).
///
/// The counter is only worth anything if something notices the output moved, which is
/// what that fixture is for (#644). The version is written into the fixture header when
/// it is regenerated, and `tests/test_key_stability.py` fails when the constant and the
/// header disagree — that catches a constant that moved without the fixture.
///
/// It does **not** catch the other direction, and this comment claimed it did until #887.
/// The generator writes the current constant into the header, so a regenerated fixture
/// agrees with whatever the constant happens to be, stale or not. #873 regenerated the
/// fixture, left the counter at 2, and stayed green. [`KEY_FIXTURE_SHA256`] below is the
/// anchor the generator does not author, and is what makes the claim true.
///
/// ```
/// assert!(disarm::api::KEY_SCHEMA_VERSION >= 1);
/// ```
/// Bumped to 2 by #788: raising `strip_zalgo`'s cap to match `is_zalgo`'s threshold
/// moved `canonicalize` and `canonicalize_strict` on 351 and 340 of the 22,878
/// key-stability rows. Nothing lost a mark — every moved row is text the old cap had
/// been truncating.
///
/// Bumped to 3 by #835: a nonspacing mark repeated on one base is now dropped, so
/// `a` + two acutes keys the same as `a` + one. That moved `sort_key` and `canonicalize`
/// on 11 of the 22,977 rows and `canonicalize_strict` on 13; `search_key`, `catalog_key`,
/// `strip_obfuscation`, `normalize_confusables` and `fold_case` are byte-identical, and
/// no row grew.
///
/// Still 3 after the correction to that change: the repeat pass runs a second time, after
/// the confusable fold, because the fold can *create* a repeat rather than merely reveal
/// one. That moved `canonicalize` on 16 (base, mark) pairs — none of them in the fixture,
/// which is why it is unchanged. No further bump: those 16 had no stable value to move
/// away from, since the whole defect was that `canonicalize` answered them differently on
/// a second call, and neither #835 nor this has shipped.
///
/// Bumped to 4 by #815: the seven single-letter Latin small capitals (`ᴀ ᴅ ᴊ ᴘ ᴛ ꜰ ꞯ`)
/// now fold as confusable *sources*, not only as targets. That moves `catalog_key`, which
/// carries a confusable step; `search_key` and `sort_key` do not, having none. The fixture
/// could not have caught it — its corpus held no small capital at all across 22,977 rows,
/// so 75 were added in the same change and the digest moves for that reason as well.
///
/// Bumped to 5 by #833: every confusable-bearing preset normalizes before it folds, so six
/// rows whose NFKC image had no row of its own were unreachable from every preset. The
/// image now carries the source's target — `\u03c2` ς to `c`/`с`, `\u0190` Ɛ to `E`,
/// `\u0237` ȷ to `j`, `\u03a3` Σ to `С`, `\u2502` │ to `ӏ`. That moves `canonicalize`,
/// `canonicalize_strict`, `strip_obfuscation` and `normalize_confusables`; the three key
/// builders do not fold confusables through this path and are byte-identical.
///
/// Bumped to 6 by #815, for the negative enclosed letters. U+1F150 and U+1F170 fold
/// on no surface while their positive counterparts fold via NFKC, so a generator offering
/// "circled" and "circled (negative)" side by side got one neutralised and one through
/// untouched. 54 rows, and `catalog_key` moves for all of them. The corpus held none of
/// these either — third time in this cycle that the fixture stayed green through a key
/// change because its corpus did not sample the class being fixed, so 58 rows were added
/// with it.
///
/// Bumped to 7 by #910: `strip_obfuscation` no longer names emoji. It wrote 1,177 of them
/// into English words, so a comparison surface was inserting attacker-chosen text into
/// the value being compared — the same defect as the `llm_guardrail` profile, which moved
/// in the same change. The emoji is left in place rather than removed: measured over 144
/// emoji, removal fuses `stop<emoji>now` into `stopnow` every time, while leaving keeps
/// the words apart every time.
///
/// This one the fixture DID catch: its corpus carries 54 emoji, unlike the three classes
/// earlier in this cycle that it could not see.
/// Bumped to 8 by #937: the deletion class is resolved rather than only reported. `BS`
/// and `DEL` now erase the preceding *cell*, before any other step runs, so every builder
/// carrying the step moves for input containing one — `search_key`, `catalog_key`,
/// `sort_key`, `skeleton_key` and `ml_normalize`, along with `canonicalize`,
/// `canonicalize_strict` and `strip_obfuscation`.
///
/// #934 recorded resolving this class as out of scope, on the grounds that it is
/// renderer-dependent and resolution could lose text a reader can see. #937 measured what
/// an erase actually removes — the cell *before* the control, which in every row of the
/// paper's released corpus is the attacker's inserted character — and the decision
/// changed. `strip_format` and the `code_context` profile deliberately keep the old
/// behaviour, and a lone `CR` stays unresolved everywhere: it is byte-identical to a
/// classic Mac OS line ending, so only an explicit `resolve_cr=True` takes it.
///
/// The fixture was green through the change, for the **fourth** time in this cycle and
/// for the same reason as the three before it: its corpus held not one `BS`, `DEL` or
/// lone `CR` across 23,135 rows. 34 were added with this, covering every shape the model
/// has a rule for — the paper's construction, overstrike bold, a format character and a
/// combining mark before the control, a rendering `Cf` that does occupy a cell, erasing
/// past the start of a line, `CRLF`, and the classic Mac row that is why `CR` is opt-in.
pub const KEY_SCHEMA_VERSION: u32 = 9;

/// SHA-256 of the key-stability fixture's *decompressed* bytes (#887).
///
/// [`KEY_SCHEMA_VERSION`]'s doc comment claims that regenerating the fixture without
/// bumping the constant "is a test failure rather than a silent lie". It was not.
/// `tests/test_key_stability.py` compared the fixture header against the constant, and
/// `scripts/gen_key_fixture.py` *writes the current constant into that header* — so a
/// regenerated fixture always agreed with whatever the constant happened to be, stale or
/// not. The gate was anchored to the thing that drifts.
///
/// #873 tripped it: that change moved `strip_obfuscation` on 90 rows, the fixture was
/// regenerated, `src/api/metadata.rs` was not touched, and the counter stayed at 2 with
/// every test green. Nothing shipped wrong only because #874 bumped it in the same
/// unreleased cycle.
///
/// This is the anchor the generator does not author. Regenerating the fixture changes the
/// digest and fails the gate; fixing it means editing *this file* — with the version on
/// the line above. Forgetting the bump becomes a deliberate act instead of an invisible
/// one.
///
/// Hashed over the fixture's **rows only**, decompressed, with the comment header
/// excluded.
///
/// Decompressed because the generator already writes with `mtime=0` — the timestamp is
/// not the problem — but DEFLATE output still varies across zlib builds and compression
/// levels, and a digest that moves when somebody's toolchain moves is a gate that cries
/// wolf.
///
/// Rows only because the header stamps `disarm.__version__`, so hashing the whole file
/// made the digest move on **every version bump** even when no key moved — noise in
/// exactly the signal this exists to carry. Caught preparing 0.15.0, where the sole
/// difference was `# generated against disarm 0.14.1` becoming `0.15.0`. The rows are
/// the semantic anchor: they change when, and only when, a key moved.
pub const KEY_FIXTURE_SHA256: &str =
    "a1f5c860d8cfb6abebdf63659f540a01a8974f518e94607d9fd051f22b738954";

/// The key-schema counter, as a function (#645).
///
/// Identical to [`KEY_SCHEMA_VERSION`]; see that constant for what the number means and
/// what it does not.
#[must_use]
pub fn key_schema_version() -> u32 {
    KEY_SCHEMA_VERSION
}

/// Every script disarm knows, as stable UCD script identifiers, sorted by name
/// (includes `"Common"` / `"Inherited"`).
#[must_use]
pub fn list_scripts() -> Vec<&'static str> {
    crate::metadata::SCRIPTS.to_vec()
}

/// The language codes with context-aware transliteration support (`context` is
/// `"partial"` or `"full"`), sorted by code.
#[must_use]
pub fn list_context_langs() -> Vec<&'static str> {
    crate::metadata::LANGS
        .iter()
        .filter(|(_, row)| row.context != "none")
        .map(|(code, _)| *code)
        .collect()
}

/// Look up the metadata for a single language by its code.
///
/// # Errors
/// Returns an [`ErrorKind::InvalidArgument`](crate::ErrorKind::InvalidArgument) error naming the
/// offending value if `code` is not a known language code.
pub fn lang_info(code: &str) -> Result<LangMeta, Error> {
    match crate::metadata::lang(code) {
        Some(row) => Ok(LangMeta {
            name: row.name,
            script: row.script,
            region: row.region,
            context: row.context,
        }),
        None => Err(Error::from(crate::ErrorRepr::UnknownLangInfo {
            got: code.to_owned(),
        })),
    }
}

/// Look up the metadata for a single script by its name.
///
/// # Errors
/// Returns an [`ErrorKind::InvalidArgument`](crate::ErrorKind::InvalidArgument) error naming the
/// offending value if `name` is not a known script.
pub fn script_info(name: &str) -> Result<ScriptMeta, Error> {
    match crate::metadata::script(name) {
        Some(row) => Ok(ScriptMeta {
            name: row.name,
            default_lang: row.default_lang,
            example: row.example,
            context_aware: row.context_aware,
        }),
        None => Err(Error::from(crate::ErrorRepr::UnknownScript {
            got: name.to_owned(),
        })),
    }
}

/// TR39 confusable sources whose prototype is in `script`, and how many of those the
/// bundled tables fold (#963, #884).
///
/// The denominator [`unmapped_confusables`](crate::api::unmapped_confusables) does not
/// have. That function measures one bundled table against the whole 6,565-source
/// population, which is the right question for a target disarm ships and a misleading
/// one for a script it does not: Greek would report almost the entire population
/// unmapped, and the number would mean only "there is no Greek table". A count
/// determined by a table's absence is a blind spot with a number in front of it.
///
/// This reports the fair figure instead — of the sources whose prototype is in this
/// script, how many does disarm reach:
///
/// ```
/// use disarm::api::confusable_coverage;
///
/// let greek = confusable_coverage("Greek").unwrap();
/// assert_eq!(greek.sources, 159);
/// assert!(greek.folded > 0 && greek.folded < greek.sources);
/// ```
///
/// `folded` counts sources any bundled table reaches, not sources folded *toward* this
/// script. Greek is not zero because 71 of its 159 sources are Greek letters that the
/// Latin table folds — the question a caller has is whether disarm neutralizes the
/// source at all, not which prototype TR39 picked for it.
///
/// The script property behind the grouping is the UCD's, from `Scripts.txt`, but the
/// census is keyed in disarm's namespace: the UCD's name with underscores removed, which
/// is the spelling [`list_scripts`] returns for every script the two tables share. So 19
/// scripts appear here that disarm's own enum does not name — `Yi`, `Siddham`,
/// `PauCinHau` and 16 others, 72 sources between them — spelled the same way as the rest.
/// A script disarm knows but TR39 never uses as a prototype returns `0` of `0`, which is
/// the truth about it.
///
/// # Errors
/// Returns an [`ErrorKind::InvalidArgument`](crate::ErrorKind::InvalidArgument) error
/// naming the offending value if `script` is neither a script disarm knows nor one the
/// census has a row for.
pub fn confusable_coverage(script: &str) -> Result<ConfusableCoverage, Error> {
    if let Some((name, sources, folded)) = crate::tables::prototype_census(script) {
        return Ok(ConfusableCoverage {
            script: name,
            sources,
            folded,
        });
    }
    // A script disarm knows that TR39 never uses as a prototype: `0 of 0` is the
    // answer, and it is a different statement from "no such script".
    //
    // The name echoed back is the identifier, not `ScriptRow::name`, which is a display
    // string — `CanadianAboriginal` has the display name "Canadian Aboriginal
    // Syllabics", and returning that would hand the caller a value no surface accepts.
    // `SCRIPTS` is strictly sorted (asserted in `metadata::tests`), so this is a
    // binary search rather than a scan of all 61.
    match crate::metadata::SCRIPTS
        .binary_search(&script)
        .ok()
        .map(|idx| crate::metadata::SCRIPTS[idx])
    {
        Some(name) => Ok(ConfusableCoverage {
            script: name,
            sources: 0,
            folded: 0,
        }),
        None => Err(Error::from(crate::ErrorRepr::UnknownScript {
            got: script.to_owned(),
        })),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The const is only useful if it is a real dotted version, not an empty string
    /// left behind by a generator change. build.rs enforces the shape; this pins the
    /// same contract from the consumer side so a regression shows up in `cargo test`
    /// and not only in a build log.
    #[test]
    fn confusables_version_is_a_dotted_numeric_version() {
        let parts: Vec<&str> = CONFUSABLES_VERSION.split('.').collect();
        assert!(
            parts.len() >= 2,
            "expected at least major.minor, got {CONFUSABLES_VERSION:?}"
        );
        for part in parts {
            assert!(
                !part.is_empty() && part.bytes().all(|b| b.is_ascii_digit()),
                "non-numeric component {part:?} in {CONFUSABLES_VERSION:?}"
            );
        }
    }

    /// Guards the "derived, not typed twice" acceptance criterion: the const must equal
    /// the version written in the TSV header that build.rs read it from. If someone
    /// hand-edits either side, this fails.
    #[test]
    fn confusables_version_matches_the_table_header() {
        let header = include_str!("../tables/data/confusables_to_latin.tsv")
            .lines()
            .next()
            .expect("table has a header line");
        assert!(
            header.contains(&format!("confusables.txt {CONFUSABLES_VERSION}")),
            "header {header:?} does not name version {CONFUSABLES_VERSION:?}"
        );
    }

    /// All four bundled tables are folded from one upstream release, which is what lets a
    /// single const cover them. build.rs asserts it at build time; assert it here too so
    /// the reason for the single const is visible in the test suite.
    #[test]
    fn both_confusable_tables_name_the_same_version() {
        let cyrillic = include_str!("../tables/data/confusables_to_cyrillic.tsv")
            .lines()
            .next()
            .expect("table has a header line");
        assert!(
            cyrillic.contains(&format!("confusables.txt {CONFUSABLES_VERSION}")),
            "cyrillic header {cyrillic:?} does not name version {CONFUSABLES_VERSION:?}"
        );
    }

    #[test]
    fn lang_info_returns_curated_row() {
        let de = lang_info("de").unwrap();
        assert_eq!(de.name, "German");
        assert_eq!(de.script, "Latin");
    }

    /// Greek is the row the fair denominator exists for: no to-Greek table ships, so
    /// `unmapped_confusables` reports almost the whole 6,565-source population for it.
    #[test]
    fn confusable_coverage_reports_the_script_denominator() {
        let greek = confusable_coverage("Greek").unwrap();
        assert_eq!(greek.script, "Greek");
        assert_eq!(greek.sources, 159);
        // Not zero: 71 of the 159 are Greek letters the Latin table folds. A test that
        // only asserted `> 0` would pass on a census that had lost the grouping.
        assert_eq!(greek.folded, 71);
    }

    /// `0 of 0` and "no such script" are different answers, and both are answers.
    #[test]
    fn confusable_coverage_separates_zero_from_unknown() {
        let thaana = confusable_coverage("Thaana").unwrap();
        assert_eq!((thaana.sources, thaana.folded), (0, 0));
        let err = confusable_coverage("Nonexistent").unwrap_err();
        assert_eq!(err.kind(), crate::ErrorKind::InvalidArgument);
    }

    /// The census groups by the UCD's script property, which names scripts disarm's own
    /// enum does not. Dropping them would lose 72 sources without any total moving.
    #[test]
    fn confusable_coverage_reaches_scripts_the_metadata_table_lacks() {
        assert_eq!(confusable_coverage("Yi").unwrap().sources, 12);
        assert!(script_info("Yi").is_err());
        // And the two buckets `script_info` refuses outright, 1,036 sources between them.
        assert_eq!(confusable_coverage("Common").unwrap().sources, 893);
        assert_eq!(confusable_coverage("Inherited").unwrap().sources, 143);
    }

    /// Every row is internally consistent, over the whole shipped table rather than the
    /// three rows the tests above name.
    #[test]
    fn confusable_coverage_folds_no_more_than_it_counts() {
        for name in list_scripts() {
            let row = confusable_coverage(name).unwrap();
            assert!(
                row.folded <= row.sources,
                "{name}: folded {} of {}",
                row.folded,
                row.sources
            );
        }
    }

    /// Every name the library hands out reaches its own row, and comes back unchanged.
    ///
    /// The UCD spells a multi-word script `Canadian_Aboriginal` and disarm spells it
    /// `CanadianAboriginal`. With the census keyed the UCD's way, the name `list_scripts`
    /// returns missed it and fell through to the `0 of 0` branch — 143 sources reported
    /// as none, which is the failure this function exists to remove.
    #[test]
    fn confusable_coverage_accepts_every_name_the_library_hands_out() {
        for name in list_scripts() {
            let row = confusable_coverage(name).unwrap();
            assert_eq!(row.script, name, "{name} echoed back as {}", row.script);
        }
        assert_eq!(
            confusable_coverage("CanadianAboriginal").unwrap().sources,
            143
        );
        // One spelling per script: the UCD's form is not a second way in.
        assert!(confusable_coverage("Canadian_Aboriginal").is_err());
    }

    #[test]
    fn script_info_returns_curated_row() {
        let coptic = script_info("Coptic").unwrap();
        assert_eq!(coptic.default_lang, Some("cop"));
    }

    #[test]
    fn list_scripts_contains_known_scripts() {
        let scripts = list_scripts();
        assert!(scripts.contains(&"Latin"));
        assert!(scripts.contains(&"Common"));
    }

    #[test]
    fn list_context_langs_filters_on_context() {
        let langs = list_context_langs();
        assert!(langs.contains(&"ar"));
        assert!(!langs.contains(&"de"));
        // LANGS is sorted by code, so the filtered result is sorted too.
        let mut sorted = langs.clone();
        sorted.sort_unstable();
        assert_eq!(langs, sorted);
    }

    #[test]
    fn unknown_lang_and_script_are_invalid_argument() {
        let lang_err = lang_info("zzz").unwrap_err();
        assert_eq!(lang_err.kind(), crate::ErrorKind::InvalidArgument);
        assert!(lang_err.to_string().contains("zzz"));
        assert!(std::error::Error::source(&lang_err).is_none());

        let script_err = script_info("Nonexistent").unwrap_err();
        assert_eq!(script_err.kind(), crate::ErrorKind::InvalidArgument);
        assert!(script_err.to_string().contains("Nonexistent"));
    }
}
