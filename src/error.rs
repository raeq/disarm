//! Pure-Rust error type for the translit core.
//!
//! `Error` is the single internal error enum constructed by the pure-Rust
//! helper functions.  It carries the structured fields needed to render each
//! message via its `Display` impl (`thiserror`). All messages follow one house
//! style (see [`Error`]), enforced by `messages_follow_house_style` (#187).
//!
//! The PyO3 boundary converts `Error` into a Python exception via
//! [`From<Error> for pyo3::PyErr`].  That conversion is the **only** place the
//! core couples to PyO3: it maps each variant into translit's unified exception
//! hierarchy — the `TranslitError` base or one of its `InvalidArgumentError` /
//! `ResourceLimitError` / `UnsupportedError` subclasses (#183), so
//! `except TranslitError` catches every variant (it missed the five
//! formerly-bare-`PyValueError` sites before #183).
//!
//! Each variant also exposes a stable machine-readable [`Error::code`] — new
//! metadata that is not yet surfaced to Python and changes no behaviour.

use std::borrow::Cow;

use thiserror::Error;

/// Maximum length (bytes) of user-controlled input echoed into an error message.
const MAX_ERROR_INPUT_BYTES: usize = 80;

/// Bound user-controlled text embedded in an error message (#200): a long or
/// sensitive input must not bloat the message or be logged in full. Truncates on
/// a UTF-8 char boundary and appends an ellipsis; short inputs pass through
/// borrowed and unchanged.
fn truncate_error_text(text: &str) -> Cow<'_, str> {
    if text.len() <= MAX_ERROR_INPUT_BYTES {
        return Cow::Borrowed(text);
    }
    let mut end = MAX_ERROR_INPUT_BYTES;
    while !text.is_char_boundary(end) {
        end -= 1;
    }
    Cow::Owned(format!("{}…", &text[..end]))
}

/// Internal error type for the translit core.
///
/// One variant per distinct error currently constructed across the core.
///
/// ## Message style (#187)
///
/// Every `#[error(...)]` message follows one policy, enforced by
/// `messages_follow_house_style` below:
/// - **No prefix.** The exception *type* already identifies translit, so messages
///   carry no `translit:` prefix.
/// - **Lowercase first word**, unless it is a proper noun / identifier
///   (`UniqueSlugifier`, `register_lang()`, `max_length`, `strict_iso9`).
/// - **Single quotes** around an echoed string value: `got '{got}'`, not
///   `{got:?}`. The exceptions are the regex `pattern` and the `register_lang`
///   bad `keys`, which render *arbitrary* user content with `{:?}` (double
///   quotes) so embedded quotes stay unambiguous. (The `Untranslatable` char
///   also uses `{:?}`, but `char` Debug already renders single quotes while
///   safely escaping control characters.)
/// - **Names the offending value and a remedy** (valid options, a limit, a
///   command, or a flag to pass) wherever one applies.
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
        "unknown language code '{got}'{suggestion}; expected 'auto', a BCP-47 \
         alias (nb, nn, da), or one of: {valid}"
    )]
    UnknownLang {
        /// The offending code (rendered with `{:?}` to match the original).
        got: String,
        /// Pre-rendered " (did you mean 'xx'?)" hint, or empty (#186).
        suggestion: String,
        /// Comma-joined list of valid codes.
        valid: String,
    },

    /// Mutually-exclusive flags, raised at the transliterate scalar/context/batch
    /// entry points (#130). Maps to `InvalidArgumentError` (#183).
    #[error("strict_iso9 and gost7034 are mutually exclusive")]
    MutuallyExclusiveBare,

    /// Mutually-exclusive flags, raised at the `TextPipeline` constructor. Same
    /// message and `InvalidArgumentError` mapping as `MutuallyExclusiveBare`;
    /// the two are kept distinct only by construction site (a future cleanup
    /// could merge them now that the Py-type split they encoded is gone).
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

    /// `register_lang` would exceed the registered-language cap. Maps to
    /// `ResourceLimitError` (#183).
    #[error(
        "register_lang(): maximum of {max} registered languages reached; \
         re-registering an existing code is still allowed"
    )]
    RegisterLangLimit {
        /// The maximum number of registered languages.
        max: usize,
    },

    /// `register_lang` mapping keys are not single Unicode characters. Maps to
    /// `InvalidArgumentError` (#183).
    #[error(
        "register_lang(): mapping keys must be exactly one Unicode character; \
         invalid keys: {keys}"
    )]
    RegisterLangBadKeys {
        /// Pre-rendered, comma-joined list of the offending keys (each `{:?}`).
        keys: String,
    },

    /// `register_replacements` would exceed the replacements cap. Maps to
    /// `ResourceLimitError` (#183).
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
        "context dictionary for {lang} not found; context-aware transliteration needs \
         the prebuilt dictionaries: run `bash scripts/bootstrap_dicts.sh` (from a \
         source checkout) and set the TRANSLIT_DICT_DIR environment variable to the \
         output directory (see docs/user-guide/abjad-transliteration.md)"
    )]
    ContextDictNotFound {
        /// Human-readable language name (e.g. "Arabic").
        lang: String,
    },

    /// Context dictionary found but corrupt (#107).
    #[error(
        "context dictionary for {lang} is corrupt and could not be loaded: {reason}; \
         rebuild it with `bash scripts/bootstrap_dicts.sh` (from a source checkout)"
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

    /// Caller-supplied regex failed to compile. Echoes the offending pattern
    /// (#186); the `regex::Error` Display carries the position/caret detail.
    /// Cause-chain enrichment is #188.
    #[error("invalid regex_pattern {pattern:?}: {source}")]
    RegexCompile {
        /// The offending pattern, echoed back to the caller.
        pattern: String,
        /// The underlying regex compile error.
        source: regex::Error,
    },

    /// `UniqueSlugifier` exhausted its attempt budget.
    #[error(
        "UniqueSlugifier exceeded {max} attempts for '{}'",
        truncate_error_text(text)
    )]
    UniqueSlugAttemptsExceeded {
        /// The attempt cap.
        max: u64,
        /// The input text that could not be made unique.
        text: String,
    },

    /// `UniqueSlugifier` `max_length` too small to ever produce a unique slug.
    #[error(
        "max_length={max_length} is too small to generate a unique slug with separator '{separator}': \
         need at least {min_unique_len} bytes for the separator plus one counter digit"
    )]
    UniqueSlugMaxLengthTooSmall {
        /// The configured `max_length`.
        max_length: usize,
        /// The configured separator.
        separator: String,
        /// The minimum length required.
        min_unique_len: usize,
    },

    /// Explicit encoding label not recognised (`decode_to_utf8`).
    #[error("unknown encoding: '{got}'{suggestion}")]
    UnknownEncoding {
        /// The unrecognised label.
        got: String,
        /// Pre-rendered " (did you mean 'UTF-8'?)" hint, or empty (#186).
        suggestion: String,
    },

    /// Auto-detected encoding label is not supported (`decode_to_utf8`).
    #[error("auto-detected encoding '{got}' is not supported")]
    UnsupportedAutoEncoding {
        /// The detected-but-unsupported label.
        got: String,
    },

    /// Auto-detection confidence below the caller's threshold.
    #[error(
        "encoding detection confidence {confidence:.2} is below the required \
         minimum {min_confidence:.2} (best guess: '{guess}'); \
         provide an explicit encoding instead"
    )]
    EncodingConfidenceTooLow {
        /// The detection confidence.
        confidence: f64,
        /// The caller's required minimum.
        min_confidence: f64,
        /// The best-guess encoding label.
        guess: String,
    },

    /// Reverse transliteration not supported for the requested language. Maps to
    /// `UnsupportedError` (#183).
    #[error("reverse transliteration not supported for lang '{lang}'; available: {available}")]
    ReverseUnsupportedLang {
        /// The requested language.
        lang: String,
        /// Comma-joined list of supported languages.
        available: String,
    },

    /// `errors="strict"` hit a character with no transliteration (#184).
    #[error("no transliteration for {ch:?} (U+{:04X}) at byte offset {byte_offset}", *ch as u32)]
    Untranslatable {
        /// The offending character.
        ch: char,
        /// Its byte offset in the input.
        byte_offset: usize,
    },

    /// `decode_to_utf8(strict=True)` hit malformed input that would otherwise be
    /// silently replaced with U+FFFD (#189).
    #[error(
        "decoding as '{encoding}' replaced malformed or invalid byte sequences \
         (lossy); pass strict=False to accept the lossy result and inspect had_errors"
    )]
    LossyDecode {
        /// The encoding that was decoded from.
        encoding: String,
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
            Error::Untranslatable { .. } => "untranslatable",
            Error::LossyDecode { .. } => "lossy_decode",
        }
    }
}

impl From<Error> for pyo3::PyErr {
    /// Convert a core `Error` into a Python exception from translit's unified
    /// hierarchy (#183): a [`crate::TranslitError`] base with `InvalidArgumentError`
    /// / `ResourceLimitError` / `UnsupportedError` subclasses. Every variant maps
    /// to exactly one of them, so `except TranslitError` catches all of them —
    /// including the five sites that were previously bare `PyValueError`
    /// (mutually-exclusive flags, register limits, reverse unsupported lang) and
    /// silently escaped it. `TranslitError` remains a `ValueError` subclass, so
    /// existing `except ValueError` code is unaffected. The message is `Display`,
    /// identical to before at every site.
    ///
    /// The match is exhaustive (no wildcard) on purpose: a new variant must be
    /// assigned a category here, not silently default.
    fn from(err: Error) -> Self {
        let msg = err.to_string();

        // #188: surface the underlying error as a chained `__cause__` for the
        // variants that wrap one, instead of only flattening it into the message.
        // Peeked by reference before `err` is consumed by the category match;
        // attached under the GIL afterwards. Python can't hold the Rust error
        // type, so the cause carries its rendered text in a `ValueError`.
        let cause: Option<pyo3::PyErr> = match &err {
            Error::RegexCompile { source, .. } => {
                Some(pyo3::exceptions::PyValueError::new_err(source.to_string()))
            }
            Error::ContextDictCorrupt { reason, .. } => {
                Some(pyo3::exceptions::PyValueError::new_err(reason.clone()))
            }
            _ => None,
        };

        let err_py = match err {
            // InvalidArgumentError — a bad argument value or a contradictory
            // combination of arguments.
            Error::InvalidErrorMode { .. }
            | Error::InvalidNormForm { .. }
            | Error::InvalidPipelineNormForm { .. }
            | Error::InvalidEmojiStyle { .. }
            | Error::InvalidPlatform { .. }
            | Error::InvalidTargetScript { .. }
            | Error::UnknownLang { .. }
            | Error::MutuallyExclusiveBare
            | Error::MutuallyExclusivePipeline
            | Error::RegisterLangBadKeys { .. }
            | Error::RegexCompile { .. }
            | Error::UniqueSlugMaxLengthTooSmall { .. }
            | Error::UnknownEncoding { .. } => crate::InvalidArgumentError::new_err(msg),

            // ResourceLimitError — a configured limit was exceeded.
            Error::BatchTooLarge { .. }
            | Error::ReplacementOutputTooLarge { .. }
            | Error::RegisterLangLimit { .. }
            | Error::RegisterReplacementsLimit { .. }
            | Error::RegexTooLong { .. }
            | Error::UniqueSlugAttemptsExceeded { .. } => crate::ResourceLimitError::new_err(msg),

            // UnsupportedError — a requested feature is unavailable.
            Error::UnsupportedAutoEncoding { .. } | Error::ReverseUnsupportedLang { .. } => {
                crate::UnsupportedError::new_err(msg)
            }

            // Base TranslitError — state / data errors that fit no category above.
            Error::Sealed { .. }
            | Error::ContextDictNotFound { .. }
            | Error::ContextDictCorrupt { .. }
            | Error::EncodingConfidenceTooLow { .. }
            | Error::Untranslatable { .. }
            | Error::LossyDecode { .. } => crate::TranslitError::new_err(msg),
        };

        if let Some(cause_err) = cause {
            pyo3::Python::with_gil(|py| err_py.set_cause(py, Some(cause_err)));
        }
        err_py
    }
}

#[cfg(test)]
mod tests {
    use super::{truncate_error_text, Error, MAX_ERROR_INPUT_BYTES};

    #[test]
    fn truncate_error_text_bounds_long_input() {
        let long = "a".repeat(500);
        let out = truncate_error_text(&long);
        // Bounded to the cap plus the multi-byte ellipsis, never the full input.
        assert!(out.len() < long.len());
        assert!(out.starts_with("aaaa"));
        assert!(out.ends_with('…'));
        assert!(out.len() <= MAX_ERROR_INPUT_BYTES + '…'.len_utf8());
    }

    #[test]
    fn truncate_error_text_passes_short_input_through() {
        assert_eq!(truncate_error_text("short"), "short");
    }

    #[test]
    fn truncate_error_text_cuts_on_char_boundary() {
        // Multi-byte chars straddling the cap must not panic or split a char.
        let s = "é".repeat(100); // 200 bytes
        let out = truncate_error_text(&s);
        assert!(out.ends_with('…'));
        // The Owned branch produced valid UTF-8 (would have panicked otherwise).
        assert!(out.chars().count() > 1);
    }

    #[test]
    fn unique_slug_error_display_is_truncated() {
        let err = Error::UniqueSlugAttemptsExceeded {
            max: 5,
            text: "x".repeat(500),
        };
        let msg = err.to_string();
        assert!(msg.starts_with("UniqueSlugifier exceeded 5 attempts for 'xxxx"));
        assert!(msg.contains('…'));
        assert!(
            msg.len() < 200,
            "error message should be bounded, got {} bytes",
            msg.len()
        );
    }

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
                suggestion: String::new(),
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
                pattern: "[".into(),
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
            Error::UnknownEncoding {
                got: "x".into(),
                suggestion: String::new(),
            },
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
            Error::Untranslatable {
                ch: '😀',
                byte_offset: 3,
            },
            Error::LossyDecode {
                encoding: "Shift_JIS".into(),
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

    /// Every message follows the house style (#187): non-empty, lowercase-first
    /// (bar identifiers), single-quoted values, and echoes the offending value.
    #[test]
    fn messages_follow_house_style() {
        // Lowercase so it doesn't trip the lowercase-first check when a message
        // (e.g. Sealed) begins with the echoed value itself.
        const MARKER: &str = "zzvaluezz";
        #[allow(clippy::invalid_regex)]
        let regex_err = regex::Regex::new("[").unwrap_err();
        // (sample, does the message echo MARKER?)
        let samples: Vec<(Error, bool)> = vec![
            (Error::InvalidErrorMode { got: MARKER.into() }, true),
            (Error::InvalidNormForm { got: MARKER.into() }, true),
            (Error::InvalidPipelineNormForm { got: MARKER.into() }, true),
            (Error::InvalidEmojiStyle { got: MARKER.into() }, true),
            (Error::InvalidPlatform { got: MARKER.into() }, true),
            (Error::InvalidTargetScript { got: MARKER.into() }, true),
            (
                Error::UnknownLang {
                    got: MARKER.into(),
                    suggestion: String::new(),
                    valid: "a, b".into(),
                },
                true,
            ),
            (Error::MutuallyExclusiveBare, false),
            (Error::MutuallyExclusivePipeline, false),
            (Error::BatchTooLarge { len: 2, max: 1 }, false),
            (Error::ReplacementOutputTooLarge { size: 2, max: 1 }, false),
            (Error::Sealed { op: MARKER.into() }, true),
            (Error::RegisterLangLimit { max: 1 }, false),
            // keys are rendered with {:?} (arbitrary content) — a double-quote exception.
            (
                Error::RegisterLangBadKeys {
                    keys: format!("{MARKER:?}"),
                },
                true,
            ),
            (
                Error::RegisterReplacementsLimit {
                    max: 1,
                    projected: 2,
                },
                false,
            ),
            (
                Error::ContextDictNotFound {
                    lang: MARKER.into(),
                },
                true,
            ),
            (
                Error::ContextDictCorrupt {
                    lang: MARKER.into(),
                    reason: "bad".into(),
                },
                true,
            ),
            (Error::RegexTooLong { len: 2, max: 1 }, false),
            (
                Error::RegexCompile {
                    pattern: MARKER.into(),
                    source: regex_err,
                },
                true,
            ),
            (
                Error::UniqueSlugAttemptsExceeded {
                    max: 1,
                    text: MARKER.into(),
                },
                true,
            ),
            (
                Error::UniqueSlugMaxLengthTooSmall {
                    max_length: 1,
                    separator: MARKER.into(),
                    min_unique_len: 2,
                },
                true,
            ),
            (
                Error::UnknownEncoding {
                    got: MARKER.into(),
                    suggestion: String::new(),
                },
                true,
            ),
            (Error::UnsupportedAutoEncoding { got: MARKER.into() }, true),
            (
                Error::EncodingConfidenceTooLow {
                    confidence: 0.5,
                    min_confidence: 0.9,
                    guess: MARKER.into(),
                },
                true,
            ),
            (
                Error::ReverseUnsupportedLang {
                    lang: MARKER.into(),
                    available: "ru".into(),
                },
                true,
            ),
            (
                Error::Untranslatable {
                    ch: '😀',
                    byte_offset: 3,
                },
                false,
            ),
            (
                Error::LossyDecode {
                    encoding: MARKER.into(),
                },
                true,
            ),
        ];

        // Identifiers permitted to begin a message with an uppercase letter.
        const ALLOWED_UPPERCASE: &[&str] = &["UniqueSlugifier"];
        // Variants that render arbitrary user content with `{:?}` (double quotes).
        fn allows_double_quote(e: &Error) -> bool {
            matches!(
                e,
                Error::RegexCompile { .. } | Error::RegisterLangBadKeys { .. }
            )
        }

        for (err, echoes_marker) in &samples {
            let msg = err.to_string();
            let code = err.code();
            assert!(!msg.is_empty(), "empty message for {code}");

            let first = msg.chars().next().unwrap();
            let upper_ok = ALLOWED_UPPERCASE.iter().any(|p| msg.starts_with(p));
            assert!(
                !first.is_alphabetic() || first.is_lowercase() || upper_ok,
                "{code}: message should start lowercase (or a known identifier): {msg:?}"
            );

            if !allows_double_quote(err) {
                assert!(
                    !msg.contains('"'),
                    "{code}: use single quotes, not double quotes: {msg:?}"
                );
            }

            if *echoes_marker {
                assert!(
                    msg.contains(MARKER),
                    "{code}: message must echo the offending value: {msg:?}"
                );
            }
        }
    }

    /// The "invalid argument value" family must always guide the caller to the
    /// valid set (#187): the message names the expected options or a remedy.
    #[test]
    fn invalid_value_messages_offer_a_remedy() {
        let samples = [
            Error::InvalidErrorMode { got: "x".into() },
            Error::InvalidNormForm { got: "x".into() },
            Error::InvalidPipelineNormForm { got: "x".into() },
            Error::InvalidEmojiStyle { got: "x".into() },
            Error::InvalidPlatform { got: "x".into() },
            Error::InvalidTargetScript { got: "x".into() },
            Error::UnknownLang {
                got: "x".into(),
                suggestion: String::new(),
                valid: "a, b".into(),
            },
        ];
        for e in &samples {
            let msg = e.to_string();
            assert!(
                msg.contains("must be") || msg.contains("expected") || msg.contains("one of"),
                "{}: should name the valid options: {msg:?}",
                e.code()
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
