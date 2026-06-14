//! PyO3 shims for `crate::reverse` (Layer-1).
//!
//! `_reverse_transliterate` validates the language at the boundary; Layer 1 / 2
//! take the typed `ReverseLang`.

use pyo3::prelude::*;

/// `reverse_transliterate(text, *, lang) -> str`
#[pyfunction]
#[pyo3(signature = (text, *, lang))]
pub fn _reverse_transliterate(text: &str, lang: &str) -> PyResult<String> {
    if !crate::reverse::supports_reverse(lang) {
        return Err(crate::ErrorRepr::ReverseUnsupportedLang {
            lang: lang.to_owned(),
            available: crate::reverse::reverse_langs().join(", "),
        }
        .into());
    }
    Ok(crate::reverse::reverse_transliterate_impl(text, lang))
}

/// `reverse_langs() -> list[str]`
#[pyfunction]
pub fn _reverse_langs() -> Vec<String> {
    crate::reverse::reverse_langs()
}
