//! PyO3 shim for `crate::collisions` (Layer-1) / [`crate::api`] (Layer-2).
//!
//! [`KeyCollision`] is a return-only `#[pyclass]` result object that re-exposes
//! the Layer-2 data as Python getters, the way
//! [`crate::py::anomalies::AnomalyReport`] does for anomalies. It reports which
//! values share a key and leaves the accept-or-refuse decision to the caller —
//! the two CVEs behind it want opposite policies from the same answer.

use pyo3::prelude::*;

/// One group of distinct inputs that reduce to the same key.
#[pyclass(skip_from_py_object)]
#[pyo3(name = "KeyCollision")]
#[derive(Clone)]
pub struct KeyCollision {
    /// The reduced form every member of the group shares.
    #[pyo3(get)]
    pub key: String,
    /// The distinct inputs that reduce to it, in order of first appearance.
    #[pyo3(get)]
    pub values: Vec<String>,
    /// Every position in the input list that belongs to this group, ascending.
    /// Not parallel to `values`: a value repeated verbatim appears once there and
    /// once per occurrence here.
    #[pyo3(get)]
    pub indices: Vec<usize>,
}

#[pymethods]
impl KeyCollision {
    fn __repr__(&self) -> String {
        let values = self
            .values
            .iter()
            .map(|v| format!("{v:?}"))
            .collect::<Vec<_>>()
            .join(", ");
        format!(
            "KeyCollision(key={:?}, values=[{values}], indices={:?})",
            self.key, self.indices
        )
    }
}

impl From<crate::api::KeyCollision> for KeyCollision {
    fn from(c: crate::api::KeyCollision) -> Self {
        KeyCollision {
            key: c.key,
            values: c.values,
            indices: c.indices,
        }
    }
}

/// `find_key_collisions(values, *, key, lang=None) -> list[KeyCollision]`
#[pyfunction]
#[pyo3(signature = (values, *, key, lang=None))]
pub fn _find_key_collisions(
    values: Vec<String>,
    key: &str,
    lang: Option<&str>,
) -> PyResult<Vec<KeyCollision>> {
    let key: crate::api::KeyForm = key.parse()?;
    Ok(crate::api::find_key_collisions(&values, key, lang)?
        .into_iter()
        .map(KeyCollision::from)
        .collect())
}

/// `edit_distance(a, b) -> int`
#[pyfunction]
pub fn _edit_distance(a: &str, b: &str) -> usize {
    crate::api::edit_distance(a, b)
}

/// One candidate name and how far it is from the value asked about (#883).
#[pyclass(skip_from_py_object)]
pub struct NearestMatch {
    /// The candidate, in the spelling the caller supplied.
    #[pyo3(get)]
    pub value: String,
    /// Its edit distance. `0` means the value *is* this candidate, which is reported
    /// rather than skipped — see `nearest_match`.
    #[pyo3(get)]
    pub distance: usize,
}

#[pymethods]
impl NearestMatch {
    fn __repr__(&self) -> String {
        format!(
            "NearestMatch(value={:?}, distance={})",
            self.value, self.distance
        )
    }
}

impl From<crate::api::NearestMatch> for NearestMatch {
    fn from(m: crate::api::NearestMatch) -> Self {
        Self {
            value: m.value,
            distance: m.distance,
        }
    }
}

/// `nearest_match(value, candidates, *, max_distance=1) -> NearestMatch | None`
#[pyfunction]
#[pyo3(signature = (value, candidates, *, max_distance=1))]
pub fn _nearest_match(
    value: &str,
    candidates: Vec<String>,
    max_distance: usize,
) -> Option<NearestMatch> {
    crate::api::nearest_match(value, candidates.iter().map(String::as_str), max_distance)
        .map(NearestMatch::from)
}
