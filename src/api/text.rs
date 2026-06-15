//! Layer 2 (part of [`crate::api`]) — text measurement (width, graphemes),
//! whitespace / zalgo / case / normalization cleanup, output encoders, slugify,
//! and emoji.

use std::borrow::Cow;

// ── Terminal width (UAX #11 / UAX #29) ───────────────────────────────────────

/// Total terminal column width of `text`, summed over UAX #29 grapheme clusters
/// (#224). Measures cells, not pixels; does not expand tabs or model wrapping.
///
/// `ambiguous_wide` selects the East-Asian Ambiguous policy (UAX #11): when
/// `true`, ambiguous-width characters count as 2 cells, otherwise 1.
#[must_use]
pub fn terminal_width(text: &str, ambiguous_wide: bool) -> usize {
    crate::width::terminal_width_opts(text, ambiguous_wide)
}

/// Column width of a single grapheme cluster (see [`terminal_width`]).
///
/// `ambiguous_wide` selects the East-Asian Ambiguous policy (UAX #11): when
/// `true`, ambiguous-width characters count as 2 cells, otherwise 1.
#[must_use]
pub fn grapheme_width(cluster: &str, ambiguous_wide: bool) -> usize {
    crate::width::grapheme_width_opts(cluster, ambiguous_wide)
}

// ── Whitespace ───────────────────────────────────────────────────────────────

/// Normalize Unicode whitespace runs to single ASCII spaces, trimming the ends.
///
/// `strip_control` also removes C0/C1 control characters (so `\r\n` → `\n`);
/// `strip_zero_width` also removes zero-width / invisible characters.
#[must_use]
pub fn collapse_whitespace(text: &str, strip_control: bool, strip_zero_width: bool) -> String {
    crate::whitespace::collapse_whitespace(text, strip_control, strip_zero_width)
}

/// Remove C0/C1 control characters (keeping `\n` and `\t`); `\r` is stripped, so
/// `\r\n` becomes `\n`. A composable primitive of [`collapse_whitespace`].
#[must_use]
pub fn strip_control_chars(text: &str) -> String {
    crate::whitespace::strip_control_chars(text)
}

/// Remove zero-width / invisible characters (ZWSP, ZWJ/ZWNJ, BOM, word joiner,
/// the invisible math operators). A composable primitive of [`collapse_whitespace`].
#[must_use]
pub fn strip_zero_width_chars(text: &str) -> String {
    crate::whitespace::strip_zero_width_chars(text)
}

// ── Zalgo (combining-mark abuse) ─────────────────────────────────────────────

/// True if any base character carries more than `threshold` consecutive
/// combining marks in NFD (zalgo-style abuse). A sane default is 3.
#[must_use]
pub fn is_zalgo(text: &str, threshold: usize) -> bool {
    crate::zalgo::is_zalgo(text, threshold)
}

/// Cap combining marks at `max_marks` per base character (recomposed to NFC),
/// stripping zalgo stacking while preserving legitimate diacritics. `max_marks`
/// of 0 strips all combining marks.
#[must_use]
pub fn strip_zalgo(text: &str, max_marks: usize) -> String {
    crate::zalgo::strip_zalgo(text, max_marks)
}

// ── Case folding ─────────────────────────────────────────────────────────────

/// Full Unicode case folding per CaseFolding.txt (status C + F) — stronger than
/// `str::to_lowercase` (folds ß→ss, ﬁ→fi, ς→σ, and ~1,500 other mappings). Use
/// for caseless matching, not display.
///
/// Returns `Cow::Borrowed` when `text` is already folded (zero allocation).
#[must_use]
pub fn fold_case(text: &str) -> Cow<'_, str> {
    crate::case_fold::fold_case_cow(text)
}

// ── Grapheme clusters (UAX #29) ──────────────────────────────────────────────

/// Number of user-perceived characters (extended grapheme clusters): `"👩‍👩‍👧‍👦"` → 1.
#[must_use]
pub fn grapheme_len(text: &str) -> usize {
    crate::grapheme::grapheme_len(text)
}

/// Split `text` into its extended grapheme clusters, one user-perceived
/// character per element. Allocates a `String` per cluster; prefer
/// [`graphemes`] when borrowed slices suffice.
#[must_use]
pub fn grapheme_split(text: &str) -> Vec<String> {
    crate::grapheme::grapheme_split(text)
}

/// Iterate the extended grapheme clusters of `text` as borrowed `&str` slices —
/// no `Vec`, no per-cluster `String`. Callers that only need a count or the
/// first few never pay for the rest; `.collect()` when you want owned data.
///
/// ```
/// use disarm::api;
/// assert_eq!(api::graphemes("a❤️b").count(), 3);
/// ```
pub fn graphemes(text: &str) -> impl Iterator<Item = &str> {
    crate::grapheme::clusters(text)
}

/// Truncate `text` to at most `max_graphemes` clusters without ever splitting a
/// cluster (so emoji / combining sequences stay intact). Returned unchanged if
/// already within the limit. Infallible — `usize` rules out the negative count
/// the Python binding must guard against.
#[must_use]
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
    /// The canonical string token for this value (the inverse of its `FromStr`,
    /// and what `Display` prints).
    #[must_use]
    pub fn as_str(self) -> &'static str {
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
#[must_use]
pub fn normalize(text: &str, form: NormalizationForm) -> String {
    crate::normalize::normalize(text, form.as_str())
        .expect("NormalizationForm is always a valid form")
}

/// True if `text` is already in the given Unicode normalization form.
///
/// Infallible: a [`NormalizationForm`] is always a valid form.
#[must_use]
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
#[must_use]
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
    /// The canonical string token for this value (the inverse of its `FromStr`,
    /// and what `Display` prints).
    #[must_use]
    pub fn as_str(self) -> &'static str {
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
#[must_use]
pub fn percent_encode(text: &str, component: UrlComponent) -> String {
    crate::encoders::percent_encode_str(text, component.as_str())
        .expect("UrlComponent always names a known component")
}

// ── Slugification ────────────────────────────────────────────────────────────

pub use crate::slugify::SlugConfig;

/// Generate a URL-safe slug from `text` according to `config` (separator, max
/// length, case folding, stopwords, custom regex, HTML-entity handling, …).
///
/// Build a [`SlugConfig`] with [`SlugConfig::new`] and the `with_*` setters.
///
/// Infallible by design — and therefore **`config.lang` is not validated**: an
/// unknown language code is treated as "best effort" and falls back to the
/// default transliterator (the same lenient behaviour as the underlying engine),
/// rather than erroring. This differs from the Python `slugify`, whose convenience
/// wrapper eagerly validates `lang` and raises. If you need strict validation in
/// Rust, check the code against [`list_langs`](crate::api::list_langs) before building the config.
#[must_use]
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
#[must_use]
pub fn demojize(text: &str, strip_modifiers: bool) -> String {
    crate::emoji::demojize_rust(text, strip_modifiers)
}
