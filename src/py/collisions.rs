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
