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
