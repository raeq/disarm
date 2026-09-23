//! Layer 1 (pure-Rust core): filename sanitization. No pyo3.
//!
//! Shim in `src/py/filename.rs`; crates.io surface is
//! `crate::api::sanitize_filename` (typed `Platform`). Fallible at Layer 2:
//! the `lang` parameter is validated against the registrable transliteration
//! language set, and the `separator` against what a filename may carry.

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

/// Replace a `%` that transliteration manufactured, leaving one the caller typed (#721).
///
/// `sanitize_filename` already accepts this premise once: `collapse_dot_sequences` runs a
/// second time after transliteration because `U+2026` and `U+00B7` can reintroduce a `..`
/// that was not in the input. The same step can assemble `%2E%2E%2F` — the percent-encoded
/// spelling of the *same* traversal — out of characters containing no `%`, no `2`, no `E`
/// and no `F`:
///
/// ```text
/// sanitize_filename("％２Ｅ％２Ｅ％２Ｆetc.txt")  ->  "%2E%2E%2Fetc.txt"
/// urllib.parse.unquote(that)                       ->  "../etc.txt"
/// ```
///
/// `%` is a legal filename character on every supported platform, so it is not in
/// `UNIVERSAL_ILLEGAL` and nothing removed it. The remedy at the dot-collapse covered one
/// spelling of traversal and not the other.
///
/// A caller who typed `%` keeps it — passing a literal `%2E%2E%2F` through is defensible,
/// since the caller wrote it; a sanitizer *manufacturing* one from fullwidth characters is
/// not. Filenames reach percent-decoders routinely (`Content-Disposition`, object-storage
/// keys, static-file routes), so `serve(unquote(segment))` is a common enough shape to be
/// worth the check.
///
/// The test used to be `contains('%')` on the whole raw input, which made the rule hold
/// only for input with no `%` at all: one typed `%` let every manufactured one through
/// (a `%` followed by fullwidth `%2E%2E%2F` gave `"%%2E%2E%2F"`). It is now per
/// character. Transliteration passes an ASCII `%` through unchanged and never removes
/// one, so the output has exactly as many `%` as the input unless something was
/// manufactured — one count on the common path. Only when the counts differ is the text
/// transliterated again **between** the typed `%`, and each `%` inside a segment is the
/// manufactured kind. The typed ones are the split points, so they come back exactly
/// where they were.
///
/// With no typed `%` the only segment is the whole text, so that case is unchanged from
/// #721. With typed ones, a segment is transliterated without its neighbours as context
/// (inter-script spacing, auto-detected language) — only on input that both typed a `%`
/// and folded another one in.
fn transliterate_keeping_typed_percent(text: &str, lang: Option<&str>, separator: &str) -> String {
    let translit = |s: &str| -> String {
        transliterate::transliterate_impl(
            s,
            lang,
            crate::ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        )
        .into_owned()
    };
    let whole = translit(text);
    let percents = |s: &str| s.bytes().filter(|&b| b == b'%').count();
    if percents(&whole) == percents(text) {
        return whole;
    }
    let mut out = String::with_capacity(whole.len());
    for (i, segment) in text.split('%').enumerate() {
        if i > 0 {
            out.push('%');
        }
        out.push_str(&translit(segment).replace('%', separator));
    }
    out
}

/// Whether `c` may appear in a `sanitize_filename` separator (Finding 2 of the Lean
/// model).
///
/// The separator is inserted *after* the illegal characters are removed, so it is the
/// one string that reaches the output without passing the filter — and before this check
/// nothing looked at it: `separator="/"` turned `"../etc/passwd"` into `"/etc/passwd"`,
/// `"\0"` put NUL in the name, and `" "` let `"con _"` truncate to a bare `"con"`. So it is
/// held to what the stem keeps, and a little more:
///
/// - **Printable, non-space ASCII.** Rules out controls, every kind of whitespace, and
///   invisible or bidi characters (`U+202E` would be a filename-spoofing primitive). It is
///   also what keeps the output a fixed point: the output is otherwise ASCII, and a
///   non-ASCII separator would be transliterated by the next call, giving another name.
/// - **Not illegal on the platform** — the same set the stem loop removes.
/// - **Not a path separator on any platform**: `\` is legal in a POSIX filename, but a
///   separator of `\` still builds a path on Windows, which is where these names end up.
///
/// The empty separator is allowed (and documented): illegal runs are simply dropped.
fn is_separator_char(c: char, illegal_chars: &[char]) -> bool {
    c.is_ascii_graphic() && c != '/' && c != '\\' && !illegal_chars.contains(&c)
}

/// Reject a separator carrying a character [`is_separator_char`] refuses — the same
/// shape as `validate_log_replacement` for `strip_log_injection`.
fn validate_separator(separator: &str, illegal_chars: &[char]) -> Result<(), crate::ErrorRepr> {
    if let Some(c) = separator
        .chars()
        .find(|&c| !is_separator_char(c, illegal_chars))
    {
        return Err(crate::ErrorRepr::InvalidFilenameSeparator {
            codepoint: c as u32,
        });
    }
    Ok(())
}

/// Check if a stem (filename without extension) matches a Windows reserved name.
fn is_windows_reserved(stem: &str) -> bool {
    // Windows reserved-name matching is ASCII case-insensitive, and every
    // `WINDOWS_RESERVED` entry is ASCII (`CON`, `PRN`, `COM1`, …). Compare with
    // `eq_ignore_ascii_case` rather than allocating a Unicode-uppercased `String`
    // per call — same result, no allocation, and a closer match to the OS rule.
    WINDOWS_RESERVED
        .iter()
        .any(|r| stem.eq_ignore_ascii_case(r))
}

/// The part of a finished filename Windows matches against the device list: everything
/// before the first dot, with trailing spaces removed (`"nul.txt"`, `"nul .txt"` and
/// `"nul"` all open the device).
fn windows_device_stem(name: &str) -> &str {
    let stem = match name.find('.') {
        Some(pos) => &name[..pos],
        None => name,
    };
    stem.trim_end_matches(' ')
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

/// Final filename hygiene shared by both return paths (#485/#487), run on the fully
/// assembled name so it covers the extension branch — which re-prepends `'.'` and is exempt
/// from the stem's leading/trailing dot trim, so the assembled name can keep a leading dot
/// (a Unix dotfile), keep a trailing dot or space (which Windows strips at the filesystem
/// layer, making disarm's output and the stored file disagree), or reduce to a bare `"."` /
/// `".."` directory reference. Trim leading and trailing dots and spaces, then fall back to
/// `"_"` — the same fallback every all-stripped input uses — for an empty, `"."`, or `".."`
/// result. Trimming only shortens, so a prior `max_length` cap still holds.
fn finalize_name(name: String) -> String {
    let trimmed = name.trim_matches(|c: char| c == '.' || c == ' ');
    if trimmed.is_empty() {
        String::from("_")
    } else if trimmed.len() == name.len() {
        name
    } else {
        trimmed.to_owned()
    }
}

/// The arguments one sanitizing pass needs, validated.
struct PassConfig<'a> {
    separator: &'a str,
    max_length: usize,
    illegal_chars: &'a [char],
    /// `universal` and `windows`: the name must not be a Windows device name.
    checks_reserved: bool,
    preserve_extension: bool,
}

/// Upper bound on sanitizing passes, the confirming one included; see
/// [`sanitize_filename`]. Every input of the Lean model's 8.5-million-case grid settles
/// within four (`fixed_point_within_the_pass_bound`); most need two, the second only
/// confirming. The margin is deliberate: hitting the bound costs idempotence, never
/// safety.
const MAX_PASSES: usize = 8;

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
///
/// # The output is a fixed point
///
/// `sanitize_filename(sanitize_filename(x)) == sanitize_filename(x)` (#487 criterion 2).
/// One pass cannot promise that on its own: its steps each undo a precondition of an
/// earlier one — an extension that cleans to `"."` is dropped, so the next call splits at
/// an earlier dot (`"_.x.*"` gave `"_.x"`, then `"x"`); truncation can end the stem in the
/// separator or a dot (`"ab_"`, `"a..txt"`); an empty separator makes the dots around a
/// deleted space adjacent (`"a..b"`). #570 fixed one of these at its source and the Lean
/// model found four more, with a proposed per-step fix that still left 100 of 8.5 million
/// grid cases open under truncation.
///
/// So the pass is applied again to its own output until it stops changing, at most
/// [`MAX_PASSES`] times. That is idempotent by construction wherever it converges: the
/// result `y` satisfies `pass(y) == y`, and a second call on `y` starts from `y`. The
/// passes after the first are cheap. The first pass's output is ASCII (transliteration
/// emits ASCII, and [`is_separator_char`] admits only ASCII), and on ASCII input NFC,
/// transliteration and the `%` rule are all the identity, so they are skipped and only
/// the string surgery runs again. Every pass, the last one included, ends with the
/// reserved-name check, so stopping at the bound can cost idempotence but never safety.
pub(crate) fn sanitize_filename(
    text: &str,
    separator: &str,
    max_length: usize,
    platform: &str,
    lang: Option<&str>,
    preserve_extension: bool,
) -> Result<String, crate::ErrorRepr> {
    crate::transliterate::validate_lang(lang)?;
    // #485: no empty-input short-circuit — `""` flows through to `finalize_name`, which
    // returns the same `"_"` fallback every all-stripped input uses (the old early return
    // here bypassed that fallback and returned `""`, a downstream write-target footgun).

    // Validate platform
    let illegal_chars: &[char] = match platform {
        "universal" | "windows" => UNIVERSAL_ILLEGAL,
        "posix" => POSIX_ILLEGAL,
        _ => {
            return Err(crate::ErrorRepr::InvalidPlatform {
                got: platform.to_owned(),
            })
        }
    };
    validate_separator(separator, illegal_chars)?;
    let config = PassConfig {
        separator,
        max_length,
        illegal_chars,
        checks_reserved: platform != "posix",
        preserve_extension,
    };

    // NFC normalize first — ensures consistent representation across platforms.
    // macOS APFS uses NFD internally; NFC here prevents mismatched filenames
    // when files are synced between macOS, Windows, and Linux.
    let nfc_text: String = text.nfc().collect();

    // Collapse .. path traversal sequences before transliteration.
    let safe_text = collapse_dot_sequences(&nfc_text);

    // Transliterate to ASCII, and neutralize a `%` the transliteration manufactured
    // (#721): the same before/after comparison the dot-collapse in `sanitize_pass`
    // embodies, for the other spelling of the same traversal. That collapse runs again
    // on the transliterated text because characters like U+2026 HORIZONTAL ELLIPSIS
    // (→ "...") or U+00B7 MIDDLE DOT (→ ".") can reintroduce ".." sequences.
    let transliterated = transliterate_keeping_typed_percent(&safe_text, lang, separator);

    let mut name = sanitize_pass(&transliterated, &config);
    for _ in 1..MAX_PASSES {
        debug_assert!(name.is_ascii(), "a pass emitted non-ASCII: {name:?}");
        let next = sanitize_pass(&name, &config);
        if next == name {
            break;
        }
        name = next;
    }
    Ok(name)
}

/// One sanitizing pass over already-transliterated text. See [`sanitize_filename`].
fn sanitize_pass(text: &str, config: &PassConfig<'_>) -> String {
    let &PassConfig {
        separator,
        max_length,
        illegal_chars,
        checks_reserved,
        preserve_extension,
    } = config;

    let transliterated = collapse_dot_sequences(text);

    // #570: trim trailing dots and spaces BEFORE choosing the extension boundary.
    //
    // `finalize_name` trims them off the *assembled* name at the end, which is too late:
    // the split below takes the LAST dot, so a trailing `.` becomes the "extension" and
    // an earlier dot stays inside the stem. Once `finalize_name` removes that trailing
    // dot, a second call splits at the earlier dot instead — and a separator that had
    // been mid-stem is now stem-trailing, where the trailing-separator rule strips it.
    // `sanitize_filename("a*.b.")` gave "a_.b", then "a.b". Two systems that sanitize a
    // different number of times derived different names from one input, defeating dedup.
    //
    // Trimming here makes the boundary the split sees the same one the output will have,
    // so the first pass already lands on the fixed point. `finalize_name` still runs and
    // is still needed — the extension branch re-prepends `'.'` and can reintroduce a
    // trailing dot (a bare `"."` extension), and it owns the empty / "." / ".." fallback.
    let transliterated = {
        // Truncate in place rather than re-owning the trimmed slice: the trim only ever
        // shortens, so there is no reason to allocate a second String for it.
        let mut owned = transliterated;
        let keep = owned.trim_end_matches(['.', ' ']).len();
        owned.truncate(keep);
        owned
    };

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

    // Strip trailing separators — except the first one of a stem that is nothing else.
    //
    // The loop above never *generates* a leading separator, so a stem made only of
    // separators is one the caller typed, or the `_` the reserved-name rule below put
    // there: `"PRN.txt"` at `max_length=5` is `"_PRN.txt"` cut to `"_.txt"`. Stripping
    // that stem to nothing made the next call return `"txt"` — the extension it had just
    // preserved, as the whole name — so the output was not a fixed point. Keeping one
    // separator keeps it one. Only a stem the strip would have emptied is affected
    // (`"_.x"` now stays `"_.x"`, where it used to become `"x"`).
    if !separator.is_empty() {
        let mut keep = result.len();
        while result[..keep].ends_with(separator) {
            keep -= separator.len();
        }
        if keep == 0 && !result.is_empty() {
            keep = separator.len();
        }
        result.truncate(keep);
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

    // A stem that is itself a reserved name is prefixed before truncation, so the
    // extension-aware cut below budgets for the `_` (`"CON.txt"` → `"_CON.txt"`).
    let mut final_name = result;
    if checks_reserved && is_windows_reserved(&final_name) {
        final_name.insert(0, '_');
    }
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

    // Final hygiene + never-empty / never-`.`-`..` fallback (#485/#487).
    let mut final_name = finalize_name(final_name);

    // The reserved-name check that matters reads the name as it is returned, after the
    // truncation and after `finalize_name`'s trim — the two steps that can turn a safe
    // stem into a device name: `"NULtra.txt"` truncated to 3 bytes is `"NUL"`, and a stem
    // that sanitizes to nothing leaves the extension as the whole name, `"*.con"` →
    // `".con"` → `"con"` (Finding 1 of the Lean model: every earlier check read the empty
    // stem, then `finalize_name` stripped the dot). A `_` prefix never starts a device
    // name, so the name after the re-cut and re-trim below is not one either.
    if checks_reserved && is_windows_reserved(windows_device_stem(&final_name)) {
        final_name.insert(0, '_');
        let kept_ext = sanitized_ext
            .as_deref()
            .filter(|e| e.len() > 1 && final_name.ends_with(e));
        apply_max_length(&mut final_name, kept_ext, max_length, preserve_extension);
        final_name = finalize_name(final_name);
    }
    final_name
}

#[cfg(test)]
#[allow(clippy::case_sensitive_file_extension_comparisons)]
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

    /// #570: the first pass must already be the fixed point.
    ///
    /// The trailing-dot trim used to run in `finalize_name`, after the extension split it
    /// invalidates: `"a*.b."` split at the LAST dot (stem `a*.b`, ext `.`), the trim then
    /// removed that dot, and a second call split at the earlier dot instead — turning a
    /// mid-stem separator into a stem-trailing one, which then got stripped.
    #[test]
    fn sanitize_filename_first_pass_is_the_fixed_point() {
        let f = |s: &str| sanitize_filename(s, "_", 255, "universal", None, true).unwrap();
        for input in [
            "a*.b.",        // literal trailing dot
            "a*.b..",       // two of them
            "0*.0\u{00B7}", // middle dot transliterates to '.'
            "a*.b\u{2026}", // ellipsis transliterates to '...'
            "ab*.c.",
            "x<.y\u{00B7}",
            "a?.b.",
        ] {
            let once = f(input);
            let twice = f(&once);
            assert_eq!(twice, once, "not idempotent for {input:?}");
        }
    }

    /// Cases that were already stable must stay stable — several of them were wrongly
    /// described as broken when the issue was first filed.
    #[test]
    fn sanitize_filename_stable_cases_unchanged_by_570() {
        let f = |s: &str| sanitize_filename(s, "_", 255, "universal", None, true).unwrap();
        assert_eq!(f("0*.0"), "0.0");
        assert_eq!(f("a*.b"), "a.b");
        assert_eq!(f("a_.b"), "a.b");
        assert_eq!(f("a*b\u{00B7}"), "a_b");
        assert_eq!(f("*.b."), "b");
    }

    /// The reported falsifying example, pinned by value.
    #[test]
    fn sanitize_filename_570_repro() {
        assert_eq!(
            sanitize_filename("0*.0\u{00B7}", "_", 255, "universal", None, true).unwrap(),
            "0.0"
        );
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
        let result = sanitize_filename("NULtra.txt", "_", 3, "universal", None, false).unwrap();
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
        let result = sanitize_filename("CON", "_", 255, "universal", None, false).unwrap();
        assert!(result.starts_with('_'));
    }

    #[test]
    fn test_reserved_name_preserve_extension() {
        // Direct reserved name with preserve_extension=true must keep the extension intact
        let result = sanitize_filename("NUL.txt", "_", 7, "universal", None, true).unwrap();
        assert!(result.ends_with(".txt"), "extension lost: {result}");
        assert!(result.len() <= 7, "exceeds max_length: {result}");
        // Must not be a reserved name
        let stem = result.split('.').next().unwrap().to_uppercase();
        assert!(
            !WINDOWS_RESERVED.iter().any(|r| stem == *r),
            "stem is reserved: {result}"
        );
    }

    #[test]
    fn test_truncation_creates_reserved_preserve_extension() {
        // "NULtra.txt" truncated to max_length=7 with preserve_extension=true:
        // stem gets truncated but extension must survive
        let result = sanitize_filename("NULtra.txt", "_", 7, "universal", None, true).unwrap();
        assert!(result.ends_with(".txt"), "extension lost: {result}");
        assert!(result.len() <= 7, "exceeds max_length: {result}");
    }

    // ── Regression tests for preserve_extension with reserved names ──────
    // Bug: both reserved-name code paths passed (None, false) to apply_max_length,
    // ignoring the caller's preserve_extension flag. These tests pin the fix.

    #[test]
    fn regress_direct_reserved_nul_preserve_ext_tight() {
        // "NUL.txt" → "_NUL.txt" (8 bytes) must truncate stem, not extension
        let r = sanitize_filename("NUL.txt", "_", 7, "universal", None, true).unwrap();
        assert!(r.ends_with(".txt"), "extension lost: {r}");
        assert!(r.len() <= 7, "exceeds max_length: {r}");
    }

    #[test]
    fn regress_direct_reserved_con_preserve_ext_tight() {
        let r = sanitize_filename("CON.dat", "_", 8, "universal", None, true).unwrap();
        assert!(r.ends_with(".dat"), "extension lost: {r}");
        assert!(r.len() <= 8, "exceeds max_length: {r}");
        assert!(r.starts_with('_'), "missing underscore prefix: {r}");
    }

    #[test]
    fn regress_direct_reserved_aux_preserve_ext_exact_fit() {
        // "_AUX.py" is 7 bytes — fits exactly in max_length=7
        let r = sanitize_filename("AUX.py", "_", 7, "universal", None, true).unwrap();
        assert_eq!(r, "_AUX.py");
    }

    #[test]
    fn regress_direct_reserved_prn_preserve_ext_very_tight() {
        // max_length=5 with ".txt" (4 bytes) leaves only 1 byte for stem
        let r = sanitize_filename("PRN.txt", "_", 5, "universal", None, true).unwrap();
        assert!(r.ends_with(".txt"), "extension lost: {r}");
        assert!(r.len() <= 5, "exceeds max_length: {r}");
    }

    #[test]
    fn regress_post_truncation_reserved_preserve_ext() {
        // "NULtra.txt" with max_length=7 and preserve_extension=true:
        // First truncation → "NUL.txt" (stem="NUL" is reserved) → "_NUL.txt" → re-truncate
        let r = sanitize_filename("NULtra.txt", "_", 7, "universal", None, true).unwrap();
        assert!(r.ends_with(".txt"), "extension lost: {r}");
        assert!(r.len() <= 7, "exceeds max_length: {r}");
    }

    #[test]
    fn regress_post_truncation_con_preserve_ext() {
        // "CONtest.pdf" with max_length=8: truncate stem → "CON.pdf" (reserved) → "_CON.pdf"
        let r = sanitize_filename("CONtest.pdf", "_", 8, "universal", None, true).unwrap();
        assert!(r.ends_with(".pdf"), "extension lost: {r}");
        assert!(r.len() <= 8, "exceeds max_length: {r}");
    }

    #[test]
    fn regress_reserved_no_extension_preserve_true() {
        // "CON" with no extension and preserve_extension=true — no extension to preserve
        let r = sanitize_filename("CON", "_", 4, "universal", None, true).unwrap();
        assert!(r.len() <= 4, "exceeds max_length: {r}");
        assert!(r.starts_with('_'), "missing underscore prefix: {r}");
    }

    #[test]
    fn regress_reserved_preserve_false_still_works() {
        // Ensure preserve_extension=false still works correctly (existing behavior)
        let r = sanitize_filename("NUL.txt", "_", 5, "universal", None, false).unwrap();
        assert!(r.len() <= 5, "exceeds max_length: {r}");
        // Extension may be truncated — that's fine with preserve_extension=false
    }

    #[test]
    fn regress_all_reserved_names_preserve_ext() {
        // Every Windows reserved name with an extension must preserve it
        for name in WINDOWS_RESERVED {
            let input = format!("{name}.txt");
            let r = sanitize_filename(&input, "_", 255, "universal", None, true).unwrap();
            assert!(
                r.ends_with(".txt"),
                "extension lost for reserved name '{name}': got '{r}'"
            );
            assert!(
                r.starts_with('_'),
                "missing underscore prefix for '{name}': got '{r}'"
            );
        }
    }

    #[test]
    fn regress_posix_reserved_names_no_prefix() {
        // On POSIX, reserved names are not special — extension should still be preserved
        let r = sanitize_filename("NUL.txt", "_", 7, "posix", None, true).unwrap();
        assert!(r.ends_with(".txt"), "extension lost on posix: {r}");
        assert!(!r.starts_with('_'), "unexpected prefix on posix: {r}");
    }

    #[test]
    fn regress_multibyte_extension_reserved_name() {
        // Extension with multibyte chars — truncation must not split a char
        let r = sanitize_filename("CON.ñ", "_", 6, "universal", None, true).unwrap();
        assert!(r.len() <= 6, "exceeds max_length: {r}");
        // Must be valid UTF-8 (implicit — Rust String guarantees this)
    }

    /// Tier-3 exhaustive gate for `collapse_dot_sequences`.
    ///
    /// The collapse state machine turns purely on `.`-vs-not, so two exhaustive sweeps
    /// prove it completely where the `\PC*` proptests sample: (1) every pattern over
    /// {`.`, `a`} up to length 12, proving no `".."`, idempotency, and single-dot
    /// preservation over every dot arrangement; and (2) every non-`.` code point is
    /// preserved verbatim (per-char property). `#[ignore]` (Tier 3); run via
    /// `--lib -- --ignored`.
    #[test]
    #[ignore = "exhaustive: collapse_dot_sequences over every dot pattern + code point; Tier 3"]
    fn exhaustive_collapse_dot_sequences() {
        // (1) every dot arrangement up to length 12.
        let alphabet = ['.', 'a'];
        let mut stack = vec![String::new()];
        while let Some(s) = stack.pop() {
            let once = collapse_dot_sequences(&s);
            assert!(!once.contains(".."), "double dots from {s:?} → {once:?}");
            assert_eq!(
                once,
                collapse_dot_sequences(&once),
                "not idempotent on {s:?}"
            );
            if !s.contains("..") {
                assert_eq!(once, s, "single-dot input altered: {s:?}");
            }
            if s.len() < 12 {
                for &a in &alphabet {
                    let mut n = s.clone();
                    n.push(a);
                    stack.push(n);
                }
            }
        }
        // (2) every non-dot code point passes through unchanged.
        for cp in 0u32..=0x0010_FFFF {
            let Some(c) = char::from_u32(cp) else {
                continue;
            };
            if c == '.' {
                continue;
            }
            let s = c.to_string();
            assert_eq!(collapse_dot_sequences(&s), s, "dropped non-dot U+{cp:04X}");
        }
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

        // ── sanitize_filename structural invariants ──────────────────────
        // These property tests check that key invariants hold for ALL inputs,
        // catching any code path that silently drops extension preservation,
        // exceeds max_length, or produces invalid filenames.

        fn reserved_name_strategy() -> impl Strategy<Value = String> {
            prop::sample::select(WINDOWS_RESERVED).prop_map(str::to_string)
        }

        fn extension_strategy() -> impl Strategy<Value = String> {
            prop::string::string_regex("[a-z]{1,6}")
                .unwrap()
                .prop_map(|e| format!(".{e}"))
        }

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(500))]

            /// When preserve_extension=true and the result has an extension,
            /// the extension from the input must survive in the output.
            #[test]
            fn preserve_ext_keeps_extension(
                stem in "[a-zA-Z0-9]{1,20}",
                ext in "[a-z]{1,4}",
                max_length in 5usize..50,
            ) {
                let input = format!("{stem}.{ext}");
                let expected_ext = format!(".{ext}");
                let result = sanitize_filename(&input, "_", max_length, "universal", None, true).unwrap();
                prop_assert!(result.len() <= max_length, "exceeds max_length {max_length}: {result}");
                // Extension must be preserved unless ext itself is >= max_length
                if expected_ext.len() < max_length {
                    prop_assert!(
                        result.ends_with(&expected_ext),
                        "extension '{expected_ext}' lost from input '{input}': got '{result}'"
                    );
                }
            }

            /// When preserve_extension=false, the output must still respect max_length.
            #[test]
            fn no_preserve_ext_respects_max_length(
                stem in "[a-zA-Z0-9]{1,30}",
                ext in "[a-z]{1,4}",
                max_length in 1usize..50,
            ) {
                let input = format!("{stem}.{ext}");
                let result = sanitize_filename(&input, "_", max_length, "universal", None, false).unwrap();
                prop_assert!(result.len() <= max_length, "exceeds max_length {max_length}: {result}");
            }

            /// Reserved names with extensions must preserve the extension
            /// when preserve_extension=true.
            #[test]
            fn reserved_name_preserve_ext(
                name in reserved_name_strategy(),
                ext in extension_strategy(),
                max_length in 6usize..50,
            ) {
                let input = format!("{name}{ext}");
                let result = sanitize_filename(&input, "_", max_length, "universal", None, true).unwrap();
                prop_assert!(result.len() <= max_length, "exceeds max_length {max_length}: {result}");
                // If there's room for the extension, it must be preserved
                if ext.len() < max_length {
                    prop_assert!(
                        result.ends_with(&ext),
                        "extension '{ext}' lost for reserved name '{name}': got '{result}'"
                    );
                }
                // Must have underscore prefix (reserved name handling)
                prop_assert!(
                    result.starts_with('_'),
                    "missing underscore prefix for reserved '{name}': got '{result}'"
                );
            }

            /// No code path in sanitize_filename should ever produce a bare
            /// Windows reserved name as the stem (before the first dot).
            #[test]
            fn never_produces_bare_reserved_stem(
                input in "[A-Za-z]{1,10}\\.[a-z]{1,4}",
                max_length in 1usize..30,
                preserve_ext in proptest::bool::ANY,
            ) {
                // #485: no `if !result.is_empty()` guard — the output is never empty, so
                // a bare reserved stem can never be hidden behind an empty result.
                let result = sanitize_filename(&input, "_", max_length, "universal", None, preserve_ext).unwrap();
                let stem = match result.find('.') {
                    Some(pos) => &result[..pos],
                    None => &result,
                };
                let upper = stem.to_uppercase();
                prop_assert!(
                    !WINDOWS_RESERVED.iter().any(|r| upper == *r),
                    "produced bare reserved stem from '{input}' (max_length={max_length}, preserve_ext={preserve_ext}): '{result}'"
                );
            }

            /// #485/#487 invariant: over the full Unicode input space the result is never
            /// empty, never a `"."` / `".."` directory reference, and carries no leading or
            /// trailing dot — so a careless edit that regresses any of these fails here.
            #[test]
            fn never_empty_dotfile_or_directory_reference(
                input in "\\PC{0,40}",
                max_length in 1usize..50,
                preserve_ext in proptest::bool::ANY,
            ) {
                let result = sanitize_filename(&input, "_", max_length, "universal", None, preserve_ext).unwrap();
                prop_assert!(!result.is_empty(), "empty output for {input:?}");
                prop_assert!(result != "." && result != "..", "directory reference {result:?} from {input:?}");
                prop_assert!(!result.starts_with('.'), "leading dot {result:?} from {input:?}");
                prop_assert!(!result.ends_with('.') && !result.ends_with(' '), "trailing dot/space {result:?} from {input:?}");
            }


            /// max_length must always be respected, regardless of platform,
            /// preserve_extension, or reserved name handling.
            #[test]
            fn max_length_always_respected(
                input in "\\PC{1,30}",
                max_length in 1usize..50,
                preserve_ext in proptest::bool::ANY,
            ) {
                if let Ok(result) = sanitize_filename(&input, "_", max_length, "universal", None, preserve_ext) {
                    prop_assert!(
                        result.len() <= max_length,
                        "exceeds max_length {max_length} for input '{input}': got '{result}' (len={})",
                        result.len()
                    );
                }
            }
        }
    }

    // Findings 1, 2, 3 and 15 of the Lean model of the sanitizers
    // (`formal/lean/Sanitizers/README.md`), pinned at the layer that owns them.
    mod formal_findings {
        use super::super::*;

        const PLATFORMS: [&str; 3] = ["universal", "windows", "posix"];

        fn sf(text: &str, sep: &str, max_length: usize, platform: &str, keep_ext: bool) -> String {
            sanitize_filename(text, sep, max_length, platform, None, keep_ext).unwrap()
        }

        fn default(text: &str) -> String {
            sf(text, "_", 255, "universal", true)
        }

        fn is_device_name(name: &str) -> bool {
            is_windows_reserved(windows_device_stem(name))
        }

        /// How many passes `sanitize_filename` runs, the confirming one included, or
        /// `None` if the output is still changing at `MAX_PASSES`. Mirrors the loop there.
        fn passes(text: &str, config: &PassConfig<'_>) -> Option<usize> {
            let nfc: String = text.nfc().collect();
            let prepared = transliterate_keeping_typed_percent(
                &collapse_dot_sequences(&nfc),
                None,
                config.separator,
            );
            let mut name = sanitize_pass(&prepared, config);
            for n in 2..=MAX_PASSES {
                let next = sanitize_pass(&name, config);
                if next == name {
                    return Some(n);
                }
                name = next;
            }
            None
        }

        /// Finding 1: a stem that sanitizes to nothing left the extension as the whole
        /// name, and `finalize_name` stripped its dot *after* both reserved checks had
        /// read the empty stem.
        #[test]
        fn empty_stem_does_not_expose_a_device_name() {
            for input in [
                "_.con", "*.con", " .nul", "/.aux", "../.con", "\0.com1", "?.LPT1",
            ] {
                for platform in ["universal", "windows"] {
                    let out = sf(input, "_", 255, platform, true);
                    assert!(!is_device_name(&out), "{input:?} ({platform}) -> {out:?}");
                    assert_eq!(sf(&out, "_", 255, platform, true), out, "{input:?}");
                }
            }
            assert_eq!(default("*.con"), "_con");
            assert_eq!(sf("*.NUL", "_", 255, "windows", true), "_NUL");
            assert_eq!(default("../.con"), "_con");
            // A typed separator is a stem, so nothing needs prefixing.
            assert_eq!(default("_.con"), "_.con");
            // Windows reads the device name before the FIRST dot; the split is at the last.
            assert_eq!(default("nul.tar.gz"), "_nul.tar.gz");
            assert_eq!(sf("*.con.tar.gz", "_", 255, "windows", true), "_con.tar.gz");
            // POSIX does not check device names, and still returns no dotfile.
            assert_eq!(sf("/.con", "_", 255, "posix", true), "con");
        }

        /// Finding 1 as swept: every scalar `c` in `c + ".con"` (185 failed).
        #[test]
        fn every_ascii_character_before_a_device_extension() {
            for c in (0u8..=0x7F).map(char::from) {
                for ext in [".con", ".NUL", ".aux", ".com1", ".lpt9"] {
                    let input = format!("{c}{ext}");
                    for platform in ["universal", "windows"] {
                        let out = sf(&input, "_", 255, platform, true);
                        assert!(!is_device_name(&out), "{input:?} ({platform}) -> {out:?}");
                    }
                }
            }
        }

        #[test]
        fn the_device_stem_is_what_windows_reads() {
            assert_eq!(windows_device_stem("nul.txt"), "nul");
            assert_eq!(windows_device_stem("nul .txt"), "nul");
            assert_eq!(windows_device_stem("con.tar.gz"), "con");
            assert_eq!(windows_device_stem("aux"), "aux");
        }

        /// Finding 2: the separator reached the output unvalidated.
        #[test]
        fn a_separator_a_filename_cannot_carry_is_rejected() {
            let rejects = |sep: &str, platform: &str| {
                matches!(
                    sanitize_filename("a b", sep, 255, platform, None, true),
                    Err(crate::ErrorRepr::InvalidFilenameSeparator { .. })
                )
            };
            for platform in PLATFORMS {
                for sep in [
                    "/", "\\", "\0", " ", "\t", "\n", "\u{7F}", "-\u{1B}", "\u{A0}", "\u{3000}",
                    "\u{202E}", "\u{200B}", "\u{E9}",
                ] {
                    assert!(rejects(sep, platform), "{sep:?} accepted on {platform}");
                }
                for sep in ["", "_", "-", ".", "--", "~", "+"] {
                    assert!(!rejects(sep, platform), "{sep:?} rejected on {platform}");
                }
            }
            // What is illegal depends on the platform, as it does for the stem.
            for sep in [":", "*", "?", "\"", "<", ">", "|"] {
                assert!(
                    rejects(sep, "universal") && rejects(sep, "windows"),
                    "{sep:?}"
                );
                assert!(!rejects(sep, "posix"), "{sep:?}");
            }
            // The error names the character.
            assert_eq!(
                sanitize_filename("x", "-/", 255, "posix", None, true)
                    .unwrap_err()
                    .code(),
                "invalid_filename_separator"
            );
        }

        /// Finding 2's reproductions, which now fail instead of returning these.
        #[test]
        fn the_reproductions_are_refused() {
            assert!(sanitize_filename("../etc/passwd", "/", 255, "universal", None, true).is_err());
            assert!(sanitize_filename("a b", "\0", 255, "universal", None, true).is_err());
            assert!(sanitize_filename("con _", " ", 4, "universal", None, false).is_err());
            assert!(sanitize_filename("AUX .txt", " ", 255, "universal", None, false).is_err());
        }

        /// Finding 3: outputs that a second call changed.
        #[test]
        fn the_non_fixed_points_are_fixed_points() {
            let cases: [(&str, &str, usize, bool, &str); 7] = [
                ("_.x.*", "_", 255, true, "_.x"),
                ("ab_cd", "_", 3, false, "ab"),
                ("a.bcd.txt", "_", 6, true, "a.txt"),
                ("a. .b", "", 255, false, "a.b"),
                (". ./", "-", 255, false, "-"),
                ("PRN.txt", "_", 5, true, "_.txt"),
                ("../../../etc/passwd", "_", 255, true, "_.etcpasswd"),
            ];
            for (input, sep, max_length, keep_ext, want) in cases {
                for platform in PLATFORMS {
                    let once = sf(input, sep, max_length, platform, keep_ext);
                    if platform != "posix" {
                        assert_eq!(once, want, "{input:?} ({platform})");
                    }
                    let twice = sf(&once, sep, max_length, platform, keep_ext);
                    assert_eq!(twice, once, "{input:?} ({platform}) not a fixed point");
                }
            }
        }

        /// Finding 15: one typed `%` let every manufactured one through.
        #[test]
        fn a_typed_percent_does_not_license_a_manufactured_one() {
            let fw = "\u{FF05}\u{FF12}\u{FF25}\u{FF05}\u{FF12}\u{FF25}\u{FF05}\u{FF12}\u{FF26}";
            assert_eq!(default(&format!("%{fw}etc.txt")), "%_2E_2E_2Fetc.txt");
            assert_eq!(default(&format!("{fw}%etc.txt")), "_2E_2E_2F%etc.txt");
            assert_eq!(default(&format!("{fw}etc.txt")), "_2E_2E_2Fetc.txt");
            // Typed ones stay exactly where they were.
            assert_eq!(default("100%.txt"), "100%.txt");
            assert_eq!(default("..%2Fetc"), "%2Fetc");
            for c in ["\u{609}", "\u{60A}", "\u{66A}", "\u{FE6A}", "\u{FF05}"] {
                let out = default(&format!("%a{c}b%.txt"));
                assert_eq!(out.matches('%').count(), 2, "{c:?} -> {out:?}");
            }
        }

        /// The pass loop skips NFC and transliteration from the second pass on, which is
        /// exact only because both are the identity on ASCII, for every language.
        #[test]
        fn preparation_is_the_identity_on_ascii() {
            let ascii: String = (0u8..=0x7F).map(char::from).collect();
            let langs: Vec<Option<String>> = std::iter::once(None)
                .chain(crate::tables::list_langs().into_iter().map(Some))
                .collect();
            for lang in &langs {
                let out = transliterate_keeping_typed_percent(&ascii, lang.as_deref(), "_");
                assert_eq!(out, ascii, "lang {lang:?}");
            }
            let nfc: String = ascii.nfc().collect();
            assert_eq!(nfc, ascii);
        }

        fn grid_words(alphabet: &[char], max_len: usize) -> Vec<String> {
            let mut words = vec![String::new()];
            let mut frontier = vec![String::new()];
            for _ in 0..max_len {
                let mut next = Vec::new();
                for w in &frontier {
                    for &c in alphabet {
                        let mut n = w.clone();
                        n.push(c);
                        next.push(n);
                    }
                }
                words.extend(next.iter().cloned());
                frontier = next;
            }
            words
        }

        /// P1-P9 of the model over its filename grid, and the pass bound.
        fn check_grid(max_word: usize) -> usize {
            let alphabet = ['.', ' ', '/', '*', '_', 'c', 'o', 'n', 'x'];
            let mut worst = 0;
            for word in grid_words(&alphabet, max_word) {
                for sep in ["_", "", "-", "."] {
                    for max_length in [0, 1, 2, 3, 4, 5, 6, 8] {
                        for platform in ["universal", "posix"] {
                            let illegal = if platform == "posix" {
                                POSIX_ILLEGAL
                            } else {
                                UNIVERSAL_ILLEGAL
                            };
                            for keep_ext in [true, false] {
                                let config = PassConfig {
                                    separator: sep,
                                    max_length,
                                    illegal_chars: illegal,
                                    checks_reserved: platform != "posix",
                                    preserve_extension: keep_ext,
                                };
                                let n = passes(&word, &config);
                                assert!(n.is_some(), "no fixed point for {word:?} {sep:?}");
                                worst = worst.max(n.unwrap_or(0));
                                let out = sf(&word, sep, max_length, platform, keep_ext);
                                let case = format!("{word:?} {sep:?} {max_length} {platform} {keep_ext} -> {out:?}");
                                assert!(!out.is_empty() && out != "." && out != "..", "{case}");
                                assert!(!out.starts_with(['.', ' ']), "{case}");
                                assert!(!out.ends_with(['.', ' ']), "{case}");
                                assert!(!out.contains(".."), "{case}");
                                assert!(
                                    !out.chars().any(|c| illegal.contains(&c) || c.is_control()),
                                    "{case}"
                                );
                                assert!(max_length == 0 || out.len() <= max_length, "{case}");
                                if platform != "posix" {
                                    assert!(!is_device_name(&out), "{case}");
                                }
                                let again = sf(&out, sep, max_length, platform, keep_ext);
                                assert_eq!(again, out, "not a fixed point: {case}");
                            }
                        }
                    }
                }
            }
            worst
        }

        #[test]
        fn grid_up_to_three_characters() {
            let worst = check_grid(3);
            assert!(worst <= 3, "took {worst} passes");
        }

        /// The model's grid at its full size (words up to 5 characters). Tier 3.
        #[test]
        #[ignore = "exhaustive: the Lean model's sanitize_filename grid; Tier 3"]
        fn fixed_point_within_the_pass_bound() {
            let worst = check_grid(5);
            assert!(worst <= 4, "took {worst} passes");
        }

        use proptest::prelude::*;

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(2000))]

            /// Off the grid: arbitrary text, multi-character separators, every platform.
            #[test]
            fn random_inputs_reach_a_fixed_point(
                text in "([. /*_\\-%:\\\\a-z0-9]|\\PC){0,24}",
                sep in prop::sample::select(vec!["_", "", "-", ".", "--", "ab", "._", "~"]),
                max_length in 0usize..20,
                platform in prop::sample::select(PLATFORMS.to_vec()),
                keep_ext in proptest::bool::ANY,
            ) {
                let illegal = if platform == "posix" { POSIX_ILLEGAL } else { UNIVERSAL_ILLEGAL };
                let config = PassConfig {
                    separator: sep,
                    max_length,
                    illegal_chars: illegal,
                    checks_reserved: platform != "posix",
                    preserve_extension: keep_ext,
                };
                let n = passes(&text, &config);
                prop_assert!(n.is_some(), "{text:?}: {n:?} passes");
                let out = sf(&text, sep, max_length, platform, keep_ext);
                prop_assert_eq!(sf(&out, sep, max_length, platform, keep_ext), out.clone());
                if platform != "posix" {
                    prop_assert!(!is_device_name(&out), "{text:?} -> {out:?}");
                }
            }
        }
    }

    // #485/#487: the attacker-filename battery (path traversal, Unicode separator
    // homoglyphs, control/NUL, RTLO/bidi, the ADS colon, dot hygiene, strips-to-empty,
    // the separator-plus-dot-like class), plus the closure and idempotency invariants.
    mod attacker_vectors {
        use super::super::*;

        fn sf(input: &str) -> String {
            sanitize_filename(input, "_", 255, "universal", None, true).unwrap()
        }

        fn assert_safe(input: &str, out: &str) {
            assert!(!out.is_empty(), "EMPTY output for {input:?}");
            assert!(
                out != "." && out != "..",
                "directory reference {out:?} from {input:?}"
            );
            assert!(
                !out.contains('/') && !out.contains('\\'),
                "path separator survived: {out:?} from {input:?}"
            );
            assert!(
                !out.contains(".."),
                "traversal survived: {out:?} from {input:?}"
            );
            assert!(
                !out.starts_with('.'),
                "leading dot (dotfile) survived: {out:?} from {input:?}"
            );
            assert!(
                !out.ends_with('.') && !out.ends_with(' '),
                "trailing dot/space survived (Windows strips these): {out:?} from {input:?}"
            );
            assert!(
                !out.chars().any(char::is_control),
                "control char survived: {out:?} from {input:?}"
            );
            let stem = out.split('.').next().unwrap_or(out).to_uppercase();
            assert!(
                !WINDOWS_RESERVED.iter().any(|r| stem == *r),
                "bare reserved device name survived: {out:?} from {input:?}"
            );
        }

        fn battery() -> Vec<(&'static str, String)> {
            vec![
                ("traversal_unix", "../../etc/passwd".into()),
                ("traversal_win", "..\\..\\Windows\\System32\\cmd.exe".into()),
                ("traversal_mixed", "....//....//etc/passwd".into()),
                ("abs_unix", "/etc/passwd".into()),
                ("abs_win", "C:\\Windows\\System32".into()),
                ("unc", "\\\\server\\share\\x".into()),
                ("win_device_ns", "\\\\.\\PhysicalDrive0".into()),
                ("fullwidth_solidus", format!("a{}b", '\u{FF0F}')),
                ("fraction_slash", format!("a{}b", '\u{2044}')),
                ("division_slash", format!("a{}b", '\u{2215}')),
                ("fullwidth_revsolidus", format!("a{}b", '\u{FF3C}')),
                (
                    "fullwidth_dotdot_sol",
                    format!("{}{}{}", '\u{FF0E}', '\u{FF0E}', '\u{FF0F}'),
                ),
                ("nul_byte", "safe\u{0}.png".into()),
                ("newline", "a\nb.txt".into()),
                ("carriage_return", "a\rb".into()),
                ("escape", "a\u{1b}b".into()),
                ("del", "a\u{7f}b".into()),
                ("rtlo", format!("exploit{}gpj.exe", '\u{202E}')),
                ("lro", format!("a{}b", '\u{202D}')),
                ("rlo_lone", "\u{202E}".into()),
                ("con", "CON".into()),
                ("con_lc", "con".into()),
                ("con_ext", "CON.txt".into()),
                ("nul_ext", "nul.dat".into()),
                ("com1", "COM1.txt".into()),
                ("lpt9", "LPT9".into()),
                ("con_trailing_dot", "CON.".into()),
                ("con_trailing_space", "CON ".into()),
                (
                    "fullwidth_con",
                    format!("{}{}{}", '\u{FF23}', '\u{FF2F}', '\u{FF2E}'),
                ),
                ("cyrillic_con", format!("{}ON", '\u{0421}')),
                ("greek_omicron_con", format!("C{}N", '\u{039F}')),
                ("ads_colon", "file.txt:secret".into()),
                ("win_illegals", "a<b>:\"|?*".into()),
                ("trailing_dots", "report...".into()),
                ("trailing_space", "report ".into()),
                ("leading_dot", ".bashrc".into()),
                ("lone_dot", ".".into()),
                ("lone_dotdot", "..".into()),
                ("dots_and_spaces", ". . .".into()),
                ("empty", String::new()),
                ("nuls_only", "\u{0}\u{0}\u{0}".into()),
                ("ctrl_only", "\u{1}\u{2}\u{1f}".into()),
                ("spaces_only", "     ".into()),
                ("seps_only", "/////".into()),
                ("zwsp_only", format!("{}{}", '\u{200b}', '\u{200b}')),
                ("very_long", format!("{}.txt", "a".repeat(1000))),
                ("long_combining", format!("a{}", "\u{0301}".repeat(400))),
                // #487 separator-plus-dot-like class: each must not yield "." and must be idempotent.
                ("sep_middle_dot", "_\u{00B7}".into()),
                ("sep_dot_above", "_\u{02D9}".into()),
                ("sep_ano_teleia", "_\u{0387}".into()),
                ("sep_armenian_stop", "_\u{0589}".into()),
                ("sep_hebrew_sof_pasuq", "_\u{05C3}".into()),
                ("sep_devanagari_danda", "_\u{0964}".into()),
            ]
        }

        #[test]
        fn attacker_battery_all_safe() {
            for (name, input) in battery() {
                let out = sf(&input);
                assert_safe(name, &out);
                assert!(
                    out.len() <= 255,
                    "over max_length: {} bytes from {name}",
                    out.len()
                );
            }
        }

        #[test]
        fn empty_input_never_returns_empty() {
            assert_eq!(sf(""), "_");
            assert_eq!(sf("     "), "_");
            assert_eq!(sf("/////"), "_");
            assert_eq!(sf("\u{0}\u{0}"), "_");
        }

        #[test]
        fn never_returns_directory_reference() {
            // #487: separator-then-dot reduces to a bare "." today; must fall back to "_".
            assert_eq!(sf("_\u{00B7}"), "_"); // "_" + MIDDLE DOT -> "_.", stem stripped -> "." -> "_"
            assert_eq!(sf("."), "_");
            assert_eq!(sf(".."), "_");
            for (_, input) in battery() {
                let out = sf(&input);
                assert!(
                    out != "." && out != "..",
                    "directory reference {out:?} from {input:?}"
                );
            }
        }

        #[test]
        fn no_leading_dot_dotfile() {
            assert!(!sf("../../etc/passwd").starts_with('.'));
            assert!(!sf("\\\\.\\PhysicalDrive0").starts_with('.'));
            assert_eq!(sf(".bashrc"), "bashrc");
        }

        #[test]
        fn no_trailing_dot_or_space() {
            assert!(!sf("report...").ends_with('.'));
            assert!(!sf("CON.").ends_with('.'));
            assert!(!sf("report ").ends_with(' '));
        }

        #[test]
        fn is_idempotent_over_the_battery() {
            // #487 criterion 2: a sanitized name is a fixed point.
            for (name, input) in battery() {
                let once = sf(&input);
                let twice = sf(&once);
                assert_eq!(
                    once, twice,
                    "not idempotent on {name}: {once:?} -> {twice:?}"
                );
            }
        }

        #[test]
        fn unicode_separator_homoglyphs_do_not_resurface() {
            use unicode_normalization::UnicodeNormalization;
            for input in [
                format!("a{}b", '\u{FF0F}'),
                format!("a{}b", '\u{2044}'),
                format!("a{}b", '\u{2215}'),
            ] {
                let out = sf(&input);
                let nfkc: String = out.nfkc().collect();
                assert!(
                    !nfkc.contains('/') && !nfkc.contains('\\'),
                    "NFKC of {out:?} reintroduced a separator"
                );
            }
        }

        #[test]
        fn homoglyph_reserved_names_neutralized() {
            for input in [
                format!("{}{}{}", '\u{FF23}', '\u{FF2F}', '\u{FF2E}'),
                format!("C{}N", '\u{039F}'),
                format!("{}ON", '\u{0421}'),
            ] {
                let out = sf(&input);
                let stem = out.split('.').next().unwrap_or(&out).to_uppercase();
                assert!(
                    !WINDOWS_RESERVED.iter().any(|r| stem == *r),
                    "reserved survived: {out:?}"
                );
            }
        }
    }
}
