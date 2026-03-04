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

use once_cell::sync::Lazy;

use crate::tables;

/// Sentinel for "no custom provider registered".
static GLOBAL_PROVIDER: Lazy<RwLock<Option<PyObject>>> = Lazy::new(|| RwLock::new(None));

/// Register a global Python emoji provider (or None to reset to default).
pub fn set_provider(provider: Option<PyObject>) {
    let mut guard = GLOBAL_PROVIDER.write().unwrap_or_else(|e| e.into_inner());
    *guard = provider;
}

/// Error handling mode — mirrors transliterate.
#[derive(Debug, Clone, Copy)]
enum ErrorMode {
    Replace,
    Ignore,
    Preserve,
}

impl ErrorMode {
    fn from_str(s: &str) -> PyResult<Self> {
        match s {
            "replace" => Ok(Self::Replace),
            "ignore" => Ok(Self::Ignore),
            "preserve" => Ok(Self::Preserve),
            _ => Err(pyo3::exceptions::PyValueError::new_err(format!(
                "errors must be 'replace', 'ignore', or 'preserve', got '{s}'"
            ))),
        }
    }
}

/// Encode a slice of codepoints as an uppercase hex key for PHF lookup.
fn encode_key(cps: &[char]) -> String {
    let mut key = String::with_capacity(cps.len() * 6);
    for (i, &c) in cps.iter().enumerate() {
        if i > 0 {
            key.push('_');
        }
        // SAFETY: write! to a String is infallible (String's fmt::Write impl never errors).
        let _ = write!(key, "{:04X}", c as u32);
    }
    key
}

/// Try to match the longest emoji sequence starting at `chars[pos]`.
/// Returns (short_name, number_of_chars_consumed) or None.
fn match_emoji_at(chars: &[char], pos: usize) -> Option<(&'static str, usize)> {
    let ch = chars[pos];
    let remaining = chars.len() - pos;

    // Try multi-codepoint sequences first (longest match)
    if tables::is_emoji_multi_starter(ch) {
        let max_len = tables::max_emoji_seq_len().min(remaining);
        // Try longest sequences first
        for len in (2..=max_len).rev() {
            let seq = &chars[pos..pos + len];

            // Skip sequences that end with a variation selector or ZWJ
            // (they're incomplete)
            let last = seq[seq.len() - 1];
            if last == '\u{200D}' || last == '\u{FE0F}' || last == '\u{FE0E}' {
                continue;
            }

            let key = encode_key(seq);
            if let Some(name) = tables::lookup_emoji_multi(&key) {
                return Some((name, len));
            }
        }
    }

    // Try single-codepoint lookup
    if let Some(name) = tables::lookup_emoji_single(ch) {
        // Check if followed by variation selector — consume it too
        let consumed = if pos + 1 < chars.len()
            && (chars[pos + 1] == '\u{FE0F}' || chars[pos + 1] == '\u{FE0E}')
        {
            2
        } else {
            1
        };
        return Some((name, consumed));
    }

    None
}

/// Try a Python provider's lookup method.
/// Returns Some(name) if the provider knows this sequence.
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
        let result = provider.call_method1(py, "lookup", (py_seq,)).ok()?;
        if !result.is_none(py) {
            let name: String = result.extract(py).ok()?;
            return Some((name, len));
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
    let chars: Vec<char> = text.chars().collect();
    let mut result = String::with_capacity(text.len());
    let mut i = 0;

    while i < chars.len() {
        let ch = chars[i];

        // Skip orphaned variation selectors and ZWJ characters
        if ch == '\u{FE0F}' || ch == '\u{FE0E}' || ch == '\u{200D}' {
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
            // If strip_modifiers, check if this is a modified variant
            // (contains ": " indicating skin tone or other modifier)
            let output_name = if strip_modifiers {
                if let Some(base_end) = name.find(": ") {
                    &name[..base_end]
                } else {
                    name
                }
            } else {
                name
            };
            result.push_str(output_name);
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
        let guard = GLOBAL_PROVIDER.read().unwrap_or_else(|e| e.into_inner());
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
/// Pass `None` to reset to the built-in default (latest English CLDR).
#[pyfunction]
#[pyo3(name = "_set_emoji_provider")]
#[pyo3(signature = (provider=None))]
pub fn _set_emoji_provider(provider: Option<PyObject>) {
    set_provider(provider);
}

/// Pure Rust demojize for use by TextPipeline (no Python provider support).
pub fn demojize_rust(text: &str, strip_modifiers: bool) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut result = String::with_capacity(text.len());
    let mut i = 0;

    while i < chars.len() {
        let ch = chars[i];

        if ch == '\u{FE0F}' || ch == '\u{FE0E}' {
            i += 1;
            continue;
        }

        if let Some((name, consumed)) = match_emoji_at(&chars, i) {
            let output_name = if strip_modifiers {
                if let Some(base_end) = name.find(": ") {
                    &name[..base_end]
                } else {
                    name
                }
            } else {
                name
            };
            result.push_str(output_name);
            i += consumed;
            // Consume any trailing orphaned ZWJ/VS after matched emoji
            while i < chars.len() && is_emoji_modifier(chars[i]) {
                i += 1;
            }
            continue;
        }

        // Unknown emoji — use replace mode with empty string (drop it)
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
        assert_eq!(encode_key(&['\u{1F600}']), "1F600");
    }

    #[test]
    fn test_encode_key_multi() {
        assert_eq!(
            encode_key(&['\u{1F468}', '\u{200D}', '\u{1F469}']),
            "1F468_200D_1F469"
        );
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
        assert!(is_emoji_modifier('\u{200D}')); // ZWJ
        assert!(is_emoji_modifier('\u{FE0F}')); // VS16
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
