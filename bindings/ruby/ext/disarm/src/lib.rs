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
    Ok(())
}
