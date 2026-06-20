//! Layer 2 (part of [`crate::api`]) — cross-script confusable folding, script /
//! reverse / hostname analysis, and filename / encoding / log-injection safety.

use crate::Error;
use std::borrow::Cow;

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
    /// The canonical string token for this value (the inverse of its `FromStr`,
    /// and what `Display` prints).
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            TargetScript::Latin => "latin",
            TargetScript::Cyrillic => "cyrillic",
        }
    }
}

impl std::fmt::Display for TargetScript {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for TargetScript {
    type Err = Error;

    /// Parse `"latin"` / `"cyrillic"`.
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "latin" => Ok(Self::Latin),
            "cyrillic" => Ok(Self::Cyrillic),
            _ => Err(Error::from(crate::ErrorRepr::InvalidTargetScript {
                got: s.to_owned(),
            })),
        }
    }
}

/// Replace Unicode confusable homoglyphs with their `target`-script prototypes
/// (TR39). Characters with no mapping pass through unchanged.
///
/// The input is canonically recomposed (NFC) before folding (#475, in the Layer-1
/// core), so the fold is invariant to the input's normal form — a decomposed
/// homoglyph (`і` + combining diaeresis) folds the same as its composed `ї`, instead
/// of leaving the mark and letting an attacker evade the fold by decomposing.
///
/// Returns `Cow::Borrowed` when the input is already NFC and nothing folds (zero
/// allocation), `Cow::Owned` otherwise. Infallible: a [`TargetScript`] is always a
/// supported script.
#[must_use]
pub fn normalize_confusables(text: &str, target: TargetScript) -> Cow<'_, str> {
    // The only error path of the Layer-1 fn is an unsupported target *string*;
    // a `TargetScript` value can never produce one, so this is unreachable.
    crate::confusables::normalize_confusables_cow(text, target.as_str())
        .expect("TargetScript always maps to a supported target script")
}

/// True if `text` contains any character confusable with a `target`-script
/// character (TR39).
///
/// Detection runs on the canonically recomposed (NFC) form (#475, in the Layer-1
/// core), so it cannot be evaded by decomposing the homoglyph (which would otherwise
/// flip a composed `ç` from detected to not-detected). Infallible: a [`TargetScript`]
/// is always a supported script.
#[must_use]
pub fn is_confusable(text: &str, target: TargetScript) -> bool {
    crate::confusables::is_confusable(text, target.as_str())
        .expect("TargetScript always maps to a supported target script")
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
    /// The canonical language-code token (the inverse of its `FromStr`, and what
    /// `Display` prints): `"el"` / `"ru"` / `"uk"`.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            ReverseLang::Greek => "el",
            ReverseLang::Russian => "ru",
            ReverseLang::Ukrainian => "uk",
        }
    }
}

impl std::fmt::Display for ReverseLang {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for ReverseLang {
    type Err = Error;

    /// Parse `"el"` / `"ru"` / `"uk"`.
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "el" => Ok(Self::Greek),
            "ru" => Ok(Self::Russian),
            "uk" => Ok(Self::Ukrainian),
            _ => Err(Error::from(crate::ErrorRepr::InvalidReverseLang {
                got: s.to_owned(),
            })),
        }
    }
}

/// Convert romanized Latin `text` back to its native script with greedy
/// longest-match scanning (digraphs/trigraphs like `shch` → щ); unmatched
/// characters pass through.
///
/// Infallible: a [`ReverseLang`] always has a reverse table.
#[must_use]
pub fn reverse_transliterate(text: &str, lang: ReverseLang) -> String {
    crate::reverse::reverse_transliterate_impl(text, lang.as_str())
}

/// The languages that support [`reverse_transliterate`], as lowercase codes.
#[must_use]
pub fn reverse_langs() -> Vec<String> {
    crate::reverse::reverse_langs()
}

// ── Script detection ─────────────────────────────────────────────────────────

/// Unicode scripts present in `text`, in order of first appearance (Common /
/// Inherited excluded). Names are stable UCD script identifiers (e.g. `"Latin"`).
#[must_use]
pub fn detect_scripts(text: &str) -> Vec<&'static str> {
    crate::scripts::detect_scripts(text)
}

/// True if `text` mixes characters from more than one script (excluding Common /
/// Inherited) — a homoglyph-spoofing signal.
#[must_use]
pub fn is_mixed_script(text: &str) -> bool {
    crate::scripts::is_mixed_script(text)
}

/// True if `text` contains both strong left-to-right and strong right-to-left
/// characters — the precondition for Unicode Bidi display-reordering (UAX #9),
/// and the structural signal behind "BiDi Swap"-style spoofs.
///
/// Unlike a bidi-override (`U+202x`) check, this fires on the *real letters*
/// (e.g. an LTR brand label beside an RTL domain, `varonis.com.ו.קום`), where no
/// override is present and override-stripping is a no-op. Latin/Cyrillic/Greek/
/// CJK/… are left-to-right; Hebrew/Arabic/Syriac/Thaana/N'Ko are right-to-left;
/// digits, punctuation and combining marks are neutral and never create a
/// conflict on their own. A `false` result is **not** a safety guarantee.
#[must_use]
pub fn has_bidi_conflict(text: &str) -> bool {
    crate::scripts::has_bidi_conflict(text)
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
#[must_use]
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
    /// The overall verdict — this is what [`is_suspicious_hostname`] keys on.
    /// **`false` is not a safety guarantee** (see the function docs); weigh the
    /// granular fields below against your own policy.
    pub suspicious: bool,
    /// Scripts detected across all labels, in order of first appearance
    /// (Common / Inherited excluded), as stable UCD script identifiers.
    pub scripts: Vec<String>,
    /// Whether any single label mixes characters from more than one script.
    pub mixed_script: bool,
    /// Whether any label contains a character confusable with a Latin one.
    pub has_confusables: bool,
    /// Whether the decoded hostname mixes strong left-to-right and strong
    /// right-to-left characters — the precondition for Bidi display-reordering
    /// ("BiDi Swap"). This is folded into [`suspicious`](Self::suspicious).
    pub bidi_conflict: bool,
    /// Whether the labels resolve to more than one distinct script (Common /
    /// Inherited excluded). Broader and noisier than [`bidi_conflict`](Self::bidi_conflict)
    /// — it fires on benign IDN-ccTLD patterns like `google.рф` — so it is
    /// **not** folded into [`suspicious`](Self::suspicious); exposed for policy.
    pub cross_label_script: bool,
    /// Per-label resolved scripts, left to right (Common / Inherited excluded),
    /// so a caller can apply position-aware policy without re-parsing.
    pub label_scripts: Vec<Vec<String>>,
    /// The Latin-normalized (canonical) form of the hostname.
    pub canonical: String,
}

/// Analyze a hostname for Unicode homoglyph spoofing, returning a
/// [`HostnameAnalysis`] whose [`suspicious`](HostnameAnalysis::suspicious) field
/// is the overall verdict (alongside the granular `scripts` / `mixed_script` /
/// `has_confusables` / `canonical` findings).
///
/// `xn--` (ACE) labels are decoded to their Unicode form via UTS#46 before
/// analysis (#63); a malformed ACE label fails closed (suspicious). A hostname
/// is flagged when any single label is mixed-script (conservative, #254), when
/// any label contains a Latin-confusable character, when the decoded hostname
/// mixes strong LTR and strong RTL characters (`bidi_conflict`, the "BiDi Swap"
/// precondition, #412), or when an ACE label fails to decode.
///
/// Infallible: the analysis runs against the fixed `"latin"` target script,
/// which is always supported.
///
/// **A `false` (not-suspicious) result is NOT a safety guarantee.** It means
/// only that no mixed-script label and no confusable *from the bundled TR39
/// table* was found. Base allow/deny decisions on the granular `scripts` /
/// `mixed_script` / `has_confusables` fields plus your own policy — a detector
/// can attest the *presence* of a problem, never the *absence* of all problems.
#[must_use]
pub fn is_suspicious_hostname(hostname: &str) -> HostnameAnalysis {
    let (_, core) = crate::hostname::is_suspicious_hostname(hostname);
    HostnameAnalysis {
        suspicious: core.suspicious,
        scripts: core.scripts,
        mixed_script: core.mixed_script,
        has_confusables: core.has_confusables,
        bidi_conflict: core.bidi_conflict,
        cross_label_script: core.cross_label_script,
        label_scripts: core.label_scripts,
        canonical: core.canonical,
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
    /// The canonical token (the inverse of its `FromStr`, and what `Display`
    /// prints): `"universal"` / `"windows"` / `"posix"`.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Platform::Universal => "universal",
            Platform::Windows => "windows",
            Platform::Posix => "posix",
        }
    }
}

impl std::fmt::Display for Platform {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for Platform {
    type Err = Error;

    /// Parse `"universal"` / `"windows"` / `"posix"`.
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "universal" => Ok(Self::Universal),
            "windows" => Ok(Self::Windows),
            "posix" => Ok(Self::Posix),
            _ => Err(Error::from(crate::ErrorRepr::InvalidPlatform {
                got: s.to_owned(),
            })),
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

/// The result of [`detect_encoding`]: a detected encoding label and the
/// detector's confidence.
#[derive(Debug, Clone, PartialEq)]
#[non_exhaustive]
pub struct EncodingDetection {
    /// The detected encoding's WHATWG label (e.g. `"UTF-8"`, `"windows-1251"`).
    pub label: String,
    /// Detector confidence in `0.0..=1.0` (probabilistic — prefer explicit
    /// metadata for critical pipelines).
    pub confidence: f64,
}

/// Detect the probable character encoding of `bytes` (chardetng, Firefox's
/// detector). Detection is probabilistic — prefer explicit encoding metadata for
/// critical pipelines.
#[must_use]
pub fn detect_encoding(bytes: &[u8]) -> EncodingDetection {
    let (label, confidence) = crate::encoding::detect_encoding_impl(bytes);
    EncodingDetection { label, confidence }
}

/// The result of [`decode_to_utf8`]: the decoded text and whether the decode was
/// lossy.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct DecodedText {
    /// The decoded UTF-8 text.
    pub text: String,
    /// Whether U+FFFD replacement characters were inserted for undecodable bytes
    /// (always `false` after a successful `strict` decode).
    pub had_errors: bool,
}

/// Decode `bytes` to UTF-8. `encoding = None` auto-detects (rejecting a guess
/// below `min_confidence`, in `0.0..=1.0`). In `strict` mode a lossy decode is an
/// error instead of setting [`DecodedText::had_errors`].
///
/// Fails ([`ErrorKind`](crate::ErrorKind)) on an unknown, unsupported, or
/// low-confidence encoding, an out-of-range `min_confidence`, or (strict) a
/// lossy decode.
pub fn decode_to_utf8(
    bytes: &[u8],
    encoding: Option<&str>,
    min_confidence: f64,
    strict: bool,
) -> Result<DecodedText, Error> {
    crate::encoding::decode_to_utf8_impl(bytes, encoding, min_confidence, strict)
        .map(|(text, had_errors)| DecodedText { text, had_errors })
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

// ── Anomaly detection ───────────────────────────────────────────────────────

pub use crate::anomalies::{
    has_anomalies, inspect_anomalies, lexicon, AnomalyKind, AnomalyReport, Finding,
};
