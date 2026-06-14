//! PyO3 shims for `crate::emoji` (Layer-1).
//!
//! emoji is Python-coupled via a custom emoji-provider callback: a registered
//! Python object implementing the `EmojiProvider` protocol can override the
//! built-in CLDR tables. The provider object, its global registration slot, the
//! provider-aware demojize loop, and the two `#[pyfunction]` entry points are all
//! inherently binding-layer (the provider is a Python object), so they live here.
//! The pure CLDR matching/replacement helpers stay in Layer 1 (`crate::emoji`).

use std::sync::LazyLock;
use std::sync::RwLock;

use pyo3::prelude::*;
use pyo3::types::PyList;

use crate::emoji::{
    is_emoji_codepoint, is_emoji_modifier, match_emoji_at, pad_emoji_replacement,
    strip_modifier_suffix, CharWindow, VS15, VS16, ZWJ,
};
use crate::tables;
use crate::ErrorMode;

/// Sentinel for "no custom provider registered".
static GLOBAL_PROVIDER: LazyLock<RwLock<Option<Py<PyAny>>>> = LazyLock::new(|| RwLock::new(None));

/// Register a global Python emoji provider (or None to reset to default).
pub fn set_provider(provider: Option<Py<PyAny>>) {
    let mut guard = crate::recover_lock(GLOBAL_PROVIDER.write(), "GLOBAL_PROVIDER");
    *guard = provider;
}

/// Try a Python provider's lookup method.
///
/// Returns `Some((name, chars_consumed))` if the provider recognises the
/// sequence starting at `window[0]`, `None` otherwise.
///
/// If the provider raises an exception or returns a non-string value, a
/// Python `UserWarning` is issued via `warnings.warn` and the call falls
/// through to the built-in CLDR tables.
///
/// # #113
/// Takes the window slice directly instead of `(&[char], pos)` — pos is
/// always 0 from the window's perspective.
fn try_python_provider(
    py: Python<'_>,
    provider: &Py<PyAny>,
    window: &[char],
    max_len: usize,
) -> Option<(String, usize)> {
    let try_len = max_len.min(window.len());

    // Try longest first
    for len in (1..=try_len).rev() {
        let seq: Vec<u32> = window[..len].iter().map(|c| *c as u32).collect();
        let py_seq = PyList::new(py, &seq).ok()?;

        let result = match provider.call_method1(py, "lookup", (py_seq,)) {
            Ok(r) => r,
            Err(e) => {
                // #251: route through the single warning helper with a uniform
                // `disarm:` prefix so all diagnostics share one log-grep token.
                let msg = format!(
                    "disarm: EmojiProvider.lookup() raised an exception and will be ignored: {e}"
                );
                crate::emit_py_warning(py, &msg);
                return None;
            }
        };

        if !result.is_none(py) {
            match result.extract::<String>(py) {
                Ok(name) => return Some((name, len)),
                Err(e) => {
                    let msg = format!(
                        "disarm: EmojiProvider.lookup() returned a non-string value \
                         and will be ignored: {e}"
                    );
                    crate::emit_py_warning(py, &msg);
                    return None;
                }
            }
        }
    }
    None
}

/// Core demojize implementation.
///
/// # #113
/// Uses a `CharWindow` sliding buffer instead of `Vec<char>` to avoid
/// materialising the full input for non-ASCII text.
fn demojize_impl(
    py: Python<'_>,
    text: &str,
    strip_modifiers: bool,
    error_mode: ErrorMode,
    replace_with: &str,
    provider: Option<&Py<PyAny>>,
) -> String {
    // Fast path: pure-ASCII text cannot contain emoji.
    if text.is_ascii() {
        return text.to_owned();
    }

    let mut win = CharWindow::new(text.chars());
    let mut result = String::with_capacity(text.len());
    let mut last_was_emoji = false;

    while let Some(ch) = win.current() {
        // Skip orphaned variation selectors and ZWJ characters
        if ch == VS16 || ch == VS15 || ch == ZWJ {
            win.advance(1);
            continue;
        }

        // Try custom Python provider first (if set).
        //
        // The window fed to the provider is `win.as_slice()`, capped at
        // `MAX_WINDOW` (9) chars by `CharWindow`'s stack buffer, so a custom
        // provider can only ever match sequences up to 9 codepoints — the
        // longest built-in CLDR sequence (`max_emoji_seq_len()`). Longer
        // provider-supported sequences are silently unmatchable; this cap is
        // documented on `set_emoji_provider` / `EmojiProvider.lookup` (#199).
        // Widening it would enlarge the per-position scan window for every
        // demojize call, so it is intentionally fixed.
        if let Some(prov) = provider {
            if let Some((name, consumed)) =
                try_python_provider(py, prov, win.as_slice(), tables::max_emoji_seq_len())
            {
                pad_emoji_replacement(&mut result, &name);
                win.advance(consumed);
                // Skip trailing modifier codepoints
                while win.current().is_some_and(is_emoji_modifier) {
                    win.advance(1);
                }
                last_was_emoji = true;
                continue;
            }
        }

        // Try built-in emoji tables
        if let Some((name, consumed)) = match_emoji_at(win.as_slice()) {
            let replacement = strip_modifier_suffix(name, strip_modifiers);
            pad_emoji_replacement(&mut result, replacement);
            win.advance(consumed);
            while win.current().is_some_and(is_emoji_modifier) {
                win.advance(1);
            }
            last_was_emoji = true;
            continue;
        }

        // Check if this is an emoji-like codepoint that we don't have data for
        if is_emoji_codepoint(ch) {
            match error_mode {
                ErrorMode::Replace => result.push_str(replace_with),
                ErrorMode::Ignore => {}
                ErrorMode::Preserve => result.push(ch),
            }
            win.advance(1);
            while let Some(mc) = win.current() {
                if !is_emoji_modifier(mc) {
                    break;
                }
                if let ErrorMode::Preserve = error_mode {
                    result.push(mc);
                }
                win.advance(1);
            }
            // Parity with the recognized-emoji path (#200): flag the position so
            // a following alphanumeric is separated by a space — but only when a
            // *visible* token was actually emitted, otherwise we inject a
            // spurious leading space. Preserve always writes the raw mark;
            // Replace writes `replace_with`, which may be empty ("drop it");
            // Ignore writes nothing.
            last_was_emoji = match error_mode {
                ErrorMode::Preserve => true,
                ErrorMode::Replace => !replace_with.is_empty(),
                ErrorMode::Ignore => false,
            };
            continue;
        }

        // Not an emoji — pass through unchanged.
        // Add space after emoji replacement if the text runs into
        // alphanumeric content (not punctuation or whitespace).
        if last_was_emoji && ch.is_alphanumeric() {
            result.push(' ');
        }
        result.push(ch);
        last_was_emoji = false;
        win.advance(1);
    }

    result
}

/// Expand emoji sequences to their CLDR short-name text descriptions.
///
/// Output is always the bare CLDR short name as plain text.
/// Supports an optional custom emoji provider; falls back to the global
/// provider or the built-in default (latest English CLDR).
#[pyfunction]
#[pyo3(name = "_demojize")]
#[pyo3(signature = (text, *, strip_modifiers=false, errors="replace", replace_with="[?]", provider=None))]
pub fn _demojize(
    py: Python<'_>,
    text: &str,
    strip_modifiers: bool,
    errors: &str,
    replace_with: &str,
    provider: Option<Py<PyAny>>,
) -> PyResult<String> {
    let error_mode = ErrorMode::parse(errors)?;

    // Determine which provider to use:
    // 1. Explicit per-call provider
    // 2. Global registered provider
    // 3. Built-in default (None)
    let effective_provider: Option<Py<PyAny>> = if provider.is_some() {
        provider
    } else {
        let guard = crate::recover_lock(GLOBAL_PROVIDER.read(), "GLOBAL_PROVIDER");
        guard.as_ref().map(|p| p.clone_ref(py))
    };

    Ok(demojize_impl(
        py,
        text,
        strip_modifiers,
        error_mode,
        replace_with,
        effective_provider.as_ref(),
    ))
}

/// Set or reset the global emoji provider for all demojize calls.
///
/// The provider must implement the `EmojiProvider` protocol:
///
/// ```python
/// class EmojiProvider(Protocol):
///     def lookup(self, sequence: list[int]) -> str | None: ...
/// ```
///
/// `sequence` is a list of Unicode codepoints (e.g. `[0x1F600]` for 😀, or
/// `[0x1F468, 0x200D, 0x1F469]` for a ZWJ family sequence).
/// Return the emoji's text description, or `None` to fall through to the
/// built-in CLDR tables.
///
/// **Exception safety**: if the provider's `lookup` method raises an exception
/// or returns a non-string value, a Python `UserWarning` is issued and the
/// built-in CLDR tables are consulted as a fallback.
///
/// Pass `None` to reset to the built-in default (latest English CLDR).
///
/// Rejected once [`seal_registrations`](crate::tables::seal_registrations) has
/// been called (#104): swapping the global emoji provider mutates process-global
/// canonicalization that every caller shares, so it must obey the same seal as
/// the other registration mutators.
#[pyfunction]
#[pyo3(name = "_set_emoji_provider")]
#[pyo3(signature = (provider=None))]
pub fn _set_emoji_provider(provider: Option<Py<PyAny>>) -> PyResult<()> {
    crate::transliterate::check_not_sealed("set_emoji_provider")?;
    set_provider(provider);
    Ok(())
}
