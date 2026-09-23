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
    advance_past_trailing_modifiers, drop_marks_the_seam_would_bind, match_emoji_at,
    needs_separator_after_a_name, pad_emoji_replacement, presentation_len_at,
    strip_modifier_suffix, unnamed_emoji_len_at, CharWindow, VS15, VS16, ZWJ,
};
use crate::tables;
use crate::ErrorMode;

/// Sentinel for "no custom provider registered".
static GLOBAL_PROVIDER: LazyLock<RwLock<Option<Py<PyAny>>>> = LazyLock::new(|| RwLock::new(None));

/// Register a global Python emoji provider (or None to reset to default).
///
/// The old provider is dropped after the lock is released, never under it. Dropping
/// a `Py<PyAny>` while attached runs its `__del__` there and then, and that is
/// arbitrary Python: it can call `set_emoji_provider` or `demojize` (re-entering this
/// lock on its own thread), or give up the GIL (closing a file does) while another
/// thread's `demojize` takes the GIL and blocks on the read lock holding it. Both
/// hung the interpreter; the TLA+ model in `formal/tla/Concurrency` found them and
/// `tests/test_no_python_under_rust_locks.py` reproduces them.
pub fn set_provider(provider: Option<Py<PyAny>>) {
    let old = {
        let mut guard = crate::recover_lock(GLOBAL_PROVIDER.write(), "GLOBAL_PROVIDER");
        std::mem::replace(&mut *guard, provider)
    };
    drop(old);
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
        // `len <= try_len <= window.len()`, so this is in bounds; `take(len)` makes
        // that panic-free without an index (satisfies the FFI no-panic gate).
        let seq: Vec<u32> = window.iter().take(len).map(|c| *c as u32).collect();
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
    // Set with `last_was_emoji` when what was written is the emoji itself (`Preserve`)
    // rather than a word. A mark after it was on the emoji in the input and stays on it;
    // only an alphanumeric is separated, as #200 asks. `needs_separator_after_a_name` is
    // about a *name*, and asking it here split `🇦́` into `🇦 ́` (#996 review).
    let mut last_was_raw = false;

    while let Some(ch) = win.current() {
        // Skip orphaned variation selectors and ZWJ characters
        if ch == VS16 || ch == VS15 || ch == ZWJ {
            win.advance(1);
            // A removal: close the seam, as the pure-Rust scanner does.
            drop_marks_the_seam_would_bind(&mut win, &result);
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
                // A provider is asked before `match_emoji_at`, so it can claim a keycap's
                // base alone; the sweep below no longer takes `U+20E3` (#996), so the
                // keycap was left behind as an orphan mark (#996 review). A keycap base
                // claimed on its own takes the rest of its keycap with it.
                let consumed = match win.as_slice() {
                    ['0'..='9' | '#' | '*', ..] if consumed == 1 => {
                        presentation_len_at(win.as_slice()).unwrap_or(1)
                    }
                    _ => consumed,
                };
                pad_emoji_replacement(&mut result, &name);
                win.advance(consumed);
                advance_past_trailing_modifiers(&mut win);
                last_was_emoji = true;
                last_was_raw = false;
                continue;
            }
        }

        // Try built-in emoji tables
        if let Some((name, consumed)) = match_emoji_at(win.as_slice()) {
            let replacement = strip_modifier_suffix(name, strip_modifiers);
            pad_emoji_replacement(&mut result, replacement);
            win.advance(consumed);
            advance_past_trailing_modifiers(&mut win);
            last_was_emoji = true;
            last_was_raw = false;
            continue;
        }

        // An emoji that neither the provider nor CLDR names, or a lone Plane 14 tag.
        // This is the only branch `errors` governs, and until #990 the test was a block
        // range: `U+2600..27BF` is Miscellaneous Symbols and Dingbats, so `\u{2606}`
        // WHITE STAR and 776 other characters carrying no emoji property at all arrived
        // here and became `[?]`. `unnamed_emoji_len_at` measures the whole sequence, so
        // the modifiers travel with their base rather than being consumed by a second
        // hand-rolled loop — and it is shared with the pure-Rust scanner, so the two
        // cannot drift apart on what they rewrite.
        if let Some(consumed) = unnamed_emoji_len_at(win.as_slice()) {
            match error_mode {
                ErrorMode::Replace => result.push_str(replace_with),
                ErrorMode::Ignore => {}
                // `take` rather than a slice: the crate denies `indexing_slicing`, and
                // the run is already measured, so no bound needs asserting here.
                ErrorMode::Preserve => {
                    result.extend(win.as_slice().iter().take(consumed).copied());
                }
            }
            win.advance(consumed);
            // Parity with the recognized-emoji path (#200): a visible token flags the
            // position so a following alphanumeric is separated. Preserve always writes
            // the raw mark; Replace writes `replace_with`, which may be empty; Ignore
            // writes nothing. When nothing is written both flags keep their values, so a
            // name written *before* the dropped emoji is still separated from what
            // follows: resetting them glued it on, `😀🇦x` giving `grinning facex` (Lean
            // model, `formal/lean/Emoji`).
            let wrote = match error_mode {
                ErrorMode::Preserve => true,
                ErrorMode::Replace => !replace_with.is_empty(),
                ErrorMode::Ignore => false,
            };
            if wrote {
                last_was_emoji = true;
                last_was_raw = matches!(error_mode, ErrorMode::Preserve);
            } else {
                // Nothing visible written: what follows now meets what came before, and a
                // keycap or selector that binds to it would be an emoji the input never
                // had (the seam `replace_emoji` closes, #995 follow-up).
                drop_marks_the_seam_would_bind(&mut win, &result);
            }
            continue;
        }

        // Not an emoji — pass through unchanged, with a separator when the character
        // would otherwise join the name in front of it. `needs_separator_after_a_name`
        // is shared with the pure-Rust scanner: this site asked a narrower question than
        // that one for as long as both existed, which is how a combining mark could land
        // on a name here and not there (#992).
        let separate = if last_was_raw {
            ch.is_alphanumeric()
        } else {
            needs_separator_after_a_name(ch)
        };
        if last_was_emoji && separate {
            result.push(' ');
        }
        result.push(ch);
        last_was_emoji = false;
        last_was_raw = false;
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
#[pyo3(signature = (text, *, replacement=None, strip_modifiers=false, errors="replace", replace_with="[?]", provider=None))]
pub fn _demojize(
    py: Python<'_>,
    text: &str,
    replacement: Option<&str>,
    strip_modifiers: bool,
    errors: &str,
    replace_with: &str,
    provider: Option<Py<PyAny>>,
) -> PyResult<String> {
    // #972: a replacement is not a name, so it takes none of the naming machinery — not
    // the provider, not the error mode, not `strip_modifiers`. Those describe what to
    // *call* an emoji, and this caller has said they do not want it called anything.
    //
    // Ignored rather than rejected, unlike `digit_policy` on `TextPipeline`, because the
    // provider can be registered globally: refusing `demojize(text, replacement="")` in
    // a process that once called `set_emoji_provider` would fail on a setting the caller
    // never passed.
    if let Some(replacement) = replacement {
        return Ok(crate::emoji::demojize_rust_replace(text, replacement));
    }

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

/// Replace every emoji with one string, verbatim (#972).
#[pyfunction]
#[pyo3(name = "_replace_emoji")]
pub fn _replace_emoji(text: &str, replacement: &str) -> String {
    crate::emoji::demojize_rust_replace(text, replacement)
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
