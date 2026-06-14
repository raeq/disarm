//! PyO3 shims for `crate::scripts` (Layer-1).
//!
//! `_detect_scripts` / `_is_mixed_script` are infallible. `_inspect_auto_lang`
//! marshals the Layer-2 [`crate::api::AutoLangInspection`] into a Python dict.

use pyo3::prelude::*;
use pyo3::types::PyDict;

/// `detect_scripts(text) -> list[str]`
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _detect_scripts(text: &str) -> Vec<&'static str> {
    crate::scripts::detect_scripts(text)
}

/// `is_mixed_script(text) -> bool`
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _is_mixed_script(text: &str) -> bool {
    crate::scripts::is_mixed_script(text)
}

/// `inspect_auto_lang(text) -> dict` with keys `script`, `chosen_lang`,
/// `reason`, `discriminators_hit`.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _inspect_auto_lang(py: Python<'_>, text: &str) -> PyResult<Py<PyAny>> {
    let r = crate::api::inspect_auto_lang(text);
    let dict = PyDict::new(py);
    dict.set_item("script", r.script)?;
    dict.set_item("chosen_lang", r.chosen_lang)?;
    dict.set_item("reason", r.reason)?;
    dict.set_item("discriminators_hit", r.discriminators_hit)?;
    Ok(dict.into_any().unbind())
}
