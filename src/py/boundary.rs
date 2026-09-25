//! The #469 surrogate contract, enforced natively at the `str` -> Rust boundary.
//!
//! A Python `str` may hold lone surrogates, which have no UTF-8 encoding, so PyO3's
//! `str` -> `&str` extraction raises `UnicodeEncodeError` before any disarm code runs.
//! `python/disarm/_boundary.py` re-exports every `_core` function wrapped so that, on
//! that failure, the string arguments are scrubbed WTF-8 -> UTF-8 and the call retried.
//!
//! The wrapper was a Python `*args, **kwargs` function, and a Python call frame on every
//! call cost 70-84 ns: two to four times the native cost of a short call, and enough to
//! lose Unidecode's own ASCII benchmark cell. [`SurrogateSafe`] is the same wrapper as a
//! native callable: it forwards the call and hands off to the Python retry only when the
//! call raised `UnicodeEncodeError`, so valid input never enters Python code. The scrub
//! itself stays in `_boundary.py`, the one place the conversion is defined.

use std::borrow::Cow;

use pyo3::exceptions::PyUnicodeEncodeError;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDict, PyString, PyTuple};

/// `types.MethodType`, looked up once.
static METHOD_TYPE: PyOnceLock<Py<PyAny>> = PyOnceLock::new();

/// A `_core` function guarded by the #469 scrub-and-retry.
///
/// `dict` so `functools.update_wrapper` can give it the wrapped function's `__name__`,
/// `__doc__` and `__wrapped__`, which `help()` and `inspect.signature` read. `__get__`
/// binds it as a method, as a Python function binds, because `_api.py` guards the
/// `__call__` of its stateful classes with it.
#[pyclass(frozen, dict, module = "disarm._core")]
pub struct SurrogateSafe {
    inner: Py<PyAny>,
    retry: Py<PyAny>,
}

#[pymethods]
impl SurrogateSafe {
    /// `SurrogateSafe(inner, retry)`: call `inner`; on `UnicodeEncodeError`, return
    /// `retry(inner, args, kwargs)`.
    #[new]
    fn new(inner: Py<PyAny>, retry: Py<PyAny>) -> Self {
        Self { inner, retry }
    }

    #[pyo3(signature = (*args, **kwargs))]
    fn __call__<'py>(
        &self,
        py: Python<'py>,
        args: &Bound<'py, PyTuple>,
        kwargs: Option<&Bound<'py, PyDict>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        match self.inner.bind(py).call(args, kwargs) {
            Err(err) if err.is_instance_of::<PyUnicodeEncodeError>(py) => self
                .retry
                .bind(py)
                .call1((self.inner.bind(py), args, kwargs)),
            result => result,
        }
    }

    /// Bind to `obj` as a method (`types.MethodType`), or return the guard itself when
    /// read from the class.
    fn __get__<'py>(
        slf: &Bound<'py, Self>,
        obj: Option<&Bound<'py, PyAny>>,
        _owner: Option<&Bound<'py, PyAny>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let py = slf.py();
        match obj {
            Some(obj) if !obj.is_none() => METHOD_TYPE
                .get_or_try_init(py, || {
                    py.import("types")?.getattr("MethodType").map(Bound::unbind)
                })?
                .bind(py)
                .call1((slf, obj)),
            _ => Ok(slf.clone().into_any()),
        }
    }
}

/// `s` converted WTF-8 -> UTF-8: a well-formed surrogate pair recombined into its astral
/// scalar, each lone surrogate replaced by one U+FFFD. The same conversion as
/// `_boundary._wtf8`, by the same two codec calls, so the two cannot disagree.
pub(crate) fn scrub_wtf8(s: &Bound<'_, PyString>) -> PyResult<String> {
    let recoded = s
        .call_method1("encode", ("utf-16-le", "surrogatepass"))?
        .call_method1("decode", ("utf-16-le", "replace"))?;
    Ok(recoded.cast::<PyString>()?.to_str()?.to_owned())
}

/// A `str` argument under the #469 contract, for an entry point that guards itself
/// instead of going through [`SurrogateSafe`].
///
/// Extracts as `&str` does, borrowing the UTF-8 of a valid string and failing with the
/// same `TypeError` on anything that is not a `str`, except that a string holding
/// surrogates is scrubbed with [`scrub_wtf8`] instead of raising `UnicodeEncodeError`.
pub(crate) struct Utf8Arg<'a>(Cow<'a, str>);

impl Utf8Arg<'static> {
    /// A default value.
    pub(crate) const fn literal(s: &'static str) -> Self {
        Self(Cow::Borrowed(s))
    }
}

impl std::ops::Deref for Utf8Arg<'_> {
    type Target = str;

    fn deref(&self) -> &str {
        &self.0
    }
}

impl<'a, 'py> FromPyObject<'a, 'py> for Utf8Arg<'a> {
    type Error = PyErr;

    fn extract(ob: Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        // `&str`'s own extraction, so the success path and every error but the one
        // below are exactly what a `&str` argument gives.
        match <&'a str as FromPyObject<'a, 'py>>::extract(ob) {
            Ok(utf8) => Ok(Self(Cow::Borrowed(utf8))),
            Err(err) if err.is_instance_of::<PyUnicodeEncodeError>(ob.py()) => Ok(Self(
                Cow::Owned(scrub_wtf8(&ob.cast::<PyString>()?.to_owned())?),
            )),
            Err(err) => Err(err),
        }
    }
}
