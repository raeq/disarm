//! PyO3 shims for `crate::encoders` (Layer-1).
//!
//! `_escape_html` hands back the original `PyString` object zero-copy when
//! nothing needs escaping (#277). `_percent_encode` validates the component name
//! at the boundary; Layer 1 / Layer 2 take the typed `UrlComponent`.

use std::borrow::Cow;

use pyo3::prelude::*;
use pyo3::types::PyString;

/// `escape_html(text) -> str`
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _escape_html<'py>(text: &Bound<'py, PyString>) -> PyResult<Bound<'py, PyString>> {
    let s = text.to_cow()?;
    match crate::encoders::escape_html_str(&s) {
        // Nothing to escape → hand back the original object (refcount bump, no
        // string copy). The common case for already-clean text.
        Cow::Borrowed(_) => Ok(text.clone()),
        Cow::Owned(escaped) => Ok(PyString::new(text.py(), &escaped)),
    }
}

/// `percent_encode(text, *, component) -> str`
#[pyfunction]
#[pyo3(signature = (text, *, component))]
pub fn _percent_encode(text: &str, component: &str) -> PyResult<String> {
    crate::encoders::percent_encode_str(text, component).ok_or_else(|| {
        crate::InvalidArgumentError::new_err(format!(
            "unknown percent-encode component {component:?}; expected one of: \
             'path', 'segment', 'query', 'form'"
        ))
    })
}
