//! magnus bindings exposing the pure-Rust `disarm` core as the Ruby `Disarm`
//! module (#45). Every method is a thin wrapper over `disarm_core::api`, so the
//! security/transform behaviour is defined once in the core and inherited here.
//!
//! This file is deliberately the *raw* shim: positional arguments, string scheme
//! / target tokens, and standard Ruby exceptions. The idiomatic Ruby surface —
//! keyword arguments, symbol tokens, defaults, the `Disarm::Error` hierarchy, and
//! the single `transliterate(text, scheme:)` entrypoint — is a thin pure-Ruby
//! layer in `lib/disarm.rb` that forwards to the `_`-prefixed methods defined
//! here (#357). Keeping the native side raw avoids fighting magnus's fixed-arity
//! `function!` over keyword handling.
//!
//! Targets magnus 0.7 (Ruby >= 3.1). Build via rake-compiler / rb-sys, not
//! `cargo build` directly (it needs the Ruby headers rb-sys configures).

use std::collections::HashSet;

use disarm_core::api;
use magnus::{function, prelude::*, Error, Ruby};

/// Map a `disarm` error onto the closest standard Ruby exception:
/// `InvalidArgument` → `ArgumentError`, everything else → `RuntimeError`. The
/// pure-Ruby layer (`lib/disarm.rb`) rescues these and re-raises them as
/// `Disarm::InvalidArgument` / `Disarm::Error` so consumers can `rescue
/// Disarm::Error` (#357); raising the built-ins here keeps the native side free
/// of any dependency on Ruby-defined classes existing at call time.
fn raise(e: &disarm_core::Error) -> Error {
    let class = match e.kind() {
        disarm_core::ErrorKind::InvalidArgument => magnus::exception::arg_error(),
        _ => magnus::exception::runtime_error(),
    };
    Error::new(class, e.to_string())
}

// ── Transliteration ───────────────────────────────────────────────────────────

/// `Disarm._transliterate(text)` — Unicode → ASCII with the default scheme (the
/// common case; keeps the core's borrow-on-no-op fast path).
fn transliterate(text: String) -> String {
    api::transliterate(&text).into_owned()
}

/// `Disarm._transliterate_opts(text, "default" | "strict_iso9" | "gost7034", lang)`
/// — a scheme and/or a language profile via the core's `Transliterate` builder.
/// `lang` is `nil` (no profile) or a code like `"uk"` (Київ → Kyiv); it composes
/// with the scheme. The idiomatic layer routes the bare-default/no-lang case to
/// `_transliterate` so this is only hit when at least one option is set.
fn transliterate_opts(text: String, scheme: String, lang: Option<String>) -> Result<String, Error> {
    let mut builder = api::Transliterate::new();
    if scheme != "default" {
        let scheme: api::Scheme = scheme.parse().map_err(|e| raise(&e))?;
        builder = builder.scheme(scheme);
    }
    if let Some(lang) = lang {
        builder = builder.lang(lang);
    }
    Ok(builder.run(&text).into_owned())
}

// ── Confusables (TR39) ────────────────────────────────────────────────────────

/// `Disarm._normalize_confusables(text, "latin" | "cyrillic")`.
fn normalize_confusables(text: String, target: String) -> Result<String, Error> {
    let target: api::TargetScript = target.parse().map_err(|e| raise(&e))?;
    Ok(api::normalize_confusables(&text, target).into_owned())
}

/// `Disarm._confusable?(text, "latin" | "cyrillic")`.
fn is_confusable(text: String, target: String) -> Result<bool, Error> {
    let target: api::TargetScript = target.parse().map_err(|e| raise(&e))?;
    Ok(api::is_confusable(&text, target))
}

// ── Canonicalization primitives ───────────────────────────────────────────────

fn strip_accents(text: String) -> String {
    api::strip_accents(&text).into_owned()
}

fn fold_case(text: String) -> String {
    api::fold_case(&text).into_owned()
}

/// `Disarm._slugify(text, …)` — the full slug option surface, positional. The
/// Ruby layer maps its keyword arguments (with the core's documented defaults)
/// onto this order. `regex_pattern` and `replacements` are intentionally not
/// surfaced yet (they need non-scalar Ruby↔Rust conversion); everything else the
/// core's `SlugConfig` exposes is reachable.
#[allow(clippy::too_many_arguments)]
fn slugify(
    text: String,
    separator: String,
    lowercase: bool,
    max_length: usize,
    word_boundary: bool,
    save_order: bool,
    stopwords: Vec<String>,
    allow_unicode: bool,
    lang: Option<String>,
    entities: bool,
    decimal: bool,
    hexadecimal: bool,
    safe_chars: String,
) -> String {
    let mut config = api::SlugConfig::default()
        .with_separator(separator)
        .with_lowercase(lowercase)
        .with_max_length(max_length)
        .with_word_boundary(word_boundary)
        .with_save_order(save_order)
        .with_stopwords(stopwords)
        .with_allow_unicode(allow_unicode)
        .with_safe_chars(safe_chars);
    if let Some(lang) = lang {
        config = config.with_lang(lang);
    }
    // `entities`/`decimal`/`hexadecimal` have no chainable setter; the fields are
    // public, so set them directly (the core defaults all three to `true`).
    config.entities = entities;
    config.decimal = decimal;
    config.hexadecimal = hexadecimal;
    api::slugify(&text, &config)
}

/// `Disarm._demojize(text, strip_modifiers)`.
fn demojize(text: String, strip_modifiers: bool) -> String {
    api::demojize(&text, strip_modifiers)
}

// ── Security presets (fallible) ───────────────────────────────────────────────

fn strip_obfuscation(text: String) -> Result<String, Error> {
    api::strip_obfuscation(&text).map_err(|e| raise(&e))
}

fn security_clean(text: String) -> Result<String, Error> {
    api::security_clean(&text).map_err(|e| raise(&e))
}

/// `Disarm._suspicious_hostname?(host)` — flags mixed-script / confusable IDN
/// spoofs. A false result asserts nothing was *found*, not that the host is safe.
fn suspicious_hostname(host: String) -> bool {
    // #362 made the Rust api return `HostnameAnalysis` (the verdict is its
    // `suspicious` field) instead of a `(bool, _)` tuple.
    api::is_suspicious_hostname(&host).suspicious
}

// ── Normalization (#375) ──────────────────────────────────────────────────────

/// `Disarm._normalize(text, "NFC" | "NFD" | "NFKC" | "NFKD")`. The idiomatic
/// layer upcases its `form:` symbol/string before forwarding.
fn normalize(text: String, form: String) -> Result<String, Error> {
    let form: api::NormalizationForm = form.parse().map_err(|e| raise(&e))?;
    Ok(api::normalize(&text, form))
}

/// `Disarm._normalized?(text, form)`.
fn is_normalized(text: String, form: String) -> Result<bool, Error> {
    let form: api::NormalizationForm = form.parse().map_err(|e| raise(&e))?;
    Ok(api::is_normalized(&text, form))
}

// ── Text cleaning (#375) ──────────────────────────────────────────────────────

/// `Disarm._collapse_whitespace(text, strip_control, strip_zero_width)`.
fn collapse_whitespace(text: String, strip_control: bool, strip_zero_width: bool) -> String {
    api::collapse_whitespace(&text, strip_control, strip_zero_width)
}

/// `Disarm._strip_control_chars(text)` — remove C0/C1 controls (except tab/newline).
fn strip_control_chars(text: String) -> String {
    api::strip_control_chars(&text)
}

/// `Disarm._strip_zero_width_chars(text)` — remove ZWSP/ZWNJ/ZWJ/word-joiner.
fn strip_zero_width_chars(text: String) -> String {
    api::strip_zero_width_chars(&text)
}

/// `Disarm._strip_bidi(text)` — remove Unicode bidirectional control characters.
fn strip_bidi(text: String) -> String {
    api::strip_bidi(&text)
}

/// `Disarm._strip_zalgo(text, max_marks)` — cap combining marks per base.
fn strip_zalgo(text: String, max_marks: usize) -> String {
    api::strip_zalgo(&text, max_marks)
}

/// `Disarm._zalgo?(text, threshold)` — any base carrying > threshold marks.
fn is_zalgo(text: String, threshold: usize) -> bool {
    api::is_zalgo(&text, threshold)
}

// ── Grapheme clusters (#375) ──────────────────────────────────────────────────

/// `Disarm._grapheme_len(text)` — count of user-perceived characters.
fn grapheme_len(text: String) -> usize {
    api::grapheme_len(&text)
}

/// `Disarm._grapheme_split(text)` — split into grapheme-cluster strings.
fn grapheme_split(text: String) -> Vec<String> {
    api::grapheme_split(&text)
}

/// `Disarm._grapheme_truncate(text, max_graphemes)` — truncate by graphemes,
/// never mid-cluster.
fn grapheme_truncate(text: String, max_graphemes: usize) -> String {
    api::grapheme_truncate(&text, max_graphemes)
}

/// `Disarm._grapheme_width(cluster, ambiguous_wide)` — display columns of one
/// cluster (East Asian Width).
fn grapheme_width(cluster: String, ambiguous_wide: bool) -> usize {
    api::grapheme_width(&cluster, ambiguous_wide)
}

/// `Disarm._terminal_width(text, ambiguous_wide)` — display columns of the whole
/// string.
fn terminal_width(text: String, ambiguous_wide: bool) -> usize {
    api::terminal_width(&text, ambiguous_wide)
}

// ── Filenames (#375) ──────────────────────────────────────────────────────────

/// `Disarm._sanitize_filename(text, separator, max_length, platform, lang,
/// preserve_extension)` — fallible; `platform` is "universal" | "windows" | "posix".
#[allow(clippy::too_many_arguments)]
fn sanitize_filename(
    text: String,
    separator: String,
    max_length: usize,
    platform: String,
    lang: Option<String>,
    preserve_extension: bool,
) -> Result<String, Error> {
    let platform: api::Platform = platform.parse().map_err(|e| raise(&e))?;
    api::sanitize_filename(
        &text,
        &separator,
        max_length,
        platform,
        lang.as_deref(),
        preserve_extension,
    )
    .map_err(|e| raise(&e))
}

// ── Reverse transliteration & untranslatable scan (#375) ──────────────────────

/// `Disarm._reverse_transliterate(text, lang)` — Latin → native; `lang` is
/// "el" | "ru" | "uk".
fn reverse_transliterate(text: String, lang: String) -> Result<String, Error> {
    let lang: api::ReverseLang = lang.parse().map_err(|e| raise(&e))?;
    Ok(api::reverse_transliterate(&text, lang))
}

/// `Disarm._find_untranslatable(text, scheme, lang)` — every character with no
/// romanization, as `[char, byte_offset]` pairs (the Ruby layer maps these to
/// `{ char:, offset: }` hashes).
fn find_untranslatable(
    text: String,
    scheme: String,
    lang: Option<String>,
) -> Result<Vec<(String, usize)>, Error> {
    let mut builder = api::Transliterate::new();
    if scheme != "default" {
        let scheme: api::Scheme = scheme.parse().map_err(|e| raise(&e))?;
        builder = builder.scheme(scheme);
    }
    if let Some(lang) = lang {
        builder = builder.lang(lang);
    }
    Ok(builder
        .find_untranslatable(&text)
        .into_iter()
        .map(|u| (u.ch.to_string(), u.offset))
        .collect())
}

// ── Script analysis (#375) ────────────────────────────────────────────────────

/// `Disarm._detect_scripts(text)` — Unicode scripts present, in first-appearance
/// order (Common/Inherited excluded).
fn detect_scripts(text: String) -> Vec<String> {
    api::detect_scripts(&text)
        .into_iter()
        .map(str::to_owned)
        .collect()
}

/// `Disarm._is_mixed_script?(text)` — whether `text` mixes more than one script.
fn is_mixed_script(text: String) -> bool {
    api::is_mixed_script(&text)
}

/// `Disarm._inspect_auto_lang(text)` — `[script, chosen_lang, reason,
/// discriminators_hit]` (the Ruby layer maps it to a hash). `script`/`chosen_lang`
/// are nil when nothing was detected.
fn inspect_auto_lang(text: String) -> (Option<String>, Option<String>, String, Vec<String>) {
    let r = api::inspect_auto_lang(&text);
    (r.script, r.chosen_lang, r.reason, r.discriminators_hit)
}

// ── Anomaly detection (#389) ──────────────────────────────────────────────────

/// `Disarm._has_anomalies?(text, lexicon)` — `lexicon` is an array of common words.
fn has_anomalies(text: String, lexicon: Vec<String>) -> bool {
    let lex: HashSet<String> = lexicon.into_iter().collect();
    api::has_anomalies(&text, &lex)
}

/// `Disarm._inspect_anomalies(text, lexicon)` — `[anomalous, kinds, findings,
/// reason]` where each finding is `[kind, token, start, end, detail, reason]` (the
/// Ruby layer maps it to a hash).
#[allow(clippy::type_complexity)]
fn inspect_anomalies(
    text: String,
    lexicon: Vec<String>,
) -> (
    bool,
    Vec<String>,
    Vec<(String, String, usize, usize, String, String)>,
    Option<String>,
) {
    let lex: HashSet<String> = lexicon.into_iter().collect();
    let r = api::inspect_anomalies(&text, &lex);
    let findings = r
        .findings
        .into_iter()
        .map(|f| {
            let reason = f.reason();
            (
                f.kind.as_str().to_string(),
                f.token,
                f.start,
                f.end,
                f.detail,
                reason,
            )
        })
        .collect();
    let kinds = r.kinds.iter().map(|k| k.as_str().to_string()).collect();
    (r.anomalous, kinds, findings, r.reason)
}

// `name = "disarm"` so the exported init symbol is `Init_disarm` (matching the
// `disarm.so` the gem loads), independent of the `disarm-ruby` package name.
#[magnus::init(name = "disarm")]
fn init(ruby: &Ruby) -> Result<(), Error> {
    let module = ruby.define_module("Disarm")?;

    // Raw, `_`-prefixed shims wrapped by the idiomatic Ruby layer (#357).
    module.define_singleton_method("_transliterate", function!(transliterate, 1))?;
    module.define_singleton_method("_transliterate_opts", function!(transliterate_opts, 3))?;
    module.define_singleton_method(
        "_normalize_confusables",
        function!(normalize_confusables, 2),
    )?;
    module.define_singleton_method("_confusable?", function!(is_confusable, 2))?;
    module.define_singleton_method("_slugify", function!(slugify, 13))?;
    module.define_singleton_method("_demojize", function!(demojize, 2))?;
    module.define_singleton_method("_strip_obfuscation", function!(strip_obfuscation, 1))?;
    module.define_singleton_method("_security_clean", function!(security_clean, 1))?;

    // No options / no symbols, but still wrapped by the Ruby layer so a wrong-type
    // argument surfaces as Disarm::InvalidArgument rather than a raw TypeError —
    // keeping `rescue Disarm::Error` exhaustive across the whole public surface.
    module.define_singleton_method("_strip_accents", function!(strip_accents, 1))?;
    module.define_singleton_method("_fold_case", function!(fold_case, 1))?;
    module.define_singleton_method("_suspicious_hostname?", function!(suspicious_hostname, 1))?;

    // Normalization + text-cleaning primitives (#375 parity backfill).
    module.define_singleton_method("_normalize", function!(normalize, 2))?;
    module.define_singleton_method("_normalized?", function!(is_normalized, 2))?;
    module.define_singleton_method("_collapse_whitespace", function!(collapse_whitespace, 3))?;
    module.define_singleton_method("_strip_control_chars", function!(strip_control_chars, 1))?;
    module.define_singleton_method(
        "_strip_zero_width_chars",
        function!(strip_zero_width_chars, 1),
    )?;
    module.define_singleton_method("_strip_bidi", function!(strip_bidi, 1))?;
    module.define_singleton_method("_strip_zalgo", function!(strip_zalgo, 2))?;
    module.define_singleton_method("_zalgo?", function!(is_zalgo, 2))?;

    // Grapheme-cluster operations (#375 parity backfill).
    module.define_singleton_method("_grapheme_len", function!(grapheme_len, 1))?;
    module.define_singleton_method("_grapheme_split", function!(grapheme_split, 1))?;
    module.define_singleton_method("_grapheme_truncate", function!(grapheme_truncate, 2))?;
    module.define_singleton_method("_grapheme_width", function!(grapheme_width, 2))?;
    module.define_singleton_method("_terminal_width", function!(terminal_width, 2))?;

    // Filenames, reverse transliteration, and script analysis (#375).
    module.define_singleton_method("_sanitize_filename", function!(sanitize_filename, 6))?;
    module.define_singleton_method(
        "_reverse_transliterate",
        function!(reverse_transliterate, 2),
    )?;
    module.define_singleton_method("_find_untranslatable", function!(find_untranslatable, 3))?;
    module.define_singleton_method("_detect_scripts", function!(detect_scripts, 1))?;
    module.define_singleton_method("_is_mixed_script?", function!(is_mixed_script, 1))?;
    module.define_singleton_method("_inspect_auto_lang", function!(inspect_auto_lang, 1))?;
    module.define_singleton_method("_has_anomalies?", function!(has_anomalies, 2))?;
    module.define_singleton_method("_inspect_anomalies", function!(inspect_anomalies, 2))?;
    Ok(())
}
