//! PyO3 shim for `crate::whitespace` (Layer-1). Infallible.

use pyo3::prelude::*;

/// `collapse_whitespace(text) -> str` — fold-only (#433).
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _collapse_whitespace(text: &str) -> String {
    crate::whitespace::collapse_whitespace(text)
}
