//! PyO3 shims for `crate::transliterate` (Layer-1).
//!
//! Built up incrementally as `transliterate` is migrated. Begins with the
//! infallible pure-transform wrappers; the registration set, the Python
//! fallback-callback machinery, and the batch/context entry points land here too.

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyString};
use std::borrow::Cow;
use std::collections::HashMap;
use std::sync::{LazyLock, RwLock};

use crate::ErrorMode;

/// `strip_accents(text) -> str`
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _strip_accents(text: &str) -> String {
    crate::transliterate::strip_accents(text)
}

/// `is_ascii(text) -> bool`
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _is_ascii(text: &str) -> bool {
    text.is_ascii()
}

/// `list_langs() -> list[str]`
#[pyfunction]
#[pyo3(signature = ())]
pub fn _list_langs() -> Vec<String> {
    crate::tables::list_langs()
}

/// Seal the global registration tables: subsequent register/remove/clear calls
/// fail. Irreversible. Call after startup configuration to prevent later code
/// from mutating the process-global canonicalization every caller shares.
///
/// Shim-only (process-global state; excluded from the crates.io surface by
/// design, #38): a thin wrapper over `crate::tables::seal_registrations`.
#[pyfunction]
#[pyo3(signature = ())]
pub fn _seal_registrations() {
    crate::tables::seal_registrations();
}

/// True if `seal_registrations()` has been called. Shim-only (#38).
#[pyfunction]
#[pyo3(signature = ())]
pub fn _registrations_sealed() -> bool {
    crate::tables::registrations_sealed()
}

/// Register or override a transliteration mapping for a language code.
/// Shim-only (#38) over [`crate::transliterate::register_lang`].
#[pyfunction]
#[pyo3(signature = (code, mappings))]
pub fn _register_lang(code: &str, mappings: HashMap<String, String>) -> PyResult<()> {
    Ok(crate::transliterate::register_lang(code, mappings)?)
}

/// Register global pre-transliteration replacements.
/// Shim-only (#38) over [`crate::transliterate::register_replacements`].
#[pyfunction]
#[pyo3(signature = (replacements,))]
pub fn _register_replacements(replacements: HashMap<String, String>) -> PyResult<()> {
    Ok(crate::transliterate::register_replacements(replacements)?)
}

/// Remove a single global pre-transliteration replacement by key.
///
/// Returns True if the key was present, False otherwise.
/// Shim-only (#38) over [`crate::transliterate::remove_replacement`].
#[pyfunction]
#[pyo3(signature = (key,))]
pub fn _remove_replacement(key: &str) -> PyResult<bool> {
    Ok(crate::transliterate::remove_replacement(key)?)
}

/// Clear all global pre-transliteration replacements.
/// Shim-only (#38) over [`crate::transliterate::clear_replacements`].
#[pyfunction]
#[pyo3(signature = ())]
pub fn _clear_replacements() -> PyResult<()> {
    Ok(crate::transliterate::clear_replacements()?)
}

/// Python-side dispatcher for the shapes the fast entry point does not handle
/// (lists, str subclasses, reverse `target=`, `context=True`, type errors).
///
/// Registered once at `disarm` package import by `_set_transliterate_fallback`.
/// An `RwLock<Option<…>>` (not a set-once cell) so `importlib.reload(disarm)`
/// re-registers cleanly instead of erroring or calling a stale dispatcher.
///
/// Inherently binding-layer (#38): the callback is a Python object, so the
/// static, its setter, and the entry point all live in the PyO3 shim. Layer 1
/// never knows the fallback exists.
static TRANSLITERATE_FALLBACK: LazyLock<RwLock<Option<Py<PyAny>>>> =
    LazyLock::new(|| RwLock::new(None));

/// Register the Python dispatcher `_transliterate_entry` delegates to (#277
/// Phase B). Called from `python/disarm/_api.py` at package import.
#[pyfunction]
pub fn _set_transliterate_fallback(f: Bound<'_, PyAny>) -> PyResult<()> {
    if !f.is_callable() {
        return Err(PyRuntimeError::new_err(
            "transliterate fallback must be callable",
        ));
    }
    // Swap under the lock, drop outside it: the old dispatcher's `__del__` is Python
    // and must not run while the lock is held (see `crate::py::emoji::swap_provider`).
    let old = {
        let mut slot =
            crate::recover_lock(TRANSLITERATE_FALLBACK.write(), "TRANSLITERATE_FALLBACK");
        slot.replace(f.unbind())
    };
    drop(old);
    Ok(())
}

/// Single-crossing public `transliterate()` entry point (#277 Phase B).
///
/// Bound directly to `disarm.transliterate` at runtime: the common shape —
/// an exact `str` with no reverse/context dispatch — runs entirely in Rust
/// with **one** Python→native call. A bare `transliterate(text)` extracts only
/// `text`; every keyword default is a Rust-side constant with zero per-call
/// extraction cost. All other shapes (list batch, str subclass, `target=`,
/// `context=True`, wrong types) delegate to the registered Python dispatcher,
/// which implements them exactly as before.
///
/// Unicode → ASCII transliteration. See the package documentation for the
/// full argument reference; semantics are identical to the Python dispatcher
/// (`disarm._api._transliterate_dispatch`), which type checkers see as the
/// signature source of truth.
#[pyfunction]
#[pyo3(
    signature = (text, *, lang=None, target=None, errors="replace", replace_with="[?]", strict_iso9=false, gost7034=false, tones=false, context=false),
    text_signature = "(text, *, lang=None, target=None, errors='replace', replace_with='[?]', strict_iso9=False, gost7034=False, tones=False, context=False)"
)]
#[allow(clippy::too_many_arguments)]
pub fn _transliterate_entry<'py>(
    text: &Bound<'py, PyAny>,
    lang: Option<&str>,
    target: Option<&str>,
    errors: &str,
    replace_with: &str,
    strict_iso9: bool,
    gost7034: bool,
    tones: bool,
    context: bool,
) -> PyResult<Bound<'py, PyAny>> {
    // Fast path: exact `str` (subclasses keep their legacy general-path
    // handling), forward direction, no context engine. The conflict-matrix
    // validation is a provable no-op without `target`/`context` (#231); all
    // remaining validation (lang, errors, strict_iso9 × gost7034) runs inside
    // `_transliterate` itself (#130).
    if target.is_none() && !context {
        if let Ok(s) = text.cast_exact::<PyString>() {
            return Ok(_transliterate(
                s,
                lang,
                errors,
                replace_with,
                strict_iso9,
                gost7034,
                tones,
            )?
            .into_any());
        }
    }
    // Everything else: delegate to the Python dispatcher.
    let py = text.py();
    let fallback = {
        let slot = crate::recover_lock(TRANSLITERATE_FALLBACK.read(), "TRANSLITERATE_FALLBACK");
        slot.as_ref().map(|f| f.clone_ref(py))
    };
    let Some(fallback) = fallback else {
        return Err(PyRuntimeError::new_err(
            "disarm internal error: transliterate dispatcher not registered — \
             import the `disarm` package rather than `disarm._core` directly",
        ));
    };
    let kwargs = PyDict::new(py);
    kwargs.set_item("lang", lang)?;
    kwargs.set_item("target", target)?;
    kwargs.set_item("errors", errors)?;
    kwargs.set_item("replace_with", replace_with)?;
    kwargs.set_item("strict_iso9", strict_iso9)?;
    kwargs.set_item("gost7034", gost7034)?;
    kwargs.set_item("tones", tones)?;
    kwargs.set_item("context", context)?;
    fallback.bind(py).call((text,), Some(&kwargs))
}

/// `transliterate()` core entry: Unicode → ASCII.
///
/// #277 lever 4: takes the Python string object itself (not an extracted
/// `&str`) so the no-op case can return the *original object* with an incref
/// instead of allocating a copy. `to_str()` is zero-copy for compact ASCII
/// strings on the abi3-py310 floor (`PyUnicode_AsUTF8AndSize`, cached on the
/// object by CPython). Wraps the Layer-1 engine `crate::transliterate::*` (#38).
#[pyfunction]
#[pyo3(signature = (text, lang=None, errors="replace", replace_with="[?]", strict_iso9=false, gost7034=false, tones=false))]
pub fn _transliterate<'py>(
    text: &Bound<'py, PyString>,
    lang: Option<&str>,
    errors: &str,
    replace_with: &str,
    strict_iso9: bool,
    gost7034: bool,
    tones: bool,
) -> PyResult<Bound<'py, PyString>> {
    // #130: Defence-in-depth — the PyO3 boundary check in each entry-point guards
    // direct Rust callers; Python callers are covered by the same check.
    if strict_iso9 && gost7034 {
        return Err(crate::ErrorRepr::MutuallyExclusiveBare.into());
    }
    crate::transliterate::validate_lang(lang)?;
    let py = text.py();
    let s = text.to_str()?;
    // "strict" is not an ErrorMode value but a separate mode (#184): `None` below.
    let on_unknown = if errors == "strict" {
        None
    } else {
        Some(ErrorMode::parse(errors)?)
    };
    // The registered replacement pre-pass, then the engine: the one body the Rust
    // API's `Transliterate::try_run` runs too (`formal/bindings`, E1). The pre-pass
    // runs before the engine's ASCII fast path, so ASCII-keyed replacements take
    // effect; its output is bounded (amplification guard); raw input size is not
    // capped (#80).
    let out = crate::transliterate::transliterate_after_replacements(
        s,
        lang,
        on_unknown,
        replace_with,
        strict_iso9,
        gost7034,
        tones,
    )?;
    // #277 lever 4: a borrowed result is the documented "output is byte-identical to
    // input" contract (the pre-pass borrows only when no replacement fired, the engine
    // only for pure-ASCII input). Returning the original object is then
    // observationally identical for an immutable `str` — and zero-alloc.
    match out {
        Cow::Borrowed(_) => Ok(text.clone()),
        Cow::Owned(out) => Ok(PyString::new(py, &out)),
    }
}

/// Validate the *combination* of `transliterate()` keyword arguments (#231).
///
/// The semantic conflict matrix lives in the core (the single source of truth)
/// rather than only in the `python/disarm/_api.py` wrapper, so a second
/// binding enforces the identical contract by calling this one function.
///
/// `target` selects *reverse* transliteration; `context` and `tones` are
/// *forward-only*. The individual `errors` enum value and the `strict_iso9`/
/// `gost7034` exclusivity are validated by the per-operation entrypoints; this
/// function only rejects contradictory *combinations* of otherwise-valid kwargs.
///
/// The default sentinels for `errors` (`"replace"`) and `replace_with`
/// (`"[?]"`) are the documented public-API defaults — a value other than the
/// default means the caller set a forward-only parameter explicitly. Wraps the
/// Layer-1 core `crate::transliterate::validate_transliterate_args` (#38).
#[pyfunction]
#[pyo3(signature = (
    *,
    lang=None,
    target=None,
    errors="replace",
    replace_with="[?]",
    strict_iso9=false,
    gost7034=false,
    tones=false,
    context=false,
))]
#[allow(clippy::too_many_arguments)]
pub fn _validate_transliterate_args(
    lang: Option<&str>,
    target: Option<&str>,
    errors: &str,
    replace_with: &str,
    strict_iso9: bool,
    gost7034: bool,
    tones: bool,
    context: bool,
) -> PyResult<()> {
    crate::transliterate::validate_transliterate_args(
        lang,
        target,
        errors,
        replace_with,
        strict_iso9,
        gost7034,
        tones,
        context,
    )?;
    Ok(())
}

/// Find every character in `text` that has no transliteration, as
/// `(char, byte_offset)` pairs in order (#184). Replacements are applied first
/// (so offsets are relative to the post-replacement text), matching
/// `transliterate`. Pure-ASCII input yields an empty list. Wraps the Layer-1
/// core `crate::transliterate::find_untranslatable_impl` (#38).
#[pyfunction]
#[pyo3(signature = (text, *, lang=None, strict_iso9=false, gost7034=false, tones=false))]
pub fn _find_untranslatable(
    text: &str,
    lang: Option<&str>,
    strict_iso9: bool,
    gost7034: bool,
    tones: bool,
) -> PyResult<Vec<(char, usize)>> {
    if strict_iso9 && gost7034 {
        return Err(crate::ErrorRepr::MutuallyExclusiveBare.into());
    }
    crate::transliterate::validate_lang(lang)?;
    Ok(
        crate::transliterate::find_untranslatable_after_replacements(
            text,
            lang,
            strict_iso9,
            gost7034,
            tones,
        )?,
    )
}

/// Context-aware transliteration using dictionary-based vowel restoration.
///
/// Returns an error if no context dictionary is loaded for the language.
/// Individual words that are absent from a loaded dictionary fall back to
/// context-free transliteration. Wraps the Layer-1 core
/// `crate::transliterate::transliterate_context` (#38).
#[pyfunction]
#[pyo3(signature = (text, *, lang=None, errors="replace", replace_with="[?]", strict_iso9=false, gost7034=false))]
pub fn _transliterate_context(
    text: &str,
    lang: Option<&str>,
    errors: &str,
    replace_with: &str,
    strict_iso9: bool,
    gost7034: bool,
) -> PyResult<String> {
    Ok(crate::transliterate::transliterate_context(
        text,
        lang,
        errors,
        replace_with,
        strict_iso9,
        gost7034,
    )?)
}

/// Batch transliteration: process a list of strings in a single PyO3 boundary
/// crossing. Wraps the Layer-1 engine `crate::transliterate::*` (#38).
#[pyfunction]
#[pyo3(signature = (texts, lang=None, errors="replace", replace_with="[?]", strict_iso9=false, gost7034=false, tones=false))]
pub fn _transliterate_batch<'py>(
    py: Python<'py>,
    texts: &Bound<'py, PyList>,
    lang: Option<&str>,
    errors: &str,
    replace_with: &str,
    strict_iso9: bool,
    gost7034: bool,
    tones: bool,
) -> PyResult<Bound<'py, PyList>> {
    // #130: Defence-in-depth — the PyO3 boundary check in each entry-point guards
    // direct Rust callers; Python callers are covered by the same check.
    if strict_iso9 && gost7034 {
        return Err(crate::ErrorRepr::MutuallyExclusiveBare.into());
    }
    // Snapshot the element references into an immutable tuple up front (one
    // GIL-held, O(N) reference copy — not a copy of the string contents). The
    // former `Vec<String>` extraction was atomic under the GIL; chunked
    // extraction releases the GIL between chunks, so without this snapshot a
    // concurrent thread could mutate the input list mid-call and later chunks
    // would observe the change (or raise IndexError). Python strings are
    // immutable, so the snapshot's element values are stable (#239 review).
    let texts = texts.to_tuple();
    let len = texts.len();
    if len > crate::MAX_BATCH_SIZE {
        return Err(crate::ErrorRepr::BatchTooLarge {
            len,
            max: crate::MAX_BATCH_SIZE,
        }
        .into());
    }
    crate::transliterate::validate_lang(lang)?;
    // `errors="strict"` (#184) raises on the first untranslatable character of
    // the first item that has one (`None`); otherwise the mode is the parsed ErrorMode.
    let on_unknown = if errors == "strict" {
        None
    } else {
        Some(ErrorMode::parse(errors)?)
    };
    // Own the borrowed args so the compute loop holds no Python-borrowed data.
    let lang = lang.map(str::to_owned);
    let replace_with = replace_with.to_owned();

    // #239: transliterate in chunks, each read with the GIL held and computed with it
    // released (#70), so other Python threads run during the compute loop. Each item's
    // UTF-8 is borrowed, not copied: the snapshot tuple holds every string alive for the
    // whole call, and `str` is immutable, so the borrow stays valid while the GIL is
    // released. An item the engine leaves unchanged (a borrowed result, the same
    // contract as the scalar path's) comes back as the original object; only a changed
    // one allocates. The copy-in, copy-out form cost more per item than a loop of
    // single calls, which return the original object the same way. All-or-raise is
    // preserved; a non-str element raises TypeError (the public wrapper's
    // `_validate_batch` already rejects those up front).
    let mut out: Vec<Bound<'py, PyAny>> = Vec::with_capacity(len);
    let mut start = 0;
    while start < len {
        let end = (start + crate::BATCH_CHUNK_SIZE).min(len);
        let items: Vec<Bound<'py, PyString>> = (start..end)
            .map(|i| Ok(texts.get_item(i)?.cast_into::<PyString>()?))
            .collect::<PyResult<_>>()?;
        let utf8: Vec<&str> = items
            .iter()
            .map(|item| item.to_str())
            .collect::<PyResult<_>>()?;
        let changed: Vec<Option<String>> = py.detach(|| -> PyResult<Vec<Option<String>>> {
            utf8.iter()
                .map(|text| -> PyResult<Option<String>> {
                    // The scalar path's body per item: the registered replacements
                    // (no-op unless any are registered, output-bounded), then the
                    // engine. `lang` was validated once, above.
                    Ok(
                        match crate::transliterate::transliterate_after_replacements(
                            text,
                            lang.as_deref(),
                            on_unknown,
                            &replace_with,
                            strict_iso9,
                            gost7034,
                            tones,
                        )? {
                            Cow::Borrowed(_) => None,
                            Cow::Owned(owned) => Some(owned),
                        },
                    )
                })
                .collect()
        })?;
        for (item, changed) in items.into_iter().zip(changed) {
            out.push(match changed {
                None => item.into_any(),
                Some(owned) => PyString::new(py, &owned).into_any(),
            });
        }
        start = end;
    }
    PyList::new(py, out)
}

/// Batch accent stripping: process a list of strings in a single PyO3 boundary
/// crossing.
///
/// Delegates to `strip_accents_into` rather than restating the algorithm (#822). It used
/// to run its own `nfd().filter(|c| !is_combining_mark(c)).nfc()` here, which is precisely the
/// stateless filter that `strip_accents_into`'s own comment rules out: whether a mark is
/// strippable depends on the base it sits on (#749). The batch path therefore deleted the
/// negation overlay the single path keeps, and inverted 45 mathematical relations —
/// `\u{2204}` ∄ became `\u{2203}` ∃, `\u{2260}` ≠ became `=`.
///
/// The batch function owns the boundary crossing and the released GIL; it does not own
/// the algorithm. One reusable buffer across the whole batch, as in the pipeline (#236).
#[pyfunction]
#[pyo3(signature = (texts,))]
pub fn _strip_accents_batch(py: Python<'_>, texts: Vec<String>) -> PyResult<Vec<String>> {
    if texts.len() > crate::MAX_BATCH_SIZE {
        return Err(crate::ErrorRepr::BatchTooLarge {
            len: texts.len(),
            max: crate::MAX_BATCH_SIZE,
        }
        .into());
    }
    // Pure-Rust loop with the GIL released (#70).
    Ok(py.detach(move || {
        let mut buf = String::new();
        texts
            .into_iter()
            .map(|text| {
                if text.is_ascii() {
                    text // move, no clone — Vec is consumed by into_iter()
                } else {
                    crate::transliterate::strip_accents_into(&text, &mut buf);
                    std::mem::take(&mut buf)
                }
            })
            .collect()
    }))
}
