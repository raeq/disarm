//! PyO3 shim for `crate::case_fold` (Layer-1). Infallible.

use pyo3::prelude::*;

/// `fold_case(text) -> str`
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _fold_case(text: &str) -> String {
    crate::case_fold::fold_case_impl(text)
}

/// `is_case_fold_stable(text) -> bool`
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _is_case_fold_stable(text: &str) -> bool {
    crate::case_fold::is_case_fold_stable_impl(text)
}
