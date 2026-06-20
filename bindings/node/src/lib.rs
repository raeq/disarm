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

// S-4: this shim is an FFI boundary that must never panic across into Node. Lock
// that in structurally with the no-panic restriction lints (caught by the binding's
// clippy gate). A genuine invariant violation should return a `napi::Error`, not
// `unwrap`/`panic`.
#![cfg_attr(
    not(test),
    deny(
        clippy::unwrap_used,
        clippy::expect_used,
        clippy::indexing_slicing,
        clippy::string_slice,
        clippy::panic,
        clippy::todo,
        clippy::unimplemented
    )
)]

use std::collections::HashSet;

use disarm_core::api;
use napi::bindgen_prelude::{ClassInstance, Either, Error as NapiError};
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

/// Validate a size/threshold parameter and cast it to `usize`.
///
/// napi coerces JS numbers to `i64` here (not `u32`) precisely so a negative
/// value survives as a negative integer instead of silently wrapping to a huge
/// `u32` via `ToUint32`. We reject negatives with a `DisarmInvalidArgument`-tagged
/// error — matching the Python/Ruby bindings, whose core `checked_*` validators
/// are crate-internal and not reachable through `disarm_core::api`.
fn checked_size(name: &str, value: i64) -> Result<usize, NapiError> {
    if value < 0 {
        return Err(NapiError::from_reason(format!(
            "DisarmInvalidArgument: {name} must be non-negative (got {value})"
        )));
    }
    Ok(value as usize)
}

/// Build the anomaly lexicon set from the incoming word list. Delegates to
/// `api::lexicon`, which lowercases entries so a title-cased wordlist (`"Free"`)
/// still matches the detector's lowercased decoded words (`fr33`).
fn to_lexicon(v: Vec<String>) -> HashSet<String> {
    api::lexicon(v)
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
    pub max_length: i64,
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
pub fn slugify(text: String, opts: SlugOptions) -> Result<String, NapiError> {
    let max_length = checked_size("maxLength", opts.max_length)?;
    let mut config = api::SlugConfig::default()
        .with_separator(opts.separator)
        .with_lowercase(opts.lowercase)
        .with_max_length(max_length)
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
    Ok(api::slugify(&text, &config))
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
pub fn collapse_whitespace(text: String) -> String {
    api::collapse_whitespace(&text)
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

/// Strip the Unicode Tags block (U+E0000–U+E007F), preserving valid emoji flags (#413).
#[napi]
pub fn strip_tags(text: String) -> String {
    api::strip_tags(&text)
}

/// Strip every variation selector (VS1–VS256) (#413).
#[napi]
pub fn strip_variation_selectors(text: String) -> String {
    api::strip_variation_selectors(&text)
}

/// Strip every Unicode noncharacter (#413).
#[napi]
pub fn strip_noncharacters(text: String) -> String {
    api::strip_noncharacters(&text)
}

/// Strip every Private Use Area code point (#413).
#[napi]
pub fn strip_pua(text: String) -> String {
    api::strip_pua(&text)
}

#[napi]
pub fn strip_zalgo(text: String, max_marks: i64) -> Result<String, NapiError> {
    let max_marks = checked_size("maxMarks", max_marks)?;
    Ok(api::strip_zalgo(&text, max_marks))
}

#[napi]
pub fn is_zalgo(text: String, threshold: i64) -> Result<bool, NapiError> {
    let threshold = checked_size("threshold", threshold)?;
    Ok(api::is_zalgo(&text, threshold))
}

// ── Deobfuscation & security presets (fallible) ───────────────────────────────

#[napi]
pub fn strip_obfuscation(text: String) -> Result<String, NapiError> {
    api::strip_obfuscation(&text)
        .map(std::borrow::Cow::into_owned)
        .map_err(|e| map_err(&e))
}

#[napi]
pub fn canonicalize(text: String) -> Result<String, NapiError> {
    api::canonicalize(&text)
        .map(std::borrow::Cow::into_owned)
        .map_err(|e| map_err(&e))
}

/// Turn arbitrary text into a safe filename. `platform` is `"universal"` |
/// `"windows"` | `"posix"`.
#[napi]
pub fn sanitize_filename(
    text: String,
    separator: String,
    max_length: i64,
    platform: String,
    lang: Option<String>,
    preserve_extension: bool,
) -> Result<String, NapiError> {
    let max_length = checked_size("maxLength", max_length)?;
    let platform: api::Platform = platform.parse().map_err(|e| map_err(&e))?;
    api::sanitize_filename(
        &text,
        &separator,
        max_length,
        platform,
        lang.as_deref(),
        preserve_extension,
    )
    .map_err(|e| map_err(&e))
}

// ── Key-derivation presets (fallible, #404) ───────────────────────────────────

/// Case/accent/script-insensitive search lookup key. `lang` selects the
/// transliteration table (omit for none).
#[napi]
pub fn search_key(text: String, lang: Option<String>) -> Result<String, NapiError> {
    api::search_key(&text, lang.as_deref())
        .map(std::borrow::Cow::into_owned)
        .map_err(|e| map_err(&e))
}

/// Collation sort key (like `searchKey` but preserves base accented characters
/// for correct ordering). `lang` selects the transliteration table.
#[napi]
pub fn sort_key(text: String, lang: Option<String>) -> Result<String, NapiError> {
    api::sort_key(&text, lang.as_deref())
        .map(std::borrow::Cow::into_owned)
        .map_err(|e| map_err(&e))
}

/// Library catalog deduplication key (like `searchKey` plus confusable folding).
/// `lang` selects the transliteration table; `strict_iso9` picks the ISO 9:1995
/// Cyrillic scheme.
#[napi]
pub fn catalog_key(
    text: String,
    lang: Option<String>,
    strict_iso9: bool,
) -> Result<String, NapiError> {
    api::catalog_key(&text, lang.as_deref(), strict_iso9)
        .map(std::borrow::Cow::into_owned)
        .map_err(|e| map_err(&e))
}

// ── Grapheme clusters ─────────────────────────────────────────────────────────

#[napi]
pub fn grapheme_len(text: String) -> i64 {
    api::grapheme_len(&text) as i64
}

#[napi]
pub fn grapheme_split(text: String) -> Vec<String> {
    api::grapheme_split(&text)
}

#[napi]
pub fn grapheme_truncate(text: String, max_graphemes: i64) -> Result<String, NapiError> {
    let max_graphemes = checked_size("maxGraphemes", max_graphemes)?;
    Ok(api::grapheme_truncate(&text, max_graphemes))
}

#[napi]
pub fn grapheme_width(cluster: String, ambiguous_wide: bool) -> i64 {
    api::grapheme_width(&cluster, ambiguous_wide) as i64
}

#[napi]
pub fn terminal_width(text: String, ambiguous_wide: bool) -> i64 {
    api::terminal_width(&text, ambiguous_wide) as i64
}

// ── Hostname / script analysis ────────────────────────────────────────────────

/// Whether the hostname looks like a mixed-script / confusable / bidi-reorder
/// IDN spoof. Flags a single mixed-script label, a Latin confusable, or a
/// bidi-direction conflict (`hasBidiConflict`, the "BiDi Swap" precondition,
/// #412). A `false` asserts nothing was *found*, not that the host is safe.
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

/// Whether `text` mixes strong left-to-right and strong right-to-left characters
/// — the precondition for Bidi display-reordering ("BiDi Swap"). Fires on the
/// real letters (no `U+202x` override); a `false` result is not a safety
/// guarantee.
#[napi]
pub fn has_bidi_conflict(text: String) -> bool {
    api::has_bidi_conflict(&text)
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

// ── Metadata introspection (#404) ─────────────────────────────────────────────

/// Static facts about a language profile (the `lang` codes accepted across the API).
#[napi(object)]
pub struct LangMeta {
    /// The language's English name (e.g. `"German"`).
    pub name: String,
    /// The primary script it is written in (e.g. `"Latin"`).
    pub script: String,
    /// The region/locale it is associated with.
    pub region: String,
    /// Context-aware transliteration support: `"none"`, `"partial"`, or `"full"`.
    pub context: String,
}

/// Static facts about a Unicode script known to the transliteration tables.
#[napi(object)]
pub struct ScriptMeta {
    /// The script's name (e.g. `"Coptic"`).
    pub name: String,
    /// The default language code for the script, if any (e.g. `"cop"`).
    pub default_lang: Option<String>,
    /// A short example string in the script.
    pub example: String,
    /// Whether transliteration of this script is context-aware.
    pub context_aware: bool,
}

/// Look up static facts about a language `code`. An unknown code raises a
/// `DisarmInvalidArgument`-tagged error.
#[napi]
pub fn lang_info(code: String) -> Result<LangMeta, NapiError> {
    let m = api::lang_info(&code).map_err(|e| map_err(&e))?;
    Ok(LangMeta {
        name: m.name.to_string(),
        script: m.script.to_string(),
        region: m.region.to_string(),
        context: m.context.to_string(),
    })
}

/// Look up static facts about a script by `name`. An unknown name raises a
/// `DisarmInvalidArgument`-tagged error.
#[napi]
pub fn script_info(name: String) -> Result<ScriptMeta, NapiError> {
    let m = api::script_info(&name).map_err(|e| map_err(&e))?;
    Ok(ScriptMeta {
        name: m.name.to_string(),
        default_lang: m.default_lang.map(str::to_owned),
        example: m.example.to_string(),
        context_aware: m.context_aware,
    })
}

/// Every Unicode script name known to the transliteration tables.
#[napi]
pub fn list_scripts() -> Vec<String> {
    api::list_scripts().into_iter().map(str::to_owned).collect()
}

/// Every language code that has a context-aware transliteration profile.
#[napi]
pub fn list_context_langs() -> Vec<String> {
    api::list_context_langs()
        .into_iter()
        .map(str::to_owned)
        .collect()
}

// ── Anomaly detection (#389) ──────────────────────────────────────────────────

/// One reason a token is anomalous (a single finding).
#[napi(object)]
pub struct Finding {
    /// Which branch fired: `"invisible"` | `"bidi"` | `"zalgo"` | `"mixed_script"` | `"bidi_mixed"` | `"leet"` | `"segmentation"`.
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

/// A reusable, opaque lexicon handle (HAI-SDLC 6.1).
///
/// `hasAnomalies` / `inspectAnomalies` rebuild a `HashSet<String>` from the
/// caller's word array on every call. A caller hitting these in a loop with a
/// large lexicon pays that rebuild each time. `Lexicon` builds the internal set
/// once in its constructor and is then reused across calls.
#[napi]
pub struct Lexicon {
    inner: HashSet<String>,
}

#[napi]
impl Lexicon {
    /// Build a reusable lexicon from a word list, folding it into the internal
    /// set once.
    #[napi(constructor)]
    pub fn new(words: Vec<String>) -> Self {
        Self {
            inner: to_lexicon(words),
        }
    }
}

/// `hasAnomalies(text, lexicon)` — `lexicon` is either an array of common words
/// or a prebuilt `Lexicon` handle (no per-call rebuild).
#[napi]
pub fn has_anomalies(text: String, lexicon: Either<Vec<String>, ClassInstance<Lexicon>>) -> bool {
    match lexicon {
        Either::A(words) => api::has_anomalies(&text, &to_lexicon(words)),
        Either::B(lex) => api::has_anomalies(&text, &lex.inner),
    }
}

/// `inspectAnomalies(text, lexicon)` — full analysis with per-token findings.
/// `lexicon` is either an array of common words or a prebuilt `Lexicon` handle.
#[napi]
pub fn inspect_anomalies(
    text: String,
    lexicon: Either<Vec<String>, ClassInstance<Lexicon>>,
) -> AnomalyReport {
    let r = match lexicon {
        Either::A(words) => api::inspect_anomalies(&text, &to_lexicon(words)),
        Either::B(lex) => api::inspect_anomalies(&text, &lex.inner),
    };
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

// ── Pipeline (reusable policy-profile handle, #404) ───────────────────────────

/// A reusable, opaque named-policy-profile pipeline handle (#404).
///
/// `getPipeline` validates and compiles a profile's steps once; the resulting
/// handle is then applied to any number of inputs via `process`. Like the
/// `Lexicon` handle, the build cost is paid a single time and reused across
/// calls, rather than re-resolved per call.
#[napi]
pub struct Pipeline {
    inner: api::Pipeline,
}

#[napi]
impl Pipeline {
    /// Run the named pipeline over `text`, returning the cleaned string.
    #[napi]
    pub fn process(&self, text: String) -> Result<String, NapiError> {
        self.inner.process(&text).map_err(|e| map_err(&e))
    }
}

/// `getPipeline(profile)` — build a reusable `Pipeline` handle for a named
/// policy profile. An unknown profile raises a `DisarmInvalidArgument`-tagged
/// error naming the available profiles.
#[napi]
pub fn get_pipeline(profile: String) -> Result<Pipeline, NapiError> {
    Ok(Pipeline {
        inner: api::get_pipeline(&profile).map_err(|e| map_err(&e))?,
    })
}
