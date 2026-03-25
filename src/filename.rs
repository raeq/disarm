use pyo3::prelude::*;
use unicode_normalization::UnicodeNormalization;

use crate::transliterate;

/// Windows reserved filenames.
///
/// Covers the standard device names (CON–LPT9) documented at
/// <https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file>.
/// Legacy 16-bit device names (CLOCK$, KEYBD$, SCREEN$) are also blocked as
/// they remain reserved on some Windows versions.
const WINDOWS_RESERVED: &[&str] = &[
    "CON", "PRN", "AUX", "NUL", "COM0", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7",
    "COM8", "COM9", "LPT0", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    "CLOCK$", "KEYBD$", "SCREEN$",
];

/// Characters illegal on various platforms.
const UNIVERSAL_ILLEGAL: &[char] = &['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0'];
const POSIX_ILLEGAL: &[char] = &['/', '\0'];

use crate::utils::floor_char_boundary;

/// Check if a stem (filename without extension) matches a Windows reserved name.
fn is_windows_reserved(stem: &str) -> bool {
    let upper = stem.to_uppercase();
    WINDOWS_RESERVED.iter().any(|r| upper == *r)
}

/// Apply max_length truncation with optional extension preservation.
///
/// When `preserve_ext` is true and an extension is provided, the stem is
/// truncated to make room for the extension within the budget.  If the
/// extension alone exceeds the budget, both stem and extension are truncated
/// as a unit.
fn apply_max_length(name: &mut String, ext: Option<&str>, max_length: usize, preserve_ext: bool) {
    if max_length == 0 || name.len() <= max_length {
        return;
    }

    if preserve_ext {
        if let Some(ext) = ext {
            let ext_len = ext.len();
            if ext_len >= max_length {
                // Extension alone exceeds limit — truncate the whole thing.
                let safe = floor_char_boundary(name, max_length);
                name.truncate(safe);
            } else {
                // Truncate stem to fit stem + extension within max_length.
                let stem_budget = max_length - ext_len;
                let safe = floor_char_boundary(name, stem_budget);
                let mut new_name = name[..safe].to_owned();
                new_name.push_str(ext);
                *name = new_name;
            }
            return;
        }
    }

    let safe = floor_char_boundary(name, max_length);
    name.truncate(safe);
}

/// Collapse consecutive `.` sequences of length >= 2 to a single `.`.
/// This neutralizes `..` path traversal while preserving single dots
/// (which delimit file extensions).
fn collapse_dot_sequences(text: &str) -> String {
    // Fast path: no consecutive dots means nothing to collapse.
    if !text.contains("..") {
        return text.to_owned();
    }

    let mut result = String::with_capacity(text.len());
    let mut dot_run = 0usize;

    for ch in text.chars() {
        if ch == '.' {
            dot_run += 1;
        } else {
            if dot_run >= 1 {
                result.push('.'); // collapse 2+ dots to one; preserve singles
            }
            dot_run = 0;
            result.push(ch);
        }
    }
    // Handle trailing dots
    if dot_run >= 1 {
        result.push('.');
    }

    result
}

/// Sanitize a string into a safe filename.
///
/// # `max_length` semantics
/// `max_length` is measured in **bytes** (UTF-8 encoded), not Unicode
/// characters. This matches the unit used by all major OS filesystem limits
/// (ext4, APFS, NTFS: 255 bytes). The helper `floor_char_boundary` ensures
/// that truncation never splits a multi-byte character.
///
/// # `preserve_extension` edge cases
/// When `preserve_extension = true`:
/// - If the extension alone (including the leading `.`) is ≥ `max_length`,
///   the extension is dropped and the whole result is truncated to `max_length`.
/// - Otherwise the stem is truncated to `max_length − extension_len` bytes
///   and the full extension is appended.
///
/// When `preserve_extension = false`, the entire string (stem + extension)
/// is truncated to `max_length` bytes as a unit.
#[pyfunction]
#[pyo3(signature = (text, *, separator="_", max_length=255, platform="universal", lang=None, preserve_extension=true))]
pub fn _sanitize_filename(
    text: &str,
    separator: &str,
    max_length: usize,
    platform: &str,
    lang: Option<&str>,
    preserve_extension: bool,
) -> PyResult<String> {
    if text.is_empty() {
        return Ok(String::new());
    }

    // Validate platform
    let illegal_chars: &[char] = match platform {
        "universal" | "windows" => UNIVERSAL_ILLEGAL,
        "posix" => POSIX_ILLEGAL,
        _ => {
            return Err(crate::TranslitError::new_err(format!(
                "platform must be 'universal', 'windows', or 'posix', got '{platform}'"
            )))
        }
    };

    // NFC normalize first — ensures consistent representation across platforms.
    // macOS APFS uses NFD internally; NFC here prevents mismatched filenames
    // when files are synced between macOS, Windows, and Linux.
    let nfc_text: String = text.nfc().collect();

    // Collapse .. path traversal sequences before transliteration.
    let safe_text = collapse_dot_sequences(&nfc_text);

    // Transliterate to ASCII
    let transliterated =
        transliterate::transliterate_impl(&safe_text, lang, crate::ErrorMode::Ignore, "", false, false)
            .into_owned();

    // Collapse dots again after transliteration — characters like U+2026
    // HORIZONTAL ELLIPSIS (→ "...") or U+00B7 MIDDLE DOT (→ ".") can
    // reintroduce ".." sequences after transliteration.
    let transliterated = collapse_dot_sequences(&transliterated);

    // Split extension if preserving
    let (stem, ext) = if preserve_extension {
        match transliterated.rfind('.') {
            Some(pos) if pos > 0 => (&transliterated[..pos], Some(&transliterated[pos..])),
            _ => (transliterated.as_str(), None),
        }
    } else {
        (transliterated.as_str(), None)
    };

    // Remove illegal characters from stem, replace with separator
    let mut result = String::with_capacity(stem.len());
    let mut prev_was_sep = true;

    for ch in stem.chars() {
        if illegal_chars.contains(&ch) || ch.is_control() || ch.is_whitespace() {
            if !prev_was_sep && !separator.is_empty() {
                result.push_str(separator);
                prev_was_sep = true;
            }
        } else {
            result.push(ch);
            prev_was_sep = false;
        }
    }

    // Strip trailing separator
    while result.ends_with(separator) && !separator.is_empty() {
        result.truncate(result.len() - separator.len());
    }

    // Strip leading dots and spaces with a single drain (avoids O(k²) repeated shifts).
    {
        let trim_start = result
            .chars()
            .take_while(|c| *c == '.' || *c == ' ')
            .map(char::len_utf8)
            .sum::<usize>();
        if trim_start > 0 {
            result.drain(..trim_start);
        }
    }
    // Strip trailing dots and spaces with a single truncate.
    {
        let trim_end = result
            .chars()
            .rev()
            .take_while(|c| *c == '.' || *c == ' ')
            .map(char::len_utf8)
            .sum::<usize>();
        if trim_end > 0 {
            result.truncate(result.len() - trim_end);
        }
    }

    // Sanitize the extension: remove illegal chars, keep only the leading dot
    // and valid filename characters.
    let sanitized_ext = ext.map(|e| {
        let mut clean = String::with_capacity(e.len());
        clean.push('.'); // always start with the dot
        for ch in e[1..].chars() {
            if !illegal_chars.contains(&ch) && !ch.is_control() && !ch.is_whitespace() {
                clean.push(ch);
            }
        }
        clean
    });

    // Handle Windows reserved names — must re-append extension before returning
    if matches!(platform, "universal" | "windows") && is_windows_reserved(&result) {
        let mut final_name = format!("_{result}");
        if let Some(ref ext) = sanitized_ext {
            final_name.push_str(ext);
        }
        apply_max_length(&mut final_name, None, max_length, false);
        return Ok(final_name);
    }

    // Append sanitized extension
    let mut final_name = result;
    if let Some(ref ext) = sanitized_ext {
        final_name.push_str(ext);
    }

    // Extension-aware truncation
    apply_max_length(
        &mut final_name,
        sanitized_ext.as_deref(),
        max_length,
        preserve_extension,
    );

    // Post-truncation reserved name check — truncation can create a reserved
    // name (e.g., "NULtra.txt" truncated to 3 bytes → "NUL").
    if matches!(platform, "universal" | "windows") {
        let check_stem = match final_name.find('.') {
            Some(pos) => &final_name[..pos],
            None => &final_name,
        };
        if is_windows_reserved(check_stem) {
            final_name.insert(0, '_');
            apply_max_length(&mut final_name, None, max_length, false);
        }
    }

    // Fallback for empty result
    if final_name.is_empty() {
        final_name = String::from("_");
    }

    Ok(final_name)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_collapse_dot_sequences_double() {
        assert_eq!(collapse_dot_sequences(".."), ".");
        assert_eq!(collapse_dot_sequences("foo..bar"), "foo.bar");
        assert_eq!(collapse_dot_sequences("../../etc"), "././etc");
    }

    #[test]
    fn test_collapse_dot_sequences_single_preserved() {
        assert_eq!(collapse_dot_sequences("file.txt"), "file.txt");
        assert_eq!(collapse_dot_sequences("a.b.c"), "a.b.c");
    }

    #[test]
    fn test_collapse_dot_sequences_triple() {
        assert_eq!(collapse_dot_sequences("..."), ".");
        assert_eq!(collapse_dot_sequences("foo...bar"), "foo.bar");
    }

    #[test]
    fn test_collapse_empty() {
        assert_eq!(collapse_dot_sequences(""), "");
    }

    #[test]
    fn test_collapse_no_dots() {
        assert_eq!(collapse_dot_sequences("hello world"), "hello world");
    }

    #[test]
    fn test_collapse_trailing_dots() {
        assert_eq!(collapse_dot_sequences("foo.."), "foo.");
    }

    #[test]
    fn test_truncation_creates_reserved_name() {
        // "NULtra.txt" truncated to max_length=3 would produce "NUL"
        // which is a Windows reserved name. The post-truncation check
        // should prefix it with underscore.
        let result = _sanitize_filename("NULtra.txt", "_", 3, "universal", None, false).unwrap();
        // Must not be exactly a reserved name
        let upper = result.to_uppercase();
        assert!(
            !WINDOWS_RESERVED.iter().any(|r| upper == *r),
            "truncation produced reserved name: {result}"
        );
    }

    #[test]
    fn test_reserved_name_prefixed() {
        // Direct reserved name gets underscore prefix
        let result = _sanitize_filename("CON", "_", 255, "universal", None, false).unwrap();
        assert!(result.starts_with('_'));
    }

    mod proptest_properties {
        use super::*;
        use proptest::prelude::*;

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            /// collapse_dot_sequences never produces ".." in its output.
            #[test]
            fn collapse_dots_no_double_dots(s in "\\PC*") {
                let result = collapse_dot_sequences(&s);
                prop_assert!(
                    !result.contains(".."),
                    "double dots in: {result:?}"
                );
            }

            /// collapse_dot_sequences is idempotent.
            #[test]
            fn collapse_dots_idempotent(s in "\\PC*") {
                let once = collapse_dot_sequences(&s);
                let twice = collapse_dot_sequences(&once);
                prop_assert_eq!(&once, &twice);
            }

            /// collapse_dot_sequences preserves single dots.
            #[test]
            fn collapse_dots_preserves_singles(s in "[a-z]{1,5}(\\.[a-z]{1,5}){0,5}") {
                // Input with only single dots should be unchanged.
                let result = collapse_dot_sequences(&s);
                prop_assert_eq!(&result, &s);
            }

            /// collapse_dot_sequences preserves non-dot characters.
            #[test]
            fn collapse_dots_preserves_non_dots(s in "[^.]{0,50}") {
                let result = collapse_dot_sequences(&s);
                prop_assert_eq!(&result, &s);
            }
        }
    }
}
