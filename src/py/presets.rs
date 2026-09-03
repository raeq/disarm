//! PyO3 shims for `crate::presets` (Layer-1) — the precompiled-pipeline presets.
//!
//! Each shim is a thin wrapper over a Layer-1 preset core. The cores compose
//! other modules' transforms and live in `src/presets.rs` (pyo3-free,
//! `pub(crate)`); these shims validate at the boundary and convert the native
//! `ErrorRepr` to a Python exception via `?`. See #38.

use pyo3::prelude::*;

/// Security-focused text canonicalization.
///
/// Pipeline: NFKC → strip bidi/format → strip invisible classes (#413) →
/// strip_control → strip_zero_width → collapse_whitespace → cap combining marks
/// (anti-zalgo, #429) → NFC → confusables → NFC (confusables sandwiched between
/// NFC passes for idempotency, #416).
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _canonicalize(text: &str) -> PyResult<String> {
    Ok(crate::presets::canonicalize(text)?.into_owned())
}

/// `skeleton_key(text, *, digit_policy="numeric") -> str`
///
/// The TR39 identifier skeleton plus the `I ≡ l ≡ 1` / `O ≡ 0` prototype classes,
/// applied on cased text (#650). A spoof key, not for display.
#[pyfunction]
#[pyo3(signature = (text, *, digit_policy="numeric"))]
pub fn _skeleton_key(text: &str, digit_policy: &str) -> PyResult<String> {
    Ok(crate::presets::skeleton_key(text, digit_policy)?.into_owned())
}

/// `is_canonical(text, *, preset="canonicalize") -> bool`
///
/// The verification-path counterpart to the generation-path presets (#730). `preset`
/// names either a preset or a policy profile. Returns without building the normalized
/// string, so nothing crosses this boundary but the boolean.
#[pyfunction]
#[pyo3(signature = (text, *, preset="canonicalize"))]
pub fn _is_canonical(text: &str, preset: &str) -> PyResult<bool> {
    Ok(crate::presets::is_canonical(text, preset)?)
}

/// ML/NLP text normalization pipeline.
///
/// Pipeline: NFKC → emoji→text → transliterate → strip_accents → [fold_case] →
/// collapse_whitespace. `fold_case=False` drops the fold step only (#559).
#[pyfunction]
#[pyo3(signature = (text, *, lang=None, emoji_style="cldr", fold_case=true))]
pub fn _ml_normalize(
    text: &str,
    lang: Option<&str>,
    emoji_style: &str,
    fold_case: bool,
) -> PyResult<String> {
    Ok(crate::presets::ml_normalize(text, lang, emoji_style, fold_case)?.into_owned())
}

/// Library catalog key generation pipeline.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None, strict_iso9=false))]
pub fn _catalog_key(text: &str, lang: Option<&str>, strict_iso9: bool) -> PyResult<String> {
    Ok(crate::presets::catalog_key(text, lang, strict_iso9)?.into_owned())
}

/// Search index key generation pipeline.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None))]
pub fn _search_key(text: &str, lang: Option<&str>) -> PyResult<String> {
    Ok(crate::presets::search_key(text, lang)?.into_owned())
}

/// Sort key generation pipeline.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None))]
pub fn _sort_key(text: &str, lang: Option<&str>) -> PyResult<String> {
    Ok(crate::presets::sort_key(text, lang)?.into_owned())
}

/// Strip bidi/format and invisible-injection vectors from rendered content.
///
/// Infallible: strip bidi/format → strip invisibles → collapse_whitespace.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _strip_format(text: &str) -> String {
    crate::presets::strip_format(text).into_owned()
}

/// Strip bidirectional override and formatting characters (UAX #9).
///
/// Removes: soft hyphen (U+00AD), Arabic Letter Mark (U+061C),
/// LRM/RLM (U+200E/F), bidi embeddings/overrides (U+202A–U+202E),
/// bidi isolates (U+2066–U+2069). Infallible.
///
/// **Keeps the logical order.** This is a pure filter: the controls are deleted and the
/// code-point order is untouched, so the result is the order the bytes are in, not the
/// order a reader saw. `"\u202e" + "paypal"[::-1] + "\u202c"` renders as `paypal` and
/// comes back as `lapyap`.
///
/// That is correct for a compiler, a filesystem or an identifier comparison, which all
/// read logical order — the Trojan Source direction (CVE-2021-42574). It is the wrong
/// answer for a search index, an NLP model or content moderation, which want what was
/// displayed. disarm has no surface that returns display order; see "Stripping preserves
/// logical order, not display order" in `docs/limitations.md` (#740).
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _strip_bidi(text: &str) -> String {
    crate::presets::strip_bidi(text)
}

/// `strip_tags(text) -> str` (#413), preserving valid emoji flag sequences.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _strip_tags(text: &str) -> String {
    crate::api::strip_tags(text)
}

/// `strip_variation_selectors(text) -> str` (#413).
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _strip_variation_selectors(text: &str) -> String {
    crate::api::strip_variation_selectors(text)
}

/// `strip_noncharacters(text) -> str` (#413).
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _strip_noncharacters(text: &str) -> String {
    crate::api::strip_noncharacters(text)
}

/// `strip_pua(text) -> str` (#413).
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _strip_pua(text: &str) -> String {
    crate::api::strip_pua(text)
}

/// Strict canonicalization of user input — Unicode hygiene, **not** a sanitizer.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _canonicalize_strict(text: &str) -> PyResult<String> {
    Ok(crate::presets::canonicalize_strict(text)?.into_owned())
}

/// Maximum-strength text deobfuscation pipeline.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _strip_obfuscation(text: &str) -> PyResult<String> {
    Ok(crate::presets::strip_obfuscation(text)?.into_owned())
}
