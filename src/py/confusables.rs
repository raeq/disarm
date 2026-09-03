//! PyO3 shims for `crate::confusables` (Layer-1).
//!
//! These expose `_normalize_confusables` / `_is_confusable` to Python. They are
//! thin: parameter parsing + the native [`crate::ErrorRepr`] → `PyErr` conversion
//! (via `?`, see `From<ErrorRepr> for PyErr` in `crate::error`). All behaviour lives
//! in the Layer-1 module.

use pyo3::prelude::*;

/// Replace Unicode confusable homoglyphs with target-script equivalents.
#[pyfunction]
#[pyo3(signature = (text, *, target_script="latin", digit_policy="numeric"))]
pub fn _normalize_confusables(
    text: &str,
    target_script: &str,
    digit_policy: &str,
) -> PyResult<String> {
    Ok(crate::confusables::normalize_confusables(
        text,
        target_script,
        digit_policy,
    )?)
}

/// True if text contains any characters confusable with target-script characters.
#[pyfunction]
#[pyo3(signature = (text, *, target_script="latin"))]
pub fn _is_confusable(text: &str, target_script: &str) -> PyResult<bool> {
    Ok(crate::confusables::is_confusable(text, target_script)?)
}

/// Every upstream confusable source the bundled table does not fold (#563).
///
/// Returns a sorted list of single-character strings; the Python wrapper freezes it
/// into a `frozenset`.
#[pyfunction]
#[pyo3(signature = (*, target_script="latin"))]
pub fn _unmapped_confusables(target_script: &str) -> PyResult<Vec<String>> {
    Ok(crate::confusables::unmapped_confusables(target_script)?
        .into_iter()
        .map(String::from)
        .collect())
}

/// Scan `text` for the confusables the bundled table DOES fold, with their targets (#737).
///
/// The mirror of `_find_unmapped_confusables`: that one answers "what would survive the
/// fold?" — exposure — and this one answers "what did the fold change, and to what?" —
/// evidence. Returns `(char, byte_offset, target)` in order of appearance.
#[pyfunction]
#[pyo3(signature = (text, *, target_script="latin", allowed_scripts=None))]
pub fn _find_confusables(
    text: &str,
    target_script: &str,
    allowed_scripts: Option<Vec<String>>,
) -> PyResult<Vec<(String, usize, String)>> {
    let allowed = allowed_scripts.unwrap_or_default();
    let allowed: Vec<&str> = allowed.iter().map(String::as_str).collect();
    Ok(
        crate::confusables::find_confusables(text, target_script, &allowed)?
            .into_iter()
            .map(|(ch, offset, target)| (ch.to_string(), offset, target.to_string()))
            .collect(),
    )
}

/// Scan `text` for upstream confusable sources the bundled table does not fold (#563).
///
/// Returns `(char, byte_offset)` pairs in order of appearance — the same convention
/// as `find_untranslatable`, which also reports byte offsets.
#[pyfunction]
#[pyo3(signature = (text, *, target_script="latin"))]
pub fn _find_unmapped_confusables(
    text: &str,
    target_script: &str,
) -> PyResult<Vec<(String, usize)>> {
    Ok(
        crate::confusables::find_unmapped_confusables(text, target_script)?
            .into_iter()
            .map(|(ch, offset)| (ch.to_string(), offset))
            .collect(),
    )
}

/// One decoded smuggled run (#701).
///
/// A return-only result object, the shape [`crate::py::collisions::KeyCollision`] uses.
#[pyclass(skip_from_py_object)]
#[pyo3(name = "SmuggledPayload")]
#[derive(Clone)]
pub struct SmuggledPayload {
    /// `"tag_ascii"`, `"variation_bytes"` or `"zero_width_binary"`.
    #[pyo3(get)]
    pub scheme: String,
    /// **Byte** offset of the first carrier character, matching `Finding.start`.
    ///
    /// Bytes, not characters, so a Python caller slices `text.encode()` rather than the
    /// `str`. Slicing the `str` works only while everything before the run is ASCII.
    #[pyo3(get)]
    pub start: usize,
    /// **Byte** offset one past the last carrier character.
    #[pyo3(get)]
    pub end: usize,
    /// Carrier characters consumed — not bytes decoded, which differ per scheme.
    #[pyo3(get)]
    pub units: usize,
    /// The decoded bytes.
    #[pyo3(get)]
    pub data: Vec<u8>,
    /// The decoded string, and only when the bytes are valid UTF-8 and wholly printable.
    #[pyo3(get)]
    pub text: Option<String>,
}

#[pymethods]
impl SmuggledPayload {
    fn __repr__(&self) -> String {
        // `{:?}` on an `Option` renders Rust's `Some("x")`/`None`, which is not what a
        // Python repr should show.
        let text = match &self.text {
            Some(s) => format!("{s:?}"),
            None => "None".to_owned(),
        };
        format!(
            "SmuggledPayload(scheme={:?}, start={}, end={}, units={}, text={text})",
            self.scheme, self.start, self.end, self.units
        )
    }
}

impl From<crate::smuggled::Payload> for SmuggledPayload {
    fn from(p: crate::smuggled::Payload) -> Self {
        SmuggledPayload {
            scheme: p.scheme.as_str().to_owned(),
            start: p.start,
            end: p.end,
            units: p.units,
            data: p.bytes,
            text: p.text,
        }
    }
}

/// `decode_smuggled(text) -> list[SmuggledPayload]`
///
/// Decode what a smuggled run spells, rather than reporting that one is present (#701).
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _decode_smuggled(text: &str) -> Vec<SmuggledPayload> {
    crate::smuggled::decode_smuggled(text)
        .into_iter()
        .map(Into::into)
        .collect()
}
