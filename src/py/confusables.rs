//! PyO3 shims for `crate::confusables` (Layer-1).
//!
//! These expose `_normalize_confusables` / `_is_confusable` to Python. They are
//! thin: parameter parsing + the native [`crate::ErrorRepr`] → `PyErr` conversion
//! (via `?`, see `From<ErrorRepr> for PyErr` in `crate::error`). All behaviour lives
//! in the Layer-1 module.

use pyo3::prelude::*;

/// Replace Unicode confusable homoglyphs with target-script equivalents.
#[pyfunction]
#[pyo3(signature = (text, *, target_script="latin"))]
pub fn _normalize_confusables(text: &str, target_script: &str) -> PyResult<String> {
    Ok(crate::confusables::normalize_confusables(
        text,
        target_script,
    )?)
}

/// True if text contains any characters confusable with target-script characters.
#[pyfunction]
#[pyo3(signature = (text, *, target_script="latin"))]
pub fn _is_confusable(text: &str, target_script: &str) -> PyResult<bool> {
    Ok(crate::confusables::is_confusable(text, target_script)?)
}
