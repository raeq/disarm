//! PyO3 shim for `crate::filename` (Layer-1).
//!
//! Validates the non-negative `max_length` contract at the boundary (#231);
//! Layer 1 / Layer 2 take an already-checked `usize`. The native
//! [`crate::ErrorRepr`] (unknown `lang`, bad `platform`) converts to a Python
//! exception via `?` (`From<ErrorRepr> for PyErr`).

use pyo3::prelude::*;

/// `sanitize_filename(text, *, separator="_", max_length=255, platform="universal",
/// lang=None, preserve_extension=True) -> str`
#[pyfunction]
#[pyo3(signature = (text, *, separator = "_", max_length = 255, platform = "universal", lang = None, preserve_extension = true))]
pub fn _sanitize_filename(
    text: &str,
    separator: &str,
    max_length: i64,
    platform: &str,
    lang: Option<&str>,
    preserve_extension: bool,
) -> PyResult<String> {
    let max_length = crate::error::checked_max_length(max_length)?;
    Ok(crate::filename::sanitize_filename(
        text,
        separator,
        max_length,
        platform,
        lang,
        preserve_extension,
    )?)
}
