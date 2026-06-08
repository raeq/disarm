//! Pure-Rust error type for the translit core.
//!
//! `Error` is the single internal error enum constructed by the pure-Rust
//! helper functions.  It carries the structured fields needed to render each
//! message, and its `Display` impl (via `thiserror`) reproduces **byte-for-byte**
//! the message text that each call site produced before this refactor (#181).
//!
//! The PyO3 boundary converts `Error` into a Python exception via
//! [`From<Error> for pyo3::PyErr`].  That conversion is the **only** place the
//! core couples to PyO3: it maps each variant to the same Python exception
//! *type* it was constructed as historically — either `crate::TranslitError`
//! (most variants) or a bare `pyo3::exceptions::PyValueError` (a deliberately
//! preserved minority — see the conversion impl).  No message text or exception
//! type changes; this is a behaviour-preserving restructuring.
//!
//! Each variant also exposes a stable machine-readable [`Error::code`] — new
//! metadata that is not yet surfaced to Python and changes no behaviour.

use thiserror::Error;

/// Internal error type for the translit core.
///
/// One variant per distinct error currently constructed across the core. The
/// `#[error(...)]` Display text is verbatim-identical to the pre-refactor
/// message at each site.
#[derive(Debug, Error)]
pub(crate) enum Error {
    /// Invalid `errors=` mode string (`ErrorMode::from_str`).
    #[error("errors must be 'replace', 'ignore', or 'preserve', got '{got}'")]
    InvalidErrorMode {
        /// The offending value.
        got: String,
    },

    /// Invalid normalization form for `normalize`/`is_normalized`.
    #[error("form must be 'NFC', 'NFD', 'NFKC', or 'NFKD', got '{got}'")]
    InvalidNormForm {
        /// The offending value.
        got: String,
    },

    /// Invalid normalization form for the `TextPipeline` `normalize` step.
    #[error("normalize must be 'NFC', 'NFD', 'NFKC', or 'NFKD', got '{got}'")]
    InvalidPipelineNormForm {
        /// The offending value.
        got: String,
    },

    /// Invalid `emoji_style` for `ml_normalize`.
    #[error("emoji_style must be 'cldr' or 'none', got '{got}'")]
    InvalidEmojiStyle {
        /// The offending value.
        got: String,
    },

    /// Invalid `platform` for `sanitize_filename`.
    #[error("platform must be 'universal', 'windows', or 'posix', got '{got}'")]
    InvalidPlatform {
        /// The offending value.
        got: String,
    },

    /// Invalid `target_script` for confusables functions.
    #[error("target_script must be 'latin' or 'cyrillic', got '{got}'")]
    InvalidTargetScript {
        /// The offending value.
        got: String,
    },

    /// Unknown `lang` code (eager validation, #68).
    #[error(
        "unknown language code {got:?}; expected \"auto\", a BCP-47 alias \
         (nb, nn, da), or one of: {valid}"
    )]
    UnknownLang {
        /// The offending code (rendered with `{:?}` to match the original).
        got: String,
        /// Comma-joined list of valid codes.
        valid: String,
    },

    /// Mutually-exclusive flags, mapped to a bare `PyValueError` (transliterate
    /// scalar/context/batch entry points, #130).
    #[error("strict_iso9 and gost7034 are mutually exclusive")]
    MutuallyExclusiveBare,

    /// Mutually-exclusive flags, mapped to `TranslitError` (the `TextPipeline`
    /// constructor — preserved as it was built historically).
    #[error("strict_iso9 and gost7034 are mutually exclusive")]
    MutuallyExclusivePipeline,

    /// Batch size over [`crate::MAX_BATCH_SIZE`].
    #[error("batch too large ({len} items); maximum is {max} items")]
    BatchTooLarge {
        /// The submitted batch length.
        len: usize,
        /// The maximum allowed.
        max: usize,
    },

    /// Registered replacements expanded the input past the output cap.
    #[error(
        "registered replacements expanded the input to {size} bytes, exceeding the {max} byte limit"
    )]
    ReplacementOutputTooLarge {
        /// The produced size in bytes.
        size: usize,
        /// The maximum allowed.
        max: usize,
    },

    /// A registration mutation attempted after `seal_registrations()`.
    #[error(
        "{op}: registration tables are sealed (seal_registrations() was called); \
         register/remove/clear are not permitted after sealing"
    )]
    Sealed {
        /// The attempted operation name.
        op: String,
    },

    /// `register_lang` would exceed the registered-language cap. Bare
    /// `PyValueError`.
    #[error(
        "register_lang(): maximum of {max} registered languages reached; \
         re-registering an existing code is still allowed"
    )]
    RegisterLangLimit {
        /// The maximum number of registered languages.
        max: usize,
    },

    /// `register_lang` mapping keys are not single Unicode characters. Bare
    /// `PyValueError`.
    #[error(
        "register_lang(): mapping keys must be exactly one Unicode character; \
         invalid keys: {keys}"
    )]
    RegisterLangBadKeys {
        /// Pre-rendered, comma-joined list of the offending keys (each `{:?}`).
        keys: String,
    },

    /// `register_replacements` would exceed the replacements cap. Bare
    /// `PyValueError`.
    #[error(
        "register_replacements(): table would exceed the maximum of {max} entries \
         (projected size: {projected}); call clear_replacements() first"
    )]
    RegisterReplacementsLimit {
        /// The maximum number of replacement entries.
        max: usize,
        /// The projected table size.
        projected: usize,
    },

    /// No context dictionary found for the language.
    #[error(
        "Context dictionary for {lang} not found. Context-aware transliteration needs \
         the prebuilt dictionaries: run `bash scripts/bootstrap_dicts.sh` (from a \
         source checkout) and set the TRANSLIT_DICT_DIR environment variable to the \
         output directory. See docs/user-guide/abjad-transliteration.md."
    )]
    ContextDictNotFound {
        /// Human-readable language name (e.g. "Arabic").
        lang: String,
    },

    /// Context dictionary found but corrupt (#107).
    #[error(
        "Context dictionary for {lang} is corrupt and could not be loaded: {reason}. \
         Rebuild it with `bash scripts/bootstrap_dicts.sh` (from a source checkout)."
    )]
    ContextDictCorrupt {
        /// Human-readable language name (e.g. "Arabic").
        lang: String,
        /// The underlying corruption detail (flattened sub-error text, #188).
        reason: String,
    },

    /// Caller-supplied regex pattern exceeds the byte cap (slugify).
    #[error("regex_pattern is too long ({len} bytes); maximum is {max} bytes")]
    RegexTooLong {
        /// The pattern length in bytes.
        len: usize,
        /// The maximum allowed.
        max: usize,
    },

    /// Caller-supplied regex failed to compile. The flattened `regex::Error`
    /// text is preserved (cause-chain enrichment is #188).
    #[error("Invalid regex: {source}")]
    RegexCompile {
        /// The underlying regex compile error.
        source: regex::Error,
    },

    /// `UniqueSlugifier` exhausted its attempt budget.
    #[error("UniqueSlugifier exceeded {max} attempts for '{text}'")]
    UniqueSlugAttemptsExceeded {
        /// The attempt cap.
        max: u64,
        /// The input text that could not be made unique.
        text: String,
    },

    /// `UniqueSlugifier` `max_length` too small to ever produce a unique slug.
    #[error(
        "max_length={max_length} is too small to generate a unique slug with separator {separator:?}: \
         need at least {min_unique_len} bytes for the separator plus one counter digit"
    )]
    UniqueSlugMaxLengthTooSmall {
        /// The configured `max_length`.
        max_length: usize,
        /// The configured separator (rendered with `{:?}`).
        separator: String,
        /// The minimum length required.
        min_unique_len: usize,
    },

    /// Explicit encoding label not recognised (`decode_to_utf8`).
    #[error("Unknown encoding: '{got}'")]
    UnknownEncoding {
        /// The unrecognised label.
        got: String,
    },

    /// Auto-detected encoding label is not supported (`decode_to_utf8`).
    #[error("Auto-detected encoding '{got}' is not supported")]
    UnsupportedAutoEncoding {
        /// The detected-but-unsupported label.
        got: String,
    },

    /// Auto-detection confidence below the caller's threshold.
    #[error(
        "Encoding detection confidence {confidence:.2} is below the required \
         minimum {min_confidence:.2} (best guess: '{guess}'). \
         Provide an explicit encoding instead."
    )]
    EncodingConfidenceTooLow {
        /// The detection confidence.
        confidence: f64,
        /// The caller's required minimum.
        min_confidence: f64,
        /// The best-guess encoding label.
        guess: String,
    },

    /// Reverse transliteration not supported for the requested language. Bare
    /// `PyValueError`.
    #[error("reverse transliteration not supported for lang={lang:?}; available: {available}")]
    ReverseUnsupportedLang {
        /// The requested language (rendered with `{:?}`).
        lang: String,
        /// Comma-joined list of supported languages.
        available: String,
    },
}

impl Error {
    /// Stable machine-readable error code for this variant.
    ///
    /// New metadata (#181): not currently surfaced to Python, so it changes no
    /// behaviour. Codes are stable identifiers, independent of the (mutable)
    /// human-readable message text. Wired into the Python surface in a follow-up
    /// (the boundary conversion will attach it); unused in non-test builds until
    /// then, hence `allow(dead_code)`.
    #[allow(dead_code)]
    pub(crate) fn code(&self) -> &'static str {
        match self {
            Error::InvalidErrorMode { .. } => "invalid_error_mode",
            Error::InvalidNormForm { .. } => "invalid_norm_form",
            Error::InvalidPipelineNormForm { .. } => "invalid_pipeline_norm_form",
            Error::InvalidEmojiStyle { .. } => "invalid_emoji_style",
            Error::InvalidPlatform { .. } => "invalid_platform",
            Error::InvalidTargetScript { .. } => "invalid_target_script",
            Error::UnknownLang { .. } => "unknown_lang",
            Error::MutuallyExclusiveBare | Error::MutuallyExclusivePipeline => "mutually_exclusive",
            Error::BatchTooLarge { .. } => "batch_too_large",
            Error::ReplacementOutputTooLarge { .. } => "replacement_output_too_large",
            Error::Sealed { .. } => "sealed",
            Error::RegisterLangLimit { .. } => "register_lang_limit",
            Error::RegisterLangBadKeys { .. } => "register_lang_bad_keys",
            Error::RegisterReplacementsLimit { .. } => "register_replacements_limit",
            Error::ContextDictNotFound { .. } => "context_dict_not_found",
            Error::ContextDictCorrupt { .. } => "context_dict_corrupt",
            Error::RegexTooLong { .. } => "regex_too_long",
            Error::RegexCompile { .. } => "regex_compile",
            Error::UniqueSlugAttemptsExceeded { .. } => "unique_slug_attempts_exceeded",
            Error::UniqueSlugMaxLengthTooSmall { .. } => "unique_slug_max_length_too_small",
            Error::UnknownEncoding { .. } => "unknown_encoding",
            Error::UnsupportedAutoEncoding { .. } => "unsupported_auto_encoding",
            Error::EncodingConfidenceTooLow { .. } => "encoding_confidence_too_low",
            Error::ReverseUnsupportedLang { .. } => "reverse_unsupported_lang",
        }
    }
}

impl From<Error> for pyo3::PyErr {
    /// Convert a core `Error` into the Python exception it was historically
    /// constructed as.
    ///
    /// Most variants become [`crate::TranslitError`]. A deliberately preserved
    /// minority become a bare [`pyo3::exceptions::PyValueError`] — these are the
    /// sites that were *not* wrapped in `TranslitError` before this refactor
    /// (#181 is behaviour-preserving; surface unification is #183). The message
    /// is `Display` (`to_string`), identical to the original at every site.
    fn from(err: Error) -> Self {
        use pyo3::exceptions::PyValueError;
        let msg = err.to_string();
        match err {
            // Bare PyValueError sites — preserved exactly, NOT promoted to
            // TranslitError (see #181 constraints).
            Error::MutuallyExclusiveBare
            | Error::RegisterLangLimit { .. }
            | Error::RegisterLangBadKeys { .. }
            | Error::RegisterReplacementsLimit { .. }
            | Error::ReverseUnsupportedLang { .. } => PyValueError::new_err(msg),
            // Everything else was built as TranslitError.
            _ => crate::TranslitError::new_err(msg),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::Error;

    /// `code()` is stable and exhaustive: every variant returns a non-empty,
    /// SCREAMING-or-snake identifier. This also keeps `code()` exercised (it is
    /// not yet wired into the Python surface).
    #[test]
    fn codes_are_nonempty_snake_case() {
        // Intentionally invalid pattern: we only need a real `regex::Error`
        // value to populate the `RegexCompile` sample below. Hoisted to a `let`
        // so the `#[allow]` can scope the lint (newer stable clippy's
        // `invalid_regex` flags the literal `"["`; expression-level attributes
        // are not stable inside the array literal).
        #[allow(clippy::invalid_regex)]
        let invalid_regex_err = regex::Regex::new("[").unwrap_err();
        let samples = [
            Error::InvalidErrorMode { got: "x".into() },
            Error::InvalidNormForm { got: "x".into() },
            Error::InvalidPipelineNormForm { got: "x".into() },
            Error::InvalidEmojiStyle { got: "x".into() },
            Error::InvalidPlatform { got: "x".into() },
            Error::InvalidTargetScript { got: "x".into() },
            Error::UnknownLang {
                got: "x".into(),
                valid: "a, b".into(),
            },
            Error::MutuallyExclusiveBare,
            Error::MutuallyExclusivePipeline,
            Error::BatchTooLarge { len: 2, max: 1 },
            Error::ReplacementOutputTooLarge { size: 2, max: 1 },
            Error::Sealed {
                op: "register".into(),
            },
            Error::RegisterLangLimit { max: 1 },
            Error::RegisterLangBadKeys {
                keys: "\"x\"".into(),
            },
            Error::RegisterReplacementsLimit {
                max: 1,
                projected: 2,
            },
            Error::ContextDictNotFound {
                lang: "Arabic".into(),
            },
            Error::ContextDictCorrupt {
                lang: "Arabic".into(),
                reason: "bad".into(),
            },
            Error::RegexTooLong { len: 2, max: 1 },
            Error::RegexCompile {
                source: invalid_regex_err,
            },
            Error::UniqueSlugAttemptsExceeded {
                max: 1,
                text: "x".into(),
            },
            Error::UniqueSlugMaxLengthTooSmall {
                max_length: 1,
                separator: "-".into(),
                min_unique_len: 2,
            },
            Error::UnknownEncoding { got: "x".into() },
            Error::UnsupportedAutoEncoding { got: "x".into() },
            Error::EncodingConfidenceTooLow {
                confidence: 0.5,
                min_confidence: 0.9,
                guess: "UTF-8".into(),
            },
            Error::ReverseUnsupportedLang {
                lang: "de".into(),
                available: "ru, uk".into(),
            },
        ];
        for e in &samples {
            let code = e.code();
            assert!(!code.is_empty());
            assert!(
                code.bytes().all(|b| b.is_ascii_lowercase() || b == b'_'),
                "code {code:?} is not lower snake_case"
            );
        }
    }

    /// The two mutually-exclusive variants intentionally share one code and one
    /// message but map to *different* Python exception types (preserved, #181).
    #[test]
    fn mutually_exclusive_variants_share_text_and_code() {
        let a = Error::MutuallyExclusiveBare;
        let b = Error::MutuallyExclusivePipeline;
        assert_eq!(a.to_string(), b.to_string());
        assert_eq!(a.code(), b.code());
        assert_eq!(
            a.to_string(),
            "strict_iso9 and gost7034 are mutually exclusive"
        );
    }
}
