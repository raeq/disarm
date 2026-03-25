//! Emoji-to-text expansion (demojize).
//!
//! Converts emoji sequences to their CLDR short-name text descriptions.
//! The matching engine handles ZWJ sequences, skin tone modifiers, flag
//! sequences, keycap sequences, and presentation selectors.
//!
//! Data is supplied by the built-in CLDR PHF tables or by a user-registered
//! Python provider via the EmojiProvider protocol.

use pyo3::prelude::*;
use pyo3::types::PyList;
use std::fmt::Write;
use std::sync::RwLock;

use std::sync::LazyLock;

use crate::tables;
use crate::ErrorMode;

/// Zero-Width Joiner — joins emoji into compound sequences (e.g. family groups).
const ZWJ: char = '\u{200D}';
/// Variation Selector 16 — request emoji presentation.
const VS16: char = '\u{FE0F}';
/// Variation Selector 15 — request text presentation.
const VS15: char = '\u{FE0E}';

/// Sentinel for "no custom provider registered".
static GLOBAL_PROVIDER: LazyLock<RwLock<Option<PyObject>>> = LazyLock::new(|| RwLock::new(None));

/// Register a global Python emoji provider (or None to reset to default).
pub fn set_provider(provider: Option<PyObject>) {
    let mut guard = crate::recover_lock(GLOBAL_PROVIDER.write());
    *guard = provider;
}

/// Write a slice of codepoints as an uppercase hex key into `buf`, reusing it.
///
/// Clears `buf` before writing.  Using a caller-supplied buffer avoids
/// repeated allocation inside the O(max_seq_len) candidate loop in
/// `match_emoji_at`.
fn encode_key_into(buf: &mut String, cps: &[char]) {
    buf.clear();
    for (i, &c) in cps.iter().enumerate() {
        if i > 0 {
            buf.push('_');
        }
        // write! to a String is infallible (String's fmt::Write impl never errors).
        let _ = write!(buf, "{:04X}", c as u32);
    }
}

/// Try to match the longest emoji sequence starting at `chars[pos]`.
/// Returns (short_name, number_of_chars_consumed) or None.
fn match_emoji_at(chars: &[char], pos: usize) -> Option<(&'static str, usize)> {
    let ch = chars[pos];
    let remaining = chars.len() - pos;

    // Try multi-codepoint sequences first (longest match)
    if tables::is_emoji_multi_starter(ch) {
        let max_len = tables::max_emoji_seq_len().min(remaining);
        // Build the full key once for max_len, then use pre-computed separator
        // positions for O(1) truncation instead of rfind('_') per iteration.
        let mut key_buf = String::with_capacity(max_len * 6);
        encode_key_into(&mut key_buf, &chars[pos..pos + max_len]);

        // Pre-compute positions of '_' separators for O(1) indexed truncation.
        // sep_positions[i] = byte offset of the (i+1)-th '_' separator.
        // To get a key for `len` codepoints, truncate at sep_positions[len-2]
        // (since the first codepoint has no leading separator).
        let sep_positions: Vec<usize> = key_buf
            .bytes()
            .enumerate()
            .filter_map(|(i, b)| if b == b'_' { Some(i) } else { None })
            .collect();

        // Try longest sequences first, truncating the key progressively
        for len in (2..=max_len).rev() {
            let last = chars[pos + len - 1];
            // Skip sequences that end with a variation selector or ZWJ
            // (they're incomplete).
            if last == ZWJ || last == VS16 || last == VS15 {
                continue;
            }

            // Truncate key to `len` codepoints using the separator index.
            // sep_positions has max_len-1 entries (one per separator between codepoints).
            // For `len` codepoints we need `len-1` separators, so truncate at
            // sep_positions[len-1] (the start of the (len+1)-th codepoint's separator).
            let key_slice = if len < max_len {
                &key_buf[..sep_positions[len - 1]]
            } else {
                &key_buf
            };

            if let Some(name) = tables::lookup_emoji_multi(key_slice) {
                return Some((name, len));
            }
        }
    }

    // Try single-codepoint lookup
    if let Some(name) = tables::lookup_emoji_single(ch) {
        // Check if followed by variation selector — consume it too
        let consumed =
            if pos + 1 < chars.len() && (chars[pos + 1] == VS16 || chars[pos + 1] == VS15) {
                2
            } else {
                1
            };
        return Some((name, consumed));
    }

    None
}

/// Emit a Python `UserWarning`, falling back to stderr if `warnings.warn` fails.
///
/// This ensures diagnostic messages are never silently swallowed even if the
/// Python interpreter is in a state where `warnings` is unavailable.
fn emit_warning(py: Python<'_>, msg: &str) {
    if py
        .import("warnings")
        .and_then(|w| w.call_method1("warn", (msg,)))
        .is_err()
    {
        eprintln!("translit warning: {msg}");
    }
}

/// Try a Python provider's lookup method.
///
/// Returns `Some((name, chars_consumed))` if the provider recognises the
/// sequence starting at `chars[pos]`, `None` otherwise.
///
/// If the provider raises an exception or returns a non-string value, a
/// Python `UserWarning` is issued via `warnings.warn` and the call falls
/// through to the built-in CLDR tables.
fn try_python_provider(
    py: Python<'_>,
    provider: &PyObject,
    chars: &[char],
    pos: usize,
    max_len: usize,
) -> Option<(String, usize)> {
    let remaining = chars.len() - pos;
    let try_len = max_len.min(remaining);

    // Try longest first
    for len in (1..=try_len).rev() {
        let seq: Vec<u32> = chars[pos..pos + len].iter().map(|c| *c as u32).collect();
        let py_seq = PyList::new(py, &seq).ok()?;

        let result = match provider.call_method1(py, "lookup", (py_seq,)) {
            Ok(r) => r,
            Err(e) => {
                let msg =
                    format!("EmojiProvider.lookup() raised an exception and will be ignored: {e}");
                emit_warning(py, &msg);
                return None;
            }
        };

        if !result.is_none(py) {
            match result.extract::<String>(py) {
                Ok(name) => return Some((name, len)),
                Err(e) => {
                    let msg = format!(
                        "EmojiProvider.lookup() returned a non-string value \
                         and will be ignored: {e}"
                    );
                    emit_warning(py, &msg);
                    return None;
                }
            }
        }
    }
    None
}

/// Core demojize implementation.
fn demojize_impl(
    py: Python<'_>,
    text: &str,
    strip_modifiers: bool,
    error_mode: ErrorMode,
    replace_with: &str,
    provider: Option<&PyObject>,
) -> String {
    // Fast path: pure-ASCII text cannot contain emoji.
    if text.is_ascii() {
        return text.to_owned();
    }

    let chars: Vec<char> = text.chars().collect();
    let mut result = String::with_capacity(text.len());
    let mut i = 0;

    while i < chars.len() {
        let ch = chars[i];

        // Skip orphaned variation selectors and ZWJ characters
        if ch == VS16 || ch == VS15 || ch == ZWJ {
            i += 1;
            continue;
        }

        // Try custom Python provider first (if set)
        if let Some(prov) = provider {
            if let Some((name, consumed)) =
                try_python_provider(py, prov, &chars, i, tables::max_emoji_seq_len())
            {
                result.push_str(&name);
                i += consumed;
                // Consume any trailing orphaned ZWJ/VS after matched emoji
                while i < chars.len() && is_emoji_modifier(chars[i]) {
                    i += 1;
                }
                continue;
            }
        }

        // Try built-in emoji tables
        if let Some((name, consumed)) = match_emoji_at(&chars, i) {
            result.push_str(strip_modifier_suffix(name, strip_modifiers));
            i += consumed;
            // Consume any trailing orphaned ZWJ/VS after matched emoji
            while i < chars.len() && is_emoji_modifier(chars[i]) {
                i += 1;
            }
            continue;
        }

        // Check if this is an emoji-like codepoint that we don't have data for
        // (i.e., in emoji ranges but not in our table)
        if is_emoji_codepoint(ch) {
            match error_mode {
                ErrorMode::Replace => result.push_str(replace_with),
                ErrorMode::Ignore => {}
                ErrorMode::Preserve => result.push(ch),
            }
            i += 1;
            // Consume any following variation selectors or modifiers
            while i < chars.len() && is_emoji_modifier(chars[i]) {
                if let ErrorMode::Preserve = error_mode {
                    result.push(chars[i]);
                }
                i += 1;
            }
            continue;
        }

        // Not an emoji — pass through unchanged
        result.push(ch);
        i += 1;
    }

    result
}

/// Check if a codepoint is in an emoji range but not in our data.
fn is_emoji_codepoint(ch: char) -> bool {
    let cp = ch as u32;
    // Emoticons, Dingbats, Symbols, Transport, Supplemental Symbols, etc.
    matches!(cp,
        0x2600..=0x27BF |     // Misc Symbols, Dingbats
        0x2B50..=0x2B55 |     // Additional symbols
        0xFE00..=0xFE0F |     // Variation selectors
        0x1F000..=0x1FAFF |   // Supplementary emoji blocks
        0x1FC00..=0x1FFFF |   // Future emoji blocks
        0xE0020..=0xE007F     // Tags (used in flag sequences)
    )
}

/// Check if a codepoint is an emoji modifier (skin tone, ZWJ, VS, tag).
fn is_emoji_modifier(ch: char) -> bool {
    let cp = ch as u32;
    matches!(cp,
        0x200D |              // ZWJ
        0xFE0E..=0xFE0F |    // Variation selectors
        0x1F3FB..=0x1F3FF |   // Skin tone modifiers
        0xE0020..=0xE007F |   // Tags
        0x20E3               // Combining Enclosing Keycap
    )
}

// --- PyO3 bindings ---

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
    provider: Option<PyObject>,
) -> PyResult<String> {
    let error_mode = ErrorMode::from_str(errors)?;

    // Determine which provider to use:
    // 1. Explicit per-call provider
    // 2. Global registered provider
    // 3. Built-in default (None)
    let effective_provider: Option<PyObject> = if provider.is_some() {
        provider
    } else {
        let guard = crate::recover_lock(GLOBAL_PROVIDER.read());
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
#[pyfunction]
#[pyo3(name = "_set_emoji_provider")]
#[pyo3(signature = (provider=None))]
pub fn _set_emoji_provider(provider: Option<PyObject>) {
    set_provider(provider);
}

/// Strip modifier suffixes (": light skin tone", etc.) from a CLDR short name
/// when `strip_modifiers` is true.
#[inline]
fn strip_modifier_suffix(name: &str, strip_modifiers: bool) -> &str {
    if strip_modifiers {
        if let Some(base_end) = name.find(": ") {
            return &name[..base_end];
        }
    }
    name
}

/// Pure Rust demojize for use by TextPipeline (no Python provider support).
pub fn demojize_rust(text: &str, strip_modifiers: bool) -> String {
    // Fast path: pure-ASCII text cannot contain emoji.
    if text.is_ascii() {
        return text.to_owned();
    }

    let chars: Vec<char> = text.chars().collect();
    let mut result = String::with_capacity(text.len());
    let mut i = 0;

    while i < chars.len() {
        let ch = chars[i];

        if ch == VS16 || ch == VS15 || ch == ZWJ {
            i += 1;
            continue;
        }

        if let Some((name, consumed)) = match_emoji_at(&chars, i) {
            result.push_str(strip_modifier_suffix(name, strip_modifiers));
            i += consumed;
            while i < chars.len() && is_emoji_modifier(chars[i]) {
                i += 1;
            }
            continue;
        }

        // Unknown emoji — drop it (Ignore mode)
        if is_emoji_codepoint(ch) {
            i += 1;
            while i < chars.len() && is_emoji_modifier(chars[i]) {
                i += 1;
            }
            continue;
        }

        result.push(ch);
        i += 1;
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encode_key_single() {
        let mut buf = String::new();
        encode_key_into(&mut buf, &['\u{1F600}']);
        assert_eq!(buf, "1F600");
    }

    #[test]
    fn test_encode_key_multi() {
        let mut buf = String::new();
        encode_key_into(&mut buf, &['\u{1F468}', ZWJ, '\u{1F469}']);
        assert_eq!(buf, "1F468_200D_1F469");
    }

    #[test]
    fn test_is_emoji_codepoint() {
        assert!(is_emoji_codepoint('\u{1F600}'));
        assert!(is_emoji_codepoint('\u{2600}'));
        assert!(!is_emoji_codepoint('A'));
        assert!(!is_emoji_codepoint('€'));
    }

    #[test]
    fn test_is_emoji_modifier() {
        assert!(is_emoji_modifier(ZWJ)); // ZWJ
        assert!(is_emoji_modifier(VS16)); // VS16
        assert!(is_emoji_modifier('\u{1F3FB}')); // Light skin tone
        assert!(!is_emoji_modifier('A'));
    }

    #[test]
    fn test_match_single_emoji() {
        let chars: Vec<char> = "😀".chars().collect();
        let result = match_emoji_at(&chars, 0);
        assert!(result.is_some());
        let (name, consumed) = result.unwrap();
        assert_eq!(name, "grinning face");
        assert_eq!(consumed, 1);
    }

    #[test]
    fn test_demojize_rust_basic() {
        let result = demojize_rust("Hello 😀 world", false);
        assert_eq!(result, "Hello grinning face world");
    }

    #[test]
    fn test_demojize_rust_no_emoji() {
        let result = demojize_rust("Hello world", false);
        assert_eq!(result, "Hello world");
    }

    #[test]
    fn test_demojize_rust_multiple() {
        let result = demojize_rust("😀😂", false);
        assert_eq!(result, "grinning faceface with tears of joy");
    }

    #[test]
    fn test_demojize_rust_empty() {
        assert_eq!(demojize_rust("", false), "");
    }
}
