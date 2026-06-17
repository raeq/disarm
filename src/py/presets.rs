//! PyO3 shims for `crate::presets` (Layer-1) — the precompiled-pipeline presets.
//!
//! Each shim is a thin wrapper over a Layer-1 preset core. The cores compose
//! other modules' transforms and live in `src/presets.rs` (pyo3-free,
//! `pub(crate)`); these shims validate at the boundary and convert the native
//! `ErrorRepr` to a Python exception via `?`. See #38.

use pyo3::prelude::*;

/// Security-focused text canonicalization.
///
/// Pipeline: NFKC → confusables → strip bidi/format → collapse_whitespace →
/// (path-separator neutralization).
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _security_clean(text: &str) -> PyResult<String> {
    Ok(crate::presets::security_clean(text)?)
}

/// ML/NLP text normalization pipeline.
///
/// Pipeline: NFKC → emoji→text → transliterate → strip_accents → fold_case →
/// collapse_whitespace.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None, emoji_style="cldr"))]
pub fn _ml_normalize(text: &str, lang: Option<&str>, emoji_style: &str) -> PyResult<String> {
    Ok(crate::presets::ml_normalize(text, lang, emoji_style)?)
}

/// Library catalog key generation pipeline.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None, strict_iso9=false))]
pub fn _catalog_key(text: &str, lang: Option<&str>, strict_iso9: bool) -> PyResult<String> {
    Ok(crate::presets::catalog_key(text, lang, strict_iso9)?)
}

/// Search index key generation pipeline.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None))]
pub fn _search_key(text: &str, lang: Option<&str>) -> PyResult<String> {
    Ok(crate::presets::search_key(text, lang)?)
}

/// Sort key generation pipeline.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None))]
pub fn _sort_key(text: &str, lang: Option<&str>) -> PyResult<String> {
    Ok(crate::presets::sort_key(text, lang)?)
}

/// Display-safe text cleaning pipeline.
///
/// Infallible: strip bidi/format → collapse_whitespace.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _display_clean(text: &str) -> String {
    crate::presets::display_clean(text)
}

/// Strip bidirectional override and formatting characters (UAX #9).
///
/// Removes: soft hyphen (U+00AD), Arabic Letter Mark (U+061C),
/// LRM/RLM (U+200E/F), bidi embeddings/overrides (U+202A–U+202E),
/// bidi isolates (U+2066–U+2069). Infallible.
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

/// Normalize user-submitted input — Unicode hygiene, **not** an output sanitizer.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _normalize_user_input(text: &str) -> PyResult<String> {
    Ok(crate::presets::normalize_user_input(text)?)
}

/// Maximum-strength text deobfuscation pipeline.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _strip_obfuscation(text: &str) -> PyResult<String> {
    Ok(crate::presets::strip_obfuscation(text)?)
}
