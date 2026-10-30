//! PyO3 shims for `crate::slugify` (Layer-1).
//!
//! The free `_slugify` / `_slugify_batch` functions and the stateful
//! `_Slugifier` / `_UniqueSlugifier` classes. `_UniqueSlugifier` holds a Python
//! `check` callback, so it is inherently a binding-layer type. All core logic is
//! in the Layer-1 module; these validate at the boundary and convert the native
//! `ErrorRepr` to a Python exception via `?`.

use std::collections::{BTreeSet, HashMap, HashSet};

use pyo3::prelude::*;

use crate::limits::MAX_UNIQUE_ATTEMPTS;
use crate::slugify::{
    build_stopset, slugify_impl, slugify_impl_with_stopset, unique_slug_candidate, SlugConfig,
};

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
    let stopset: HashSet<String> = build_stopset(&config.stopwords);

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
        let stopset: HashSet<String> = build_stopset(&config.stopwords);
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
    /// #242 item 3, #1100: where the suffix walk of each base stands, so the k-th
    /// duplicate of a base does not re-walk suffixes 1..k (O(n²) → amortized O(n)).
    /// A cache and nothing more: a base with no entry is walked from counter 0 and
    /// gives the same slugs and the same `check` calls, slower. A walk that has not
    /// passed counter 0 is not kept, so a base that is used once costs no entry.
    walks: HashMap<String, SuffixWalk>,
}

/// The suffix walk of one base (bare, base-1, base-2, …), resumed on each call.
///
/// Invariant: the candidate of every counter below `next` is in `seen`, or the
/// counter is in `refused`. `seen` only grows until `reset`, so a counter that is
/// in neither can be skipped without a look.
#[derive(Default)]
struct SuffixWalk {
    /// The first counter the walk has not reached.
    next: u64,
    /// #1100: the counters below `next` whose candidate `check` refused. A refused
    /// candidate is *not* in `seen`, and `check` may accept it later, so each call
    /// asks about these again, lowest first, before it goes on at `next`. Until
    /// #1100 a `check` meant a full walk from 0 instead, a `format!` and a lookup
    /// for each counter already in `seen`: 32 million of them for 8,000 equal slugs.
    /// Without a `check` nothing is ever refused and this stays empty.
    refused: BTreeSet<u64>,
}

/// The candidate for `counter`, or the error for a `max_length` with no room for it.
fn candidate_at(base: &str, counter: u64, config: &SlugConfig) -> PyResult<String> {
    // No candidate: the suffix leaves no room for one character (one cluster under
    // `allow_unicode`) of the base. This is the fail-fast check of #102 as well: it
    // fires on the first suffixed counter when `max_length` cannot hold a character,
    // the separator and a digit. The suffix only grows with the counter, so no later
    // one fits either.
    unique_slug_candidate(base, counter, config).map_err(|too_short| {
        tl_warn!(
            "unique_slug_max_length_too_small: max_length={} min_unique_len={}",
            config.max_length,
            too_short.min_unique_len
        );
        crate::ErrorRepr::UniqueSlugMaxLengthTooSmall {
            max_length: config.max_length,
            separator: config.separator.clone(),
            min_unique_len: too_short.min_unique_len,
        }
        .into()
    })
}

/// Whether `check` accepts `candidate`; no `check` accepts everything.
fn is_free(py: Python<'_>, check: Option<&Py<PyAny>>, candidate: &str) -> PyResult<bool> {
    match check {
        Some(check_fn) => Ok(!check_fn.call1(py, (candidate,))?.extract::<bool>(py)?),
        None => Ok(true),
    }
}

/// Take the first free candidate of `base`: not in `seen`, and accepted by `check`.
///
/// The candidates are tried in rising counter order and `check` is asked about
/// exactly those that are not in `seen`, which is what a walk from counter 0 does.
/// An error leaves `walk` at the counter it stopped on, so the next call asks again.
fn take_first_free(
    py: Python<'_>,
    base: &str,
    text: &str,
    config: &SlugConfig,
    seen: &mut HashSet<String>,
    check: Option<&Py<PyAny>>,
    walk: &mut SuffixWalk,
) -> PyResult<String> {
    let mut pending = walk.refused.first().copied();
    while let Some(counter) = pending {
        pending = walk.refused.range(counter + 1..).next().copied();
        let candidate = candidate_at(base, counter, config)?;
        if seen.contains(&candidate) {
            // Another base has produced this slug since. It stays taken.
            walk.refused.remove(&counter);
        } else if is_free(py, check, &candidate)? {
            walk.refused.remove(&counter);
            seen.insert(candidate.clone());
            return Ok(candidate);
        }
    }
    // A candidate never cuts into the suffix digits (the base is cut instead, and a
    // budget with no room for one base character is an error), so distinct counters
    // never alias, and the former M1 `lossy` tracking has nothing left to detect.
    loop {
        let counter = walk.next;
        if counter > MAX_UNIQUE_ATTEMPTS {
            tl_warn!("unique_slug_attempts_exceeded: max={MAX_UNIQUE_ATTEMPTS}");
            return Err(crate::ErrorRepr::UniqueSlugAttemptsExceeded {
                max: MAX_UNIQUE_ATTEMPTS,
                text: text.to_owned(),
            }
            .into());
        }
        let candidate = candidate_at(base, counter, config)?;
        if !seen.contains(&candidate) {
            if is_free(py, check, &candidate)? {
                seen.insert(candidate.clone());
                walk.next = counter + 1;
                return Ok(candidate);
            }
            walk.refused.insert(counter);
        }
        walk.next = counter + 1;
    }
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
            walks: HashMap::new(),
        })
    }

    /// Generate a unique slug, appending numeric suffixes as needed.
    ///
    /// Bounded to `MAX_UNIQUE_ATTEMPTS` iterations to prevent infinite loops
    /// when a `check` callback always rejects candidates. The candidates are
    /// built by the core (`crate::slugify::unique_slug_candidate`).
    fn slugify(&mut self, py: Python<'_>, text: &str) -> PyResult<String> {
        let base = self.inner.slugify(text);
        // An empty slug is `slugify`'s documented result for an input with nothing
        // sluggable, and it is returned as it is every time: suffixing it gave `-1`,
        // `-2`, ..., a namespace every such input shared, each with a leading
        // separator (Finding 9 of `formal/lean/Sanitizers`). It is not recorded, so
        // it never displaces a real slug, and `check` is not consulted for it.
        if base.is_empty() {
            return Ok(base);
        }
        // #242 item 3, #1100: resume the walk of this base where the last call left
        // it. The entry is taken out for the call and put back after it, error or not,
        // so a `check` that raises loses nothing.
        let mut walk = self.walks.remove(&base).unwrap_or_default();
        let found = take_first_free(
            py,
            &base,
            text,
            &self.inner.config,
            &mut self.seen,
            self.check.as_ref(),
            &mut walk,
        );
        // A walk still at counter 0 or 1 with nothing refused saves one lookup at
        // most, and most bases are used once: not worth an entry each.
        if walk.next > 1 || !walk.refused.is_empty() {
            self.walks.insert(base, walk);
        }
        found
    }

    fn reset(&mut self) {
        self.seen.clear();
        // The walks index into `seen`; clearing one without the other would let a
        // stale walk skip now-free counters and change output.
        self.walks.clear();
    }
}
