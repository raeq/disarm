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
//! Targets magnus 0.8 (Ruby >= 3.1). Build via rake-compiler / rb-sys, not
//! `cargo build` directly (it needs the Ruby headers rb-sys configures).

// S-4: this shim is an FFI boundary that must never panic across into Ruby. Lock
// that in structurally with the no-panic restriction lints (caught by the binding's
// clippy gate). The handful of `Ruby::get().expect(...)` calls are GVL invariants
// (a Ruby callback always holds the GVL) and carry a local `#[allow]` with that
// justification; everything else must return a magnus `Error`, never panic.
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
use magnus::{function, method, prelude::*, Error, RHash, Ruby};

/// Map a `disarm` error onto the closest standard Ruby exception:
/// `InvalidArgument` → `ArgumentError`, everything else → `RuntimeError`. The
/// pure-Ruby layer (`lib/disarm.rb`) rescues these and re-raises them as
/// `Disarm::InvalidArgument` / `Disarm::Error` so consumers can `rescue
/// Disarm::Error` (#357); raising the built-ins here keeps the native side free
/// of any dependency on Ruby-defined classes existing at call time.
///
/// Named `map_err` (not `raise`) to signal it constructs a magnus `Error` value
/// rather than raising immediately — mirrors the Node shim's convention.
fn map_err(e: &disarm_core::Error) -> Error {
    // magnus 0.8 moved the exception-class constructors onto the `Ruby` handle
    // (Ractor-safety). map_err is only ever called from inside a Ruby method
    // callback, so the GVL is held and `Ruby::get()` cannot fail — a justified
    // exception to the no-panic gate above.
    #[allow(clippy::expect_used)]
    let ruby = Ruby::get().expect("map_err must run while holding the Ruby GVL");
    let class = match e.kind() {
        disarm_core::ErrorKind::InvalidArgument => ruby.exception_arg_error(),
        _ => ruby.exception_runtime_error(),
    };
    Error::new(class, e.to_string())
}

// ── Malformed-Unicode boundary (#469 / #472) ──────────────────────────────────
//
// Ruby has no "lone surrogate" scalar; the equivalent malformed input is a String
// tagged UTF-8 whose bytes are not valid UTF-8 — typically WTF-8, where a surrogate
// code point is the (forbidden) 3-byte sequence `ED A0–BF 80–BF`. magnus's
// `String` conversion validates UTF-8 and raises `EncodingError` on such bytes, so
// every entrypoint would reject it. [`Wtf8Text`] takes the raw `RString` bytes
// *before* that validation and brings them to the same WTF-8 → UTF-8 contract the
// Python and Node bindings honor: a well-formed high+low pair recombines into its
// astral scalar, and each genuinely lone surrogate code unit (or non-decodable byte)
// becomes exactly one `U+FFFD`. Valid UTF-8 skips the WTF-8 decoder via a `from_utf8`
// check (it still allocates the owned `String` magnus would have).

/// Decode WTF-8 bytes to valid UTF-8: recombine surrogate pairs into astral scalars,
/// map each lone surrogate — and any byte that is not part of a valid WTF-8 sequence —
/// to one `U+FFFD`. (Per code unit, not Ruby's per-byte `String#scrub`.)
fn wtf8_to_utf8(bytes: &[u8]) -> String {
    // A continuation byte (`10xx_xxxx`); its low 6 bits, or `None` if absent/not a
    // continuation. Slice access is via `get` so the binding's no-panic gate holds.
    #[inline]
    fn cont(b: Option<&u8>) -> Option<u32> {
        b.filter(|&&x| x & 0xC0 == 0x80)
            .map(|&x| u32::from(x & 0x3F))
    }
    // Pass 1: decode to code points, allowing surrogate scalars. A byte that does not
    // begin a *valid* 1–4 byte WTF-8 sequence — including an overlong encoding (e.g. the
    // 2-byte `C0 AF` for `/`) or an out-of-range 4-byte lead (`F5..F7`, > U+10FFFF) —
    // yields one U+FFFD and advances by a single byte, so the following bytes are
    // re-examined individually rather than swallowed.
    let mut cps: Vec<u32> = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while let Some(&b) = bytes.get(i) {
        let c1 = cont(bytes.get(i + 1));
        let c2 = cont(bytes.get(i + 2));
        let c3 = cont(bytes.get(i + 3));
        let (cp, len) = if b < 0x80 {
            (u32::from(b), 1)
        } else if let (0b110, Some(x1)) = (b >> 5, c1) {
            let cp = (u32::from(b & 0x1F) << 6) | x1;
            // reject overlong (a 2-byte form for < U+0080 — lead C0/C1).
            if cp >= 0x80 {
                (cp, 2)
            } else {
                (0xFFFD, 1)
            }
        } else if let (0b1110, Some(x1), Some(x2)) = (b >> 4, c1, c2) {
            let cp = (u32::from(b & 0x0F) << 12) | (x1 << 6) | x2;
            // reject overlong (< U+0800); surrogates U+D800..U+DFFF are valid WTF-8.
            if cp >= 0x800 {
                (cp, 3)
            } else {
                (0xFFFD, 1)
            }
        } else if let (0b11110, Some(x1), Some(x2), Some(x3)) = (b >> 3, c1, c2, c3) {
            let cp = (u32::from(b & 0x07) << 18) | (x1 << 12) | (x2 << 6) | x3;
            // reject overlong (< U+10000) and out-of-range (> U+10FFFF — lead F5..F7).
            if (0x1_0000..=0x10_FFFF).contains(&cp) {
                (cp, 4)
            } else {
                (0xFFFD, 1)
            }
        } else {
            (0xFFFD, 1)
        };
        cps.push(cp);
        i += len;
    }
    // Pass 2: recombine high+low surrogate pairs into the astral scalar; a lone
    // surrogate becomes one U+FFFD.
    let mut out = String::with_capacity(bytes.len());
    let mut j = 0;
    while let Some(&cp) = cps.get(j) {
        let low = cps
            .get(j + 1)
            .copied()
            .filter(|n| (0xDC00..=0xDFFF).contains(n));
        if let (true, Some(lo)) = ((0xD800..=0xDBFF).contains(&cp), low) {
            let astral = 0x1_0000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
            out.push(char::from_u32(astral).unwrap_or('\u{FFFD}'));
            j += 2;
        } else {
            out.push(char::from_u32(cp).unwrap_or('\u{FFFD}')); // surrogate -> None -> U+FFFD
            j += 1;
        }
    }
    out
}

/// A text argument decoded at the boundary with the WTF-8 → UTF-8 contract (#472).
/// Used in place of `String` for every text parameter; `Deref<Target = str>` lets the
/// existing `&text` call sites reach the core unchanged.
struct Wtf8Text(String);

impl std::ops::Deref for Wtf8Text {
    type Target = str;
    fn deref(&self) -> &str {
        &self.0
    }
}

impl magnus::TryConvert for Wtf8Text {
    fn try_convert(val: magnus::Value) -> Result<Self, Error> {
        let s = magnus::RString::try_convert(val)?;
        // SAFETY: the bytes are copied out immediately; no Ruby API runs between
        // `as_slice` and `to_vec`, so the string cannot be moved or collected.
        let bytes = unsafe { s.as_slice().to_vec() };
        let decoded = match std::str::from_utf8(&bytes) {
            Ok(valid) => valid.to_owned(),
            Err(_) => wtf8_to_utf8(&bytes),
        };
        Ok(Wtf8Text(decoded))
    }
}

// ── Transliteration ───────────────────────────────────────────────────────────

/// `Disarm._transliterate(text)` — Unicode → ASCII with the default scheme (the
/// common case; keeps the core's borrow-on-no-op fast path).
fn transliterate(text: Wtf8Text) -> String {
    api::transliterate(&text).into_owned()
}

/// `Disarm._transliterate_opts(text, "default" | "strict_iso9" | "gost7034", lang)`
/// — a scheme and/or a language profile via the core's `Transliterate` builder.
/// `lang` is `nil` (no profile) or a code like `"uk"` (Київ → Kyiv); it composes
/// with the scheme. The idiomatic layer routes the bare-default/no-lang case to
/// `_transliterate` so this is only hit when at least one option is set.
fn transliterate_opts(
    text: Wtf8Text,
    scheme: String,
    lang: Option<String>,
) -> Result<String, Error> {
    let mut builder = api::Transliterate::new();
    if scheme != "default" {
        let scheme: api::Scheme = scheme.parse().map_err(|e| map_err(&e))?;
        builder = builder.scheme(scheme);
    }
    if let Some(lang) = lang {
        builder = builder.lang(lang);
    }
    Ok(builder.run(&text).into_owned())
}

// ── Confusables (TR39) ────────────────────────────────────────────────────────

/// `Disarm._normalize_confusables(text, "latin" | "cyrillic")`.
fn normalize_confusables(text: Wtf8Text, target: String) -> Result<String, Error> {
    let target: api::TargetScript = target.parse().map_err(|e| map_err(&e))?;
    Ok(api::normalize_confusables(&text, target).into_owned())
}

/// `Disarm._confusable?(text, "latin" | "cyrillic")`.
fn is_confusable(text: Wtf8Text, target: String) -> Result<bool, Error> {
    let target: api::TargetScript = target.parse().map_err(|e| map_err(&e))?;
    Ok(api::is_confusable(&text, target))
}

// ── Canonicalization primitives ───────────────────────────────────────────────

fn strip_accents(text: Wtf8Text) -> String {
    api::strip_accents(&text).into_owned()
}

fn fold_case(text: Wtf8Text) -> String {
    api::fold_case(&text).into_owned()
}

/// `Disarm._slugify(text, …)` — the full slug option surface, positional. The
/// Ruby layer maps its keyword arguments (with the core's documented defaults)
/// onto this order. `regex_pattern` and `replacements` are intentionally not
/// surfaced yet (they need non-scalar Ruby↔Rust conversion); everything else the
/// core's `SlugConfig` exposes is reachable.
#[allow(clippy::too_many_arguments)]
fn slugify(
    text: Wtf8Text,
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
fn demojize(text: Wtf8Text, strip_modifiers: bool) -> String {
    api::demojize(&text, strip_modifiers)
}

// ── Security presets (fallible) ───────────────────────────────────────────────

fn strip_obfuscation(text: Wtf8Text) -> Result<String, Error> {
    api::strip_obfuscation(&text)
        .map(std::borrow::Cow::into_owned)
        .map_err(|e| map_err(&e))
}

fn canonicalize(text: Wtf8Text) -> Result<String, Error> {
    api::canonicalize(&text)
        .map(std::borrow::Cow::into_owned)
        .map_err(|e| map_err(&e))
}

/// `Disarm._search_key(text, lang)` — case/accent/script-insensitive lookup key.
/// `lang` is `nil` (no profile) or a code like `"ru"`. Fails on an unknown `lang`.
fn search_key(text: Wtf8Text, lang: Option<String>) -> Result<String, Error> {
    api::search_key(&text, lang.as_deref())
        .map(std::borrow::Cow::into_owned)
        .map_err(|e| map_err(&e))
}

/// `Disarm._sort_key(text, lang)` — collation sort key (preserves base accented
/// characters for correct ordering). Fails on an unknown `lang`.
fn sort_key(text: Wtf8Text, lang: Option<String>) -> Result<String, Error> {
    api::sort_key(&text, lang.as_deref())
        .map(std::borrow::Cow::into_owned)
        .map_err(|e| map_err(&e))
}

/// `Disarm._catalog_key(text, lang, strict_iso9)` — catalog deduplication key.
/// `strict_iso9` selects the ISO 9:1995 Cyrillic scheme. Fails on an unknown `lang`.
fn catalog_key(text: Wtf8Text, lang: Option<String>, strict_iso9: bool) -> Result<String, Error> {
    api::catalog_key(&text, lang.as_deref(), strict_iso9)
        .map(std::borrow::Cow::into_owned)
        .map_err(|e| map_err(&e))
}

/// `Disarm._suspicious_hostname?(host)` — flags mixed-script / confusable IDN
/// spoofs. A false result asserts nothing was *found*, not that the host is safe.
fn suspicious_hostname(host: Wtf8Text) -> bool {
    // #362 made the Rust api return `HostnameAnalysis` (the verdict is its
    // `suspicious` field) instead of a `(bool, _)` tuple.
    api::is_suspicious_hostname(&host).suspicious
}

// ── Normalization (#375) ──────────────────────────────────────────────────────

/// `Disarm._normalize(text, "NFC" | "NFD" | "NFKC" | "NFKD")`. The idiomatic
/// layer upcases its `form:` symbol/string before forwarding.
fn normalize(text: Wtf8Text, form: String) -> Result<String, Error> {
    let form: api::NormalizationForm = form.parse().map_err(|e| map_err(&e))?;
    Ok(api::normalize(&text, form))
}

/// `Disarm._normalized?(text, form)`.
fn is_normalized(text: Wtf8Text, form: String) -> Result<bool, Error> {
    let form: api::NormalizationForm = form.parse().map_err(|e| map_err(&e))?;
    Ok(api::is_normalized(&text, form))
}

// ── Text cleaning (#375) ──────────────────────────────────────────────────────

/// `Disarm._collapse_whitespace(text)` — fold whitespace only (#433).
fn collapse_whitespace(text: Wtf8Text) -> String {
    api::collapse_whitespace(&text)
}

/// `Disarm._strip_control_chars(text)` — remove C0/C1 controls (except tab/newline).
fn strip_control_chars(text: Wtf8Text) -> String {
    api::strip_control_chars(&text)
}

/// `Disarm._strip_zero_width_chars(text)` — remove ZWSP/ZWNJ/ZWJ/word-joiner.
fn strip_zero_width_chars(text: Wtf8Text) -> String {
    api::strip_zero_width_chars(&text)
}

/// `Disarm._strip_bidi(text)` — remove Unicode bidirectional control characters.
fn strip_bidi(text: Wtf8Text) -> String {
    api::strip_bidi(&text)
}

/// `Disarm._strip_tags(text)` — strip the Unicode Tags block, keeping emoji flags (#413).
fn strip_tags(text: Wtf8Text) -> String {
    api::strip_tags(&text)
}

/// `Disarm._strip_variation_selectors(text)` — strip every variation selector (#413).
fn strip_variation_selectors(text: Wtf8Text) -> String {
    api::strip_variation_selectors(&text)
}

/// `Disarm._strip_noncharacters(text)` — strip every Unicode noncharacter (#413).
fn strip_noncharacters(text: Wtf8Text) -> String {
    api::strip_noncharacters(&text)
}

/// `Disarm._strip_pua(text)` — strip every Private Use Area code point (#413).
fn strip_pua(text: Wtf8Text) -> String {
    api::strip_pua(&text)
}

/// `Disarm._strip_zalgo(text, max_marks)` — cap combining marks per base.
fn strip_zalgo(text: Wtf8Text, max_marks: usize) -> String {
    api::strip_zalgo(&text, max_marks)
}

/// `Disarm._zalgo?(text, threshold)` — any base carrying > threshold marks.
fn is_zalgo(text: Wtf8Text, threshold: usize) -> bool {
    api::is_zalgo(&text, threshold)
}

// ── Grapheme clusters (#375) ──────────────────────────────────────────────────

/// `Disarm._grapheme_len(text)` — count of user-perceived characters.
fn grapheme_len(text: Wtf8Text) -> usize {
    api::grapheme_len(&text)
}

/// `Disarm._grapheme_split(text)` — split into grapheme-cluster strings.
fn grapheme_split(text: Wtf8Text) -> Vec<String> {
    api::grapheme_split(&text)
}

/// `Disarm._grapheme_truncate(text, max_graphemes)` — truncate by graphemes,
/// never mid-cluster.
fn grapheme_truncate(text: Wtf8Text, max_graphemes: usize) -> String {
    api::grapheme_truncate(&text, max_graphemes)
}

/// `Disarm._grapheme_width(cluster, ambiguous_wide)` — display columns of one
/// cluster (East Asian Width).
fn grapheme_width(cluster: String, ambiguous_wide: bool) -> usize {
    api::grapheme_width(&cluster, ambiguous_wide)
}

/// `Disarm._terminal_width(text, ambiguous_wide)` — display columns of the whole
/// string.
fn terminal_width(text: Wtf8Text, ambiguous_wide: bool) -> usize {
    api::terminal_width(&text, ambiguous_wide)
}

// ── Filenames (#375) ──────────────────────────────────────────────────────────

/// `Disarm._sanitize_filename(text, separator, max_length, platform, lang,
/// preserve_extension)` — fallible; `platform` is "universal" | "windows" | "posix".
#[allow(clippy::too_many_arguments)]
fn sanitize_filename(
    text: Wtf8Text,
    separator: String,
    max_length: usize,
    platform: String,
    lang: Option<String>,
    preserve_extension: bool,
) -> Result<String, Error> {
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

// ── Reverse transliteration & untranslatable scan (#375) ──────────────────────

/// `Disarm._reverse_transliterate(text, lang)` — Latin → native; `lang` is
/// "el" | "ru" | "uk".
fn reverse_transliterate(text: Wtf8Text, lang: String) -> Result<String, Error> {
    let lang: api::ReverseLang = lang.parse().map_err(|e| map_err(&e))?;
    Ok(api::reverse_transliterate(&text, lang))
}

/// `Disarm._find_untranslatable(text, scheme, lang)` — every character with no
/// romanization, as `[char, byte_offset]` pairs (the Ruby layer maps these to
/// `{ char:, offset: }` hashes).
fn find_untranslatable(
    text: Wtf8Text,
    scheme: String,
    lang: Option<String>,
) -> Result<Vec<(String, usize)>, Error> {
    let mut builder = api::Transliterate::new();
    if scheme != "default" {
        let scheme: api::Scheme = scheme.parse().map_err(|e| map_err(&e))?;
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
fn detect_scripts(text: Wtf8Text) -> Vec<String> {
    api::detect_scripts(&text)
        .into_iter()
        .map(str::to_owned)
        .collect()
}

/// `Disarm._is_mixed_script?(text)` — whether `text` mixes more than one script.
fn is_mixed_script(text: Wtf8Text) -> bool {
    api::is_mixed_script(&text)
}

/// `Disarm._has_bidi_conflict?(text)` — whether `text` mixes strong left-to-right
/// and strong right-to-left characters (the "BiDi Swap" reorder precondition,
/// #412). Fires on the real letters, no `U+202x` override; `false` is not a
/// safety guarantee.
fn has_bidi_conflict(text: Wtf8Text) -> bool {
    api::has_bidi_conflict(&text)
}

/// `Disarm._inspect_auto_lang(text)` — `[script, chosen_lang, reason,
/// discriminators_hit]` (the Ruby layer maps it to a hash). `script`/`chosen_lang`
/// are nil when nothing was detected.
fn inspect_auto_lang(text: Wtf8Text) -> (Option<String>, Option<String>, String, Vec<String>) {
    let r = api::inspect_auto_lang(&text);
    (r.script, r.chosen_lang, r.reason, r.discriminators_hit)
}

// ── Metadata introspection (#404 phase 3) ─────────────────────────────────────

/// `Disarm._lang_info(code)` — curated metadata for one language as a Ruby Hash
/// with symbol keys (`{ name:, script:, region:, context: }`), mirroring the
/// hash-building style of `inspect_auto_lang`'s wrapper. Fails (ArgumentError →
/// Disarm::InvalidArgument) on an unknown code.
fn lang_info(code: String) -> Result<RHash, Error> {
    let meta = api::lang_info(&code).map_err(|e| map_err(&e))?;
    // GVL invariant: a Ruby method callback always holds the GVL. Justified.
    #[allow(clippy::expect_used)]
    let ruby = Ruby::get().expect("a Ruby method callback always holds the GVL");
    let hash = ruby.hash_new();
    hash.aset(ruby.to_symbol("name"), meta.name)?;
    hash.aset(ruby.to_symbol("script"), meta.script)?;
    hash.aset(ruby.to_symbol("region"), meta.region)?;
    hash.aset(ruby.to_symbol("context"), meta.context)?;
    Ok(hash)
}

/// `Disarm._script_info(name)` — curated metadata for one script as a Ruby Hash
/// with symbol keys (`{ name:, default_lang:, example:, context_aware: }`);
/// `default_lang` is `nil` when the core has none. Fails (ArgumentError →
/// Disarm::InvalidArgument) on an unknown script.
fn script_info(name: String) -> Result<RHash, Error> {
    let meta = api::script_info(&name).map_err(|e| map_err(&e))?;
    // GVL invariant: a Ruby method callback always holds the GVL. Justified.
    #[allow(clippy::expect_used)]
    let ruby = Ruby::get().expect("a Ruby method callback always holds the GVL");
    let hash = ruby.hash_new();
    hash.aset(ruby.to_symbol("name"), meta.name)?;
    // `Option<&str>` maps to the string or `nil`, matching the core's `None`.
    hash.aset(ruby.to_symbol("default_lang"), meta.default_lang)?;
    hash.aset(ruby.to_symbol("example"), meta.example)?;
    hash.aset(ruby.to_symbol("context_aware"), meta.context_aware)?;
    Ok(hash)
}

/// `Disarm._list_scripts` — every script disarm knows, as stable UCD identifiers.
fn list_scripts() -> Vec<String> {
    api::list_scripts().into_iter().map(str::to_owned).collect()
}

/// `Disarm._list_context_langs` — language codes with context-aware support.
fn list_context_langs() -> Vec<String> {
    api::list_context_langs()
        .into_iter()
        .map(str::to_owned)
        .collect()
}

// ── Anomaly detection (#389) ──────────────────────────────────────────────────

/// Collect a `Vec<String>` lexicon into a `HashSet<String>` for O(1) membership
/// lookups. Shared by `has_anomalies` and `inspect_anomalies`.
fn collect_lexicon(lexicon: Vec<String>) -> HashSet<String> {
    // Delegates to api::lexicon, which lowercases entries so a title-cased wordlist
    // still matches the detector's lowercased decoded words.
    api::lexicon(lexicon)
}

/// A reusable, pre-built lexicon (`Disarm::Lexicon`) — the `HashSet<String>` is
/// collected once at construction so repeated `has_anomalies?`/`inspect_anomalies`
/// calls over the same word list skip the per-call Array→HashSet rebuild (HAI-SDLC
/// 6.1). Mirrors the Python binding's reusable lexicon handle.
#[magnus::wrap(class = "Disarm::Lexicon", free_immediately, size)]
struct Lexicon {
    inner: HashSet<String>,
}

/// `Disarm::Lexicon.new(words)` — build the internal `HashSet<String>` once from an
/// Array/Set of words (reusing `collect_lexicon`).
fn lexicon_new(words: Vec<String>) -> Lexicon {
    Lexicon {
        inner: collect_lexicon(words),
    }
}

/// `Disarm._has_anomalies?(text, lexicon)` — `lexicon` is an array of common words.
fn has_anomalies(text: Wtf8Text, lexicon: Vec<String>) -> bool {
    api::has_anomalies(&text, &collect_lexicon(lexicon))
}

/// `Disarm._has_anomalies_lex(text, lexicon)` — the reuse path: takes a pre-built
/// `Disarm::Lexicon`, so the `HashSet` is shared rather than rebuilt per call.
fn has_anomalies_lex(text: Wtf8Text, lex: &Lexicon) -> bool {
    api::has_anomalies(&text, &lex.inner)
}

// The flat tuple return is intentional: `lib/disarm.rb` maps it to a named hash.
// A dedicated magnus struct would require registering a Ruby class just for this
// internal boundary, which is more boilerplate than the tuple costs.
#[allow(clippy::type_complexity)]
type AnomalyReportTuple = (
    bool,
    Vec<String>,
    Vec<(String, String, usize, usize, String, String)>,
    Option<String>,
);

/// Run `api::inspect_anomalies` and flatten its report into the tuple shape the
/// Ruby layer maps to a hash. Shared by the Array and `Disarm::Lexicon` entrypoints.
fn inspect_anomalies_impl(text: &str, lex: &HashSet<String>) -> AnomalyReportTuple {
    let r = api::inspect_anomalies(text, lex);
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

/// `Disarm._inspect_anomalies(text, lexicon)` — `[anomalous, kinds, findings,
/// reason]` where each finding is `[kind, token, start, end, detail, reason]` (the
/// Ruby layer maps it to a hash).
fn inspect_anomalies(text: Wtf8Text, lexicon: Vec<String>) -> AnomalyReportTuple {
    inspect_anomalies_impl(&text, &collect_lexicon(lexicon))
}

/// `Disarm._inspect_anomalies_lex(text, lexicon)` — the reuse path: the same tuple
/// shape as `inspect_anomalies`, but taking a pre-built `Disarm::Lexicon`.
fn inspect_anomalies_lex(text: Wtf8Text, lex: &Lexicon) -> AnomalyReportTuple {
    inspect_anomalies_impl(&text, &lex.inner)
}

// ── Pipeline (#404 phase 2) ───────────────────────────────────────────────────

/// A reusable, pre-built policy pipeline (`Disarm::Pipeline`) — the profile's
/// steps are validated and assembled once at construction (`get_pipeline`), so
/// repeated `process` calls over the same profile skip the per-call profile
/// lookup/validation. Mirrors the `Disarm::Lexicon` reusable handle (and the
/// Python binding's pipeline handle).
#[magnus::wrap(class = "Disarm::Pipeline", free_immediately, size)]
struct Pipeline {
    inner: api::Pipeline,
}

/// `Disarm::Pipeline#process(text)` — run the pre-built pipeline over `text`.
fn pipeline_process(rb_self: &Pipeline, text: Wtf8Text) -> Result<String, Error> {
    rb_self.inner.process(&text).map_err(|e| map_err(&e))
}

/// `Disarm._get_pipeline(profile)` — build a reusable `Disarm::Pipeline` for a
/// named policy profile. Fails (Disarm::InvalidArgument) on an unknown profile.
fn get_pipeline(profile: String) -> Result<Pipeline, Error> {
    Ok(Pipeline {
        inner: api::get_pipeline(&profile).map_err(|e| map_err(&e))?,
    })
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
    module.define_singleton_method("_canonicalize", function!(canonicalize, 1))?;

    // Key-derivation presets (#404 Group A parity backfill).
    module.define_singleton_method("_search_key", function!(search_key, 2))?;
    module.define_singleton_method("_sort_key", function!(sort_key, 2))?;
    module.define_singleton_method("_catalog_key", function!(catalog_key, 3))?;

    // No options / no symbols, but still wrapped by the Ruby layer so a wrong-type
    // argument surfaces as Disarm::InvalidArgument rather than a raw TypeError —
    // keeping `rescue Disarm::Error` exhaustive across the whole public surface.
    module.define_singleton_method("_strip_accents", function!(strip_accents, 1))?;
    module.define_singleton_method("_fold_case", function!(fold_case, 1))?;
    module.define_singleton_method("_suspicious_hostname?", function!(suspicious_hostname, 1))?;

    // Normalization + text-cleaning primitives (#375 parity backfill).
    module.define_singleton_method("_normalize", function!(normalize, 2))?;
    module.define_singleton_method("_normalized?", function!(is_normalized, 2))?;
    module.define_singleton_method("_collapse_whitespace", function!(collapse_whitespace, 1))?;
    module.define_singleton_method("_strip_control_chars", function!(strip_control_chars, 1))?;
    module.define_singleton_method(
        "_strip_zero_width_chars",
        function!(strip_zero_width_chars, 1),
    )?;
    module.define_singleton_method("_strip_bidi", function!(strip_bidi, 1))?;
    module.define_singleton_method("_strip_tags", function!(strip_tags, 1))?;
    module.define_singleton_method(
        "_strip_variation_selectors",
        function!(strip_variation_selectors, 1),
    )?;
    module.define_singleton_method("_strip_noncharacters", function!(strip_noncharacters, 1))?;
    module.define_singleton_method("_strip_pua", function!(strip_pua, 1))?;
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
    module.define_singleton_method("_has_bidi_conflict?", function!(has_bidi_conflict, 1))?;
    module.define_singleton_method("_inspect_auto_lang", function!(inspect_auto_lang, 1))?;

    // Metadata introspection (#404 phase 3 parity backfill).
    module.define_singleton_method("_lang_info", function!(lang_info, 1))?;
    module.define_singleton_method("_script_info", function!(script_info, 1))?;
    module.define_singleton_method("_list_scripts", function!(list_scripts, 0))?;
    module.define_singleton_method("_list_context_langs", function!(list_context_langs, 0))?;

    module.define_singleton_method("_has_anomalies?", function!(has_anomalies, 2))?;
    module.define_singleton_method("_inspect_anomalies", function!(inspect_anomalies, 2))?;

    // Reusable lexicon handle (HAI-SDLC 6.1): build the HashSet once, reuse it
    // across calls. `Disarm::Lexicon.new(words)` wraps the Rust `Lexicon`; the
    // `_lex` variants take it directly so the membership set is shared, not rebuilt.
    let lexicon = module.define_class("Lexicon", ruby.class_object())?;
    lexicon.define_singleton_method("new", function!(lexicon_new, 1))?;
    module.define_singleton_method("_has_anomalies_lex", function!(has_anomalies_lex, 2))?;
    module.define_singleton_method(
        "_inspect_anomalies_lex",
        function!(inspect_anomalies_lex, 2),
    )?;

    // Reusable pipeline handle (#404 phase 2): build the profile's steps once via
    // `Disarm.get_pipeline(profile)` (routed through the `_get_pipeline` shim) and
    // reuse the `Disarm::Pipeline` across calls. `process` is the Rust-defined
    // instance method on the wrapped handle. Mirrors `Disarm::Lexicon` above.
    let pipeline = module.define_class("Pipeline", ruby.class_object())?;
    pipeline.define_method("process", method!(pipeline_process, 1))?;
    module.define_singleton_method("_get_pipeline", function!(get_pipeline, 1))?;
    Ok(())
}
