//! PyO3 shims for `crate::pipeline` (Layer-1).
//!
//! The stateful `_TextPipeline` `#[pyclass]` plus the `_get_pipeline` /
//! `_list_profiles` `#[pyfunction]`s. All ordering/execution/profile logic lives
//! in the Layer-1 [`crate::pipeline`] module; these validate at the boundary
//! (notably the signed `strip_zalgo` parameter) and convert the native
//! `ErrorRepr` to a Python exception via `?`.

use pyo3::prelude::*;

use crate::pipeline::Pipeline;

/// Composable, pre-compiled text cleaning pipeline.
#[pyclass]
#[pyo3(name = "_TextPipeline")]
pub struct _TextPipeline {
    inner: Pipeline,
}

#[pymethods]
impl _TextPipeline {
    #[new]
    #[pyo3(signature = (
        *,
        normalize=None,
        transliterate=false,
        lang=None,
        strict_iso9=false,
        gost7034=false,
        confusables=false,
        strip_accents=false,
        fold_case=false,
        collapse_whitespace=false,
        strip_control=None,
        strip_zero_width=None,
        demojize=false,
        strip_bidi=false,
        strip_zalgo=None,
        strip_pua=false,
        strip_plane14=false,
        resolve_deletions=false,
        resolve_cr=false,
        digit_policy="numeric",
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        normalize: Option<&str>,
        transliterate: bool,
        lang: Option<&str>,
        strict_iso9: bool,
        gost7034: bool,
        confusables: bool,
        strip_accents: bool,
        fold_case: bool,
        collapse_whitespace: bool,
        strip_control: Option<bool>,
        strip_zero_width: Option<bool>,
        demojize: bool,
        strip_bidi: bool,
        strip_zalgo: Option<i64>,
        strip_pua: bool,
        strip_plane14: bool,
        resolve_deletions: bool,
        resolve_cr: bool,
        digit_policy: &str,
    ) -> PyResult<Self> {
        // strip_zalgo's value is `max_marks`, which must be a non-negative value
        // that fits `usize`. This signed→unsigned narrowing is the one binding-
        // boundary concern: `usize::try_from` rejects both a negative value and
        // one too large for the platform word (32-bit), so neither can reach the
        // core's `usize` cap, where it would silently wrap into an enormous value
        // (effectively disabling the step) instead of being rejected.
        let zalgo_max_marks: Option<usize> = match strip_zalgo {
            Some(n) => Some(usize::try_from(n).map_err(|_| {
                crate::InvalidArgumentError::new_err(format!(
                    "strip_zalgo (max_marks) must be a non-negative value that fits the platform word size, got {n}"
                ))
            })?),
            None => None,
        };

        let inner = Pipeline::new(
            normalize,
            transliterate,
            lang,
            strict_iso9,
            gost7034,
            confusables,
            strip_accents,
            fold_case,
            collapse_whitespace,
            strip_control,
            strip_zero_width,
            demojize,
            strip_bidi,
            zalgo_max_marks,
            strip_pua,
            strip_plane14,
            resolve_deletions,
            resolve_cr,
        )?
        // #646: fixed at construction, and refused when no confusables step would run it.
        .with_digit_policy(crate::confusables::DigitPolicy::from_token(digit_policy)?)?;
        Ok(Self { inner })
    }

    /// What the named profile this was built from is for, or `None` (#860).
    fn purpose(&self) -> Option<&'static str> {
        self.inner.purpose()
    }

    /// Return the ordered list of active pipeline steps and their parameters.
    fn steps(&self) -> Vec<(String, Option<String>)> {
        self.inner.steps()
    }

    fn __repr__(&self) -> String {
        self.inner.repr()
    }

    /// Process text through the pipeline.
    fn process(&self, text: &str) -> PyResult<String> {
        Ok(self.inner.process(text)?)
    }
}

impl _TextPipeline {
    /// Wrap a pure [`Pipeline`] for return across the PyO3 boundary
    /// (used by `_get_pipeline`).
    fn from_inner(inner: Pipeline) -> Self {
        Self { inner }
    }
}

/// Build the `_TextPipeline` for a named policy profile (`get_pipeline`).
///
/// `digit_policy` is fixed here, at construction (#646): a profile is a resolved pipeline
/// and `process` takes text and nothing else. A profile with no confusables step refuses
/// a non-default policy rather than keeping a setting that would never run.
#[pyfunction]
#[pyo3(signature = (profile, *, digit_policy="numeric"))]
pub fn _get_pipeline(profile: &str, digit_policy: &str) -> PyResult<_TextPipeline> {
    match crate::pipeline::get_pipeline(profile)? {
        Some(inner) => Ok(_TextPipeline::from_inner(inner.with_digit_policy(
            crate::confusables::DigitPolicy::from_token(digit_policy)?,
        )?)),
        None => Err(crate::InvalidArgumentError::new_err(format!(
            "Unknown profile {profile:?}; available: {}",
            crate::pipeline::profile_names().join(", ")
        ))),
    }
}

/// Sorted names of the available named policy profiles (`list_profiles`).
#[pyfunction]
pub fn _list_profiles() -> Vec<String> {
    crate::pipeline::profile_names()
}
