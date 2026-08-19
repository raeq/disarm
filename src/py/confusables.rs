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
