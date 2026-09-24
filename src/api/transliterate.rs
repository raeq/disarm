//! Layer 2 (part of [`crate::api`]) — transliteration (the [`Transliterate`]
//! builder, [`Scheme`], [`OnUnknown`]) and registration of the process-global
//! transliteration tables.

use crate::Error;
use std::borrow::Cow;
use std::collections::HashMap;

// ── Transliteration ──────────────────────────────────────────────────────────

/// Remove diacritical marks while preserving base characters (NFD → strip
/// combining marks → NFC). For example `"café"` → `"cafe"`.
///
/// **Destructive for Indic scripts, and not in the way "accent" suggests** (#624).
/// A Latin acute and a Devanagari vowel sign are both general category `Mn`, so
/// both go — but in Latin an `Mn` is decoration and in an Indic script it carries
/// the vowel. `José` → `Jose` stays readable; `বাংলা` → `বল` is not a word. Scope
/// this to identifiers, filenames and search keys rather than to body text in
/// Devanagari, Bengali, Tamil, Telugu, Kannada, Malayalam, Gujarati or Khmer.
///
/// Returns `Cow::Borrowed` when there are no accents to strip (zero allocation).
#[must_use]
pub fn strip_accents(text: &str) -> Cow<'_, str> {
    crate::transliterate::strip_accents_cow(text)
}

/// True if every character in `text` is ASCII (U+0000–U+007F).
#[must_use]
pub fn is_ascii(text: &str) -> bool {
    text.is_ascii()
}

/// The language codes available for transliteration (built-in plus any
/// registered at runtime).
#[must_use]
pub fn list_langs() -> Vec<String> {
    crate::tables::list_langs()
}

/// Cyrillic romanization scheme for [`Transliterate`].
///
/// The schemes are mutually exclusive *by construction* — you can't be in two at
/// once, so the old representable-but-invalid `strict_iso9 && gost7034` state
/// simply can't be expressed.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Default)]
#[non_exhaustive]
pub enum Scheme {
    /// The default multi-script romanization tables.
    #[default]
    Default,
    /// ISO 9:1995 strict Cyrillic romanization (a reversible 1:1 mapping).
    StrictIso9,
    /// GOST 7.034 Cyrillic romanization.
    GostR7034,
}

impl Scheme {
    /// The engine's `(strict_iso9, gost7034)` flag pair.
    fn flags(self) -> (bool, bool) {
        match self {
            Scheme::Default => (false, false),
            Scheme::StrictIso9 => (true, false),
            Scheme::GostR7034 => (false, true),
        }
    }

    /// The canonical lowercase token (`"default"` / `"strict_iso9"` / `"gost7034"`).
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Scheme::Default => "default",
            Scheme::StrictIso9 => "strict_iso9",
            Scheme::GostR7034 => "gost7034",
        }
    }
}

impl std::fmt::Display for Scheme {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for Scheme {
    type Err = Error;

    /// Parse `"default"` / `"strict_iso9"` / `"gost7034"`.
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "default" => Ok(Self::Default),
            "strict_iso9" => Ok(Self::StrictIso9),
            "gost7034" => Ok(Self::GostR7034),
            _ => Err(Error::from(crate::ErrorRepr::InvalidScheme {
                got: s.to_owned(),
            })),
        }
    }
}

/// What [`Transliterate`] does with a character that has no romanization.
///
/// The replacement string lives in [`OnUnknown::Replace`] — exactly where it is
/// meaningful — so it can't be silently ignored by pairing it with `Ignore`.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub enum OnUnknown {
    /// Substitute this string for each untranslatable character (e.g. `"[?]"`).
    Replace(String),
    /// Drop untranslatable characters.
    Ignore,
    /// Pass untranslatable characters through unchanged.
    Preserve,
}

impl Default for OnUnknown {
    /// `Replace("[?]")` — the documented default sentinel.
    fn default() -> Self {
        OnUnknown::Replace("[?]".to_owned())
    }
}

impl OnUnknown {
    /// The engine's `(ErrorMode, replacement)` pair.
    pub(crate) fn parts(&self) -> (crate::ErrorMode, &str) {
        match self {
            OnUnknown::Replace(s) => (crate::ErrorMode::Replace, s.as_str()),
            OnUnknown::Ignore => (crate::ErrorMode::Ignore, ""),
            OnUnknown::Preserve => (crate::ErrorMode::Preserve, ""),
        }
    }
}

/// Builder for Unicode → ASCII transliteration.
///
/// Replaces a positional 7-argument function: the mutually-exclusive Cyrillic
/// schemes collapse into [`Scheme`], the replacement string moves inside
/// [`OnUnknown::Replace`], and adding a future knob no longer breaks call sites.
///
/// ```
/// use disarm::api::{Transliterate, Scheme, OnUnknown};
/// let s = Transliterate::new()
///     .scheme(Scheme::StrictIso9)
///     .on_unknown(OnUnknown::Replace("?".into()))
///     .run("Москва");
/// assert!(s.is_ascii());
/// ```
#[derive(Debug, Clone, Default)]
pub struct Transliterate {
    lang: Option<String>,
    scheme: Scheme,
    // `None` is the default `Replace("[?]")` policy without eagerly heap-allocating
    // the sentinel — so `transliterate(ascii)` stays allocation-free (#352 review).
    on_unknown: Option<OnUnknown>,
    tones: bool,
}

impl Transliterate {
    /// A new builder with defaults: default tables, `OnUnknown::Replace("[?]")`,
    /// tones off. The default policy is stored lazily, so building and running on
    /// pure-ASCII input allocates nothing.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Select a language-specific romanization table. `"auto"` enables script
    /// detection; the default (unset) uses the multi-script tables.
    ///
    /// The code is checked when the builder runs, not here: [`try_run`](Self::try_run)
    /// and [`try_find_untranslatable`](Self::try_find_untranslatable) reject a code
    /// [`validate_lang`] does not accept, and the infallible [`run`](Self::run) falls
    /// back to the default tables.
    #[must_use]
    pub fn lang(mut self, lang: impl Into<String>) -> Self {
        self.lang = Some(lang.into());
        self
    }

    /// Select the Cyrillic romanization scheme (default / ISO 9 / GOST 7.034).
    #[must_use]
    pub fn scheme(mut self, scheme: Scheme) -> Self {
        self.scheme = scheme;
        self
    }

    /// Set the policy for characters with no romanization.
    #[must_use]
    pub fn on_unknown(mut self, on_unknown: OnUnknown) -> Self {
        self.on_unknown = Some(on_unknown);
        self
    }

    /// Keep tone marks (pinyin) instead of dropping them.
    #[must_use]
    pub fn tones(mut self, tones: bool) -> Self {
        self.tones = tones;
        self
    }

    /// Transliterate `text` with the tables alone. Returns `Cow::Borrowed` for
    /// pure-ASCII input (zero allocation), `Cow::Owned` otherwise. Infallible, and so
    /// **lenient** in two ways [`try_run`](Self::try_run) is not: an unknown
    /// [`lang`](Self::lang) falls back to the default tables instead of being rejected,
    /// and the replacements registered with [`register_replacements`] are not applied.
    /// Prefer `try_run`; it is what every binding's `transliterate` calls.
    #[must_use]
    pub fn run<'a>(&self, text: &'a str) -> Cow<'a, str> {
        // `None` = the default `Replace("[?]")`, supplied as a borrowed `'static`
        // literal so the default path never allocates the sentinel.
        let (error_mode, replacement) = match &self.on_unknown {
            None => (crate::ErrorMode::Replace, "[?]"),
            Some(on_unknown) => on_unknown.parts(),
        };
        let (strict_iso9, gost7034) = self.scheme.flags();
        crate::transliterate::transliterate_impl(
            text,
            self.lang.as_deref(),
            error_mode,
            replacement,
            strict_iso9,
            gost7034,
            self.tones,
        )
    }

    /// Transliterate `text` the way every binding does: reject an unknown
    /// [`lang`](Self::lang), apply the replacements registered with
    /// [`register_replacements`], then run the tables.
    ///
    /// Returns `Cow::Borrowed` only when nothing changed, so a borrowed result is the
    /// input itself.
    ///
    /// # Errors
    ///
    /// [`ErrorKind::InvalidArgument`](crate::ErrorKind::InvalidArgument) when `lang`
    /// names no language [`validate_lang`] accepts (the rule Python has enforced since
    /// #68, now in the core so every binding shares it), and
    /// [`ErrorKind::ResourceLimit`](crate::ErrorKind::ResourceLimit) when the registered
    /// replacements expand the text past their output cap.
    ///
    /// ```
    /// use disarm::api::Transliterate;
    /// use disarm::ErrorKind;
    ///
    /// let kyiv = "\u{41A}\u{438}\u{457}\u{432}";
    /// let err = Transliterate::new().lang("UK").try_run(kyiv).unwrap_err();
    /// assert_eq!(err.kind(), ErrorKind::InvalidArgument);
    /// assert_eq!(Transliterate::new().lang("uk").try_run(kyiv).unwrap(), "Kyiv");
    /// ```
    pub fn try_run<'a>(&self, text: &'a str) -> Result<Cow<'a, str>, Error> {
        if let Some(lang) = &self.lang {
            validate_lang(lang)?;
        }
        let (error_mode, replacement) = match &self.on_unknown {
            None => (crate::ErrorMode::Replace, "[?]"),
            Some(on_unknown) => on_unknown.parts(),
        };
        let (strict_iso9, gost7034) = self.scheme.flags();
        crate::transliterate::transliterate_after_replacements(
            text,
            self.lang.as_deref(),
            Some(error_mode),
            replacement,
            strict_iso9,
            gost7034,
            self.tones,
        )
        .map_err(Error::from)
    }

    /// Every character in `text` that has no romanization, in order of
    /// appearance — exactly the set [`run`](Self::run) would
    /// replace/ignore/preserve. (Independent of [`on_unknown`](Self::on_unknown),
    /// which only decides what to *do* with them.) Lenient as `run` is: see
    /// [`try_find_untranslatable`](Self::try_find_untranslatable).
    #[must_use]
    pub fn find_untranslatable(&self, text: &str) -> Vec<Untranslatable> {
        let (strict_iso9, gost7034) = self.scheme.flags();
        crate::transliterate::find_untranslatable_impl(
            text,
            self.lang.as_deref(),
            strict_iso9,
            gost7034,
            self.tones,
        )
        .into_iter()
        .map(|(ch, offset)| Untranslatable { ch, offset })
        .collect()
    }

    /// [`find_untranslatable`](Self::find_untranslatable) as [`try_run`](Self::try_run)
    /// sees the text: an unknown [`lang`](Self::lang) is rejected, and the registered
    /// replacements are applied first, so offsets are relative to the post-replacement
    /// text (identical to the input when none are registered).
    ///
    /// # Errors
    ///
    /// As [`try_run`](Self::try_run).
    pub fn try_find_untranslatable(&self, text: &str) -> Result<Vec<Untranslatable>, Error> {
        if let Some(lang) = &self.lang {
            validate_lang(lang)?;
        }
        let (strict_iso9, gost7034) = self.scheme.flags();
        Ok(
            crate::transliterate::find_untranslatable_after_replacements(
                text,
                self.lang.as_deref(),
                strict_iso9,
                gost7034,
                self.tones,
            )?
            .into_iter()
            .map(|(ch, offset)| Untranslatable { ch, offset })
            .collect(),
        )
    }
}

/// Check a transliteration language code: a built-in or registered code, one of the
/// accepted BCP-47 aliases (`nb`, `nn`, `da`), or `"auto"`.
///
/// Every `lang` argument in the API goes through this rule: the key builders,
/// [`sanitize_filename`](crate::api::sanitize_filename),
/// [`Transliterate::try_run`] and [`try_slugify`](crate::api::try_slugify). An unknown
/// code used to fall back to the default tables silently in the Rust API and in every
/// binding but Python (#68), so a typo (`"UK"` for `"uk"`) produced quietly wrong
/// output (`formal/bindings`, B2).
///
/// # Errors
///
/// [`ErrorKind::InvalidArgument`](crate::ErrorKind::InvalidArgument), with the valid
/// codes and the closest one in the message.
///
/// ```
/// use disarm::api::validate_lang;
/// assert!(validate_lang("uk").is_ok());
/// assert!(validate_lang("auto").is_ok());
/// assert!(validate_lang("UK").unwrap_err().to_string().contains("did you mean"));
/// ```
pub fn validate_lang(lang: &str) -> Result<(), Error> {
    crate::transliterate::validate_lang(Some(lang)).map_err(Error::from)
}

/// A character with no transliteration, located in the input — an element of
/// [`Transliterate::find_untranslatable`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[non_exhaustive]
pub struct Untranslatable {
    /// The untranslatable character.
    ///
    /// The input's own character at [`offset`](Self::offset). A base followed by combining
    /// marks is looked up as the character they compose to, so a decomposed spelling is
    /// judged as the precomposed one is; when that is what is reported, `ch` is the base as
    /// written, and the report covers the cluster that starts there (#1040).
    pub ch: char,
    /// Its byte offset in the input string.
    pub offset: usize,
}

/// Transliterate `text` to ASCII with every default (default tables,
/// `Replace("[?]")`, no tones). Shorthand for `Transliterate::new().run(text)`, and
/// like it does not apply the replacements registered with [`register_replacements`];
/// `Transliterate::new().try_run(text)` does. Use the [`Transliterate`] builder to
/// choose a [`Scheme`] or [`OnUnknown`].
#[must_use]
pub fn transliterate(text: &str) -> Cow<'_, str> {
    Transliterate::new().run(text)
}

// ── Registration of process-global tables ────────────────────────────────────
//
// These mutate the process-global transliteration tables every caller shares, so
// they are the *guarded* entry point: each enforces the registration cap and the
// one-way seal latch (`seal_registrations`) before delegating to the internal
// `crate::tables` mutators (which are themselves `pub(crate)` and must not be
// reached directly). Configure at startup, then `seal_registrations()` to freeze.

/// Register or override a transliteration mapping for a language `code`.
///
/// `mappings` is single-character keys → ASCII (best-effort) replacements. Fails
/// ([`ErrorKind::InvalidArgument`](crate::ErrorKind::InvalidArgument)) if a key is not exactly one
/// character, ([`ErrorKind::ResourceLimit`](crate::ErrorKind::ResourceLimit)) past the
/// registered-language cap, or ([`ErrorKind::Unsupported`](crate::ErrorKind::Unsupported)) once
/// [`seal_registrations`] has been called. The cap holds under concurrent
/// registration: two calls racing for the last slot cannot both take it.
pub fn register_lang(code: &str, mappings: HashMap<String, String>) -> Result<(), Error> {
    crate::transliterate::register_lang(code, mappings).map_err(Error::from)
}

/// Register global pre-transliteration replacements, applied before the tables by
/// [`Transliterate::try_run`] and [`Transliterate::try_find_untranslatable`] (and by
/// Python's `transliterate`, which shares that code). The infallible
/// [`transliterate`] and [`Transliterate::run`] run the tables alone.
///
/// Fails ([`ErrorKind::ResourceLimit`](crate::ErrorKind::ResourceLimit)) past the replacement cap
/// or ([`ErrorKind::Unsupported`](crate::ErrorKind::Unsupported)) once sealed.
pub fn register_replacements(replacements: HashMap<String, String>) -> Result<(), Error> {
    crate::transliterate::register_replacements(replacements).map_err(Error::from)
}

/// Remove a single global replacement by `key`. Returns whether it was present.
/// Fails ([`ErrorKind::Unsupported`](crate::ErrorKind::Unsupported)) once sealed.
pub fn remove_replacement(key: &str) -> Result<bool, Error> {
    crate::transliterate::remove_replacement(key).map_err(Error::from)
}

/// Clear all global replacements. Fails ([`ErrorKind::Unsupported`](crate::ErrorKind::Unsupported))
/// once sealed.
pub fn clear_replacements() -> Result<(), Error> {
    crate::transliterate::clear_replacements().map_err(Error::from)
}

/// Freeze the registration tables (langs + replacements). One-way latch: after
/// this, every `register_*`/`remove_*`/`clear_*` call fails, so an application can
/// configure canonicalization at startup and prevent later code from mutating the
/// process-global state every caller shares (#64). Idempotent.
///
/// A registration running on another thread when this is called either finishes
/// first or fails: none lands after this returns.
pub fn seal_registrations() {
    crate::tables::seal_registrations();
}

/// Whether [`seal_registrations`] has been called.
#[must_use]
pub fn registrations_sealed() -> bool {
    crate::tables::registrations_sealed()
}
