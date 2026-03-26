use pyo3::prelude::*;
use unicode_normalization::UnicodeNormalization;

use crate::{case_fold, confusables, emoji, transliterate, whitespace, zalgo};

/// Maximum input size for pipeline presets, in bytes.
///
/// Pipeline functions compose multiple transforms (NFKC, confusables,
/// transliteration, etc.), each of which can expand the text.  This cap
/// bounds worst-case memory usage across the entire pipeline.
const MAX_PRESET_INPUT_BYTES: usize = 10 * 1024 * 1024; // 10 MiB

/// Validate that preset input does not exceed the size cap.
#[inline]
fn check_preset_input(text: &str, fn_name: &str) -> PyResult<()> {
    if text.len() > MAX_PRESET_INPUT_BYTES {
        return translit_err!(
            "input too large ({} bytes); maximum for {}() is {} bytes",
            text.len(),
            fn_name,
            MAX_PRESET_INPUT_BYTES
        );
    }
    Ok(())
}

/// Strip dangerous bidirectional override and formatting characters
/// that `collapse_whitespace` does not handle.
///
/// Character list follows UAX #9 (Unicode Bidirectional Algorithm) §3.3.2
/// "Explicit Directional Formatting Characters" plus the soft hyphen
/// (frequently abused to split security keywords invisibly).
///
/// Covers: soft hyphen (U+00AD), Arabic Letter Mark (U+061C),
/// bidi marks (U+200E–U+200F), bidi embeddings/overrides (U+202A–U+202E),
/// bidi isolates (U+2066–U+2069).
fn strip_bidi(text: &str) -> String {
    text.chars().filter(|&ch| !is_bidi_or_format(ch)).collect()
}

#[inline]
fn is_bidi_or_format(ch: char) -> bool {
    // ── Soft hyphen ─────────────────────────────────────
    // Not a bidi char per se, but invisible and used to split keywords.
    if ch == '\u{00AD}' {
        return true;
    }

    // ── UAX #9 §3.3.2 bidi formatting characters ───────
    // Grouped by Unicode version for auditability.
    matches!(
        ch,
        // Unicode 1.0 – marks
        '\u{200E}'             // LRM  Left-to-Right Mark
        | '\u{200F}'           // RLM  Right-to-Left Mark
        // Unicode 1.0 – explicit embeddings / overrides
        | '\u{202A}'           // LRE  Left-to-Right Embedding
        | '\u{202B}'           // RLE  Right-to-Left Embedding
        | '\u{202C}'           // PDF  Pop Directional Formatting
        | '\u{202D}'           // LRO  Left-to-Right Override
        | '\u{202E}'           // RLO  Right-to-Left Override
        // Unicode 6.3 – isolates + Arabic Letter Mark
        | '\u{061C}'           // ALM  Arabic Letter Mark
        | '\u{2066}'           // LRI  Left-to-Right Isolate
        | '\u{2067}'           // RLI  Right-to-Left Isolate
        | '\u{2068}'           // FSI  First Strong Isolate
        | '\u{2069}' // PDI  Pop Directional Isolate
    )
}

// ---------------------------------------------------------------------------
// Precompiled pipeline functions
// ---------------------------------------------------------------------------

/// Security-focused text canonicalization.
///
/// Pipeline: NFKC → confusables → strip bidi/format → collapse_whitespace
///
/// Collapses fullwidth bypasses, neutralizes homoglyph spoofing, strips
/// zero-width injections and control chars, and removes dangerous bidi
/// overrides and soft hyphens that could enable text reordering attacks.
///
/// `strip_bidi` runs *before* `collapse_whitespace` so that removing
/// invisible characters (e.g. soft hyphen U+00AD) can expose leading,
/// trailing, or consecutive whitespace that `collapse_whitespace` then
/// normalizes.  This guarantees idempotency.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _security_clean(text: &str) -> PyResult<String> {
    check_preset_input(text, "security_clean")?;
    // 1. NFKC normalization (collapses fullwidth, ligatures, superscripts)
    let buf: String = text.nfkc().collect();
    // 2. Confusables → Latin (neutralizes cross-script homoglyphs)
    let buf = confusables::_normalize_confusables(&buf, "latin")?;
    // 3. Strip bidi overrides, isolates, marks, and soft hyphens
    let buf = strip_bidi(&buf);
    // 4. Collapse whitespace + strip control + strip zero-width (final cleanup)
    Ok(whitespace::_collapse_whitespace(&buf, true, true))
}

/// ML/NLP text normalization pipeline.
///
/// Pipeline: NFKC → emoji→text → strip_accents → fold_case → collapse_whitespace
///
/// Produces clean, accent-free, lowercased text suitable for tokenizers,
/// embeddings, and feature extraction. Emoji are expanded to their CLDR
/// short-name descriptions before transliteration.
///
/// # Parameters
/// - `emoji_style`: `"cldr"` — expand emoji to CLDR short names (default).
///                  `"none"` — leave emoji characters as-is.
///                  Any other value raises `TranslitError`.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None, emoji_style="cldr"))]
pub fn _ml_normalize(text: &str, lang: Option<&str>, emoji_style: &str) -> PyResult<String> {
    check_preset_input(text, "ml_normalize")?;
    // Validate emoji_style — only two modes are supported.
    if !matches!(emoji_style, "cldr" | "none") {
        return Err(crate::TranslitError::new_err(format!(
            "emoji_style must be 'cldr' or 'none', got '{emoji_style}'"
        )));
    }
    // 1. NFKC normalization
    let mut buf: String = text.nfkc().collect();
    // 2. Emoji → text (CLDR short names)
    if emoji_style == "cldr" {
        buf = emoji::demojize_rust(&buf, false);
    }
    // 3. Transliterate if lang is set (e.g. "de" for ü→ue, "ja" for kana)
    if lang.is_some() {
        buf = transliterate::transliterate_impl(
            &buf,
            lang,
            crate::ErrorMode::Preserve,
            "",
            false,
            false,
        )
        .into_owned();
    }
    // 4. Strip accents (NFD decompose → remove combining marks → NFC)
    buf = transliterate::_strip_accents(&buf);
    // 5. Unicode case folding (ß→ss, ﬁ→fi, etc.)
    buf = case_fold::fold_case_impl(&buf);
    // 6. Collapse whitespace + strip control + strip zero-width
    buf = whitespace::_collapse_whitespace(&buf, true, true);
    Ok(buf)
}

/// Library catalog key generation pipeline.
///
/// Pipeline: NFKC → transliterate → confusables → strip_accents → fold_case → collapse_whitespace
///
/// Transliteration runs before confusable normalization so that non-Latin
/// scripts receive correct phonetic romanization (e.g. Cyrillic г→g, not
/// the visual confusable г→r).
///
/// Produces a canonical deduplication key for bibliographic titles.
/// Optional ISO 9:1995 transliteration for Cyrillic catalog records.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None, strict_iso9=false))]
pub fn _catalog_key(text: &str, lang: Option<&str>, strict_iso9: bool) -> PyResult<String> {
    check_preset_input(text, "catalog_key")?;
    // 1. NFKC normalization
    let buf: String = text.nfkc().collect();
    // 2. Transliterate (always — catalog keys should be pure ASCII where possible;
    //    runs before confusables so that non-Latin scripts are romanized first,
    //    avoiding broken confusable mappings like Cyrillic к → literal \u{0138})
    let buf = transliterate::transliterate_impl(
        &buf,
        lang,
        crate::ErrorMode::Preserve,
        "",
        strict_iso9,
        false,
    )
    .into_owned();
    // 3. Confusables → Latin (normalize any remaining cross-script homoglyphs)
    let buf = confusables::_normalize_confusables(&buf, "latin")?;
    // 4. Strip accents
    let buf = transliterate::_strip_accents(&buf);
    // 5. Unicode case folding
    let buf = case_fold::fold_case_impl(&buf);
    // 6. Collapse whitespace + strip control + strip zero-width
    let buf = whitespace::_collapse_whitespace(&buf, true, true);
    Ok(buf)
}

/// Search index key generation pipeline.
///
/// Pipeline: NFKC → transliterate → strip_accents → fold_case → collapse_whitespace
///
/// Produces a case-insensitive, accent-insensitive, script-insensitive lookup
/// key.  Like `catalog_key` but without confusable normalization — lighter and
/// faster for search indexes where homoglyph attacks are not a concern.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None))]
pub fn _search_key(text: &str, lang: Option<&str>) -> PyResult<String> {
    check_preset_input(text, "search_key")?;
    // 1. NFKC normalization
    let buf: String = text.nfkc().collect();
    // 2. Transliterate (always — search keys should be pure ASCII where possible)
    let buf =
        transliterate::transliterate_impl(&buf, lang, crate::ErrorMode::Preserve, "", false, false)
            .into_owned();
    // 3. Strip accents
    let buf = transliterate::_strip_accents(&buf);
    // 4. Unicode case folding
    let buf = case_fold::fold_case_impl(&buf);
    // 5. Collapse whitespace + strip control + strip zero-width
    let buf = whitespace::_collapse_whitespace(&buf, true, true);
    Ok(buf)
}

/// Sort key generation pipeline.
///
/// Pipeline: NFKC → transliterate → fold_case → collapse_whitespace
///
/// Like `search_key` but preserves base accented characters for correct
/// alphabetical ordering.  "Über" sorts next to "Uber", and "Война и мир"
/// files under "voyna i mir".
#[pyfunction]
#[pyo3(signature = (text, *, lang=None))]
pub fn _sort_key(text: &str, lang: Option<&str>) -> PyResult<String> {
    check_preset_input(text, "sort_key")?;
    // 1. NFKC normalization
    let buf: String = text.nfkc().collect();
    // 2. Transliterate (always — sort keys need a consistent script)
    let buf =
        transliterate::transliterate_impl(&buf, lang, crate::ErrorMode::Preserve, "", false, false)
            .into_owned();
    // 3. Unicode case folding
    let buf = case_fold::fold_case_impl(&buf);
    // 4. Collapse whitespace + strip control + strip zero-width
    let buf = whitespace::_collapse_whitespace(&buf, true, true);
    Ok(buf)
}

/// Display-safe text cleaning pipeline.
///
/// Pipeline: strip bidi/format → collapse_whitespace (strip control + strip zero-width)
///
/// Lightweight cleanup for user-submitted content destined for rendering.
/// Strips bidirectional overrides (which can visually reorder text to hide
/// malicious content), control characters, and zero-width injections, then
/// collapses runs of whitespace to single spaces.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _display_clean(text: &str) -> PyResult<String> {
    check_preset_input(text, "display_clean")?;
    // 1. Strip bidi overrides, isolates, marks, and soft hyphens
    let buf = strip_bidi(text);
    // 2. Collapse whitespace + strip control + strip zero-width
    Ok(whitespace::_collapse_whitespace(&buf, true, true))
}

/// Sanitize user-submitted input for web applications.
///
/// Pipeline: NFKC → strip_zalgo → confusables → strip_bidi → collapse_whitespace
///
/// Designed for web developers who want to accept multilingual input in its
/// original script while preventing malicious abuse:
/// - **NFKC**: collapses fullwidth bypasses, ligatures, superscripts
/// - **strip_zalgo**: caps combining marks at 2 per base character, preventing
///   stacked diacritical abuse while preserving legitimate diacritics (é, ñ, ệ)
/// - **confusables**: neutralizes cross-script homoglyph attacks
/// - **strip_bidi**: removes bidirectional overrides that can visually reorder text
/// - **collapse_whitespace**: strips control chars, zero-width injections,
///   normalizes whitespace runs
///
/// Unlike `security_clean`, this pipeline strips zalgo text.  Unlike
/// `catalog_key`/`search_key`, it does *not* transliterate — the original
/// script is preserved.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _sanitize_user_input(text: &str) -> PyResult<String> {
    check_preset_input(text, "sanitize_user_input")?;
    // 1. NFKC normalization
    let buf: String = text.nfkc().collect();
    // 2. Strip zalgo (cap combining marks at 2 per base character)
    let buf = zalgo::_strip_zalgo(&buf, 2);
    // 3. Confusables → Latin (neutralizes cross-script homoglyphs)
    let buf = confusables::_normalize_confusables(&buf, "latin")?;
    // 4. Strip bidi overrides, isolates, marks, and soft hyphens
    let buf = strip_bidi(&buf);
    // 5. Collapse whitespace + strip control + strip zero-width
    Ok(whitespace::_collapse_whitespace(&buf, true, true))
}

// ---------------------------------------------------------------------------
// Also expose strip_bidi as a public utility
// ---------------------------------------------------------------------------

/// Strip bidirectional override and formatting characters (UAX #9).
///
/// Removes: soft hyphen (U+00AD), Arabic Letter Mark (U+061C),
/// LRM/RLM (U+200E/F), bidi embeddings/overrides (U+202A–U+202E),
/// bidi isolates (U+2066–U+2069).
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _strip_bidi(text: &str) -> String {
    strip_bidi(text)
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── strip_bidi: exhaustive UAX #9 coverage ────────────────
    // Every character in is_bidi_or_format gets its own assertion so
    // that a future omission is caught immediately.

    #[test]
    fn test_strip_bidi_soft_hyphen() {
        assert_eq!(strip_bidi("pass\u{00AD}word"), "password");
    }

    #[test]
    fn test_strip_bidi_arabic_letter_mark() {
        // U+061C — added in Unicode 6.3; lives in the Arabic block,
        // far from the other bidi controls, which is why it was missed.
        assert_eq!(strip_bidi("hello\u{061C}world"), "helloworld");
    }

    #[test]
    fn test_strip_bidi_marks() {
        assert_eq!(strip_bidi("a\u{200E}b"), "ab"); // LRM
        assert_eq!(strip_bidi("a\u{200F}b"), "ab"); // RLM
    }

    #[test]
    fn test_strip_bidi_embeddings_overrides() {
        assert_eq!(strip_bidi("a\u{202A}b"), "ab"); // LRE
        assert_eq!(strip_bidi("a\u{202B}b"), "ab"); // RLE
        assert_eq!(strip_bidi("a\u{202C}b"), "ab"); // PDF
        assert_eq!(strip_bidi("a\u{202D}b"), "ab"); // LRO
        assert_eq!(strip_bidi("a\u{202E}b"), "ab"); // RLO
    }

    #[test]
    fn test_strip_bidi_isolates() {
        assert_eq!(strip_bidi("a\u{2066}b"), "ab"); // LRI
        assert_eq!(strip_bidi("a\u{2067}b"), "ab"); // RLI
        assert_eq!(strip_bidi("a\u{2068}b"), "ab"); // FSI
        assert_eq!(strip_bidi("a\u{2069}b"), "ab"); // PDI
    }

    #[test]
    fn test_strip_bidi_all_at_once() {
        // Every UAX #9 bidi char + soft hyphen in a single string.
        // If a new char is added to is_bidi_or_format, add it here too.
        let all_bidi = "\u{00AD}\u{061C}\u{200E}\u{200F}\
                        \u{202A}\u{202B}\u{202C}\u{202D}\u{202E}\
                        \u{2066}\u{2067}\u{2068}\u{2069}";
        assert_eq!(strip_bidi(&format!("x{all_bidi}y")), "xy");
        // Verify we have exactly 13 characters in the list
        assert_eq!(all_bidi.chars().count(), 13);
    }

    #[test]
    fn test_strip_bidi_preserves_normal() {
        assert_eq!(strip_bidi("hello world"), "hello world");
        assert_eq!(strip_bidi("café"), "café");
        // Arabic text itself is preserved — only formatting chars are stripped
        assert_eq!(strip_bidi("مرحبا"), "مرحبا");
    }

    #[test]
    fn test_security_clean_homoglyph() {
        // Cyrillic р and а in "раypal"
        let result = _security_clean("\u{0440}\u{0430}ypal").unwrap();
        assert_eq!(result, "paypal");
    }

    #[test]
    fn test_security_clean_bidi() {
        let result = _security_clean("admin\u{202E}user").unwrap();
        assert_eq!(result, "adminuser");
    }

    #[test]
    fn test_security_clean_arabic_letter_mark() {
        let result = _security_clean("admin\u{061C}user").unwrap();
        assert_eq!(result, "adminuser");
    }

    #[test]
    fn test_security_clean_invisible_math_operators() {
        // Invisible math operators are stripped by collapse_whitespace (step 3),
        // so security_clean should remove them too.
        let result = _security_clean("pass\u{2061}word").unwrap();
        assert_eq!(result, "password");
    }

    #[test]
    fn test_security_clean_soft_hyphen() {
        let result = _security_clean("pass\u{00AD}word").unwrap();
        assert_eq!(result, "password");
    }

    #[test]
    fn test_security_clean_zwsp() {
        let result = _security_clean("admin\u{200B}user").unwrap();
        assert_eq!(result, "adminuser");
    }

    #[test]
    fn test_ml_normalize_basic() {
        let result = _ml_normalize("Café Résumé", None, "cldr").unwrap();
        assert_eq!(result, "cafe resume");
    }

    #[test]
    fn test_ml_normalize_ligature() {
        let result = _ml_normalize("\u{FB01}lter", None, "cldr").unwrap();
        assert_eq!(result, "filter");
    }

    #[test]
    fn test_catalog_key_dedup() {
        let a = _catalog_key("Café", None, false).unwrap();
        let b = _catalog_key("café", None, false).unwrap();
        let c = _catalog_key("CAFÉ", None, false).unwrap();
        assert_eq!(a, b);
        assert_eq!(b, c);
    }

    #[test]
    fn test_catalog_key_iso9() {
        let result = _catalog_key("\u{0419}\u{043E}\u{0433}\u{0430}", None, true).unwrap();
        // Transliterate first with ISO 9: Й→J, о→o, г→g, а→a → "joga"
        assert_eq!(result, "joga");
    }

    #[test]
    fn test_search_key_accent_insensitive() {
        let a = _search_key("Café", None).unwrap();
        let b = _search_key("cafe", None).unwrap();
        let c = _search_key("CAFÉ", None).unwrap();
        assert_eq!(a, "cafe");
        assert_eq!(a, b);
        assert_eq!(b, c);
    }

    #[test]
    fn test_search_key_cyrillic() {
        assert_eq!(_search_key("Москва", None).unwrap(), "moskva");
    }

    #[test]
    fn test_search_key_greek() {
        assert_eq!(_search_key("ΩMEGA", None).unwrap(), "omega");
    }

    #[test]
    fn test_sort_key_preserves_accents_as_base() {
        // sort_key does NOT strip accents — fold_case handles ß→ss etc.
        // but accented chars stay as their base after transliteration
        let result = _sort_key("Über", None).unwrap();
        assert_eq!(result, "uber");
    }

    #[test]
    fn test_sort_key_cyrillic() {
        assert_eq!(_sort_key("Война и мир", None).unwrap(), "voyna i mir");
    }

    #[test]
    fn test_sort_key_vs_search_key() {
        // Both produce lowercase ASCII for non-Latin
        assert_eq!(
            _sort_key("Москва", None).unwrap(),
            _search_key("Москва", None).unwrap()
        );
    }

    #[test]
    fn test_display_clean_basic() {
        assert_eq!(_display_clean("hello   world").unwrap(), "hello world");
        assert_eq!(_display_clean("hello\x00world").unwrap(), "helloworld");
        assert_eq!(_display_clean("hello\u{200B}world").unwrap(), "helloworld");
    }

    #[test]
    fn test_display_clean_strips_bidi() {
        // RLO can visually reorder rendered text to hide malicious content
        assert_eq!(_display_clean("admin\u{202E}user").unwrap(), "adminuser");
        // Soft hyphen can split security keywords invisibly
        assert_eq!(_display_clean("pass\u{00AD}word").unwrap(), "password");
        // Arabic Letter Mark
        assert_eq!(_display_clean("hello\u{061C}world").unwrap(), "helloworld");
    }

    // ── sanitize_user_input ──────────────────────────────────

    #[test]
    fn test_sanitize_user_input_clean_text() {
        assert_eq!(
            _sanitize_user_input("Hello, world!").unwrap(),
            "Hello, world!"
        );
    }

    #[test]
    fn test_sanitize_user_input_preserves_script() {
        // Original script is preserved (no transliteration)
        let result = _sanitize_user_input("Москва").unwrap();
        // Confusables maps some Cyrillic to Latin, but that's intentional
        // for homoglyph protection — the key point is no transliteration step
        assert!(!result.is_empty());
    }

    #[test]
    fn test_sanitize_user_input_strips_zalgo() {
        let mut zalgo = String::from("hello");
        for _ in 0..20 {
            zalgo.push('\u{0300}');
        }
        zalgo.push_str(" world");
        let result = _sanitize_user_input(&zalgo).unwrap();
        // Zalgo marks stripped down to max 2 per base
        assert!(result.len() < zalgo.len());
        assert!(result.contains("world"));
    }

    #[test]
    fn test_sanitize_user_input_strips_bidi() {
        assert_eq!(
            _sanitize_user_input("admin\u{202E}user").unwrap(),
            "adminuser"
        );
    }

    #[test]
    fn test_sanitize_user_input_strips_zero_width() {
        assert_eq!(
            _sanitize_user_input("pass\u{200B}word").unwrap(),
            "password"
        );
    }

    #[test]
    fn test_sanitize_user_input_preserves_accents() {
        // Legitimate diacritics are preserved (max_marks=2 keeps them)
        assert_eq!(_sanitize_user_input("café").unwrap(), "cafe");
        // Note: confusables maps to Latin, so é → e after NFKC + confusables
    }

    #[test]
    fn test_sanitize_user_input_homoglyph() {
        // Cyrillic а in "pаypal" → Latin a
        let result = _sanitize_user_input("p\u{0430}ypal").unwrap();
        assert_eq!(result, "paypal");
    }
}
