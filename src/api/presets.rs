//! Layer 2 (part of [`crate::api`]) — the precompiled pipeline presets and the
//! named-policy-profile registry.

use std::borrow::Cow;

use crate::Error;

// ── Precompiled pipeline presets ──────────────────────────────────────────────

/// Canonicalize text for security-sensitive *comparison* (homoglyph / bidi /
/// zero-width / control neutralization).
///
/// Pipeline: NFKC → strip bidi/format → strip invisible classes (#413) →
/// strip control → strip zero-width → collapse whitespace → cap combining marks
/// (anti-zalgo, #429) → NFC → confusables → NFC. (The confusable fold is
/// sandwiched between two NFC passes
/// so TR39 skeletoning is normalization-stable and the preset is idempotent —
/// #416.) Fallible only through the confusables stage, whose target script is
/// fixed internally, so in practice this never errors; the [`Result`] keeps the
/// surface uniform with the other key/clean presets.
///
/// The name describes the mechanism (Unicode canonicalization for matching), not
/// a safety guarantee: this is **not** an output sanitizer — encode at the sink.
#[inline]
pub fn canonicalize(text: &str) -> Result<Cow<'_, str>, Error> {
    crate::presets::canonicalize(text).map_err(Error::from)
}

/// Deprecated alias for [`canonicalize`]. Renamed in 0.11 because the `*_clean`
/// name overpromised safety (see `THREAT_MODEL.md`); removed in 1.0.
///
/// # Errors
/// Propagates [`canonicalize`]'s error.
#[deprecated(since = "0.11.0", note = "renamed to `canonicalize`; removed in 1.0")]
#[inline]
pub fn security_clean(text: &str) -> Result<Cow<'_, str>, Error> {
    canonicalize(text)
}

/// ML/NLP text normalization: NFKC → emoji→text → transliterate → strip accents →
/// case fold → collapse whitespace.
///
/// `lang` selects the transliteration table (`None` skips transliteration).
/// `emoji_style` is `"cldr"` (expand emoji to CLDR short names) or `"none"`
/// (leave emoji as-is). Fails ([`ErrorKind::InvalidArgument`](crate::ErrorKind))
/// on an unknown `lang` or an unsupported `emoji_style`.
#[inline]
pub fn ml_normalize<'a>(
    text: &'a str,
    lang: Option<&str>,
    emoji_style: &str,
) -> Result<Cow<'a, str>, Error> {
    crate::presets::ml_normalize(text, lang, emoji_style).map_err(Error::from)
}

/// Library catalog deduplication key: NFKC → strip bidi → case fold →
/// transliterate → confusables → strip accents → case fold → collapse whitespace.
///
/// `strict_iso9` selects the ISO 9:1995 Cyrillic scheme. Fails
/// ([`ErrorKind::InvalidArgument`](crate::ErrorKind)) on an unknown `lang`.
#[inline]
pub fn catalog_key<'a>(
    text: &'a str,
    lang: Option<&str>,
    strict_iso9: bool,
) -> Result<Cow<'a, str>, Error> {
    crate::presets::catalog_key(text, lang, strict_iso9).map_err(Error::from)
}

/// Case/accent/script-insensitive search lookup key (like [`catalog_key`] without
/// confusable folding). Fails ([`ErrorKind::InvalidArgument`](crate::ErrorKind))
/// on an unknown `lang`.
#[inline]
pub fn search_key<'a>(text: &'a str, lang: Option<&str>) -> Result<Cow<'a, str>, Error> {
    crate::presets::search_key(text, lang).map_err(Error::from)
}

/// Collation sort key (like [`search_key`] but preserves base accented characters
/// for correct ordering). Fails ([`ErrorKind::InvalidArgument`](crate::ErrorKind))
/// on an unknown `lang`.
#[inline]
pub fn sort_key<'a>(text: &'a str, lang: Option<&str>) -> Result<Cow<'a, str>, Error> {
    crate::presets::sort_key(text, lang).map_err(Error::from)
}

/// Strip bidi/format and other invisible-injection vectors from rendered user
/// content: strip bidi/format → strip invisibles (rendering policy) → collapse
/// whitespace (also stripping control + zero-width). Infallible.
///
/// Visual hygiene only — **not** markup-safe; still escape at the output layer.
#[must_use]
#[inline]
pub fn strip_format(text: &str) -> Cow<'_, str> {
    crate::presets::strip_format(text)
}

/// Deprecated alias for [`strip_format`]. Renamed in 0.11 because `display_clean`
/// implied markup-safety it does not provide (see `THREAT_MODEL.md`); removed in 1.0.
#[deprecated(since = "0.11.0", note = "renamed to `strip_format`; removed in 1.0")]
#[must_use]
#[inline]
pub fn display_clean(text: &str) -> Cow<'_, str> {
    strip_format(text)
}

/// Strip bidirectional override and formatting characters (UAX #9 §3.3.2 plus the
/// soft hyphen and deprecated/interlinear format controls). A composable primitive
/// shared by the security/key presets. Infallible.
#[must_use]
pub fn strip_bidi(text: &str) -> String {
    crate::presets::strip_bidi(text)
}

/// Normalize user-submitted input — Unicode hygiene that **preserves the original
/// script** (no transliteration): NFKC → strip bidi/format → strip zero-width →
/// strip control → strip invisible classes (#413) → cap combining marks
/// (anti-zalgo) → confusables → collapse whitespace → NFC. (The invisibles are
/// stripped before the zalgo cap so they cannot split a mark run, and the
/// terminal NFC recomposes any base+mark left adjacent — keeping the preset
/// idempotent, #121/#416.)
///
/// Not an output sanitizer (no HTML/JS/SQL escaping). Fallible only through the
/// fixed-target confusables stage; the [`Result`] keeps the surface uniform.
#[inline]
pub fn canonicalize_strict(text: &str) -> Result<Cow<'_, str>, Error> {
    crate::presets::canonicalize_strict(text).map_err(Error::from)
}

/// Deprecated alias for [`canonicalize_strict`]. Renamed in 0.11 (the old name
/// conceded itself a relic in `THREAT_MODEL.md`); removed in 1.0.
///
/// # Errors
/// Propagates [`canonicalize_strict`]'s error.
#[deprecated(
    since = "0.11.0",
    note = "renamed to `canonicalize_strict`; removed in 1.0"
)]
#[inline]
pub fn normalize_user_input(text: &str) -> Result<Cow<'_, str>, Error> {
    canonicalize_strict(text)
}

/// Maximum-strength deobfuscation: NFKC → strip all combining marks → strip bidi →
/// strip zero-width → demojize → confusables → strip accents → collapse
/// whitespace. Preserves case; does not transliterate.
///
/// Fallible only through the fixed-target confusables stage; the [`Result`] keeps
/// the surface uniform.
#[inline]
pub fn strip_obfuscation(text: &str) -> Result<Cow<'_, str>, Error> {
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
#[must_use]
pub fn list_profiles() -> Vec<String> {
    crate::pipeline::profile_names()
}

/// A reusable, read-only handle to a named policy-profile pipeline (#404).
///
/// Built with [`get_pipeline`] from one of the profiles in [`list_profiles`],
/// then applied to any number of inputs via [`Pipeline::process`]. This is the
/// pure crates.io counterpart to the binding-only stateful builder
/// (`_TextPipeline`): a precompiled, immutable handle the Node/Ruby bindings can
/// wrap as a reusable object (mirroring the `Lexicon` handle), not a mutable
/// pipeline builder.
///
/// ```
/// use disarm::api::get_pipeline;
/// let pipe = get_pipeline("search_index").unwrap();
/// assert_eq!(pipe.process("Café").unwrap(), "cafe");
/// ```
#[derive(Debug, Clone)]
pub struct Pipeline {
    inner: crate::pipeline::Pipeline,
}

impl Pipeline {
    /// Run the named pipeline over `text`.
    ///
    /// # Errors
    /// Propagates the pipeline's error (a profile's steps are validated at
    /// [`get_pipeline`] time, so in practice `process` does not error; the
    /// [`Result`] keeps the surface uniform).
    pub fn process(&self, text: &str) -> Result<String, Error> {
        self.inner.process(text).map_err(Error::from)
    }
}

/// Build the reusable [`Pipeline`] handle for a named policy profile (#404).
///
/// `profile` is one of the names returned by [`list_profiles`]. Fails
/// ([`ErrorKind::InvalidArgument`](crate::ErrorKind)) on an unknown profile,
/// naming the offending value and the available profiles.
///
/// # Errors
/// Returns an [`ErrorKind::InvalidArgument`](crate::ErrorKind) error if
/// `profile` is not a known profile name.
pub fn get_pipeline(profile: &str) -> Result<Pipeline, Error> {
    match crate::pipeline::get_pipeline(profile).map_err(Error::from)? {
        Some(inner) => Ok(Pipeline { inner }),
        None => Err(Error::from(crate::ErrorRepr::UnknownProfile {
            got: profile.to_owned(),
            available: crate::pipeline::profile_names().join(", "),
        })),
    }
}
