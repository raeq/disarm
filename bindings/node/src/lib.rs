//! napi-rs bindings exposing the pure-Rust `disarm` core to Node.js (#44).
//!
//! Like the Ruby binding (`bindings/ruby/ext/disarm/src/lib.rs`), this file is the
//! **raw native shim**: each function is a thin wrapper over `disarm_core::api`
//! with positional arguments and string-token enums. The idiomatic TypeScript
//! surface — options objects, string-union types, sensible defaults, and the
//! `DisarmError` class — lives in the hand-written `index.ts` layer that calls
//! these. Keeping the shim dumb lets the core's surface be reshaped without
//! re-teaching the binding its idioms.
//!
//! napi-rs auto-camelCases the exported names (`normalize_confusables` →
//! `normalizeConfusables`) and generates `binding.d.ts` from these signatures and
//! doc comments. Fallible calls return a `napi::Error` whose message is prefixed
//! with `DisarmInvalidArgument:` (vs `DisarmError:`) so the TS layer can raise the
//! matching error subclass.

use std::collections::HashSet;

use disarm_core::api;
use napi::bindgen_prelude::Error as NapiError;
use napi_derive::napi;

/// Map a core error to a napi error, tagging the kind so the TS layer re-raises
/// the right `DisarmError` subclass.
fn map_err(e: &disarm_core::Error) -> NapiError {
    let tag = match e.kind() {
        disarm_core::ErrorKind::InvalidArgument => "DisarmInvalidArgument",
        _ => "DisarmError",
    };
    NapiError::from_reason(format!("{tag}: {e}"))
}

// ── Transliteration ───────────────────────────────────────────────────────────

/// Unicode → ASCII with the default scheme (the borrow-on-no-op fast path).
#[napi]
pub fn transliterate(text: String) -> String {
    api::transliterate(&text).into_owned()
}

/// Transliterate with a scheme (`"default"` | `"strict_iso9"` | `"gost7034"`)
/// and/or a language profile (`lang`), via the core's builder.
#[napi]
pub fn transliterate_opts(
    text: String,
    scheme: String,
    lang: Option<String>,
) -> Result<String, NapiError> {
    let mut b = api::Transliterate::new();
    if scheme != "default" {
        let scheme: api::Scheme = scheme.parse().map_err(|e| map_err(&e))?;
        b = b.scheme(scheme);
    }
    if let Some(lang) = lang {
        b = b.lang(lang);
    }
    Ok(b.run(&text).into_owned())
}

/// Reverse-transliterate Latin → native script. `lang` is `"el"` | `"ru"` | `"uk"`.
#[napi]
pub fn reverse_transliterate(text: String, lang: String) -> Result<String, NapiError> {
    let lang: api::ReverseLang = lang.parse().map_err(|e| map_err(&e))?;
    Ok(api::reverse_transliterate(&text, lang))
}

/// Characters with no romanization, as `{ char, offset }` (byte offset), in order.
#[napi]
pub fn find_untranslatable(
    text: String,
    scheme: String,
    lang: Option<String>,
) -> Result<Vec<Untranslatable>, NapiError> {
    let mut b = api::Transliterate::new();
    if scheme != "default" {
        let scheme: api::Scheme = scheme.parse().map_err(|e| map_err(&e))?;
        b = b.scheme(scheme);
    }
    if let Some(lang) = lang {
        b = b.lang(lang);
    }
    Ok(b.find_untranslatable(&text)
        .into_iter()
        .map(|u| Untranslatable {
            char: u.ch.to_string(),
            // i64 (→ JS number) holds any real byte offset without the u32
            // truncation a >4 GiB input could otherwise cause.
            offset: u.offset as i64,
        })
        .collect())
}

/// A character with no transliteration, located in the input.
#[napi(object)]
pub struct Untranslatable {
    /// The untranslatable character.
    pub char: String,
    /// Its byte offset in the input string.
    pub offset: i64,
}

// ── Confusables (TR39) ────────────────────────────────────────────────────────

/// Fold cross-script confusables toward `target` (`"latin"` | `"cyrillic"`).
#[napi]
pub fn normalize_confusables(text: String, target: String) -> Result<String, NapiError> {
    let target: api::TargetScript = target.parse().map_err(|e| map_err(&e))?;
    Ok(api::normalize_confusables(&text, target).into_owned())
}

/// Whether `text` contains a character confusable with `target`.
#[napi]
pub fn is_confusable(text: String, target: String) -> Result<bool, NapiError> {
    let target: api::TargetScript = target.parse().map_err(|e| map_err(&e))?;
    Ok(api::is_confusable(&text, target))
}

// ── Slugs ─────────────────────────────────────────────────────────────────────

/// The full slug option surface (the TS layer fills defaults before calling).
#[napi(object)]
pub struct SlugOptions {
    pub separator: String,
    pub lowercase: bool,
    pub max_length: u32,
    pub word_boundary: bool,
    pub save_order: bool,
    pub stopwords: Vec<String>,
    pub allow_unicode: bool,
    pub lang: Option<String>,
    pub entities: bool,
    pub decimal: bool,
    pub hexadecimal: bool,
    pub safe_chars: String,
}

/// Generate a URL-safe slug.
#[napi]
pub fn slugify(text: String, opts: SlugOptions) -> String {
    let mut config = api::SlugConfig::default()
        .with_separator(opts.separator)
        .with_lowercase(opts.lowercase)
        .with_max_length(opts.max_length as usize)
        .with_word_boundary(opts.word_boundary)
        .with_save_order(opts.save_order)
        .with_stopwords(opts.stopwords)
        .with_allow_unicode(opts.allow_unicode)
        .with_safe_chars(opts.safe_chars);
    if let Some(lang) = opts.lang {
        config = config.with_lang(lang);
    }
    config.entities = opts.entities;
    config.decimal = opts.decimal;
    config.hexadecimal = opts.hexadecimal;
    api::slugify(&text, &config)
}

// ── Canonicalization primitives ───────────────────────────────────────────────

#[napi]
pub fn strip_accents(text: String) -> String {
    api::strip_accents(&text).into_owned()
}

#[napi]
pub fn fold_case(text: String) -> String {
    api::fold_case(&text).into_owned()
}

/// Replace emoji with their plain names; `strip_modifiers` drops skin-tone marks.
#[napi]
pub fn demojize(text: String, strip_modifiers: bool) -> String {
    api::demojize(&text, strip_modifiers)
}

// ── Normalization ─────────────────────────────────────────────────────────────

/// Apply a normalization form: `"NFC"` | `"NFD"` | `"NFKC"` | `"NFKD"`.
#[napi]
pub fn normalize(text: String, form: String) -> Result<String, NapiError> {
    let form: api::NormalizationForm = form.parse().map_err(|e| map_err(&e))?;
    Ok(api::normalize(&text, form))
}

/// Whether `text` is already in normalization `form`.
#[napi]
pub fn is_normalized(text: String, form: String) -> Result<bool, NapiError> {
    let form: api::NormalizationForm = form.parse().map_err(|e| map_err(&e))?;
    Ok(api::is_normalized(&text, form))
}

// ── Text cleaning ─────────────────────────────────────────────────────────────

#[napi]
pub fn collapse_whitespace(text: String, strip_control: bool, strip_zero_width: bool) -> String {
    api::collapse_whitespace(&text, strip_control, strip_zero_width)
}

#[napi]
pub fn strip_control_chars(text: String) -> String {
    api::strip_control_chars(&text)
}

#[napi]
pub fn strip_zero_width_chars(text: String) -> String {
    api::strip_zero_width_chars(&text)
}

#[napi]
pub fn strip_bidi(text: String) -> String {
    api::strip_bidi(&text)
}

#[napi]
pub fn strip_zalgo(text: String, max_marks: u32) -> String {
    api::strip_zalgo(&text, max_marks as usize)
}

#[napi]
pub fn is_zalgo(text: String, threshold: u32) -> bool {
    api::is_zalgo(&text, threshold as usize)
}

// ── Deobfuscation & security presets (fallible) ───────────────────────────────

#[napi]
pub fn strip_obfuscation(text: String) -> Result<String, NapiError> {
    api::strip_obfuscation(&text).map_err(|e| map_err(&e))
}

#[napi]
pub fn security_clean(text: String) -> Result<String, NapiError> {
    api::security_clean(&text).map_err(|e| map_err(&e))
}

/// Turn arbitrary text into a safe filename. `platform` is `"universal"` |
/// `"windows"` | `"posix"`.
#[napi]
pub fn sanitize_filename(
    text: String,
    separator: String,
    max_length: u32,
    platform: String,
    lang: Option<String>,
    preserve_extension: bool,
) -> Result<String, NapiError> {
    let platform: api::Platform = platform.parse().map_err(|e| map_err(&e))?;
    api::sanitize_filename(
        &text,
        &separator,
        max_length as usize,
        platform,
        lang.as_deref(),
        preserve_extension,
    )
    .map_err(|e| map_err(&e))
}

// ── Grapheme clusters ─────────────────────────────────────────────────────────

#[napi]
pub fn grapheme_len(text: String) -> u32 {
    api::grapheme_len(&text) as u32
}

#[napi]
pub fn grapheme_split(text: String) -> Vec<String> {
    api::grapheme_split(&text)
}

#[napi]
pub fn grapheme_truncate(text: String, max_graphemes: u32) -> String {
    api::grapheme_truncate(&text, max_graphemes as usize)
}

#[napi]
pub fn grapheme_width(cluster: String, ambiguous_wide: bool) -> u32 {
    api::grapheme_width(&cluster, ambiguous_wide) as u32
}

#[napi]
pub fn terminal_width(text: String, ambiguous_wide: bool) -> u32 {
    api::terminal_width(&text, ambiguous_wide) as u32
}

// ── Hostname / script analysis ────────────────────────────────────────────────

/// Whether the hostname looks like a mixed-script / confusable IDN spoof. A
/// `false` asserts nothing was *found*, not that the host is safe.
#[napi]
pub fn is_suspicious_hostname(host: String) -> bool {
    api::is_suspicious_hostname(&host).suspicious
}

/// The Unicode scripts present, in first-appearance order (Common/Inherited
/// excluded), as stable UCD identifiers.
#[napi]
pub fn detect_scripts(text: String) -> Vec<String> {
    api::detect_scripts(&text)
        .into_iter()
        .map(str::to_owned)
        .collect()
}

/// Whether `text` mixes characters from more than one script.
#[napi]
pub fn is_mixed_script(text: String) -> bool {
    api::is_mixed_script(&text)
}

/// How `lang: "auto"` detection resolves `text`.
#[napi(object)]
pub struct AutoLangInspection {
    /// The primary non-Latin script detected, if any (e.g. `"Cyrillic"`).
    pub script: Option<String>,
    /// The language auto-detection chose, if any (e.g. `"ru"`).
    pub chosen_lang: Option<String>,
    /// Why that choice was made.
    pub reason: String,
    /// The discriminator characters that drove the choice, if any.
    pub discriminators_hit: Vec<String>,
}

/// Explain how auto-language detection resolves `text`.
#[napi]
pub fn inspect_auto_lang(text: String) -> AutoLangInspection {
    let r = api::inspect_auto_lang(&text);
    AutoLangInspection {
        script: r.script,
        chosen_lang: r.chosen_lang,
        reason: r.reason,
        discriminators_hit: r.discriminators_hit,
    }
}

// ── Anomaly detection (#389) ──────────────────────────────────────────────────

/// One reason a token is anomalous (a single finding).
#[napi(object)]
pub struct Finding {
    /// Which branch fired: `"invisible"` | `"bidi"` | `"zalgo"` | `"mixed_script"` | `"leet"` | `"segmentation"`.
    pub kind: String,
    /// The offending whitespace token, as it appeared.
    pub token: String,
    /// Byte offset of the token start in the input.
    pub start: i64,
    /// Byte offset of the token end in the input.
    pub end: i64,
    /// Evidence: the codepoint, the scripts, or the decoded word.
    pub detail: String,
    /// A plain-language sentence describing the finding.
    pub reason: String,
}

/// Structured anomaly report.
#[napi(object)]
pub struct AnomalyReport {
    /// Whether any token tripped (the same value `hasAnomalies` returns).
    pub anomalous: bool,
    /// The anomaly kinds that fired, in first-appearance order.
    pub kinds: Vec<String>,
    /// Every finding, with span and detail.
    pub findings: Vec<Finding>,
    /// The first finding's reason, if any.
    pub reason: Option<String>,
}

/// `hasAnomalies(text, lexicon)` — `lexicon` is an array of common words.
#[napi]
pub fn has_anomalies(text: String, lexicon: Vec<String>) -> bool {
    let lex: HashSet<String> = lexicon.into_iter().collect();
    api::has_anomalies(&text, &lex)
}

/// `inspectAnomalies(text, lexicon)` — full analysis with per-token findings.
#[napi]
pub fn inspect_anomalies(text: String, lexicon: Vec<String>) -> AnomalyReport {
    let lex: HashSet<String> = lexicon.into_iter().collect();
    let r = api::inspect_anomalies(&text, &lex);
    AnomalyReport {
        anomalous: r.anomalous,
        kinds: r.kinds.iter().map(|k| k.as_str().to_string()).collect(),
        findings: r
            .findings
            .into_iter()
            .map(|f| {
                let reason = f.reason();
                Finding {
                    kind: f.kind.as_str().to_string(),
                    token: f.token,
                    start: f.start as i64,
                    end: f.end as i64,
                    detail: f.detail,
                    reason,
                }
            })
            .collect(),
        reason: r.reason,
    }
}
