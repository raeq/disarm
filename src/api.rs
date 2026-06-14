//! Layer 2: the idiomatic, pyo3-free Rust API — the future crates.io surface (#38).
//!
//! These wrap the Layer-1 algorithm modules with typed parameters and infallible
//! signatures where the type system already rules out the error. The PyO3 shims
//! (`src/py/`) and the planned C-ABI consume the same Layer-1 core, so this is
//! the one place the public Rust behaviour is defined.
//!
//! This module is built up incrementally (sub-PR by sub-PR) as each algorithm
//! module is migrated to the Layer-1/Layer-2/Layer-3 split; `confusables` was the
//! first, landing the canonical template.

use std::borrow::Cow;

use crate::Error;

// ── Confusables (TR39) ──────────────────────────────────────────────────────

/// Target script for confusable folding (see [`normalize_confusables`]).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum TargetScript {
    /// Fold confusables onto their Latin prototypes (the common case).
    Latin,
    /// Fold confusables onto their Cyrillic prototypes.
    Cyrillic,
}

impl TargetScript {
    /// The lowercase token the underlying tables are keyed by.
    fn as_str(self) -> &'static str {
        match self {
            TargetScript::Latin => "latin",
            TargetScript::Cyrillic => "cyrillic",
        }
    }
}

/// Replace Unicode confusable homoglyphs with their `target`-script prototypes
/// (TR39). Characters with no mapping pass through unchanged.
///
/// Infallible: a [`TargetScript`] is always a supported script.
pub fn normalize_confusables(text: &str, target: TargetScript) -> String {
    // The only error path of the Layer-1 fn is an unsupported target *string*;
    // a `TargetScript` value can never produce one, so this is unreachable.
    crate::confusables::normalize_confusables(text, target.as_str())
        .expect("TargetScript always maps to a supported target script")
}

/// True if `text` contains any character confusable with a `target`-script
/// character (TR39).
///
/// Infallible: a [`TargetScript`] is always a supported script.
pub fn is_confusable(text: &str, target: TargetScript) -> bool {
    crate::confusables::is_confusable(text, target.as_str())
        .expect("TargetScript always maps to a supported target script")
}

// ── Terminal width (UAX #11 / UAX #29) ───────────────────────────────────────

/// Total terminal column width of `text`, summed over UAX #29 grapheme clusters
/// (#224). Measures cells, not pixels; does not expand tabs or model wrapping.
///
/// `ambiguous_wide` selects the East-Asian Ambiguous policy (UAX #11): when
/// `true`, ambiguous-width characters count as 2 cells, otherwise 1.
pub fn terminal_width(text: &str, ambiguous_wide: bool) -> usize {
    crate::width::terminal_width_opts(text, ambiguous_wide)
}

/// Column width of a single grapheme cluster (see [`terminal_width`]).
///
/// `ambiguous_wide` selects the East-Asian Ambiguous policy (UAX #11): when
/// `true`, ambiguous-width characters count as 2 cells, otherwise 1.
pub fn grapheme_width(cluster: &str, ambiguous_wide: bool) -> usize {
    crate::width::grapheme_width_opts(cluster, ambiguous_wide)
}

// ── Whitespace ───────────────────────────────────────────────────────────────

/// Normalize Unicode whitespace runs to single ASCII spaces, trimming the ends.
///
/// `strip_control` also removes C0/C1 control characters (so `\r\n` → `\n`);
/// `strip_zero_width` also removes zero-width / invisible characters.
pub fn collapse_whitespace(text: &str, strip_control: bool, strip_zero_width: bool) -> String {
    crate::whitespace::collapse_whitespace(text, strip_control, strip_zero_width)
}

/// Remove C0/C1 control characters (keeping `\n` and `\t`); `\r` is stripped, so
/// `\r\n` becomes `\n`. A composable primitive of [`collapse_whitespace`].
pub fn strip_control_chars(text: &str) -> String {
    crate::whitespace::strip_control_chars(text)
}

/// Remove zero-width / invisible characters (ZWSP, ZWJ/ZWNJ, BOM, word joiner,
/// the invisible math operators). A composable primitive of [`collapse_whitespace`].
pub fn strip_zero_width_chars(text: &str) -> String {
    crate::whitespace::strip_zero_width_chars(text)
}

// ── Zalgo (combining-mark abuse) ─────────────────────────────────────────────

/// True if any base character carries more than `threshold` consecutive
/// combining marks in NFD (zalgo-style abuse). A sane default is 3.
pub fn is_zalgo(text: &str, threshold: usize) -> bool {
    crate::zalgo::is_zalgo(text, threshold)
}

/// Cap combining marks at `max_marks` per base character (recomposed to NFC),
/// stripping zalgo stacking while preserving legitimate diacritics. `max_marks`
/// of 0 strips all combining marks.
pub fn strip_zalgo(text: &str, max_marks: usize) -> String {
    crate::zalgo::strip_zalgo(text, max_marks)
}

// ── Case folding ─────────────────────────────────────────────────────────────

/// Full Unicode case folding per CaseFolding.txt (status C + F) — stronger than
/// `str::to_lowercase` (folds ß→ss, ﬁ→fi, ς→σ, and ~1,500 other mappings). Use
/// for caseless matching, not display.
pub fn fold_case(text: &str) -> String {
    crate::case_fold::fold_case_impl(text)
}

// ── Grapheme clusters (UAX #29) ──────────────────────────────────────────────

/// Number of user-perceived characters (extended grapheme clusters): `"👩‍👩‍👧‍👦"` → 1.
pub fn grapheme_len(text: &str) -> usize {
    crate::grapheme::grapheme_len(text)
}

/// Split `text` into its extended grapheme clusters, one user-perceived
/// character per element.
pub fn grapheme_split(text: &str) -> Vec<String> {
    crate::grapheme::grapheme_split(text)
}

/// Truncate `text` to at most `max_graphemes` clusters without ever splitting a
/// cluster (so emoji / combining sequences stay intact). Returned unchanged if
/// already within the limit. Infallible — `usize` rules out the negative count
/// the Python binding must guard against.
pub fn grapheme_truncate(text: &str, max_graphemes: usize) -> String {
    crate::grapheme::truncate_to_graphemes(text, max_graphemes)
}

// ── Unicode normalization (UAX #15) ──────────────────────────────────────────

/// Unicode normalization form for [`normalize`] / [`is_normalized`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum NormalizationForm {
    /// Canonical composition (NFC).
    Nfc,
    /// Canonical decomposition (NFD).
    Nfd,
    /// Compatibility composition (NFKC).
    Nfkc,
    /// Compatibility decomposition (NFKD).
    Nfkd,
}

impl NormalizationForm {
    /// The uppercase token the underlying normalizer is keyed by.
    fn as_str(self) -> &'static str {
        match self {
            NormalizationForm::Nfc => "NFC",
            NormalizationForm::Nfd => "NFD",
            NormalizationForm::Nfkc => "NFKC",
            NormalizationForm::Nfkd => "NFKD",
        }
    }
}

/// Normalize `text` to the given Unicode normalization form.
///
/// Infallible: a [`NormalizationForm`] is always a valid form.
pub fn normalize(text: &str, form: NormalizationForm) -> String {
    crate::normalize::normalize(text, form.as_str())
        .expect("NormalizationForm is always a valid form")
}

/// True if `text` is already in the given Unicode normalization form.
///
/// Infallible: a [`NormalizationForm`] is always a valid form.
pub fn is_normalized(text: &str, form: NormalizationForm) -> bool {
    crate::normalize::is_normalized(text, form.as_str())
        .expect("NormalizationForm is always a valid form")
}

// ── Output encoders (encode once, at the sink) ───────────────────────────────

/// Escape the five HTML metacharacters for element-body (PCDATA) and
/// quoted-attribute context: `&`→`&amp;`, `<`→`&lt;`, `>`→`&gt;`, `"`→`&quot;`,
/// `'`→`&#x27;`. Returns `Cow::Borrowed` (zero-copy) when nothing needs escaping.
///
/// **Not** correct inside `<script>` / `<style>`, unquoted attributes, or URL
/// attributes — there HTML-entity escaping is insufficient or corrupting. Encode
/// once at the output sink; disarm is not a context-aware auto-escaper.
pub fn escape_html(text: &str) -> Cow<'_, str> {
    crate::encoders::escape_html_str(text)
}

/// URL component whose RFC 3986 safe-character set drives [`percent_encode`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum UrlComponent {
    /// A whole path: unreserved + sub-delims + `:` `@` `/`.
    Path,
    /// A single path segment: `Path` without `/`.
    Segment,
    /// A query value: unreserved only (reserved characters are encoded).
    Query,
    /// `Query` plus `application/x-www-form-urlencoded` space → `+`.
    Form,
}

impl UrlComponent {
    /// The lowercase token the underlying encoder is keyed by.
    fn as_str(self) -> &'static str {
        match self {
            UrlComponent::Path => "path",
            UrlComponent::Segment => "segment",
            UrlComponent::Query => "query",
            UrlComponent::Form => "form",
        }
    }
}

/// Percent-encode `text` for `component` (RFC 3986): the input is UTF-8 encoded,
/// then every byte outside the component's safe set becomes `%XX`. Output is ASCII.
///
/// Infallible: a [`UrlComponent`] always names a known component.
pub fn percent_encode(text: &str, component: UrlComponent) -> String {
    crate::encoders::percent_encode_str(text, component.as_str())
        .expect("UrlComponent always names a known component")
}

// ── Reverse transliteration (romanized Latin → native script) ────────────────

/// Language for [`reverse_transliterate`] — the scripts disarm ships reverse
/// tables for.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum ReverseLang {
    /// Greek (`el`).
    Greek,
    /// Russian (`ru`).
    Russian,
    /// Ukrainian (`uk`).
    Ukrainian,
}

impl ReverseLang {
    /// The lowercase language code the underlying tables are keyed by.
    fn as_str(self) -> &'static str {
        match self {
            ReverseLang::Greek => "el",
            ReverseLang::Russian => "ru",
            ReverseLang::Ukrainian => "uk",
        }
    }
}

/// Convert romanized Latin `text` back to its native script with greedy
/// longest-match scanning (digraphs/trigraphs like `shch` → щ); unmatched
/// characters pass through.
///
/// Infallible: a [`ReverseLang`] always has a reverse table.
pub fn reverse_transliterate(text: &str, lang: ReverseLang) -> String {
    crate::reverse::reverse_transliterate_impl(text, lang.as_str())
}

/// The languages that support [`reverse_transliterate`], as lowercase codes.
pub fn reverse_langs() -> Vec<String> {
    crate::reverse::reverse_langs()
}

// ── Script detection ─────────────────────────────────────────────────────────

/// Unicode scripts present in `text`, in order of first appearance (Common /
/// Inherited excluded). Names are stable UCD script identifiers (e.g. `"Latin"`).
pub fn detect_scripts(text: &str) -> Vec<&'static str> {
    crate::scripts::detect_scripts(text)
}

/// True if `text` mixes characters from more than one script (excluding Common /
/// Inherited) — a homoglyph-spoofing signal.
pub fn is_mixed_script(text: &str) -> bool {
    crate::scripts::is_mixed_script(text)
}

/// How disarm's auto-language detection resolved a string — returned by
/// [`inspect_auto_lang`] for diagnostics / explainability.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct AutoLangInspection {
    /// The primary non-Latin script detected, if any (e.g. `"Cyrillic"`).
    pub script: Option<String>,
    /// The language auto-detection chose, if any (e.g. `"ru"`).
    pub chosen_lang: Option<String>,
    /// Why that choice was made (`"discriminator"`, `"script_default"`,
    /// `"unambiguous_script"`, `"latin_discriminator"`, `"no_detection"`).
    pub reason: String,
    /// The discriminator characters that drove the choice, if any.
    pub discriminators_hit: Vec<String>,
}

/// Explain how auto-language detection resolves `text` (which script, which
/// language, and why) — for diagnostics, not the hot path.
pub fn inspect_auto_lang(text: &str) -> AutoLangInspection {
    let (script, chosen_lang, reason, discriminators_hit) = crate::scripts::inspect_auto_lang(text);
    AutoLangInspection {
        script: script.map(str::to_owned),
        chosen_lang,
        reason: reason.to_owned(),
        discriminators_hit,
    }
}

// ── Hostname homoglyph safety ────────────────────────────────────────────────

/// Findings from a hostname homoglyph analysis — returned by
/// [`is_suspicious_hostname`].
///
/// Reports factual findings; it claims nothing about absolute safety. A
/// `suspicious == false` result is **not** a safety certificate (see
/// [`is_suspicious_hostname`]).
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct HostnameAnalysis {
    /// Whether the hostname is flagged suspicious overall (the same value
    /// returned as the first element of [`is_suspicious_hostname`]'s tuple).
    pub suspicious: bool,
    /// Scripts detected across all labels, in order of first appearance
    /// (Common / Inherited excluded), as stable UCD script identifiers.
    pub scripts: Vec<String>,
    /// Whether any single label mixes characters from more than one script.
    pub mixed_script: bool,
    /// Whether any label contains a character confusable with a Latin one.
    pub has_confusables: bool,
    /// The Latin-normalized (canonical) form of the hostname.
    pub canonical: String,
}

/// Detect whether a hostname is *suspicious* for Unicode homoglyph spoofing,
/// returning `(is_suspicious, analysis)`.
///
/// `xn--` (ACE) labels are decoded to their Unicode form via UTS#46 before
/// analysis (#63); a malformed ACE label fails closed (suspicious). A hostname
/// is flagged when any single label is mixed-script (conservative, #254), when
/// any label contains a Latin-confusable character, or when an ACE label fails
/// to decode.
///
/// Infallible: the analysis runs against the fixed `"latin"` target script,
/// which is always supported.
///
/// **A `false` (not-suspicious) result is NOT a safety guarantee.** It means
/// only that no mixed-script label and no confusable *from the bundled TR39
/// table* was found. Base allow/deny decisions on the granular `scripts` /
/// `mixed_script` / `has_confusables` fields plus your own policy — a detector
/// can attest the *presence* of a problem, never the *absence* of all problems.
pub fn is_suspicious_hostname(hostname: &str) -> (bool, HostnameAnalysis) {
    let (suspicious, core) = crate::hostname::is_suspicious_hostname(hostname);
    (
        suspicious,
        HostnameAnalysis {
            suspicious: core.suspicious,
            scripts: core.scripts,
            mixed_script: core.mixed_script,
            has_confusables: core.has_confusables,
            canonical: core.canonical,
        },
    )
}

// ── Filename sanitization ────────────────────────────────────────────────────

/// Target platform whose illegal-character set and reserved-name rules drive
/// [`sanitize_filename`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum Platform {
    /// The intersection of all platforms' rules (the safe default).
    Universal,
    /// Windows: the universal illegal set plus reserved device names (CON, …).
    Windows,
    /// POSIX (Linux/macOS): only `/` and NUL are illegal.
    Posix,
}

impl Platform {
    /// The lowercase token the underlying sanitizer is keyed by.
    fn as_str(self) -> &'static str {
        match self {
            Platform::Universal => "universal",
            Platform::Windows => "windows",
            Platform::Posix => "posix",
        }
    }
}

/// Sanitize `text` into a filename safe for `platform`: transliterate to ASCII,
/// strip illegal characters (replacing runs with `separator`), neutralize `..`
/// traversal and reserved names, and truncate to `max_length` **bytes**
/// (extension-aware when `preserve_extension`).
///
/// `lang` selects the transliteration language (`None` = auto-detect). This is
/// the one fallible argument: an unknown language code is a runtime error
/// ([`ErrorKind::InvalidArgument`](crate::ErrorKind)); `Platform` and the
/// `usize` length make every other input infallible by construction.
///
/// [`ErrorKind::InvalidArgument`]: crate::ErrorKind::InvalidArgument
pub fn sanitize_filename(
    text: &str,
    separator: &str,
    max_length: usize,
    platform: Platform,
    lang: Option<&str>,
    preserve_extension: bool,
) -> Result<String, Error> {
    crate::filename::sanitize_filename(
        text,
        separator,
        max_length,
        platform.as_str(),
        lang,
        preserve_extension,
    )
    .map_err(Error::from)
}

// ── Encoding detection & decoding ────────────────────────────────────────────

/// Detect the probable character encoding of `bytes` (chardetng, Firefox's
/// detector), returning `(whatwg_label, confidence)`. Detection is probabilistic
/// — prefer explicit encoding metadata for critical pipelines.
pub fn detect_encoding(bytes: &[u8]) -> (String, f64) {
    crate::encoding::detect_encoding_impl(bytes)
}

/// Decode `bytes` to UTF-8. `encoding = None` auto-detects (rejecting a guess
/// below `min_confidence`, in `0.0..=1.0`). Returns `(text, had_errors)` where
/// `had_errors` flags inserted U+FFFD replacements; in `strict` mode a lossy
/// decode is an error instead.
///
/// Fails ([`ErrorKind`](crate::ErrorKind)) on an unknown, unsupported, or
/// low-confidence encoding, an out-of-range `min_confidence`, or (strict) a
/// lossy decode.
pub fn decode_to_utf8(
    bytes: &[u8],
    encoding: Option<&str>,
    min_confidence: f64,
    strict: bool,
) -> Result<(String, bool), Error> {
    crate::encoding::decode_to_utf8_impl(bytes, encoding, min_confidence, strict)
        .map_err(Error::from)
}

// ── Log-injection neutralization ─────────────────────────────────────────────

/// Neutralize log-injection / terminal-control characters in `text` so it is
/// safe to *write* as a log line: each CR, LF, NEL, LS, PS, NUL, C0/C1 control,
/// ESC, and DEL (and tab, unless `keep_tab`) is replaced with `replacement`
/// (use `""` to drop them). Returns `Cow::Borrowed` for an already-clean line.
///
/// Not an HTML/SQL sanitizer and not a defense against logging-framework
/// interpolation — encode at the *viewer's* sink for those. Fails
/// ([`ErrorKind::InvalidArgument`](crate::ErrorKind)) if `replacement` itself
/// contains a character this call neutralizes (which would break the
/// no-raw-CR/LF and idempotency guarantees).
pub fn strip_log_injection<'a>(
    text: &'a str,
    replacement: &str,
    keep_tab: bool,
) -> Result<Cow<'a, str>, Error> {
    crate::log_injection::validate_log_replacement(replacement, keep_tab).map_err(Error::from)?;
    Ok(crate::log_injection::strip_log_injection_str(
        text,
        replacement,
        keep_tab,
    ))
}

// ── Slugification ────────────────────────────────────────────────────────────

pub use crate::slugify::SlugConfig;

/// Generate a URL-safe slug from `text` according to `config` (separator, max
/// length, case folding, stopwords, custom regex, HTML-entity handling, …).
///
/// Build a [`SlugConfig`] from [`SlugConfig::default`] plus field updates.
///
/// Infallible by design — and therefore **`config.lang` is not validated**: an
/// unknown language code is treated as "best effort" and falls back to the
/// default transliterator (the same lenient behaviour as the underlying engine),
/// rather than erroring. This differs from the Python `slugify`, whose convenience
/// wrapper eagerly validates `lang` and raises. If you need strict validation in
/// Rust, check the code against [`list_langs`] before building the config.
pub fn slugify(text: &str, config: &SlugConfig) -> String {
    crate::slugify::slugify_impl(text, config)
}

// ── Emoji ────────────────────────────────────────────────────────────────────

/// Expand emoji sequences in `text` to their CLDR short-name text descriptions
/// (e.g. `"😀"` → `"grinning face"`). The matching engine handles ZWJ sequences,
/// skin-tone modifiers, flag/keycap sequences, and presentation selectors;
/// `strip_modifiers` drops the modifier suffix (`": light skin tone"`, etc.) from
/// each name. Pure-ASCII input is returned unchanged.
///
/// This uses the **built-in CLDR data** (latest English). The custom Python
/// `EmojiProvider` override exposed by the `disarm` package is binding-layer-only
/// (Python-only) and is intentionally **not** part of the Rust surface.
pub fn demojize(text: &str, strip_modifiers: bool) -> String {
    crate::emoji::demojize_rust(text, strip_modifiers)
}

// ── Transliteration ──────────────────────────────────────────────────────────

/// Remove diacritical marks while preserving base characters (NFD → strip
/// combining marks → NFC). For example `"café"` → `"cafe"`.
pub fn strip_accents(text: &str) -> String {
    crate::transliterate::strip_accents(text)
}

/// True if every character in `text` is ASCII (U+0000–U+007F).
pub fn is_ascii(text: &str) -> bool {
    text.is_ascii()
}

/// The language codes available for transliteration (built-in plus any
/// registered at runtime).
pub fn list_langs() -> Vec<String> {
    crate::tables::list_langs()
}

/// Transliterate `text` from Unicode to ASCII.
///
/// `lang` selects a language-specific romanization table (`None` = the default
/// multi-script tables; `Some("auto")` enables script detection). `error_mode`
/// governs unmapped characters: [`crate::ErrorMode::Replace`] substitutes
/// `replacement`, `Ignore` drops them, `Preserve` passes them through. `tones`
/// keeps tone marks (pinyin); `strict_iso9` and `gost7034` select the ISO 9 /
/// GOST 7.034 Cyrillic schemes. They are intended to be mutually exclusive, but
/// this infallible Rust API does **not** reject passing both — `strict_iso9`
/// takes precedence if you do. (The Python binding validates and raises; enforce
/// the constraint yourself if you need it in Rust.)
///
/// Returns `Cow::Borrowed` for pure-ASCII input (zero allocation), `Cow::Owned`
/// otherwise. Infallible: wraps the Layer-1 engine
/// [`crate::transliterate::transliterate_impl`].
///
/// Note: the public bool order is intentionally `(tones, strict_iso9, gost7034)`
/// to mirror the Python keyword order; the wrapper reorders onto the engine's
/// `(strict_iso9, gost7034, tones)`. Keep the public order stable.
#[allow(clippy::too_many_arguments)]
pub fn transliterate<'a>(
    text: &'a str,
    lang: Option<&str>,
    error_mode: crate::ErrorMode,
    replacement: &str,
    tones: bool,
    strict_iso9: bool,
    gost7034: bool,
) -> std::borrow::Cow<'a, str> {
    crate::transliterate::transliterate_impl(
        text,
        lang,
        error_mode,
        replacement,
        strict_iso9,
        gost7034,
        tones,
    )
}

/// Find every character in `text` that has no transliteration, as
/// `(char, byte_offset)` pairs in order of appearance. Pure-ASCII input yields
/// an empty vector. Mirrors [`transliterate`]'s engine, so the reported set is
/// exactly what that transform would replace/ignore/preserve. Wraps the Layer-1
/// core [`crate::transliterate::find_untranslatable_impl`].
///
/// As with [`transliterate`], the public bool order is intentionally
/// `(tones, strict_iso9, gost7034)`; the wrapper reorders onto the engine's
/// `(strict_iso9, gost7034, tones)`.
pub fn find_untranslatable(
    text: &str,
    lang: Option<&str>,
    tones: bool,
    strict_iso9: bool,
    gost7034: bool,
) -> Vec<(char, usize)> {
    crate::transliterate::find_untranslatable_impl(text, lang, strict_iso9, gost7034, tones)
}

// ── Precompiled pipeline presets ──────────────────────────────────────────────

/// Security-focused text canonicalization (homoglyph / bidi / zero-width / control
/// neutralization with a path-safety guarantee).
///
/// Pipeline: NFKC → confusables → strip bidi/format → collapse whitespace →
/// path-separator neutralization. Fallible only through the confusables stage,
/// whose target script is fixed internally, so in practice this never errors;
/// the [`Result`] keeps the surface uniform with the other key/clean presets.
pub fn security_clean(text: &str) -> Result<String, Error> {
    crate::presets::security_clean(text).map_err(Error::from)
}

/// ML/NLP text normalization: NFKC → emoji→text → transliterate → strip accents →
/// case fold → collapse whitespace.
///
/// `lang` selects the transliteration table (`None` skips transliteration).
/// `emoji_style` is `"cldr"` (expand emoji to CLDR short names) or `"none"`
/// (leave emoji as-is). Fails ([`ErrorKind::InvalidArgument`](crate::ErrorKind))
/// on an unknown `lang` or an unsupported `emoji_style`.
pub fn ml_normalize(text: &str, lang: Option<&str>, emoji_style: &str) -> Result<String, Error> {
    crate::presets::ml_normalize(text, lang, emoji_style).map_err(Error::from)
}

/// Library catalog deduplication key: NFKC → strip bidi → transliterate →
/// confusables → strip accents → case fold → collapse whitespace.
///
/// `strict_iso9` selects the ISO 9:1995 Cyrillic scheme. Fails
/// ([`ErrorKind::InvalidArgument`](crate::ErrorKind)) on an unknown `lang`.
pub fn catalog_key(text: &str, lang: Option<&str>, strict_iso9: bool) -> Result<String, Error> {
    crate::presets::catalog_key(text, lang, strict_iso9).map_err(Error::from)
}

/// Case/accent/script-insensitive search lookup key (like [`catalog_key`] without
/// confusable folding). Fails ([`ErrorKind::InvalidArgument`](crate::ErrorKind))
/// on an unknown `lang`.
pub fn search_key(text: &str, lang: Option<&str>) -> Result<String, Error> {
    crate::presets::search_key(text, lang).map_err(Error::from)
}

/// Collation sort key (like [`search_key`] but preserves base accented characters
/// for correct ordering). Fails ([`ErrorKind::InvalidArgument`](crate::ErrorKind))
/// on an unknown `lang`.
pub fn sort_key(text: &str, lang: Option<&str>) -> Result<String, Error> {
    crate::presets::sort_key(text, lang).map_err(Error::from)
}

/// Display-safe cleanup for rendered user content: strip bidi/format → collapse
/// whitespace (also stripping control + zero-width). Infallible.
pub fn display_clean(text: &str) -> String {
    crate::presets::display_clean(text)
}

/// Strip bidirectional override and formatting characters (UAX #9 §3.3.2 plus the
/// soft hyphen and deprecated/interlinear format controls). A composable primitive
/// shared by the security/key presets. Infallible.
pub fn strip_bidi(text: &str) -> String {
    crate::presets::strip_bidi(text)
}

/// Normalize user-submitted input — Unicode hygiene that **preserves the original
/// script** (no transliteration): NFKC → strip bidi/zero-width/control →
/// strip zalgo → confusables → collapse whitespace → path-separator
/// neutralization.
///
/// Not an output sanitizer (no HTML/JS/SQL escaping). Fallible only through the
/// fixed-target confusables stage; the [`Result`] keeps the surface uniform.
pub fn normalize_user_input(text: &str) -> Result<String, Error> {
    crate::presets::normalize_user_input(text).map_err(Error::from)
}

/// Maximum-strength deobfuscation: NFKC → strip all combining marks → strip bidi →
/// strip zero-width → demojize → confusables → strip accents → collapse
/// whitespace. Preserves case; does not transliterate.
///
/// Fallible only through the fixed-target confusables stage; the [`Result`] keeps
/// the surface uniform.
pub fn strip_obfuscation(text: &str) -> Result<String, Error> {
    crate::presets::strip_obfuscation(text).map_err(Error::from)
}

// ── Named policy profiles ─────────────────────────────────────────────────────

/// Sorted names of the available named policy profiles (the registry that the
/// `get_pipeline` Python entrypoint builds from).
///
/// The stateful pipeline builder itself (`_TextPipeline`) stays binding-only for
/// now — exposing it as a pure crates.io type is deferred (see the module-level
/// `src/pipeline.rs` `Pipeline` core), so this read-only registry view is the
/// pipeline surface Layer 2 exposes. Infallible.
pub fn list_profiles() -> Vec<String> {
    crate::pipeline::profile_names()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_folds_cyrillic_to_latin() {
        // Cyrillic 'а' (U+0430) → Latin 'a'.
        assert_eq!(
            normalize_confusables("\u{0430}pple", TargetScript::Latin),
            "apple"
        );
        assert_eq!(normalize_confusables("hello", TargetScript::Latin), "hello");
        assert_eq!(normalize_confusables("", TargetScript::Latin), "");
    }

    #[test]
    fn is_confusable_detects_homoglyph() {
        assert!(is_confusable("p\u{0430}ypal", TargetScript::Latin)); // Cyrillic 'а'
        assert!(!is_confusable("paypal", TargetScript::Latin));
    }

    #[test]
    fn target_script_tokens() {
        assert_eq!(TargetScript::Latin.as_str(), "latin");
        assert_eq!(TargetScript::Cyrillic.as_str(), "cyrillic");
    }

    #[test]
    fn terminal_width_sums_clusters() {
        assert_eq!(terminal_width("hello", false), 5);
        assert_eq!(terminal_width("世界", false), 4); // wide CJK
        assert_eq!(terminal_width("", false), 0);
    }

    #[test]
    fn grapheme_width_single_cluster() {
        assert_eq!(grapheme_width("a", false), 1);
        assert_eq!(grapheme_width("世", false), 2);
        assert_eq!(grapheme_width("👨\u{200D}👩\u{200D}👧\u{200D}👦", false), 2);
        // ZWJ family
    }

    #[test]
    fn ambiguous_wide_policy() {
        // U+00A1 INVERTED EXCLAMATION MARK is East Asian Ambiguous.
        assert_eq!(terminal_width("\u{00A1}", false), 1);
        assert_eq!(terminal_width("\u{00A1}", true), 2);
        assert_eq!(grapheme_width("\u{00A1}", true), 2);
    }

    #[test]
    fn sanitize_filename_happy_path() {
        // Transliterates to ASCII and strips illegal characters.
        let out = sanitize_filename("héllo/wörld.txt", "_", 255, Platform::Universal, None, true)
            .unwrap();
        assert_eq!(out, "hello_world.txt");
        // POSIX keeps ':' (only '/' and NUL are illegal there).
        let out = sanitize_filename("a:b", "_", 255, Platform::Posix, None, true).unwrap();
        assert_eq!(out, "a:b");
    }

    #[test]
    fn sanitize_filename_bad_lang_is_invalid_argument() {
        // The one fallible argument: an unknown language code surfaces the opaque
        // Error, classified as InvalidArgument (the first fallible Layer-2 path).
        let err =
            sanitize_filename("x", "_", 255, Platform::Universal, Some("zzz"), true).unwrap_err();
        assert_eq!(err.kind(), crate::ErrorKind::InvalidArgument);
        // Opaque: no inner source leaks.
        assert!(std::error::Error::source(&err).is_none());
    }

    #[test]
    fn decode_to_utf8_explicit_and_error() {
        // Explicit encoding round-trips; "café" in ISO-8859-1 is 0x63 61 66 E9.
        let (text, had_errors) =
            decode_to_utf8(&[0x63, 0x61, 0x66, 0xE9], Some("ISO-8859-1"), 0.0, false).unwrap();
        assert_eq!(text, "café");
        assert!(!had_errors);
        // An unknown label surfaces the opaque Error (InvalidArgument).
        let err = decode_to_utf8(b"hi", Some("FAKE-999"), 0.0, false).unwrap_err();
        assert_eq!(err.kind(), crate::ErrorKind::InvalidArgument);
        // detect_encoding is infallible.
        let (label, conf) = detect_encoding(b"hello world");
        assert!(!label.is_empty() && conf > 0.0);
    }

    #[test]
    fn strip_log_injection_and_bad_replacement() {
        // CR/LF/NUL are neutralized; a clean line borrows.
        assert_eq!(
            strip_log_injection("a\r\nb\0c", "\u{FFFD}", false).unwrap(),
            "a\u{FFFD}\u{FFFD}b\u{FFFD}c"
        );
        assert!(matches!(
            strip_log_injection("plain line", "\u{FFFD}", false).unwrap(),
            std::borrow::Cow::Borrowed(_)
        ));
        // A replacement that itself contains a neutralized char (CR) is rejected.
        let err = strip_log_injection("x", "\r", false).unwrap_err();
        assert_eq!(err.kind(), crate::ErrorKind::InvalidArgument);
        assert_eq!(err.code(), "invalid_log_replacement");
    }

    #[test]
    fn slugify_with_config() {
        assert_eq!(
            slugify("Héllo Wörld", &SlugConfig::default()),
            "hello-world"
        );
        let bounded = SlugConfig {
            max_length: 5,
            word_boundary: true,
            ..SlugConfig::default()
        };
        assert_eq!(slugify("hello world", &bounded), "hello");
    }

    #[test]
    fn transliterate_surface() {
        use crate::ErrorMode;
        // ASCII passes through unchanged (Cow::Borrowed fast path).
        assert_eq!(
            transliterate("hello", None, ErrorMode::Replace, "?", false, false, false),
            "hello"
        );
        // Cyrillic auto-transliterates to ASCII.
        let out = transliterate("Москва", None, ErrorMode::Replace, "?", false, false, false);
        assert!(out.is_ascii() && !out.is_empty(), "got {out:?}");
        // strip_accents / is_ascii / list_langs.
        assert_eq!(strip_accents("café"), "cafe");
        assert!(is_ascii("hi") && !is_ascii("café"));
        assert!(list_langs().iter().any(|l| l == "ru"));
        // ASCII has nothing untranslatable.
        assert!(find_untranslatable("hello", None, false, false, false).is_empty());
    }

    #[test]
    fn preset_pipelines_surface() {
        // security_clean folds Cyrillic homoglyphs (р а → p a) and strips bidi.
        assert_eq!(security_clean("\u{0440}\u{0430}ypal").unwrap(), "paypal");
        // Key presets are case/accent/script insensitive.
        assert_eq!(search_key("CAFÉ", None).unwrap(), "cafe");
        assert_eq!(sort_key("Москва", None).unwrap(), "moskva");
        assert_eq!(catalog_key("Café", None, false).unwrap(), "cafe");
        // ml_normalize lowercases, strips accents.
        assert_eq!(ml_normalize("Café", None, "cldr").unwrap(), "cafe");
        // Infallible presets.
        assert_eq!(display_clean("hello   world"), "hello world");
        assert_eq!(strip_bidi("pass\u{00AD}word"), "password");
        // normalize_user_input preserves script/accents; strip_obfuscation runs.
        assert_eq!(normalize_user_input("café").unwrap(), "café");
        assert!(!strip_obfuscation("p\u{0430}ypal").unwrap().is_empty());
        // Bad lang / emoji_style surface InvalidArgument.
        assert_eq!(
            search_key("x", Some("zzz")).unwrap_err().kind(),
            crate::ErrorKind::InvalidArgument
        );
        assert_eq!(
            ml_normalize("x", None, "bogus").unwrap_err().kind(),
            crate::ErrorKind::InvalidArgument
        );
    }

    #[test]
    fn list_profiles_surface() {
        let profiles = list_profiles();
        // Known profiles are present, and the list is sorted (stable contract).
        assert!(profiles.iter().any(|p| p == "llm_guardrail"));
        assert!(profiles.iter().any(|p| p == "search_index"));
        let mut sorted = profiles.clone();
        sorted.sort();
        assert_eq!(profiles, sorted);
    }

    #[test]
    fn is_suspicious_hostname_surface() {
        // Plain ASCII hostname: not suspicious, single-script, canonical == input.
        let (susp, a) = is_suspicious_hostname("example.com");
        assert!(!susp && !a.suspicious && !a.mixed_script);
        assert_eq!(a.canonical, "example.com");
        // A label mixing Cyrillic 'а' (U+0430) into Latin "paypal" is a homoglyph
        // spoof — flagged, with the mixed-script / confusable findings set.
        let (susp2, a2) = is_suspicious_hostname("p\u{0430}ypal.com");
        assert!(susp2);
        assert!(a2.mixed_script || a2.has_confusables);
    }
}
