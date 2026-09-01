//! PyO3 shims for `crate::zalgo` (Layer-1). Infallible.

use pyo3::prelude::*;

use crate::zalgo::{DEFAULT_MAX_MARKS, DEFAULT_THRESHOLD};

/// `is_zalgo(text, *, threshold=3) -> bool`
#[pyfunction]
#[pyo3(signature = (text, *, threshold = DEFAULT_THRESHOLD))]
pub fn _is_zalgo(text: &str, threshold: usize) -> bool {
    crate::zalgo::is_zalgo(text, threshold)
}

/// `strip_zalgo(text, *, max_marks=3) -> str` — the default equals `is_zalgo`'s
/// threshold, so this never strips from text the library calls ordinary (#788).
#[pyfunction]
#[pyo3(signature = (text, *, max_marks = DEFAULT_MAX_MARKS))]
pub fn _strip_zalgo(text: &str, max_marks: usize) -> String {
    crate::zalgo::strip_zalgo(text, max_marks)
}
