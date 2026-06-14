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
}
