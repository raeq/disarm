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

/// `is_mixed_script(text, *, per_word=False) -> bool`
///
/// `per_word` asks the question of each word rather than the whole string, so bilingual
/// text answers `False` (#901).
#[pyfunction]
#[pyo3(signature = (text, *, per_word=false))]
pub fn _is_mixed_script(text: &str, per_word: bool) -> bool {
    if per_word {
        crate::scripts::is_mixed_script_per_word(text)
    } else {
        crate::scripts::is_mixed_script(text)
    }
}

/// `has_bidi_conflict(text, *, per_word=False) -> bool`
#[pyfunction]
#[pyo3(signature = (text, *, per_word=false))]
pub fn _has_bidi_conflict(text: &str, per_word: bool) -> bool {
    if per_word {
        crate::scripts::has_bidi_conflict_per_word(text)
    } else {
        crate::scripts::has_bidi_conflict(text)
    }
}

/// `has_bidi_control(text) -> bool` — all twelve UAX #9 controls, uncontexted (#778).
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _has_bidi_control(text: &str) -> bool {
    crate::scripts::has_bidi_control(text)
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
