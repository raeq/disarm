//! #208: binding-neutral, opt-in, zero-cost-when-off diagnostic logging.
//!
//! The [`log`](https://docs.rs/log) crate is an **optional** dependency behind
//! the `log` feature (default OFF). When the feature is off, the `tl_*!` macros
//! below expand to nothing — there is no `log` dependency, no callsite statics,
//! and no atomic level load — so the shipped artifact pays literally zero cost
//! and the hot-path machine code is byte-identical to a build without logging.
//!
//! When the feature is on but a level is disabled at runtime, a `log` macro is a
//! `STATIC_MAX_LEVEL` compile-time check plus one relaxed atomic load+compare
//! with its arguments left unevaluated — and we only ever place these at core
//! API **boundaries**, never inside a per-codepoint / per-token loop.
//!
//! ## Binding-neutral
//! The core depends only on the `log` facade. The *sink* (where records actually
//! go) is each binding's concern: native Rust installs `env_logger` /
//! `tracing-subscriber`; the Python layer bridges via `pyo3-log`; C-ABI bindings
//! (Ruby/Java/Go/PHP/R) register a callback `Log` impl. No `pyo3`/`napi`/`wasm`
//! ever appears in this path.
//!
//! ## Redaction (hard requirement, enforced here in core)
//! Default-level records (ERROR/WARN/INFO/DEBUG) carry **only metadata** — never
//! input or output content: function name, `lang`, `errors` mode, flags, input
//! length (bytes + chars), output length, counts, durations, and `Error::code`.
//! Content logging is a separate, louder gate ([`tl_trace_content!`], behind
//! `log-content` + TRACE) and even then routes the sample through
//! [`crate::error::truncate_error_text`] (80-byte, char-boundary) — the macro
//! enforces the truncation, callers cannot bypass it. A sentinel test
//! (`tests/logging.rs`) fails the build if any default-level record contains the
//! input.

/// `target` every disarm record is tagged with, so a sink can filter on it.
#[cfg(feature = "log")]
pub(crate) const TARGET: &str = "disarm";

macro_rules! tl_error {
    ($($arg:tt)+) => {{
        #[cfg(feature = "log")]
        log::error!(target: $crate::obs::TARGET, $($arg)+);
    }};
}

macro_rules! tl_warn {
    ($($arg:tt)+) => {{
        #[cfg(feature = "log")]
        log::warn!(target: $crate::obs::TARGET, $($arg)+);
    }};
}

macro_rules! tl_info {
    ($($arg:tt)+) => {{
        #[cfg(feature = "log")]
        log::info!(target: $crate::obs::TARGET, $($arg)+);
    }};
}

// Only invoked from inside `#[cfg(feature = "log")]` blocks (the DEBUG records
// pair with a runtime-gated timer), so it is "unused" in a default build.
#[allow(unused_macros)]
macro_rules! tl_debug {
    ($($arg:tt)+) => {{
        #[cfg(feature = "log")]
        log::debug!(target: $crate::obs::TARGET, $($arg)+);
    }};
}

/// TRACE-level **content** record — behind `log-content` only, documented unsafe
/// for production and never reachable on a default build. Takes a static `label`
/// and a `text` value; the macro **always** routes `text` through
/// [`crate::error::truncate_error_text`] (80-byte, char-boundary), so a caller
/// cannot accidentally emit untruncated content.
///
/// `tl_trace_content!("transliterate.in", text)`
#[allow(unused_macros)]
macro_rules! tl_trace_content {
    ($label:expr, $text:expr $(,)?) => {{
        #[cfg(feature = "log-content")]
        log::trace!(
            target: $crate::obs::TARGET,
            "{}: {:?}",
            $label,
            $crate::error::truncate_error_text($text),
        );
    }};
}
