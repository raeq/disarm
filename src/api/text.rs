//! Layer 2 (part of [`crate::api`]) — text measurement (width, graphemes),
//! whitespace / zalgo / case / normalization cleanup, output encoders, slugify,
//! and emoji.

use std::borrow::Cow;

use crate::Error;

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

/// Fold Unicode whitespace runs to single ASCII spaces, trimming the ends (#433).
///
/// Folds **whitespace only** — the line controls (TAB/LF/VT/FF/CR), the
/// information separators (`U+001C`–`U+001F`), NEL, the `Zs`/`Zl`/`Zp` spaces,
/// and the blank-rendering set (Braille blank, the Hangul fillers) each become a
/// single space. It does **not** delete control or zero-width characters — pair
/// it with [`strip_control_chars`] / [`strip_zero_width_chars`] for that. Folding
/// (not deleting) the line controls means `a\rb` → `a b`, never `ab`.
#[must_use]
pub fn collapse_whitespace(text: &str) -> String {
    crate::whitespace::collapse_whitespace(text)
}

/// Remove C0/C1 control characters that are **not** whitespace (#433): NUL, DEL,
/// the C1 block, etc. are stripped, while the line controls (TAB, LF, VT, FF, CR,
/// `U+001C`–`U+001F`, NEL) are preserved for [`collapse_whitespace`] to fold. A
/// composable primitive of [`collapse_whitespace`].
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

// ── Invisible / non-interchange code points (#413) ───────────────────────────

/// Remove the Unicode **Tags** block (`U+E0000`–`U+E007F`) — the "ASCII
/// smuggling" covert channel — **preserving** well-formed emoji subdivision flag
/// sequences (`U+1F3F4` + tag letters + `U+E007F`, e.g. the Scotland flag).
#[must_use]
pub fn strip_tags(text: &str) -> String {
    crate::invisibles::strip_tags(text)
}

/// Remove every Unicode **variation selector** (VS1–VS16, `U+FE00`–`U+FE0F`, and
/// the Variation Selectors Supplement VS17–VS256, `U+E0100`–`U+E01EF`) — the
/// arbitrary-byte smuggling channel.
#[must_use]
pub fn strip_variation_selectors(text: &str) -> String {
    crate::invisibles::strip_variation_selectors(text)
}

/// Remove every Unicode **noncharacter** (`U+FDD0`–`U+FDEF` and the last two
/// code points of every plane) — permanently reserved, invalid for interchange.
#[must_use]
pub fn strip_noncharacters(text: &str) -> String {
    crate::invisibles::strip_noncharacters(text)
}

/// Remove every **Private Use Area** code point (BMP `U+E000`–`U+F8FF`, plane 15,
/// plane 16) — renders as arbitrary, font-defined glyphs.
#[must_use]
pub fn strip_pua(text: &str) -> String {
    crate::invisibles::strip_pua(text)
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
    /// The canonical token (the inverse of its `FromStr`, and what `Display`
    /// prints): `"NFC"` / `"NFD"` / `"NFKC"` / `"NFKD"`.
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

impl std::fmt::Display for NormalizationForm {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for NormalizationForm {
    type Err = Error;

    /// Parse `"NFC"` / `"NFD"` / `"NFKC"` / `"NFKD"`.
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "NFC" => Ok(Self::Nfc),
            "NFD" => Ok(Self::Nfd),
            "NFKC" => Ok(Self::Nfkc),
            "NFKD" => Ok(Self::Nfkd),
            _ => Err(Error::from(crate::ErrorRepr::InvalidNormForm {
                got: s.to_owned(),
            })),
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
    /// The canonical token (the inverse of its `FromStr`, and what `Display`
    /// prints): `"path"` / `"segment"` / `"query"` / `"form"`.
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

impl std::fmt::Display for UrlComponent {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for UrlComponent {
    type Err = Error;

    /// Parse `"path"` / `"segment"` / `"query"` / `"form"`.
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "path" => Ok(Self::Path),
            "segment" => Ok(Self::Segment),
            "query" => Ok(Self::Query),
            "form" => Ok(Self::Form),
            _ => Err(Error::from(crate::ErrorRepr::InvalidUrlComponent {
                got: s.to_owned(),
            })),
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
/// rather than erroring. The Python `slugify` wrapper treats `lang` the same way
/// — it forwards the code unvalidated and silently falls back, so neither
/// binding raises on an unknown slug `lang`. If you need strict validation,
/// check the code against [`list_langs`](crate::api::list_langs) before building the config.
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
