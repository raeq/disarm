//! PyO3 shims for `crate::normalize` (Layer-1).
//!
//! `_normalize` / `_is_normalized` propagate the native [`crate::ErrorRepr`] via `?`.
//! `_normalize_batch` is a Python-boundary batch optimization: one boundary
//! crossing for N strings, the `MAX_BATCH_SIZE` cap, and a GIL-released loop
//! (#70) since the work touches no Python objects.

use pyo3::prelude::*;
use unicode_normalization::UnicodeNormalization;

/// `normalize(text, *, form="NFC") -> str`
#[pyfunction]
#[pyo3(signature = (text, *, form = "NFC"))]
pub fn _normalize(text: &str, form: &str) -> PyResult<String> {
    Ok(crate::normalize::normalize(text, form)?)
}

/// `is_normalized(text, *, form="NFC") -> bool`
#[pyfunction]
#[pyo3(signature = (text, *, form = "NFC"))]
pub fn _is_normalized(text: &str, form: &str) -> PyResult<bool> {
    Ok(crate::normalize::is_normalized(text, form)?)
}

/// `normalize_batch(texts, *, form="NFC") -> list[str]`
#[pyfunction]
#[pyo3(signature = (texts, *, form = "NFC"))]
pub fn _normalize_batch(py: Python<'_>, texts: Vec<String>, form: &str) -> PyResult<Vec<String>> {
    crate::normalize::validate_form(form)?;
    if texts.len() > crate::MAX_BATCH_SIZE {
        return Err(crate::ErrorRepr::BatchTooLarge {
            len: texts.len(),
            max: crate::MAX_BATCH_SIZE,
        }
        .into());
    }
    // Pick the normalizer once (form is validated), then run the pure-Rust loop
    // with the GIL released (#70): the closure touches no Python objects, so
    // other Python threads run in parallel during a large batch.
    let normalize_one: fn(&str) -> String = match form {
        "NFC" => |t| t.nfc().collect(),
        "NFD" => |t| t.nfd().collect(),
        "NFKC" => |t| t.nfkc().collect(),
        "NFKD" => |t| t.nfkd().collect(),
        _ => unreachable!(),
    };
    Ok(py.detach(move || texts.iter().map(|t| normalize_one(t)).collect()))
}
