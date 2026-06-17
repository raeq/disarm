//! PyO3 shims for `crate::hostname` (Layer-1) / [`crate::api`] (Layer-2).
//!
//! `_is_suspicious_hostname` is infallible (the analysis runs against the fixed
//! `"latin"` target). [`HostnameAnalysis`] is the `#[pyclass]` result object: it
//! wraps the Layer-2 [`crate::api::HostnameAnalysis`] data and re-exposes its
//! fields as Python getters.

use pyo3::prelude::*;

/// Findings from a hostname homoglyph analysis.
///
/// Reports factual findings; it claims nothing about absolute safety. A
/// `suspicious == false` result is not a safety certificate (see
/// `_is_suspicious_hostname`).
//
// `skip_from_py_object`: this is a return-only struct (it is never extracted
// from a Python object as a `#[pyfunction]` argument), so we opt out of the
// `FromPyObject` derive that pyo3 0.29 makes opt-in for `Clone` pyclasses.
#[pyclass(skip_from_py_object)]
#[pyo3(name = "HostnameAnalysis")]
#[derive(Clone)]
pub struct HostnameAnalysis {
    #[pyo3(get)]
    pub suspicious: bool,
    #[pyo3(get)]
    pub scripts: Vec<String>,
    #[pyo3(get)]
    pub mixed_script: bool,
    #[pyo3(get)]
    pub has_confusables: bool,
    #[pyo3(get)]
    pub bidi_conflict: bool,
    #[pyo3(get)]
    pub cross_label_script: bool,
    #[pyo3(get)]
    pub label_scripts: Vec<Vec<String>>,
    #[pyo3(get)]
    pub canonical: String,
}

impl From<crate::api::HostnameAnalysis> for HostnameAnalysis {
    fn from(a: crate::api::HostnameAnalysis) -> Self {
        HostnameAnalysis {
            suspicious: a.suspicious,
            scripts: a.scripts,
            mixed_script: a.mixed_script,
            has_confusables: a.has_confusables,
            bidi_conflict: a.bidi_conflict,
            cross_label_script: a.cross_label_script,
            label_scripts: a.label_scripts,
            canonical: a.canonical,
        }
    }
}

/// `is_suspicious_hostname(hostname) -> (bool, HostnameAnalysis)`
#[pyfunction]
#[pyo3(signature = (hostname,))]
pub fn _is_suspicious_hostname(hostname: &str) -> (bool, HostnameAnalysis) {
    // The Python surface keeps its (bool, analysis) tuple shape; the Rust api now
    // returns the analysis alone, with the verdict on its `suspicious` field.
    let analysis = crate::api::is_suspicious_hostname(hostname);
    (analysis.suspicious, analysis.into())
}
