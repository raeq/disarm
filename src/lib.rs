//! Fast Unicode transliteration, slugification, and text normalization — Rust core.
//!
//! All public access goes through the Python package `translit`.
//! Rust-internal modules are marked `#[doc(hidden)]` and not part of the public API.

use pyo3::prelude::*;

// Core modules — `pub` so Criterion benchmarks (external crate) can access
// the pure-Rust implementation functions directly.
#[doc(hidden)]
pub mod case_fold;
#[doc(hidden)]
pub mod confusables;
mod emoji;
mod encoding;
#[doc(hidden)]
pub mod filename;
#[doc(hidden)]
pub mod grapheme;
mod hostname;
#[doc(hidden)]
pub mod normalize;
mod pipeline;
#[doc(hidden)]
pub mod presets;
#[doc(hidden)]
pub mod scripts;
#[doc(hidden)]
pub mod slugify;
// Generated PHF code contains unseparated integer literals and non-NFC
// Unicode confusable characters (which is the point of the confusables table).
#[allow(clippy::unreadable_literal, clippy::unicode_not_nfc)]
#[doc(hidden)]
pub mod tables;
#[doc(hidden)]
pub mod transliterate;
#[doc(hidden)]
pub mod unicode_ranges;
#[doc(hidden)]
pub mod whitespace;

/// Internal Rust module. Not part of the public Python API.
/// All public access goes through python/translit/__init__.py.
#[pymodule]
#[pyo3(name = "_translit")]
fn _translit(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Core transforms
    m.add_function(wrap_pyfunction!(transliterate::_transliterate, m)?)?;
    m.add_function(wrap_pyfunction!(transliterate::_strip_accents, m)?)?;
    m.add_function(wrap_pyfunction!(transliterate::_is_ascii, m)?)?;
    m.add_function(wrap_pyfunction!(transliterate::_list_langs, m)?)?;
    m.add_function(wrap_pyfunction!(transliterate::_register_lang, m)?)?;
    m.add_function(wrap_pyfunction!(transliterate::_register_replacements, m)?)?;
    m.add_function(wrap_pyfunction!(transliterate::_remove_replacement, m)?)?;
    m.add_function(wrap_pyfunction!(transliterate::_clear_replacements, m)?)?;
    m.add_function(wrap_pyfunction!(slugify::_slugify, m)?)?;
    m.add_function(wrap_pyfunction!(normalize::_normalize, m)?)?;
    m.add_function(wrap_pyfunction!(normalize::_is_normalized, m)?)?;
    m.add_function(wrap_pyfunction!(confusables::_normalize_confusables, m)?)?;
    m.add_function(wrap_pyfunction!(confusables::_is_confusable, m)?)?;
    m.add_function(wrap_pyfunction!(filename::_sanitize_filename, m)?)?;
    m.add_function(wrap_pyfunction!(case_fold::_fold_case, m)?)?;
    m.add_function(wrap_pyfunction!(whitespace::_collapse_whitespace, m)?)?;
    m.add_function(wrap_pyfunction!(scripts::_detect_scripts, m)?)?;
    m.add_function(wrap_pyfunction!(scripts::_is_mixed_script, m)?)?;

    // Batch APIs (single PyO3 boundary crossing for N strings)
    m.add_function(wrap_pyfunction!(transliterate::_transliterate_batch, m)?)?;
    m.add_function(wrap_pyfunction!(transliterate::_strip_accents_batch, m)?)?;
    m.add_function(wrap_pyfunction!(slugify::_slugify_batch, m)?)?;
    m.add_function(wrap_pyfunction!(normalize::_normalize_batch, m)?)?;

    // Stateful classes
    m.add_class::<slugify::_Slugifier>()?;
    m.add_class::<slugify::_UniqueSlugifier>()?;
    m.add_class::<pipeline::_TextPipeline>()?;

    // Precompiled pipelines
    m.add_function(wrap_pyfunction!(presets::_security_clean, m)?)?;
    m.add_function(wrap_pyfunction!(presets::_ml_normalize, m)?)?;
    m.add_function(wrap_pyfunction!(presets::_catalog_key, m)?)?;
    m.add_function(wrap_pyfunction!(presets::_display_clean, m)?)?;
    m.add_function(wrap_pyfunction!(presets::_strip_bidi, m)?)?;

    // Grapheme cluster functions
    m.add_function(wrap_pyfunction!(grapheme::_grapheme_len, m)?)?;
    m.add_function(wrap_pyfunction!(grapheme::_grapheme_split, m)?)?;
    m.add_function(wrap_pyfunction!(grapheme::_grapheme_truncate, m)?)?;

    // Hostname safety
    m.add_function(wrap_pyfunction!(hostname::_is_safe_hostname, m)?)?;
    m.add_class::<hostname::SafeHostnameDetails>()?;

    // Encoding detection
    m.add_function(wrap_pyfunction!(encoding::_detect_encoding, m)?)?;
    m.add_function(wrap_pyfunction!(encoding::_decode_to_utf8, m)?)?;

    // Emoji
    m.add_function(wrap_pyfunction!(emoji::_demojize, m)?)?;
    m.add_function(wrap_pyfunction!(emoji::_set_emoji_provider, m)?)?;

    // Custom exception
    m.add("TranslitError", m.py().get_type::<TranslitError>())?;

    Ok(())
}

/// Recover from a poisoned `RwLock` or `Mutex`, logging a warning to stderr.
///
/// A poisoned lock means a thread panicked while holding it.  The underlying
/// data may be in an inconsistent state.  We log a diagnostic and continue
/// rather than propagating the panic to every subsequent caller.
pub(crate) fn recover_lock<T>(result: std::sync::LockResult<T>) -> T {
    result.unwrap_or_else(|e| {
        eprintln!(
            "translit: RwLock poisoned (a thread panicked while holding the lock). \
             Recovering from poisoned state — data may be inconsistent. \
             This is a bug; please report it."
        );
        e.into_inner()
    })
}

pyo3::create_exception!(
    translit,
    TranslitError,
    pyo3::exceptions::PyValueError,
    "Exception raised by translit for invalid input or internal Rust errors.\n\
     Exposed to Python as ``translit.TranslitError``, a subclass of ``ValueError``."
);
