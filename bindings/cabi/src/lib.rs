//! C ABI for the pure-Rust `disarm` core, via `safer-ffi`.
//!
//! This crate contains **no hand-written `unsafe`**: `#[ffi_export]` and the
//! `char_p`/`repr_c` types marshal raw C pointers inside the macro/library, so each
//! entry point reads like ordinary Rust over `disarm_core::api`. It is a parallel
//! substrate to the JNI binding (which calls the core directly for the JVM hot
//! path), intended for iOS/Swift, Kotlin-Native, Panama/FFM, and C/C++ consumers.
//!
//! Strings cross the boundary as NUL-terminated UTF-8 (`char *`). Every string a
//! `disarm_*` function returns (directly or inside a [`DisarmResult`]) transfers
//! ownership to the caller, who must free it with [`disarm_string_free`]. Nullable
//! arguments (e.g. `lang`) are passed as a NULL `char *`.
//!
//! This initial substrate covers the scalar transforms; the reusable handles and
//! structured reports (already in the JNI binding) can be layered on as needed.

use disarm_core::api;
use safer_ffi::prelude::*;

/// Convert an owned Rust `String` into a C string the caller must free.
///
/// disarm outputs never contain an interior NUL, so this cannot realistically
/// fail; if one ever did we substitute an empty string rather than panicking.
fn to_c(s: String) -> char_p::Box {
    char_p::Box::try_from(s).unwrap_or_else(|_| char_p::Box::try_from(String::new()).unwrap())
}

/// Result of a fallible transform: exactly one of `value` / `error` is non-NULL.
/// The caller frees whichever is set with [`disarm_string_free`].
#[derive_ReprC]
#[repr(C)]
pub struct DisarmResult {
    /// The output string, or NULL on error.
    pub value: Option<char_p::Box>,
    /// The error message, or NULL on success.
    pub error: Option<char_p::Box>,
}

fn ok(s: String) -> DisarmResult {
    DisarmResult {
        value: Some(to_c(s)),
        error: None,
    }
}

fn err(e: &disarm_core::Error) -> DisarmResult {
    DisarmResult {
        value: None,
        error: Some(to_c(e.to_string())),
    }
}

/// Decode an optional C string argument (NULL → `None`) to `Option<&str>`.
fn opt_str<'a>(s: Option<char_p::Ref<'a>>) -> Option<&'a str> {
    s.map(|v| v.to_str())
}

// ── Transliteration ─────────────────────────────────────────────────────────────

/// Unicode → ASCII with the default scheme.
#[ffi_export]
fn disarm_transliterate(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::transliterate(text.to_str()).into_owned())
}

/// Transliterate with a scheme (`"default"` | `"strict_iso9"` | `"gost7034"`) and an
/// optional language profile (`lang` may be NULL).
#[ffi_export]
fn disarm_transliterate_opts(
    text: char_p::Ref<'_>,
    scheme: char_p::Ref<'_>,
    lang: Option<char_p::Ref<'_>>,
) -> DisarmResult {
    match build_transliterate(text.to_str(), scheme.to_str(), opt_str(lang)) {
        Ok(s) => ok(s),
        Err(e) => err(&e),
    }
}

/// Reverse-transliterate Latin → native script. `lang` is `"el"` | `"ru"` | `"uk"`.
#[ffi_export]
fn disarm_reverse_transliterate(text: char_p::Ref<'_>, lang: char_p::Ref<'_>) -> DisarmResult {
    match lang.to_str().parse::<api::ReverseLang>() {
        Ok(l) => ok(api::reverse_transliterate(text.to_str(), l)),
        Err(e) => err(&e),
    }
}

fn build_transliterate(
    text: &str,
    scheme: &str,
    lang: Option<&str>,
) -> Result<String, disarm_core::Error> {
    let mut b = api::Transliterate::new();
    if scheme != "default" {
        b = b.scheme(scheme.parse()?);
    }
    if let Some(lang) = lang {
        b = b.lang(lang);
    }
    Ok(b.run(text).into_owned())
}

// ── Confusables & normalization (fallible) ──────────────────────────────────────

/// Fold cross-script confusables toward `target` (`"latin"` | `"cyrillic"`).
#[ffi_export]
fn disarm_normalize_confusables(text: char_p::Ref<'_>, target: char_p::Ref<'_>) -> DisarmResult {
    match target.to_str().parse::<api::TargetScript>() {
        Ok(t) => ok(api::normalize_confusables(text.to_str(), t).into_owned()),
        Err(e) => err(&e),
    }
}

/// Apply a normalization form: `"NFC"` | `"NFD"` | `"NFKC"` | `"NFKD"`.
#[ffi_export]
fn disarm_normalize(text: char_p::Ref<'_>, form: char_p::Ref<'_>) -> DisarmResult {
    match form.to_str().parse::<api::NormalizationForm>() {
        Ok(f) => ok(api::normalize(text.to_str(), f)),
        Err(e) => err(&e),
    }
}

// ── Canonicalization primitives (infallible) ────────────────────────────────────

/// Strip diacritics, leaving base letters.
#[ffi_export]
fn disarm_strip_accents(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_accents(text.to_str()).into_owned())
}

/// Unicode case folding (aggressive lowercase for caseless comparison).
#[ffi_export]
fn disarm_fold_case(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::fold_case(text.to_str()).into_owned())
}

/// Replace emoji with their plain names; `strip_modifiers` drops skin-tone marks.
#[ffi_export]
fn disarm_demojize(text: char_p::Ref<'_>, strip_modifiers: bool) -> char_p::Box {
    to_c(api::demojize(text.to_str(), strip_modifiers))
}

// ── Text cleaning (infallible) ──────────────────────────────────────────────────

/// Collapse runs of whitespace to single spaces and trim.
#[ffi_export]
fn disarm_collapse_whitespace(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::collapse_whitespace(text.to_str()))
}

/// Remove control characters.
#[ffi_export]
fn disarm_strip_control_chars(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_control_chars(text.to_str()))
}

/// Remove zero-width characters.
#[ffi_export]
fn disarm_strip_zero_width_chars(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_zero_width_chars(text.to_str()))
}

/// Remove bidi control characters.
#[ffi_export]
fn disarm_strip_bidi(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_bidi(text.to_str()))
}

/// Strip the Unicode Tags block (U+E0000–U+E007F), preserving valid emoji flags.
#[ffi_export]
fn disarm_strip_tags(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_tags(text.to_str()))
}

/// Strip every variation selector (VS1–VS256).
#[ffi_export]
fn disarm_strip_variation_selectors(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_variation_selectors(text.to_str()))
}

/// Strip every Unicode noncharacter.
#[ffi_export]
fn disarm_strip_noncharacters(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_noncharacters(text.to_str()))
}

/// Strip every Private Use Area code point.
#[ffi_export]
fn disarm_strip_pua(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_pua(text.to_str()))
}

// ── Deobfuscation & key-derivation presets (fallible) ───────────────────────────

/// Aggressively strip obfuscation (invisibles, bidi, zero-width, etc.).
#[ffi_export]
fn disarm_strip_obfuscation(text: char_p::Ref<'_>) -> DisarmResult {
    match api::strip_obfuscation(text.to_str()) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// The strongest security-canonicalization preset.
#[ffi_export]
fn disarm_canonicalize(text: char_p::Ref<'_>) -> DisarmResult {
    match api::canonicalize(text.to_str()) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// Case/accent/script-insensitive search key; `lang` may be NULL.
#[ffi_export]
fn disarm_search_key(text: char_p::Ref<'_>, lang: Option<char_p::Ref<'_>>) -> DisarmResult {
    match api::search_key(text.to_str(), opt_str(lang)) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// Collation sort key (preserves base accented characters); `lang` may be NULL.
#[ffi_export]
fn disarm_sort_key(text: char_p::Ref<'_>, lang: Option<char_p::Ref<'_>>) -> DisarmResult {
    match api::sort_key(text.to_str(), opt_str(lang)) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// Library-catalog dedup key; `lang` may be NULL, `strict_iso9` selects ISO 9:1995.
#[ffi_export]
fn disarm_catalog_key(
    text: char_p::Ref<'_>,
    lang: Option<char_p::Ref<'_>>,
    strict_iso9: bool,
) -> DisarmResult {
    match api::catalog_key(text.to_str(), opt_str(lang), strict_iso9) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

// ── Predicates (infallible) ─────────────────────────────────────────────────────

/// Whether the hostname looks like a mixed-script / confusable / bidi IDN spoof.
#[ffi_export]
fn disarm_is_suspicious_hostname(host: char_p::Ref<'_>) -> bool {
    api::is_suspicious_hostname(host.to_str()).suspicious
}

/// Whether `text` mixes characters from more than one script.
#[ffi_export]
fn disarm_is_mixed_script(text: char_p::Ref<'_>) -> bool {
    api::is_mixed_script(text.to_str())
}

/// Whether `text` mixes strong LTR and strong RTL characters ("BiDi Swap").
#[ffi_export]
fn disarm_has_bidi_conflict(text: char_p::Ref<'_>) -> bool {
    api::has_bidi_conflict(text.to_str())
}

// ── Measurements (infallible) ───────────────────────────────────────────────────

/// Number of grapheme clusters (user-perceived characters) in `text`.
#[ffi_export]
fn disarm_grapheme_len(text: char_p::Ref<'_>) -> u64 {
    api::grapheme_len(text.to_str()) as u64
}

/// Total terminal display width of `text` (`ambiguous_wide` treats ambiguous
/// East-Asian width characters as wide).
#[ffi_export]
fn disarm_terminal_width(text: char_p::Ref<'_>, ambiguous_wide: bool) -> u64 {
    api::terminal_width(text.to_str(), ambiguous_wide) as u64
}

// ── Memory management ───────────────────────────────────────────────────────────

/// Free a string previously returned by any `disarm_*` function. NULL-safe: the
/// argument is a nullable owned box, so passing NULL (e.g. the unused half of a
/// [`DisarmResult`]) is a no-op; a non-NULL box is dropped, freeing it.
#[ffi_export]
fn disarm_string_free(string: Option<char_p::Box>) {
    drop(string);
}

// ── Header generation ───────────────────────────────────────────────────────────

/// Write the C header. Run: `cargo test --features headers -- generate_headers`.
#[cfg(feature = "headers")]
#[test]
fn generate_headers() -> std::io::Result<()> {
    safer_ffi::headers::builder()
        .to_file("disarm.h")?
        .generate()
}
