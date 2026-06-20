//! PyO3 shims for `crate::slugify` (Layer-1).
//!
//! The free `_slugify` / `_slugify_batch` functions and the stateful
//! `_Slugifier` / `_UniqueSlugifier` classes. `_UniqueSlugifier` holds a Python
//! `check` callback, so it is inherently a binding-layer type. All core logic is
//! in the Layer-1 module; these validate at the boundary and convert the native
//! `ErrorRepr` to a Python exception via `?`.

use std::collections::{HashMap, HashSet};

use pyo3::prelude::*;

use crate::limits::MAX_UNIQUE_ATTEMPTS;
use crate::slugify::{slugify_impl, slugify_impl_with_stopset, SlugConfig};
use crate::utils::floor_char_boundary;

/// Generate a URL-safe slug from Unicode text.
#[pyfunction]
#[pyo3(signature = (
    text,
    *,
    separator="-",
    lowercase=true,
    max_length=0,
    word_boundary=false,
    save_order=false,
    stopwords=vec![],
    regex_pattern=None,
    replacements=vec![],
    allow_unicode=false,
    lang=None,
    entities=true,
    decimal=true,
    hexadecimal=true,
))]
pub fn _slugify(
    text: &str,
    separator: &str,
    lowercase: bool,
    max_length: i64,
    word_boundary: bool,
    save_order: bool,
    stopwords: Vec<String>,
    regex_pattern: Option<&str>,
    replacements: Vec<(String, String)>,
    allow_unicode: bool,
    lang: Option<&str>,
    entities: bool,
    decimal: bool,
    hexadecimal: bool,
) -> PyResult<String> {
    // #119: delegate to SlugConfig::from_pyargs (shared constructor).
    crate::transliterate::validate_lang(lang)?;
    // #231: validate the non-negative contract in the core, not the binding.
    let max_length = crate::error::checked_max_length(max_length)?;
    let config = SlugConfig::from_pyargs(
        separator,
        lowercase,
        max_length,
        word_boundary,
        save_order,
        stopwords,
        regex_pattern,
        replacements,
        allow_unicode,
        lang,
        entities,
        decimal,
        hexadecimal,
    )
    .map_err(pyo3::PyErr::from)?;
    Ok(slugify_impl(text, &config))
}

/// Batch slugification: process a list of strings in a single PyO3 boundary crossing.
#[pyfunction]
#[pyo3(signature = (
    texts,
    *,
    separator="-",
    lowercase=true,
    max_length=0,
    word_boundary=false,
    save_order=false,
    stopwords=vec![],
    regex_pattern=None,
    replacements=vec![],
    allow_unicode=false,
    lang=None,
    entities=true,
    decimal=true,
    hexadecimal=true,
))]
pub fn _slugify_batch(
    py: Python<'_>,
    texts: &Bound<'_, pyo3::types::PyList>,
    separator: &str,
    lowercase: bool,
    max_length: i64,
    word_boundary: bool,
    save_order: bool,
    stopwords: Vec<String>,
    regex_pattern: Option<&str>,
    replacements: Vec<(String, String)>,
    allow_unicode: bool,
    lang: Option<&str>,
    entities: bool,
    decimal: bool,
    hexadecimal: bool,
) -> PyResult<Vec<String>> {
    // Snapshot the element references into an immutable tuple up front so chunked
    // extraction stays atomic w.r.t. concurrent mutation of the input list — see
    // the matching note in `_transliterate_batch` (#239 review).
    let texts = texts.to_tuple();
    let len = texts.len();
    if len > crate::MAX_BATCH_SIZE {
        return Err(crate::ErrorRepr::BatchTooLarge {
            len,
            max: crate::MAX_BATCH_SIZE,
        }
        .into());
    }
    // #119: delegate to SlugConfig::from_pyargs (shared constructor).
    crate::transliterate::validate_lang(lang)?;
    // #231: validate the non-negative contract in the core, not the binding.
    let max_length = crate::error::checked_max_length(max_length)?;
    let config = SlugConfig::from_pyargs(
        separator,
        lowercase,
        max_length,
        word_boundary,
        save_order,
        stopwords,
        regex_pattern,
        replacements,
        allow_unicode,
        lang,
        entities,
        decimal,
        hexadecimal,
    )
    .map_err(pyo3::PyErr::from)?;

    // Pre-build the stopword set once for the entire batch instead of
    // reconstructing it on every call to slugify_impl.
    let stopset: HashSet<String> = config.stopwords.iter().cloned().collect();

    // #239: extract Rust `String` copies from the snapshot and slugify in chunks,
    // so peak Rust-side string residency is one chunk rather than a full copy of
    // every input up front. Each chunk is extracted with the GIL held, then
    // slugified with the GIL released (#70) — the compute loop touches no Python
    // objects. All-or-raise is preserved; a non-str element raises TypeError (the
    // public wrapper's `_validate_batch` already rejects those up front).
    let mut out: Vec<String> = Vec::with_capacity(len);
    let mut start = 0;
    while start < len {
        let end = (start + crate::BATCH_CHUNK_SIZE).min(len);
        let mut chunk: Vec<String> = Vec::with_capacity(end - start);
        for i in start..end {
            chunk.push(texts.get_item(i)?.extract::<String>()?);
        }
        let processed: Vec<String> = py.detach(|| {
            chunk
                .iter()
                .map(|text| slugify_impl_with_stopset(text, &config, Some(&stopset)))
                .collect()
        });
        out.extend(processed);
        start = end;
    }
    Ok(out)
}

#[pyclass]
#[pyo3(name = "_Slugifier")]
pub struct _Slugifier {
    config: SlugConfig,
    /// Pre-built stopword set so `slugify()` calls pay O(1) per word
    /// rather than O(stopwords) for HashSet construction on every call.
    stopset: HashSet<String>,
}

#[pymethods]
impl _Slugifier {
    #[new]
    #[pyo3(signature = (
        *,
        separator="-",
        lowercase=true,
        max_length=0,
        word_boundary=false,
        save_order=false,
        stopwords=vec![],
        regex_pattern=None,
        replacements=vec![],
        allow_unicode=false,
        lang=None,
        entities=true,
        decimal=true,
        hexadecimal=true,
        safe_chars="",
    ))]
    fn new(
        separator: &str,
        lowercase: bool,
        max_length: i64,
        word_boundary: bool,
        save_order: bool,
        stopwords: Vec<String>,
        regex_pattern: Option<&str>,
        replacements: Vec<(String, String)>,
        allow_unicode: bool,
        lang: Option<&str>,
        entities: bool,
        decimal: bool,
        hexadecimal: bool,
        safe_chars: &str,
    ) -> PyResult<Self> {
        // #257: validate `lang` in the constructor too. The stateful classes are
        // a first-class entrypoint (the typical long-lived web-handler form), so
        // they must fail-closed on an unknown lang exactly like the free
        // `_slugify` / `_slugify_batch` — not silently fall back to the default
        // transliterator.
        crate::transliterate::validate_lang(lang)?;
        // #231: validate the non-negative contract in the core, consistent with
        // the free `_slugify` / `_slugify_batch` entrypoints.
        let max_length = crate::error::checked_max_length(max_length)?;
        // #119: delegate to SlugConfig::from_pyargs (shared constructor).
        let mut config = SlugConfig::from_pyargs(
            separator,
            lowercase,
            max_length,
            word_boundary,
            save_order,
            stopwords,
            regex_pattern,
            replacements,
            allow_unicode,
            lang,
            entities,
            decimal,
            hexadecimal,
        )
        .map_err(pyo3::PyErr::from)?;
        // #230: safe_chars is native to the core now (no Python marker logic).
        safe_chars.clone_into(&mut config.safe_chars);
        let stopset: HashSet<String> = config.stopwords.iter().cloned().collect();
        Ok(Self { config, stopset })
    }

    fn slugify(&self, text: &str) -> String {
        slugify_impl_with_stopset(text, &self.config, Some(&self.stopset))
    }

    #[getter]
    fn separator(&self) -> &str {
        &self.config.separator
    }

    #[getter]
    fn lang(&self) -> Option<&str> {
        self.config.lang.as_deref()
    }
}

#[pyclass]
#[pyo3(name = "_UniqueSlugifier")]
pub struct _UniqueSlugifier {
    inner: _Slugifier,
    seen: HashSet<String>,
    check: Option<Py<PyAny>>,
    /// #242 item 3: per-base hint for the next suffix counter to try, so the
    /// k-th duplicate of a base does not re-walk suffixes 1..k (O(n²) →
    /// amortized O(n)). Only used when `check` is `None`: without an external
    /// callback the candidate sequence (bare, base-1, base-2, …) is rejected
    /// solely by `seen`, which grows monotonically and stays contiguous from the
    /// start, so skipping ahead can only skip already-`seen` candidates. With a
    /// `check` callback a rejected suffix is *not* in `seen`, leaving gaps that
    /// the hint would unsafely skip — there we keep the full walk so output is
    /// byte-identical.
    next_counter: HashMap<String, u64>,
}

/// Build the `counter`-th unique-slug candidate for `base`: counter 0 is the
/// bare base; counter k ≥ 1 is `base{sep}k`, truncated on a char boundary to
/// `max_length` if set (#102/#242 item 3 — extracted so the dedup loop can build
/// a candidate for any counter, including a cached starting hint).
///
/// Returns `(candidate, lossy)` where `lossy` is true when the `max_length`
/// truncation dropped suffix *digits* — a lossy candidate no longer faithfully
/// encodes `counter`, so distinct counters can alias to one string (e.g. with
/// `max_length == sep_len + 1`, counters 1 and 10 both truncate to `{sep}1`).
/// The dedup loop uses the flag to report `UniqueSlugMaxLengthTooSmall` rather
/// than the generic attempts-exceeded error (M1).
fn build_unique_candidate(base: &str, counter: u64, config: &SlugConfig) -> (String, bool) {
    if counter == 0 {
        return (base.to_owned(), false);
    }
    let sep = &config.separator;
    let mut candidate = format!("{base}{sep}{counter}");
    let mut lossy = false;
    if config.max_length > 0 && candidate.len() > config.max_length {
        let suffix = format!("{sep}{counter}");
        if suffix.len() >= config.max_length {
            // Suffix alone exceeds max_length — use the suffix truncated on a
            // char boundary (the separator may be multibyte). Cutting inside the
            // digits is the aliasing case, so flag it lossy.
            let boundary = floor_char_boundary(&suffix, config.max_length);
            lossy = boundary < suffix.len();
            // `floor_char_boundary` returns a valid char boundary <= len, so this
            // slice cannot panic — a justified exception to the FFI no-panic gate.
            #[allow(clippy::string_slice)]
            suffix[..boundary].clone_into(&mut candidate);
        } else {
            // Only the base is truncated; the full `{sep}{counter}` is preserved,
            // so the counter stays faithfully encoded (not lossy).
            let avail = config.max_length - suffix.len();
            let boundary = floor_char_boundary(base, avail);
            // `floor_char_boundary` returns a valid char boundary <= len, so this
            // slice cannot panic — a justified exception to the FFI no-panic gate.
            #[allow(clippy::string_slice)]
            let head = &base[..boundary];
            candidate = format!("{head}{suffix}");
        }
    }
    (candidate, lossy)
}

#[pymethods]
impl _UniqueSlugifier {
    #[new]
    #[pyo3(signature = (
        *,
        check=None,
        separator="-",
        lowercase=true,
        max_length=0,
        word_boundary=false,
        save_order=false,
        stopwords=vec![],
        regex_pattern=None,
        replacements=vec![],
        allow_unicode=false,
        lang=None,
        entities=true,
        decimal=true,
        hexadecimal=true,
        safe_chars="",
    ))]
    fn new(
        check: Option<Py<PyAny>>,
        separator: &str,
        lowercase: bool,
        max_length: i64,
        word_boundary: bool,
        save_order: bool,
        stopwords: Vec<String>,
        regex_pattern: Option<&str>,
        replacements: Vec<(String, String)>,
        allow_unicode: bool,
        lang: Option<&str>,
        entities: bool,
        decimal: bool,
        hexadecimal: bool,
        safe_chars: &str,
    ) -> PyResult<Self> {
        // #231: the non-negative check is delegated to _Slugifier::new (signed param).
        // #119: delegates to _Slugifier::new which uses SlugConfig::from_pyargs.
        let inner = _Slugifier::new(
            separator,
            lowercase,
            max_length,
            word_boundary,
            save_order,
            stopwords,
            regex_pattern,
            replacements,
            allow_unicode,
            lang,
            entities,
            decimal,
            hexadecimal,
            safe_chars,
        )?;
        Ok(Self {
            inner,
            seen: HashSet::new(),
            check,
            next_counter: HashMap::new(),
        })
    }

    /// Generate a unique slug, appending numeric suffixes as needed.
    ///
    /// Bounded to `MAX_UNIQUE_ATTEMPTS` iterations to prevent infinite loops
    /// when a `check` callback always rejects candidates.
    fn slugify(&mut self, py: Python<'_>, text: &str) -> PyResult<String> {
        let base = self.inner.slugify(text);
        // #242 item 3: when there's no external `check`, start the suffix counter
        // from the cached per-base hint so the k-th duplicate of `base` doesn't
        // re-walk 1..k (amortized O(1) vs O(k)). Counter 0 is the bare base; each
        // later counter is the suffixed form. See `next_counter` for why the hint
        // is sound only on the check-less path.
        let use_hint = self.check.is_none();
        let mut counter: u64 = if use_hint {
            self.next_counter.get(&base).copied().unwrap_or(0)
        } else {
            0
        };

        let config = &self.inner.config;
        // M1: once truncation starts dropping suffix digits, distinct counters
        // alias to the same string and the loop can never find a free candidate.
        // Track it so exhaustion is reported as the (accurate) max-length error.
        let mut saw_lossy = false;
        loop {
            if counter > MAX_UNIQUE_ATTEMPTS {
                if saw_lossy {
                    // The `max_length` is too small to encode this many distinct
                    // suffixes — the truncated forms aliased (M1/M4).
                    tl_warn!(
                        "unique_slug_max_length_too_small: max_length={} sep_len={}",
                        config.max_length,
                        config.separator.len()
                    );
                    return Err(crate::ErrorRepr::UniqueSlugMaxLengthTooSmall {
                        max_length: config.max_length,
                        separator: config.separator.clone(),
                        min_unique_len: config.separator.len() + 1,
                    }
                    .into());
                }
                tl_warn!("unique_slug_attempts_exceeded: max={MAX_UNIQUE_ATTEMPTS}");
                return Err(crate::ErrorRepr::UniqueSlugAttemptsExceeded {
                    max: MAX_UNIQUE_ATTEMPTS,
                    text: text.to_owned(),
                }
                .into());
            }
            // Fail fast on an impossible constraint (#102 review): a suffixed slug
            // (counter ≥ 1) needs room for the separator plus at least one digit.
            // If max_length is smaller, every suffix truncates to a constant that
            // collides forever — error clearly instead of looping to MAX.
            if counter >= 1 {
                let min_unique_len = config.separator.len() + 1;
                if config.max_length > 0 && config.max_length < min_unique_len {
                    tl_warn!(
                        "unique_slug_max_length_too_small: max_length={} min_unique_len={min_unique_len}",
                        config.max_length
                    );
                    return Err(crate::ErrorRepr::UniqueSlugMaxLengthTooSmall {
                        max_length: config.max_length,
                        separator: config.separator.clone(),
                        min_unique_len,
                    }
                    .into());
                }
            }

            let (candidate, lossy) = build_unique_candidate(&base, counter, config);
            saw_lossy |= lossy;
            if !self.seen.contains(&candidate) {
                let free = match self.check.as_ref() {
                    Some(check_fn) => !check_fn.call1(py, (&candidate,))?.extract::<bool>(py)?,
                    None => true,
                };
                if free {
                    self.seen.insert(candidate.clone());
                    if use_hint {
                        // Next duplicate of this base starts right after the
                        // counter we just consumed.
                        self.next_counter.insert(base, counter + 1);
                    }
                    return Ok(candidate);
                }
            }
            counter += 1;
        }
    }

    fn reset(&mut self) {
        self.seen.clear();
        // The per-base hints index into `seen`; clearing one without the other
        // would let a stale hint skip now-free counters and change output.
        self.next_counter.clear();
    }
}
