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
/// what that fixture is for (#644). The two are wired together: the version is written
/// into the fixture header when it is regenerated, and `tests/test_key_stability.py`
/// fails when the constant and the header disagree. Regenerating the fixture without
/// bumping the constant — the exact way a counter like this goes stale — is a test
/// failure rather than a silent lie.
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
pub const KEY_SCHEMA_VERSION: u32 = 3;

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
/// Returns an [`ErrorKind::InvalidArgument`](crate::ErrorKind) error naming the
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
/// Returns an [`ErrorKind::InvalidArgument`](crate::ErrorKind) error naming the
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
