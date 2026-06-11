//! SPIKE (#277 lever 5): unsafe PEP 393 fast paths — **measurement only**.
//!
//! Throwaway prototype of the proposed unsafe binding crate: direct CPython
//! string-header access that the limited API (abi3) cannot express. Compiled
//! only in this branch's non-abi3 configuration. MUST NOT ship: production
//! keeps `unsafe_code = "forbid"` and abi3 wheels (#277).
#![allow(unsafe_code)]

use pyo3::exceptions::PyMemoryError;
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::PyString;

/// True iff CPython's compact-ASCII flag bit is set on the `str` header.
///
/// Replaces `to_str()` + `is_ascii()` scan with a single bit test.
///
/// SAFETY: `s` is a live `Bound<PyString>`, so `s.as_ptr()` is a valid
/// `PyUnicodeObject`; `PyUnicode_IS_ASCII` only reads the header bitfield.
#[inline]
pub(crate) fn pystr_is_ascii(s: &Bound<'_, PyString>) -> bool {
    unsafe { ffi::PyUnicode_IS_ASCII(s.as_ptr()) != 0 }
}

/// Build a compact-ASCII `str` directly: one allocation + one memcpy.
///
/// `PyString::new` goes through `PyUnicode_FromStringAndSize`, which re-scans
/// the bytes to derive a maximum character we already know. Falls back to the
/// safe constructor when `bytes` is not pure ASCII (possible via a non-ASCII
/// `replace_with`), so this is correct for every input.
pub(crate) fn new_ascii_pystring<'py>(
    py: Python<'py>,
    bytes: &[u8],
) -> PyResult<Bound<'py, PyString>> {
    if bytes.is_empty() || !bytes.is_ascii() {
        // Empty: CPython returns the shared empty singleton from
        // PyUnicode_New — its buffer must never be written. Non-ASCII:
        // outside this constructor's contract (non-ASCII replace_with).
        return Ok(PyString::new(
            py,
            std::str::from_utf8(bytes).map_err(|_| {
                PyMemoryError::new_err("internal: non-UTF-8 transliteration output")
            })?,
        ));
    }
    // SAFETY: PyUnicode_New(len, 0x7F) allocates a compact-ASCII object with
    // a (len + 1)-byte data buffer; PyUnicode_DATA points at it. We fill
    // exactly `len` bytes and write the NUL terminator CPython expects at
    // data[len]. The object is fresh and uniquely owned — no aliasing.
    unsafe {
        let obj = ffi::PyUnicode_New(bytes.len() as ffi::Py_ssize_t, 0x7F);
        if obj.is_null() {
            return Err(
                PyErr::take(py).unwrap_or_else(|| PyMemoryError::new_err("PyUnicode_New failed"))
            );
        }
        let data = ffi::PyUnicode_DATA(obj).cast::<u8>();
        std::ptr::copy_nonoverlapping(bytes.as_ptr(), data, bytes.len());
        data.add(bytes.len()).write(0);
        Ok(Bound::from_owned_ptr(py, obj).downcast_into_unchecked())
    }
}
