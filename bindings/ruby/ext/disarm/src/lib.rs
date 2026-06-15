//! magnus bindings exposing the pure-Rust `disarm` core as the Ruby `Disarm`
//! module (#45). Every method is a thin wrapper over `disarm_core::api`, so the
//! security/transform behaviour is defined once in the core and inherited here.
//!
//! Targets magnus 0.7 (Ruby >= 3.0). Build via rake-compiler / rb-sys, not
//! `cargo build` directly (it needs the Ruby headers rb-sys configures).

use disarm_core::api;
use magnus::{function, prelude::*, Error, Ruby};

/// Map a `disarm` error onto the closest standard Ruby exception:
/// `InvalidArgument` → `ArgumentError`, everything else → `RuntimeError`.
fn raise(e: &disarm_core::Error) -> Error {
    let class = match e.kind() {
        disarm_core::ErrorKind::InvalidArgument => magnus::exception::arg_error(),
        _ => magnus::exception::runtime_error(),
    };
    Error::new(class, e.to_string())
}

// ── Transliteration ───────────────────────────────────────────────────────────

/// `Disarm.transliterate(text)` — Unicode → ASCII with the default scheme.
fn transliterate(text: String) -> String {
    api::transliterate(&text).into_owned()
}

/// `Disarm.transliterate_scheme(text, "strict_iso9" | "gost7034" | "default")`.
fn transliterate_scheme(text: String, scheme: String) -> Result<String, Error> {
    let scheme: api::Scheme = scheme.parse().map_err(|e| raise(&e))?;
    Ok(api::Transliterate::new().scheme(scheme).run(&text).into_owned())
}

// ── Confusables (TR39) ────────────────────────────────────────────────────────

/// `Disarm.normalize_confusables(text, "latin" | "cyrillic")`.
fn normalize_confusables(text: String, target: String) -> Result<String, Error> {
    let target: api::TargetScript = target.parse().map_err(|e| raise(&e))?;
    Ok(api::normalize_confusables(&text, target).into_owned())
}

/// `Disarm.confusable?(text, "latin" | "cyrillic")`.
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

fn slugify(text: String) -> String {
    api::slugify(&text, &api::SlugConfig::default())
}

fn demojize(text: String) -> String {
    api::demojize(&text, false)
}

// ── Security presets (fallible) ───────────────────────────────────────────────

fn strip_obfuscation(text: String) -> Result<String, Error> {
    api::strip_obfuscation(&text).map_err(|e| raise(&e))
}

fn security_clean(text: String) -> Result<String, Error> {
    api::security_clean(&text).map_err(|e| raise(&e))
}

/// `Disarm.suspicious_hostname?(host)` — flags mixed-script / confusable IDN
/// spoofs. A false result asserts nothing was *found*, not that the host is safe.
fn suspicious_hostname(host: String) -> bool {
    api::is_suspicious_hostname(&host).0
}

#[magnus::init]
fn init(ruby: &Ruby) -> Result<(), Error> {
    let module = ruby.define_module("Disarm")?;
    module.define_singleton_method("transliterate", function!(transliterate, 1))?;
    module.define_singleton_method("transliterate_scheme", function!(transliterate_scheme, 2))?;
    module.define_singleton_method("normalize_confusables", function!(normalize_confusables, 2))?;
    module.define_singleton_method("confusable?", function!(is_confusable, 2))?;
    module.define_singleton_method("strip_accents", function!(strip_accents, 1))?;
    module.define_singleton_method("fold_case", function!(fold_case, 1))?;
    module.define_singleton_method("slugify", function!(slugify, 1))?;
    module.define_singleton_method("demojize", function!(demojize, 1))?;
    module.define_singleton_method("strip_obfuscation", function!(strip_obfuscation, 1))?;
    module.define_singleton_method("security_clean", function!(security_clean, 1))?;
    module.define_singleton_method("suspicious_hostname?", function!(suspicious_hostname, 1))?;
    Ok(())
}
