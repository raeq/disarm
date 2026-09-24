//! C ABI for the pure-Rust `disarm` core, via `safer-ffi`.
//!
//! This crate contains **no hand-written `unsafe`**: `#[ffi_export]` and the
//! `char_p`/`repr_c` types marshal raw C pointers inside the macro/library, so each
//! entry point reads like ordinary Rust over `disarm_core::api`. It is a parallel
//! substrate to the JNI binding (which calls the core directly for the JVM hot
//! path), intended for iOS/Swift, Kotlin-Native, Panama/FFM, and C/C++ consumers.
//!
//! Strings cross the boundary as NUL-terminated `char *`. Every string a `disarm_*`
//! function returns is UTF-8 (directly or inside a [`DisarmResult`]), transfers
//! ownership to the caller, who must free it with [`disarm_string_free`], and is
//! read-only until then. Arguments should be UTF-8; bytes that are not are decoded
//! lossily (U+FFFD) at the boundary, never trusted. Nullable arguments (e.g. `lang`)
//! are passed as a NULL `char *`; every other pointer argument must be non-NULL. See
//! [`disarm_string_free`] for the whole contract.
//!
//! Scalar transforms return a `char *` (or [`DisarmResult`]) directly. The
//! **structured reports** — [`disarm_analyze_hostname`], [`disarm_inspect_anomalies`],
//! [`disarm_inspect_auto_lang`], [`disarm_lang_info`], [`disarm_script_info`] (#553) —
//! cross the boundary as a **JSON string** (still freed with [`disarm_string_free`]):
//! one transport for every nested shape, trivially parsed by a Go/C/Swift consumer.
//! The reusable handles from the JNI binding can still be layered on as needed.

use std::borrow::Cow;

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

/// Decode a C string argument, replacing any byte sequence that is not UTF-8 with
/// U+FFFD — the same contract every other binding applies at its boundary (#469).
///
/// safer-ffi's `char_p::Ref::to_str` is `str::from_utf8_unchecked`, so a C caller that
/// passed Latin-1 or truncated bytes produced a `&str` that was not UTF-8, which is
/// undefined behaviour the moment the core reads it: `disarm_strip_bidi("caf\xE9")`
/// crashed, `disarm_fold_case` aborted with a panic that could not unwind, and
/// `disarm_canonicalize` returned bytes that were not UTF-8 either. Found by the
/// bindings harness (`formal/bindings`, C1). Valid input borrows; only malformed input
/// allocates.
fn arg(s: char_p::Ref<'_>) -> Cow<'_, str> {
    String::from_utf8_lossy(s.to_bytes())
}

/// Decode an optional C string argument (NULL → `None`), as [`arg`] does.
fn opt_str(s: Option<char_p::Ref<'_>>) -> Option<Cow<'_, str>> {
    s.map(arg)
}

// ── Transliteration ─────────────────────────────────────────────────────────────

/// Unicode → ASCII with the default scheme.
#[ffi_export]
fn disarm_transliterate(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::transliterate(&arg(text)).into_owned())
}

/// Transliterate with a scheme (`"default"` | `"strict_iso9"` | `"gost7034"`) and an
/// optional language profile (`lang` may be NULL).
///
/// An unknown `scheme` or `lang` is an error in the result's `error` half, as it is for
/// `disarm_search_key` and in every other binding. An unknown `lang` used to fall back
/// to the default tables with no error (`formal/bindings`, B2).
#[ffi_export]
fn disarm_transliterate_opts(
    text: char_p::Ref<'_>,
    scheme: char_p::Ref<'_>,
    lang: Option<char_p::Ref<'_>>,
) -> DisarmResult {
    match build_transliterate(&arg(text), &arg(scheme), opt_str(lang).as_deref()) {
        Ok(s) => ok(s),
        Err(e) => err(&e),
    }
}

/// Reverse-transliterate Latin → native script. `lang` is `"el"` | `"ru"` | `"uk"`.
#[ffi_export]
fn disarm_reverse_transliterate(text: char_p::Ref<'_>, lang: char_p::Ref<'_>) -> DisarmResult {
    match arg(lang).parse::<api::ReverseLang>() {
        Ok(l) => ok(api::reverse_transliterate(&arg(text), l)),
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
    // `try_run` rejects an unknown `lang` instead of falling back to the default tables.
    Ok(b.try_run(text)?.into_owned())
}

// ── Confusables & normalization (fallible) ──────────────────────────────────────

/// Fold cross-script confusables toward `target` (`"latin"` | `"cyrillic"` | `"arabic"` | `"hebrew"`).
#[ffi_export]
fn disarm_normalize_confusables(text: char_p::Ref<'_>, target: char_p::Ref<'_>) -> DisarmResult {
    build_normalize_confusables(&arg(text), &arg(target), api::DigitPolicy::Numeric.as_str())
}

/// [`disarm_normalize_confusables`] with an explicit `digit_policy` (#561).
///
/// `digit_policy` is `"numeric"` (disarm's reading: a non-Latin digit folds to the ASCII
/// digit) or `"tr39"` (upstream's, which folds most of them to a Latin letter; three of
/// the 47 rows are not — two fold to `.` and one to the two characters `rn`). `"tr39"` is
/// scoped to `target = "latin"`: the override rows are generated from the Latin table and
/// carry TR39's Latin-script targets, so with any other target it is a no-op.
/// `"preserve"` leaves the digit alone (#648); the other two both produce a mixed-script
/// numeral, and it applies under every target script. Added as an
/// `_opts` variant rather than by widening the existing entry point, so the two-argument
/// symbol keeps its ABI for callers already linked against it — the same shape
/// `disarm_transliterate` / `disarm_transliterate_opts` already use in this file.
#[ffi_export]
fn disarm_normalize_confusables_opts(
    text: char_p::Ref<'_>,
    target: char_p::Ref<'_>,
    digit_policy: char_p::Ref<'_>,
) -> DisarmResult {
    build_normalize_confusables(&arg(text), &arg(target), &arg(digit_policy))
}

/// Shared body of the two entry points above: parse both tokens (target first, so the
/// `_opts` form reports the same error as the two-argument form on a bad target), then
/// fold. Mirrors `build_transliterate` — the default-policy shim passes the canonical
/// token straight from the enum rather than minting a C string to parse back.
fn build_normalize_confusables(text: &str, target: &str, digit_policy: &str) -> DisarmResult {
    let target = match target.parse::<api::TargetScript>() {
        Ok(t) => t,
        Err(e) => return err(&e),
    };
    let digit_policy = match digit_policy.parse::<api::DigitPolicy>() {
        Ok(d) => d,
        Err(e) => return err(&e),
    };
    ok(api::normalize_confusables_with(text, target, digit_policy).into_owned())
}

/// The `digit_policy` token the key builders' `_opts` entry points take (#896).
fn parse_policy(digit_policy: &str) -> Result<api::DigitPolicy, disarm_core::Error> {
    digit_policy.parse::<api::DigitPolicy>()
}

/// Apply a normalization form: `"NFC"` | `"NFD"` | `"NFKC"` | `"NFKD"`.
#[ffi_export]
fn disarm_normalize(text: char_p::Ref<'_>, form: char_p::Ref<'_>) -> DisarmResult {
    match arg(form).parse::<api::NormalizationForm>() {
        Ok(f) => ok(api::normalize(&arg(text), f)),
        Err(e) => err(&e),
    }
}

// ── Canonicalization primitives (infallible) ────────────────────────────────────

/// Strip diacritics, leaving base letters.
#[ffi_export]
fn disarm_strip_accents(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_accents(&arg(text)).into_owned())
}

/// Unicode case folding (aggressive lowercase for caseless comparison).
#[ffi_export]
fn disarm_fold_case(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::fold_case(&arg(text)).into_owned())
}

/// Whether case folding and simple lowercasing agree, so `text` is a stable
/// identity key ("groß.txt" is not; "gross.txt" is).
#[ffi_export]
fn disarm_is_case_fold_stable(text: char_p::Ref<'_>) -> bool {
    api::is_case_fold_stable(&arg(text))
}

/// Replace emoji with their plain names; `strip_modifiers` drops skin-tone marks. An
/// emoji CLDR cannot name (a regional indicator or a Plane 14 tag character standing
/// alone) becomes `[?]`, as in every binding.
#[ffi_export]
fn disarm_demojize(text: char_p::Ref<'_>, strip_modifiers: bool) -> char_p::Box {
    to_c(api::demojize(&arg(text), strip_modifiers))
}

/// Replace every emoji with `replacement`, verbatim (#972). Free the result with
/// [`disarm_string_free`].
///
/// The counterpart to [`disarm_demojize`], and a different question of a different
/// table: naming reads CLDR, which annotates more than the emoji, and this reads the
/// UCD's emoji properties, so `\u{00A9}` and `\u{2122}` stay put. `replacement` is
/// inserted exactly as given — `""` closes an intra-word split and `" "` keeps two
/// words apart, and no rule serves both.
#[ffi_export]
fn disarm_replace_emoji(text: char_p::Ref<'_>, replacement: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::replace_emoji(&arg(text), &arg(replacement)))
}

// ── Text cleaning (infallible) ──────────────────────────────────────────────────

/// Collapse runs of whitespace to single spaces and trim.
#[ffi_export]
fn disarm_collapse_whitespace(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::collapse_whitespace(&arg(text)))
}

/// Remove control characters.
#[ffi_export]
fn disarm_strip_control_chars(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_control_chars(&arg(text)))
}

/// Remove zero-width characters.
#[ffi_export]
fn disarm_strip_zero_width_chars(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_zero_width_chars(&arg(text)))
}

/// Remove bidi control characters.
#[ffi_export]
fn disarm_strip_bidi(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_bidi(&arg(text)))
}

/// Strip the Unicode Tags block (U+E0000–U+E007F), preserving valid emoji flags.
#[ffi_export]
fn disarm_strip_tags(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_tags(&arg(text)))
}

/// Strip every variation selector (VS1–VS256).
#[ffi_export]
fn disarm_strip_variation_selectors(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_variation_selectors(&arg(text)))
}

/// Strip every Unicode noncharacter.
#[ffi_export]
fn disarm_strip_noncharacters(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_noncharacters(&arg(text)))
}

/// Strip every Private Use Area code point.
#[ffi_export]
fn disarm_strip_pua(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_pua(&arg(text)))
}

// ── Deobfuscation & key-derivation presets (fallible) ───────────────────────────

/// Canonicalize, but fail rather than silently normalize a structural difference away.
///
/// The half of the pair that lets a caller *reject* input instead of comparing a value
/// the sender never wrote.
#[ffi_export]
fn disarm_canonicalize_strict(text: char_p::Ref<'_>) -> DisarmResult {
    match api::canonicalize_strict(&arg(text)) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// Strip the non-interchange and invisible classes while KEEPING the script (#698).
///
/// The seven universal `strip*` primitives cannot be composed into this, and the
/// difference runs in both directions. `strip_format` is *less* destructive where
/// rendering matters — it preserves the Private Use Area for icon fonts and keeps the
/// VS15/VS16 presentation selectors after a base (`RENDERING_STRIP`), both of which the
/// naive chain deletes — and *more* destructive with whitespace, because it ends in
/// `CollapseWs` and folds TAB/LF to a space where the primitives leave them. The policy
/// itself is a private constant, so a caller on this binding could not express it at all.
///
/// Unlike `canonicalize` it does NOT fold confusables, so non-Latin text keeps its script
/// — the point of the preset.
///
/// Infallible: returns the string directly rather than a `DisarmResult`.
#[ffi_export]
fn disarm_strip_format(text: char_p::Ref<'_>) -> char_p::Box {
    to_c(api::strip_format(&arg(text)).into_owned())
}

/// Aggressively strip obfuscation (invisibles, bidi, zero-width, etc.).
#[ffi_export]
fn disarm_strip_obfuscation(text: char_p::Ref<'_>) -> DisarmResult {
    match api::strip_obfuscation(&arg(text)) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// The strongest security-canonicalization preset.
///
/// Two steps introduce ASCII, not one (#719): the leading NFKC, and the confusable fold,
/// which reaches characters NFKC leaves alone. `U+2236 RATIO` becomes `:`, `U+2044
/// FRACTION SLASH` becomes `/`, `U+2216 SET MINUS` becomes `\`. A string that carried no
/// delimiter can leave here carrying one. `disarm_inspect_anomalies` reports it as
/// `confusable` WHEN the word also carries an ASCII letter, which is the gate that keeps
/// ordinary non-Latin text from firing; a delimiter-only string is not reported.
#[ffi_export]
fn disarm_canonicalize(text: char_p::Ref<'_>) -> DisarmResult {
    match api::canonicalize(&arg(text)) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// Case/accent/script-insensitive search key; `lang` may be NULL.
#[ffi_export]
fn disarm_search_key(text: char_p::Ref<'_>, lang: Option<char_p::Ref<'_>>) -> DisarmResult {
    match api::search_key(&arg(text), opt_str(lang).as_deref()) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// Collation sort key (preserves base accented characters); `lang` may be NULL.
#[ffi_export]
fn disarm_sort_key(text: char_p::Ref<'_>, lang: Option<char_p::Ref<'_>>) -> DisarmResult {
    match api::sort_key(&arg(text), opt_str(lang).as_deref()) {
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
    match api::catalog_key(&arg(text), opt_str(lang).as_deref(), strict_iso9) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// `disarm_canonicalize` under a `digit_policy` (#896): `"numeric"` — the default, and
/// byte-identical to the one-argument form — `"tr39"` or `"preserve"`. An `_opts` symbol
/// rather than a widened one, so the existing entry point keeps its ABI for callers already
/// linked against it — the shape `disarm_normalize_confusables_opts` uses.
#[ffi_export]
fn disarm_canonicalize_opts(text: char_p::Ref<'_>, digit_policy: char_p::Ref<'_>) -> DisarmResult {
    let policy = match parse_policy(&arg(digit_policy)) {
        Ok(p) => p,
        Err(e) => return err(&e),
    };
    match api::canonicalize_with(&arg(text), policy) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// `disarm_canonicalize_strict` under a `digit_policy` (#896). See `disarm_canonicalize_opts`.
#[ffi_export]
fn disarm_canonicalize_strict_opts(
    text: char_p::Ref<'_>,
    digit_policy: char_p::Ref<'_>,
) -> DisarmResult {
    let policy = match parse_policy(&arg(digit_policy)) {
        Ok(p) => p,
        Err(e) => return err(&e),
    };
    match api::canonicalize_strict_with(&arg(text), policy) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// `disarm_strip_obfuscation` under a `digit_policy` (#896). See `disarm_canonicalize_opts`.
#[ffi_export]
fn disarm_strip_obfuscation_opts(
    text: char_p::Ref<'_>,
    digit_policy: char_p::Ref<'_>,
) -> DisarmResult {
    let policy = match parse_policy(&arg(digit_policy)) {
        Ok(p) => p,
        Err(e) => return err(&e),
    };
    match api::strip_obfuscation_with(&arg(text), policy) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// `disarm_search_key` under a `digit_policy` (#896); `lang` may be NULL. The fold runs on
/// the raw text, before transliteration consumes the non-Latin digit the policy reads.
#[ffi_export]
fn disarm_search_key_opts(
    text: char_p::Ref<'_>,
    lang: Option<char_p::Ref<'_>>,
    digit_policy: char_p::Ref<'_>,
) -> DisarmResult {
    let policy = match parse_policy(&arg(digit_policy)) {
        Ok(p) => p,
        Err(e) => return err(&e),
    };
    match api::search_key_with(&arg(text), opt_str(lang).as_deref(), policy) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// `disarm_sort_key` under a `digit_policy` (#896); `lang` may be NULL.
#[ffi_export]
fn disarm_sort_key_opts(
    text: char_p::Ref<'_>,
    lang: Option<char_p::Ref<'_>>,
    digit_policy: char_p::Ref<'_>,
) -> DisarmResult {
    let policy = match parse_policy(&arg(digit_policy)) {
        Ok(p) => p,
        Err(e) => return err(&e),
    };
    match api::sort_key_with(&arg(text), opt_str(lang).as_deref(), policy) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// `disarm_catalog_key` under a `digit_policy` (#896); `lang` may be NULL.
#[ffi_export]
fn disarm_catalog_key_opts(
    text: char_p::Ref<'_>,
    lang: Option<char_p::Ref<'_>>,
    strict_iso9: bool,
    digit_policy: char_p::Ref<'_>,
) -> DisarmResult {
    let policy = match parse_policy(&arg(digit_policy)) {
        Ok(p) => p,
        Err(e) => return err(&e),
    };
    match api::catalog_key_with(&arg(text), opt_str(lang).as_deref(), strict_iso9, policy) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// The TR39 identifier skeleton plus the two prototype classes disarm's table keeps apart
/// (#650). A spoof key: its only job is to make confusable identifiers collide, and its
/// output is never for display. `digit_policy` is `"numeric"` (the letter half only),
/// `"tr39"` (adds `1 ≡ l` and `0 ≡ O`) or `"preserve"`.
#[ffi_export]
fn disarm_skeleton_key(text: char_p::Ref<'_>, digit_policy: char_p::Ref<'_>) -> DisarmResult {
    let policy = match parse_policy(&arg(digit_policy)) {
        Ok(p) => p,
        Err(e) => return err(&e),
    };
    match api::skeleton_key(&arg(text), policy) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// Levenshtein edit distance between `a` and `b`, in characters (#894). The one class of
/// registry spoofing the confusable tables deliberately do not model: `paypa1`, `adm1n`.
#[ffi_export]
fn disarm_edit_distance(a: char_p::Ref<'_>, b: char_p::Ref<'_>) -> usize {
    api::edit_distance(&arg(a), &arg(b))
}

/// The candidate closest to `value`, or `null` beyond `max_distance` (#894).
///
/// `candidates_json` is a JSON array of strings; the result is the JSON object
/// `{"value": "...", "distance": n}` or the JSON literal `null` — the same transport the
/// structured reports use. Malformed `candidates_json` is an error rather than `null`, so
/// a caller cannot read a parse failure as "nothing close". An exact match is reported
/// with distance 0; ties go to the first candidate at the lowest distance.
#[ffi_export]
fn disarm_nearest_match(
    value: char_p::Ref<'_>,
    candidates_json: char_p::Ref<'_>,
    max_distance: usize,
) -> DisarmResult {
    let Ok(candidates) = serde_json::from_str::<Vec<String>>(&arg(candidates_json)) else {
        return DisarmResult {
            value: None,
            error: Some(to_c(
                "candidates_json must be a JSON array of strings".to_owned(),
            )),
        };
    };
    let hit = api::nearest_match(
        &arg(value),
        candidates.iter().map(String::as_str),
        max_distance,
    );
    let json = match hit {
        Some(m) => serde_json::json!({ "value": m.value, "distance": m.distance }).to_string(),
        None => "null".to_owned(),
    };
    ok(json)
}

// ── Predicates (infallible) ─────────────────────────────────────────────────────

/// Whether `text` is already its own canonical form under `preset` (#730).
///
/// Returns `1` for canonical, `0` for not, and `-1` when the question could not be
/// answered: `preset` names neither a preset nor a profile, or running the preset hit a
/// resource limit (an input whose normalized form exceeds the output cap, #768). A
/// tri-state rather than a `bool`, because every other predicate here is infallible and
/// this one can fail — answering `0` would report "not canonical" for a question that was
/// never answered. Treat `-1` as "unknown", never as either answer; the preset functions
/// (`disarm_canonicalize` and the rest) return the reason in their `DisarmResult`.
///
/// `-1` used to be documented as the unknown-preset case alone (`formal/bindings`, E3).
/// A distinct code for the resource limit was not added: a caller testing `r == -1` and
/// otherwise treating a non-zero value as "canonical" would read a new `-2` as a yes.
#[ffi_export]
fn disarm_is_canonical(text: char_p::Ref<'_>, preset: char_p::Ref<'_>) -> i8 {
    match api::is_canonical(&arg(text), &arg(preset)) {
        Ok(true) => 1,
        Ok(false) => 0,
        Err(_) => -1,
    }
}

/// Whether the hostname looks like a mixed-script / confusable / bidi IDN spoof.
#[ffi_export]
fn disarm_is_suspicious_hostname(host: char_p::Ref<'_>) -> bool {
    api::is_suspicious_hostname(&arg(host)).suspicious
}

/// Whether `text` mixes characters from more than one script.
#[ffi_export]
fn disarm_is_mixed_script(text: char_p::Ref<'_>) -> bool {
    api::is_mixed_script(&arg(text))
}

/// Whether `text` mixes strong LTR and strong RTL characters ("BiDi Swap").
#[ffi_export]
fn disarm_has_bidi_conflict(text: char_p::Ref<'_>) -> bool {
    api::has_bidi_conflict(&arg(text))
}

/// All twelve UAX #9 explicit formatting characters, uncontexted (#778).
/// The counterpart to `has_bidi_conflict`, which reads strong-direction letters and is
/// blind to these; the two are disjoint. The anomaly detector's `bidi` kind reports nine
/// of the twelve, holding back LRM, RLM and ALM because a lone directional mark is
/// ordinary in right-to-left text.
#[ffi_export]
fn disarm_has_bidi_control(text: char_p::Ref<'_>) -> bool {
    api::has_bidi_control(&arg(text))
}

// ── Measurements (infallible) ───────────────────────────────────────────────────

/// Number of grapheme clusters (user-perceived characters) in `text`.
#[ffi_export]
fn disarm_grapheme_len(text: char_p::Ref<'_>) -> u64 {
    api::grapheme_len(&arg(text)) as u64
}

/// Total terminal display width of `text` (`ambiguous_wide` treats ambiguous
/// East-Asian width characters as wide).
#[ffi_export]
fn disarm_terminal_width(text: char_p::Ref<'_>, ambiguous_wide: bool) -> u64 {
    api::terminal_width(&arg(text), ambiguous_wide) as u64
}

// ── Structured reports (JSON transport, #553) ───────────────────────────────────
//
// Nested reports (Vec<Vec<String>>, Vec<Finding>, …) cross the C boundary as a JSON
// string built with `serde_json::json!` — one transport for every shape, freed like
// any other string via `disarm_string_free`. Consumers parse it with their language's
// JSON library (Go `encoding/json`, cJSON, …). Infallible analyses return the JSON
// directly; fallible lookups (`lang_info`/`script_info`) return a `DisarmResult` whose
// `value` is the JSON.

/// Full hostname homoglyph analysis as a JSON object (fields mirror the Rust/Node/
/// Ruby/Java `HostnameAnalysis`: `suspicious`, `scripts`, `mixed_script`,
/// `has_confusables`, `bidi_conflict`, `bidi_control`, `has_invisible`, `compat_fold`,
/// `cross_label_script`, `label_scripts`, `whole_script_confusable`,
/// `label_whole_script_confusable`, `canonical`).
#[ffi_export]
fn disarm_analyze_hostname(host: char_p::Ref<'_>) -> char_p::Box {
    disarm_analyze_hostname_opts(host, false)
}

/// [`disarm_analyze_hostname`] with the opt-in digraph contraction pass (#562).
///
/// `contractions = true` additionally folds the ASCII digraphs (`rn`→`m`, `vv`→`w`,
/// `cl`→`d`) per label, so `arnazon.com` canonicalizes to `amazon.com`. It changes
/// `canonical` only — the `suspicious` verdict is unaffected, because an all-ASCII label
/// carries no mixed-script or cross-script evidence. Compare `canonical` against your own
/// brand list.
///
/// Separate entry point rather than a widened `disarm_analyze_hostname`: that symbol
/// shipped in 0.13.0 and callers are linked against its 1-argument form. Same shape as
/// `disarm_transliterate` / `_opts` and `disarm_normalize_confusables` / `_opts`.
#[ffi_export]
fn disarm_analyze_hostname_opts(host: char_p::Ref<'_>, contractions: bool) -> char_p::Box {
    let a = api::analyze_hostname_with(&arg(host), contractions);
    to_c(
        serde_json::json!({
            "suspicious": a.suspicious,
            "scripts": a.scripts,
            "mixed_script": a.mixed_script,
            "has_confusables": a.has_confusables,
            "bidi_conflict": a.bidi_conflict,
            "bidi_control": a.bidi_control,
            "has_invisible": a.has_invisible,
            "compat_fold": a.compat_fold,
            "cross_label_script": a.cross_label_script,
            "label_scripts": a.label_scripts,
            "whole_script_confusable": a.whole_script_confusable,
            "label_whole_script_confusable": a.label_whole_script_confusable,
            "canonical": a.canonical,
        })
        .to_string(),
    )
}

/// Structural anomaly report for `text` as a JSON object (`anomalous`, `kinds`,
/// `findings` [each `kind`/`token`/`start`/`end`/`detail`/`reason`], `reason`).
///
/// `lexicon_json` is a JSON array of common words (e.g. `["free","account"]`),
/// mirroring the array form the Node/Ruby bindings accept — it feeds the
/// word-list branches (`leet`, `segmentation`). An empty string, `"[]"`, `"null"`,
/// or malformed JSON means "no lexicon": the structural branches (invisible, bidi,
/// zalgo, mixed-script) still fire, matching the other bindings' no-arg behaviour.
#[ffi_export]
fn disarm_inspect_anomalies(text: char_p::Ref<'_>, lexicon_json: char_p::Ref<'_>) -> char_p::Box {
    let words: Vec<String> = serde_json::from_str(&arg(lexicon_json)).unwrap_or_default();
    let report = api::inspect_anomalies(&arg(text), &api::lexicon(words));
    let findings: Vec<_> = report
        .findings
        .iter()
        .map(|f| {
            serde_json::json!({
                "kind": f.kind.as_str(),
                "token": f.token,
                "start": f.start,
                "end": f.end,
                "detail": f.detail,
                "reason": f.reason(),
            })
        })
        .collect();
    to_c(
        serde_json::json!({
            "anomalous": report.anomalous,
            "kinds": report.kinds.iter().map(|k| k.as_str()).collect::<Vec<_>>(),
            "findings": findings,
            "reason": report.reason,
        })
        .to_string(),
    )
}

/// Which of `values_json` are the same name under `key` (#620), as a JSON array of
/// objects (`key`, `values`, `indices`).
///
/// `values_json` is a JSON array of strings — the set to check. `key` names the
/// reducer: `"fold_case"`, `"search_key"`, `"catalog_key"`, `"canonicalize"`,
/// `"canonicalize_strict"` or `"normalize_confusables"`. There is no default,
/// because a stronger key finds more collisions and the choice is the caller's
/// policy. `lang` may be NULL and reaches `search_key` / `catalog_key` only.
///
/// A group is reported only when two or more **distinct** inputs share a key.
/// Malformed `values_json` is an error rather than an empty set, so a caller
/// cannot read a parse failure as "no collisions".
#[ffi_export]
fn disarm_find_key_collisions(
    values_json: char_p::Ref<'_>,
    key: char_p::Ref<'_>,
    lang: Option<char_p::Ref<'_>>,
) -> DisarmResult {
    // Parse the key first: an unknown token is a real core `Error` with the
    // canonical message, and reporting it before the JSON means a caller who got
    // both wrong is told about the one they can fix from the docs.
    let key: api::KeyForm = match arg(key).parse() {
        Ok(k) => k,
        Err(e) => return err(&e),
    };
    // A parse failure is NOT an empty set: reading "malformed input" as "no
    // collisions" is the exact confusion this function exists to prevent, so it
    // is reported as an error string rather than as a clean result.
    let Ok(values) = serde_json::from_str::<Vec<String>>(&arg(values_json)) else {
        return DisarmResult {
            value: None,
            error: Some(to_c(
                "values_json must be a JSON array of strings".to_owned(),
            )),
        };
    };
    match api::find_key_collisions(&values, key, opt_str(lang).as_deref()) {
        Ok(found) => ok(serde_json::json!(found
            .iter()
            .map(|c| serde_json::json!({
                "key": c.key,
                "values": c.values,
                "indices": c.indices,
            }))
            .collect::<Vec<_>>())
        .to_string()),
        Err(e) => err(&e),
    }
}

/// Auto-language inspection for `text` as a JSON object (`script`, `chosen_lang`,
/// `reason`, `discriminators_hit`).
#[ffi_export]
fn disarm_inspect_auto_lang(text: char_p::Ref<'_>) -> char_p::Box {
    let a = api::inspect_auto_lang(&arg(text));
    to_c(
        serde_json::json!({
            "script": a.script,
            "chosen_lang": a.chosen_lang,
            "reason": a.reason,
            "discriminators_hit": a.discriminators_hit,
        })
        .to_string(),
    )
}

/// Metadata for a language code as JSON (`name`, `script`, `region`, `context`), or
/// an error in the [`DisarmResult`] for an unknown code.
#[ffi_export]
fn disarm_lang_info(code: char_p::Ref<'_>) -> DisarmResult {
    match api::lang_info(&arg(code)) {
        Ok(m) => ok(serde_json::json!({
            "name": m.name,
            "script": m.script,
            "region": m.region,
            "context": m.context,
        })
        .to_string()),
        Err(e) => err(&e),
    }
}

/// Metadata for a script name as JSON (`name`, `default_lang`, `example`,
/// `context_aware`), or an error in the [`DisarmResult`] for an unknown name.
#[ffi_export]
fn disarm_script_info(name: char_p::Ref<'_>) -> DisarmResult {
    match api::script_info(&arg(name)) {
        Ok(m) => ok(serde_json::json!({
            "name": m.name,
            "default_lang": m.default_lang,
            "example": m.example,
            "context_aware": m.context_aware,
        })
        .to_string()),
        Err(e) => err(&e),
    }
}

/// Per-script confusable coverage as JSON (`script`, `sources`, `folded`), or an error
/// in the [`DisarmResult`] for an unknown script (#963).
///
/// The denominator [`disarm_unmapped_confusables`] does not have: that measures one
/// bundled table against the whole 6,565-source population, so a script disarm ships no
/// table for reports a number determined by that absence rather than by its coverage.
/// `folded` counts sources any bundled table reaches, not sources folded *toward* this
/// script.
#[ffi_export]
fn disarm_confusable_coverage(script: char_p::Ref<'_>) -> DisarmResult {
    match api::confusable_coverage(&arg(script)) {
        Ok(row) => ok(serde_json::json!({
            "script": row.script,
            "sources": row.sources,
            "folded": row.folded,
        })
        .to_string()),
        Err(e) => err(&e),
    }
}

// ── Bundled data versions ───────────────────────────────────────────────────────

/// The Unicode `confusables.txt` release the bundled confusable tables were folded
/// from, e.g. `"17.0.0"` (#560). Free the result with [`disarm_string_free`].
///
/// Not a Unicode version for the library as a whole: disarm's case-folding and width
/// tables track different releases (see `docs/provenance.md`). This answers one
/// question — how current is the confusables fold?
#[ffi_export]
fn disarm_confusables_version() -> char_p::Box {
    to_c(api::CONFUSABLES_VERSION.to_owned())
}

/// The UCD release disarm's normalizer implements (#645). Free with
/// [`disarm_string_free`].
///
/// Not a library-wide Unicode version — the bundled tables track different releases, and
/// `docs/provenance.md` is the census. This is the one integrators ask about, because it
/// decides whether disarm's normalization agrees with the host platform's.
#[ffi_export]
fn disarm_unicode_version() -> char_p::Box {
    to_c(api::UNICODE_VERSION.to_owned())
}

/// Whether a key stored under an earlier release still compares equal (#645).
///
/// A monotonic counter, not a version: two artifacts reporting the same value produce the
/// same key for the same input, and different values mean reindex. Meaningless in
/// isolation, by design — the question a key consumer has is a comparison, not a lookup.
#[ffi_export]
fn disarm_key_schema_version() -> u32 {
    api::KEY_SCHEMA_VERSION
}

/// ML/NLP normalization: resolve deletions → NFKC → emoji→text → transliterate →
/// strip accents → emoji→text → [case fold] → strip control → strip zero-width →
/// collapse whitespace → NFC.
///
/// `lang` is nullable (NULL = no transliteration). `emoji_style` is `"cldr"` or
/// `"none"`. `fold_case` drops the case-fold step when false — pass false in front of a
/// CASED model; it restores case, not diacritics. Folds no confusables, so it is not a
/// homoglyph defence at any setting.
#[ffi_export]
fn disarm_ml_normalize(
    text: char_p::Ref<'_>,
    lang: Option<char_p::Ref<'_>>,
    emoji_style: char_p::Ref<'_>,
    fold_case: bool,
) -> DisarmResult {
    match api::ml_normalize(
        &arg(text),
        opt_str(lang).as_deref(),
        &arg(emoji_style),
        fold_case,
    ) {
        Ok(s) => ok(s.into_owned()),
        Err(e) => err(&e),
    }
}

/// Sanitize `text` into a filename safe on `platform` (#707).
///
/// The only entry point disarm ships whose *whole* purpose is a filesystem sink, and the
/// C ABI is the surface most likely to be feeding one. `platform` is `"universal"`,
/// `"posix"` or `"windows"`; `lang` is nullable (NULL = no transliteration profile).
///
/// Transliteration is load-bearing here, not a convenience: 19 of the 53 vectors in the
/// attacker battery are neutralized by the romanization step rather than by the denylist
/// (#601), so a caller who reaches for `disarm_strip_obfuscation` and its own denylist
/// instead does not get the same protection.
#[ffi_export]
fn disarm_sanitize_filename(
    text: char_p::Ref<'_>,
    separator: char_p::Ref<'_>,
    max_length: usize,
    platform: char_p::Ref<'_>,
    lang: Option<char_p::Ref<'_>>,
    preserve_extension: bool,
) -> DisarmResult {
    let platform: api::Platform = match arg(platform).parse() {
        Ok(p) => p,
        Err(e) => return err(&e),
    };
    match api::sanitize_filename(
        &arg(text),
        &arg(separator),
        max_length,
        platform,
        opt_str(lang).as_deref(),
        preserve_extension,
    ) {
        Ok(s) => ok(s),
        Err(e) => err(&e),
    }
}

// ── Coverage introspection (#563) ───────────────────────────────────────────────

/// Every upstream confusable source the bundled `target` table does not fold, as a
/// JSON array of single-character strings. Free with [`disarm_string_free`].
///
/// Read as exposure, not as a score. The set includes five ASCII characters
/// (`%`, `0`, `1`, `I`, `m`): TR39 is a skeleton transform, and disarm deliberately
/// does not apply those rows because folding a legitimate `m` to `rn` corrupts prose.
#[ffi_export]
fn disarm_unmapped_confusables(target: char_p::Ref<'_>) -> DisarmResult {
    match arg(target).parse::<api::TargetScript>() {
        Ok(target) => {
            let items: Vec<String> = api::unmapped_confusables(target)
                .into_iter()
                .map(String::from)
                .collect();
            ok(serde_json::json!(items).to_string())
        }
        Err(e) => err(&e),
    }
}

/// Confusable sources in `text` the bundled `target` table does not fold, as a JSON
/// array of `{"char": "…", "offset": N}` objects in order of appearance — the
/// confusables analogue of `find_untranslatable`, with the same byte-offset
/// convention. Free with [`disarm_string_free`].
#[ffi_export]
fn disarm_find_unmapped_confusables(
    text: char_p::Ref<'_>,
    target: char_p::Ref<'_>,
) -> DisarmResult {
    match arg(target).parse::<api::TargetScript>() {
        Ok(target) => {
            let items: Vec<_> = api::find_unmapped_confusables(&arg(text), target)
                .into_iter()
                .map(|u| serde_json::json!({ "char": u.ch.to_string(), "offset": u.offset }))
                .collect();
            ok(serde_json::json!(items).to_string())
        }
        Err(e) => err(&e),
    }
}

// ── Memory management ───────────────────────────────────────────────────────────

/// Free a string previously returned by any `disarm_*` function. NULL-safe: the
/// argument is a nullable owned box, so passing NULL (e.g. the unused half of a
/// [`DisarmResult`]) is a no-op; a non-NULL box is dropped, freeing it.
///
/// The contract for every `disarm_*` function (found by `formal/bindings`, C1-C3):
///
/// - **Arguments.** Every `char const *` argument must be non-NULL and NUL-terminated,
///   except those documented as nullable (such as `lang`). Bytes that are not UTF-8
///   are accepted: each malformed sequence is read as U+FFFD, as every other binding
///   does, so Latin-1 or truncated input never reaches the core as invalid text.
/// - **Results.** A returned string is owned by the caller until passed here, and is
///   **read-only**: do not write through it, not even to shorten it. An empty result
///   can be a shared static, and a string shortened in place is freed with the wrong
///   size.
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
