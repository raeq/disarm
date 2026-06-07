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

// #112: key_buf and sep_positions are now stack-allocated to avoid two heap
// allocations per emoji-multi-starter character in match_emoji_at.
const KEY_BUF_CAP: usize = 64; // MAX_EMOJI_SEQ_LEN(9) × 5 hex + 8 '_' = 53 bytes; 64 is safe

/// Write a slice of codepoints as an uppercase hex key into `buf`.
///
/// Returns the number of bytes written.  The buffer must be at least
/// `KEY_BUF_CAP` bytes long.  Using a caller-supplied stack buffer avoids
/// repeated heap allocation inside the O(max_seq_len) candidate loop in
/// `match_emoji_at`.
fn encode_key_into(buf: &mut [u8; KEY_BUF_CAP], cps: &[char]) -> usize {
    let mut pos = 0usize;
    for (i, &c) in cps.iter().enumerate() {
        if i > 0 {
            buf[pos] = b'_';
            pos += 1;
        }
        // Format codepoint as uppercase hex (4–6 digits) into the stack buffer.
        // All emoji codepoints fit in 5 hex digits (max U+10FFFF = 6 digits, but
        // emoji top out at ~1FAFF), and {:04X} zero-pads to at least 4.
        let cp = c as u32;
        // Determine digit count (minimum 4 per the format spec).
        let digits: u32 = if cp >= 0x10_0000 {
            6
        } else if cp >= 0x1_0000 {
            5
        } else {
            4
        };
        for d in (0..digits).rev() {
            let nibble = ((cp >> (d * 4)) & 0xF) as u8;
            buf[pos] = if nibble < 10 {
                b'0' + nibble
            } else {
                b'A' + nibble - 10
            };
            pos += 1;
        }
    }
    pos
}

/// Try to match the longest emoji sequence starting at `window[0]`.
///
/// `window` is a fixed-size lookahead slice of up to `MAX_EMOJI_SEQ_LEN`
/// chars beginning at the current position; `window.len()` equals the number
/// of chars still available.  Returns `(short_name, chars_consumed)` or
/// `None`.
///
/// # #112 / #113
/// Stack-only allocations: `key_buf` is a `[u8; KEY_BUF_CAP]` array and
/// `sep_positions` is a `[usize; MAX_WINDOW]` array — no heap
/// allocation occurs here regardless of input.
fn match_emoji_at(window: &[char]) -> Option<(&'static str, usize)> {
    let ch = window[0];
    let remaining = window.len();

    // Try multi-codepoint sequences first (longest match)
    if tables::is_emoji_multi_starter(ch) {
        let max_len = MAX_WINDOW.min(remaining);

        // #112: stack-allocate key buffer (no heap).
        // Build the full key once for max_len, then use pre-computed separator
        // positions for O(1) truncation instead of rfind('_') per iteration.
        let mut key_buf = [0u8; KEY_BUF_CAP];
        let total_len = encode_key_into(&mut key_buf, &window[..max_len]);

        // #112: stack-allocate sep_positions (at most MAX_WINDOW - 1 entries).
        // sep_positions[i] = byte offset of the (i+1)-th '_' separator.
        // To get a key for `len` codepoints, truncate at sep_positions[len-1].
        let mut sep_positions = [0usize; MAX_WINDOW];
        let mut sep_count = 0usize;
        for (idx, &b) in key_buf[..total_len].iter().enumerate() {
            if b == b'_' {
                sep_positions[sep_count] = idx;
                sep_count += 1;
            }
        }

        // Try longest sequences first, truncating the key progressively
        for len in (2..=max_len).rev() {
            let last = window[len - 1];
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
                // SAFETY: sep_positions[len-1] is a valid byte offset within key_buf
                // (it was recorded from the encoded key), and key_buf contains only
                // ASCII hex digits and '_', so the slice is valid UTF-8.
                std::str::from_utf8(&key_buf[..sep_positions[len - 1]])
                    .expect("key_buf is always ASCII")
            } else {
                std::str::from_utf8(&key_buf[..total_len]).expect("key_buf is always ASCII")
            };

            if let Some(name) = tables::lookup_emoji_multi(key_slice) {
                return Some((name, len));
            }
        }
    }

    // Try single-codepoint lookup
    if let Some(name) = tables::lookup_emoji_single(ch) {
        // Check if followed by variation selector — consume it too
        let consumed = if window.len() > 1 && (window[1] == VS16 || window[1] == VS15) {
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

/// Fixed-size sliding window over the character stream.
///
/// # #113
/// Replaces the `Vec<char>` full-input materialisation in `demojize_impl` and
/// `demojize_rust`.  The buffer holds up to `MAX_EMOJI_SEQ_LEN` chars of
/// lookahead — the maximum the matching engine ever needs.  Characters are
/// consumed from the inner iterator one-by-one; advancing the window shifts
/// buffered chars left and refills from the iterator, requiring no heap
/// allocation regardless of input length.
struct CharWindow<'a> {
    buf: [char; MAX_WINDOW],
    /// Number of valid chars currently in `buf` (always <= MAX_WINDOW).
    len: usize,
    rest: std::str::Chars<'a>,
}

/// Window capacity = MAX_EMOJI_SEQ_LEN so we always have enough lookahead.
const MAX_WINDOW: usize = 9; // mirrors MAX_EMOJI_SEQ_LEN = 9

impl<'a> CharWindow<'a> {
    /// Create a new window, pre-filling the buffer from `chars`.
    fn new(mut chars: std::str::Chars<'a>) -> Self {
        let mut buf = ['\0'; MAX_WINDOW];
        let mut len = 0;
        while len < MAX_WINDOW {
            match chars.next() {
                Some(c) => {
                    buf[len] = c;
                    len += 1;
                }
                None => break,
            }
        }
        CharWindow {
            buf,
            len,
            rest: chars,
        }
    }

    /// The current character (first in the window), or `None` if exhausted.
    #[inline]
    fn current(&self) -> Option<char> {
        if self.len > 0 {
            Some(self.buf[0])
        } else {
            None
        }
    }

    /// A slice of all valid chars in the window (up to MAX_WINDOW chars).
    #[inline]
    fn as_slice(&self) -> &[char] {
        &self.buf[..self.len]
    }

    /// Advance the window by `n` chars (1 <= n <= self.len).
    ///
    /// Shifts `buf[n..]` to the front, then refills from the iterator.
    fn advance(&mut self, n: usize) {
        debug_assert!(n > 0 && n <= self.len);
        // Shift remaining buffered chars to the front.
        self.buf.copy_within(n..self.len, 0);
        let remaining = self.len - n;
        // Refill from the iterator.
        let mut fill = remaining;
        while fill < MAX_WINDOW {
            match self.rest.next() {
                Some(c) => {
                    self.buf[fill] = c;
                    fill += 1;
                }
                None => break,
            }
        }
        self.len = fill;
    }
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
    provider: &PyObject,
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
    provider: Option<&PyObject>,
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

        // Try custom Python provider first (if set)
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
            last_was_emoji = false;
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
///
/// Rejected once [`seal_registrations`](crate::tables::seal_registrations) has
/// been called (#104): swapping the global emoji provider mutates process-global
/// canonicalization that every caller shares, so it must obey the same seal as
/// the other registration mutators.
#[pyfunction]
#[pyo3(name = "_set_emoji_provider")]
#[pyo3(signature = (provider=None))]
pub fn _set_emoji_provider(provider: Option<PyObject>) -> PyResult<()> {
    crate::transliterate::check_not_sealed("set_emoji_provider")?;
    set_provider(provider);
    Ok(())
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

/// Insert emoji replacement text with leading space padding.
///
/// Adds a leading space only if the result is non-empty and doesn't already end
/// with whitespace. Checking for any whitespace (not just `' '`) avoids a
/// double separator when the preceding char is a tab or newline: `"a\t😀"`
/// becomes `"a\tgrinning face"`, not `"a\t grinning face"`. The caller must set
/// `last_was_emoji = true` so the next non-emoji alphanumeric also gets a space.
#[inline]
fn pad_emoji_replacement(result: &mut String, text: &str) {
    let ends_with_ws = result.chars().next_back().is_some_and(char::is_whitespace);
    if !result.is_empty() && !ends_with_ws {
        result.push(' ');
    }
    result.push_str(text);
}

/// Pure Rust demojize for use by TextPipeline (no Python provider support).
///
/// # #113
/// Uses a `CharWindow` sliding buffer instead of `Vec<char>` to avoid
/// materialising the full input for non-ASCII text.
pub fn demojize_rust(text: &str, strip_modifiers: bool) -> String {
    // Fast path: pure-ASCII text cannot contain emoji.
    if text.is_ascii() {
        return text.to_owned();
    }

    let mut win = CharWindow::new(text.chars());
    let mut result = String::with_capacity(text.len());
    let mut last_was_emoji = false;

    while let Some(ch) = win.current() {
        if ch == VS16 || ch == VS15 || ch == ZWJ {
            win.advance(1);
            continue;
        }

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

        // Unknown emoji — drop it (Ignore mode)
        if is_emoji_codepoint(ch) {
            win.advance(1);
            while win.current().is_some_and(is_emoji_modifier) {
                win.advance(1);
            }
            last_was_emoji = false;
            continue;
        }

        if last_was_emoji && ch.is_alphanumeric() {
            result.push(' ');
        }
        result.push(ch);
        last_was_emoji = false;
        win.advance(1);
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encode_key_single() {
        // #112: encode_key_into now writes into a stack [u8; KEY_BUF_CAP].
        let mut buf = [0u8; KEY_BUF_CAP];
        let n = encode_key_into(&mut buf, &['\u{1F600}']);
        assert_eq!(std::str::from_utf8(&buf[..n]).unwrap(), "1F600");
    }

    #[test]
    fn test_encode_key_multi() {
        let mut buf = [0u8; KEY_BUF_CAP];
        let n = encode_key_into(&mut buf, &['\u{1F468}', ZWJ, '\u{1F469}']);
        assert_eq!(std::str::from_utf8(&buf[..n]).unwrap(), "1F468_200D_1F469");
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
        // #113: match_emoji_at now takes a window slice (pos=0 is always current).
        let chars: Vec<char> = "😀".chars().collect();
        let result = match_emoji_at(&chars);
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
        assert_eq!(result, "grinning face face with tears of joy");
    }

    #[test]
    fn test_demojize_rust_empty() {
        assert_eq!(demojize_rust("", false), "");
    }
}
