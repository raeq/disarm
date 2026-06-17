//! PyO3 shims for `crate::anomalies` (Layer-1) / [`crate::api`] (Layer-2).
//!
//! [`AnomalyReport`] and [`Finding`] are return-only `#[pyclass]` result objects
//! that wrap the Layer-2 data and re-expose its fields as Python getters, the way
//! [`crate::py::hostname::HostnameAnalysis`] does for hostnames. The detector
//! reports a technical fact and leaves the malicious-or-not judgement to the
//! caller. `lexicon` is accepted as any Python iterable of strings (a `set` is
//! idiomatic) and converted to a `HashSet`.

use std::collections::HashSet;

use pyo3::prelude::*;

/// One reason a token is anomalous (a single [`crate::api::Finding`]).
#[pyclass(skip_from_py_object)]
#[pyo3(name = "Finding")]
#[derive(Clone)]
pub struct Finding {
    /// Which branch fired: `"invisible"`, `"bidi"`, `"zalgo"`, `"mixed_script"`, `"leet"`, or `"segmentation"`.
    #[pyo3(get)]
    pub kind: String,
    /// The offending whitespace token, as it appeared.
    #[pyo3(get)]
    pub token: String,
    /// Byte offset of the token start in the input.
    #[pyo3(get)]
    pub start: usize,
    /// Byte offset of the token end in the input.
    #[pyo3(get)]
    pub end: usize,
    /// Evidence: the codepoint, the scripts, or the decoded word.
    #[pyo3(get)]
    pub detail: String,
    /// A plain-language sentence describing the finding.
    #[pyo3(get)]
    pub reason: String,
}

#[pymethods]
impl Finding {
    fn __repr__(&self) -> String {
        format!(
            "Finding(kind={:?}, token={:?}, start={}, end={}, detail={:?})",
            self.kind, self.token, self.start, self.end, self.detail
        )
    }
}

impl From<crate::api::Finding> for Finding {
    fn from(f: crate::api::Finding) -> Self {
        let reason = f.reason();
        Finding {
            kind: f.kind.as_str().to_string(),
            token: f.token,
            start: f.start,
            end: f.end,
            detail: f.detail,
            reason,
        }
    }
}

/// Structured anomaly report, parallel to `HostnameAnalysis`.
#[pyclass(skip_from_py_object)]
#[pyo3(name = "AnomalyReport")]
#[derive(Clone)]
pub struct AnomalyReport {
    /// Whether any token tripped (the same value `has_anomalies` returns).
    #[pyo3(get)]
    pub anomalous: bool,
    /// The anomaly kinds that fired, in order of first appearance.
    #[pyo3(get)]
    pub kinds: Vec<String>,
    /// Every finding, with span and detail.
    #[pyo3(get)]
    pub findings: Vec<Finding>,
    /// The first finding's reason, or `None`.
    #[pyo3(get)]
    pub reason: Option<String>,
}

#[pymethods]
impl AnomalyReport {
    fn __repr__(&self) -> String {
        let kinds = self
            .kinds
            .iter()
            .map(|k| format!("'{k}'"))
            .collect::<Vec<_>>()
            .join(", ");
        format!(
            "AnomalyReport(anomalous={}, kinds=[{kinds}])",
            if self.anomalous { "True" } else { "False" }
        )
    }
}

impl From<crate::api::AnomalyReport> for AnomalyReport {
    fn from(r: crate::api::AnomalyReport) -> Self {
        AnomalyReport {
            anomalous: r.anomalous,
            kinds: r.kinds.iter().map(|k| k.as_str().to_string()).collect(),
            findings: r.findings.into_iter().map(Finding::from).collect(),
            reason: r.reason,
        }
    }
}

/// A reusable, opaque lexicon handle (HAI-SDLC 6.1).
///
/// `has_anomalies` / `inspect_anomalies` rebuild a `HashSet<String>` from the
/// caller's word collection on every call. A caller hitting these in a loop with
/// a large lexicon pays that rebuild each time. `Lexicon` builds the internal set
/// once and is then reused across calls. It is immutable, hence `frozen`.
#[pyclass(frozen)]
#[pyo3(name = "Lexicon")]
pub struct Lexicon {
    pub(crate) inner: HashSet<String>,
}

#[pymethods]
impl Lexicon {
    #[new]
    fn new(words: Vec<String>) -> Self {
        // Accept any Python iterable of strings (`set`, `list`, generator, …),
        // mirroring `has_anomalies(text, lexicon=...)`, and fold it into the
        // internal set once. `api::lexicon` lowercases entries so a title-cased
        // wordlist still matches the detector's lowercased decoded words.
        Self {
            inner: crate::api::lexicon(words),
        }
    }

    /// Number of distinct words in the lexicon.
    fn __len__(&self) -> usize {
        self.inner.len()
    }
}

/// Fold a Python iterable of strings (a `set` — idiomatic — or a `list`,
/// generator, …) into a lowercased lexicon set in a **single pass**.
///
/// Extracting the argument as a `HashSet<String>` and then handing it to
/// `api::lexicon` would build the set twice (once at extraction, once when
/// lowercasing); iterating the raw object folds straight into one set, matching
/// the cost of a prebuilt [`Lexicon`] handle. The lowercasing mirrors
/// [`crate::api::lexicon`] so the raw-set and handle paths agree.
fn lexicon_from_py(words: Option<Bound<'_, PyAny>>) -> PyResult<HashSet<String>> {
    let Some(words) = words else {
        return Ok(HashSet::new());
    };
    let mut set = HashSet::new();
    for item in words.try_iter()? {
        set.insert(item?.extract::<String>()?.to_lowercase());
    }
    Ok(set)
}

/// `has_anomalies(text, lexicon=None) -> bool`
#[pyfunction]
#[pyo3(signature = (text, lexicon=None))]
pub fn _has_anomalies(text: &str, lexicon: Option<Bound<'_, PyAny>>) -> PyResult<bool> {
    let lexicon = lexicon_from_py(lexicon)?;
    Ok(crate::api::has_anomalies(text, &lexicon))
}

/// `inspect_anomalies(text, lexicon=None) -> AnomalyReport`
#[pyfunction]
#[pyo3(signature = (text, lexicon=None))]
pub fn _inspect_anomalies(
    text: &str,
    lexicon: Option<Bound<'_, PyAny>>,
) -> PyResult<AnomalyReport> {
    let lexicon = lexicon_from_py(lexicon)?;
    Ok(crate::api::inspect_anomalies(text, &lexicon).into())
}

/// `has_anomalies` against a prebuilt [`Lexicon`] handle (no per-call rebuild).
#[pyfunction]
pub fn _has_anomalies_lex(text: &str, lexicon: PyRef<'_, Lexicon>) -> bool {
    crate::api::has_anomalies(text, &lexicon.inner)
}

/// `inspect_anomalies` against a prebuilt [`Lexicon`] handle (no per-call rebuild).
#[pyfunction]
pub fn _inspect_anomalies_lex(text: &str, lexicon: PyRef<'_, Lexicon>) -> AnomalyReport {
    crate::api::inspect_anomalies(text, &lexicon.inner).into()
}
