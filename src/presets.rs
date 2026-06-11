use std::borrow::Cow;

use pyo3::prelude::*;
use unicode_normalization::UnicodeNormalization;

use crate::{case_fold, confusables, emoji, transliterate, whitespace, zalgo};

// disarm does not cap input size in the pipeline presets — bounding untrusted
// input is the caller's responsibility (every stage is linear time/memory;
// see #80). The only retained size guard is the register_replacements output
// amplification bound in src/transliterate.rs.

/// NFKC-normalize `text`, skipping the normalization pass for all-ASCII input.
///
/// Every ASCII scalar (U+0000–U+007F) is already in NFKC normal form — ASCII has
/// no compatibility decompositions and no combining marks to compose — so
/// `nfkc()` is the identity on ASCII (the same property `normalize()`'s ASCII
/// fast path relies on). Detecting that with one SIMD-friendly `is_ascii()` scan
/// lets these presets skip the normalizer's per-character state machine **and**
/// the allocation for the common ASCII case: the ASCII branch borrows the input
/// (`Cow::Borrowed`, like transliterate()'s fast path) rather than copying it.
/// Each preset then takes ownership at the first stage that produces a new
/// `String` (every next step returns one), so the only ASCII allocation is the
/// one that stage would make anyway. See #198.
#[inline]
fn nfkc_normalize(text: &str) -> Cow<'_, str> {
    if text.is_ascii() {
        Cow::Borrowed(text)
    } else {
        Cow::Owned(text.nfkc().collect())
    }
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
/// bidi isolates (U+2066–U+2069), deprecated format controls (U+206A–U+206F),
/// and interlinear annotation marks (U+FFF9–U+FFFB).
fn strip_bidi(text: &str) -> String {
    let mut out = String::new();
    strip_bidi_into(text, &mut out);
    out
}

/// In-place form of [`strip_bidi`] (#236 item 7).
pub fn strip_bidi_into(text: &str, out: &mut String) {
    out.clear();
    out.extend(text.chars().filter(|&ch| !is_bidi_or_format(ch)));
}

/// Make text safe to use as a path component (#248).
///
/// The security presets must *guarantee* path-safe output: confusable folding
/// can synthesise a separator from a homoglyph (e.g. U+2044 FRACTION SLASH →
/// `/`, U+2215 DIVISION SLASH → `/`, U+2025 TWO DOT LEADER → `..`), and a caller
/// using a preset literally named to *sanitize* untrusted input may reasonably
/// treat the result as safe. Replace ASCII path separators with `_` (matching
/// `sanitize_filename`'s default separator) and collapse runs of `.` so no `..`
/// traversal token survives. With no `/` or `\` left, `../`-style traversal is
/// impossible regardless of dots. Idempotent.
fn neutralize_path_separators(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut prev_dot = false;
    for ch in text.chars() {
        match ch {
            '/' | '\\' => {
                out.push('_');
                prev_dot = false;
            }
            '.' => {
                if !prev_dot {
                    out.push('.');
                }
                prev_dot = true;
            }
            other => {
                out.push(other);
                prev_dot = false;
            }
        }
    }
    out
}

#[inline]
fn is_bidi_or_format(ch: char) -> bool {
    // ── Soft hyphen ─────────────────────────────────────
    // Not a bidi char per se, but invisible and used to split keywords.
    if ch == '\u{00AD}' {
        return true;
    }

    // ── Deprecated format controls + interlinear annotation (#67.2) ──
    // U+206A–U+206F (deprecated: symmetric/digit shaping, inhibit join) and
    // U+FFF9–U+FFFB (interlinear annotation anchor/separator/terminator) are
    // invisible/format characters; strip them here too so strip_bidi /
    // display_clean don't leave them behind (they were previously only handled
    // as transliteration-table entries).
    if matches!(ch, '\u{206A}'..='\u{206F}' | '\u{FFF9}'..='\u{FFFB}') {
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
    // 1. NFKC normalization (collapses fullwidth, ligatures, superscripts)
    let buf = nfkc_normalize(text);
    // 2. Confusables → Latin (neutralizes cross-script homoglyphs)
    let buf = confusables::_normalize_confusables(&buf, "latin")?;
    // 3. Strip bidi overrides, isolates, marks, and soft hyphens
    let buf = strip_bidi(&buf);
    // 4. Collapse whitespace + strip control + strip zero-width
    let buf = whitespace::_collapse_whitespace(&buf, true, true);
    // 5. Path-safety guarantee (#248): never emit a synthesised '/', '\', or
    //    '..' traversal (a confusable like U+2044 must not become an actionable
    //    separator in security-preset output).
    Ok(neutralize_path_separators(&buf))
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
///                  Any other value raises `DisarmError`.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None, emoji_style="cldr"))]
pub fn _ml_normalize(text: &str, lang: Option<&str>, emoji_style: &str) -> PyResult<String> {
    crate::transliterate::validate_lang(lang)?;
    // Validate emoji_style — only two modes are supported.
    if !matches!(emoji_style, "cldr" | "none") {
        return Err(crate::Error::InvalidEmojiStyle {
            got: emoji_style.to_owned(),
        }
        .into());
    }
    // 1. NFKC normalization (borrowed for ASCII; ownership is taken below).
    let normalized = nfkc_normalize(text);
    // 2. Emoji → text (CLDR short names). This stage — or `into_owned()` when
    //    emoji expansion is off — yields the owned `buf` the remaining stages
    //    mutate in place. For the common ASCII+CLDR path `demojize_rust` borrows
    //    `normalized`, so the NFKC step adds no allocation of its own.
    let mut buf = if emoji_style == "cldr" {
        emoji::demojize_rust(&normalized, false)
    } else {
        normalized.into_owned()
    };
    // 3. Transliterate if lang is set (e.g. "de" for ü→ue, "ja" for kana).
    //    Use Ignore mode: ML pipelines need clean ASCII-ish output, so
    //    characters with no mapping (e.g. katakana ー) should be dropped
    //    rather than preserved verbatim.
    if lang.is_some() {
        buf = transliterate::transliterate_impl(
            &buf,
            lang,
            crate::ErrorMode::Ignore,
            "",
            false,
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
/// Pipeline: NFKC → strip_bidi → transliterate → confusables → strip_accents → fold_case → collapse_whitespace
///
/// Transliteration runs before confusable normalization so that non-Latin
/// scripts receive correct phonetic romanization (e.g. Cyrillic г→g, not
/// the visual confusable г→r).
///
/// `strip_bidi` runs early (#93) so bidi overrides (U+202E) and soft hyphens
/// (U+00AD) cannot survive into the key — otherwise two visually-identical
/// titles produce different keys and dedup/lookup silently misses.
///
/// Produces a canonical deduplication key for bibliographic titles.
/// Optional ISO 9:1995 transliteration for Cyrillic catalog records.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None, strict_iso9=false))]
pub fn _catalog_key(text: &str, lang: Option<&str>, strict_iso9: bool) -> PyResult<String> {
    crate::transliterate::validate_lang(lang)?;
    // 1. NFKC normalization
    let buf = nfkc_normalize(text);
    // 2. Strip bidi overrides + soft hyphen + format marks (#93)
    let buf = strip_bidi(&buf);
    // 3. Transliterate (always — catalog keys should be pure ASCII where possible;
    //    runs before confusables so that non-Latin scripts are romanized first,
    //    avoiding broken confusable mappings like Cyrillic к → literal \u{0138})
    let buf = transliterate::transliterate_impl(
        &buf,
        lang,
        crate::ErrorMode::Preserve,
        "",
        strict_iso9,
        false,
        false,
    )
    .into_owned();
    // 4. Confusables → Latin (normalize any remaining cross-script homoglyphs)
    let buf = confusables::_normalize_confusables(&buf, "latin")?;
    // 5. Strip accents
    let buf = transliterate::_strip_accents(&buf);
    // 6. Unicode case folding
    let buf = case_fold::fold_case_impl(&buf);
    // 7. Collapse whitespace + strip control + strip zero-width
    let buf = whitespace::_collapse_whitespace(&buf, true, true);
    Ok(buf)
}

/// Search index key generation pipeline.
///
/// Pipeline: NFKC → strip_bidi → transliterate → strip_accents → fold_case → collapse_whitespace
///
/// Produces a case-insensitive, accent-insensitive, script-insensitive lookup
/// key.  Like `catalog_key` but without confusable normalization — lighter and
/// faster for search indexes where homoglyph attacks are not a concern.
///
/// `strip_bidi` runs early (#93) so an invisible char (bidi override, soft
/// hyphen) embedded in a stored value still produces the same key as the clean
/// query — otherwise lookups silently miss.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None))]
pub fn _search_key(text: &str, lang: Option<&str>) -> PyResult<String> {
    crate::transliterate::validate_lang(lang)?;
    // 1. NFKC normalization
    let buf = nfkc_normalize(text);
    // 2. Strip bidi overrides + soft hyphen + format marks (#93)
    let buf = strip_bidi(&buf);
    // 3. Transliterate (always — search keys should be pure ASCII where possible)
    let buf = transliterate::transliterate_impl(
        &buf,
        lang,
        crate::ErrorMode::Preserve,
        "",
        false,
        false,
        false,
    )
    .into_owned();
    // 4. Strip accents
    let buf = transliterate::_strip_accents(&buf);
    // 5. Unicode case folding
    let buf = case_fold::fold_case_impl(&buf);
    // 6. Collapse whitespace + strip control + strip zero-width
    let buf = whitespace::_collapse_whitespace(&buf, true, true);
    Ok(buf)
}

/// Sort key generation pipeline.
///
/// Pipeline: NFKC → strip_bidi → transliterate → fold_case → collapse_whitespace
///
/// Like `search_key` but preserves base accented characters for correct
/// alphabetical ordering.  "Über" sorts next to "Uber", and "Война и мир"
/// files under "voyna i mir".
///
/// `strip_bidi` runs early (#93) so invisible bidi/format chars cannot perturb
/// the ordering of otherwise-identical strings.
#[pyfunction]
#[pyo3(signature = (text, *, lang=None))]
pub fn _sort_key(text: &str, lang: Option<&str>) -> PyResult<String> {
    crate::transliterate::validate_lang(lang)?;
    // 1. NFKC normalization
    let buf = nfkc_normalize(text);
    // 2. Strip bidi overrides + soft hyphen + format marks (#93)
    let buf = strip_bidi(&buf);
    // 3. Transliterate (always — sort keys need a consistent script)
    let buf = transliterate::transliterate_impl(
        &buf,
        lang,
        crate::ErrorMode::Preserve,
        "",
        false,
        false,
        false,
    )
    .into_owned();
    // 4. Unicode case folding
    let buf = case_fold::fold_case_impl(&buf);
    // 5. Collapse whitespace + strip control + strip zero-width
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
    // 1. Strip bidi overrides, isolates, marks, and soft hyphens
    let buf = strip_bidi(text);
    // 2. Collapse whitespace + strip control + strip zero-width
    Ok(whitespace::_collapse_whitespace(&buf, true, true))
}

/// Sanitize user-submitted input for web applications.
///
/// Pipeline: NFKC → strip_bidi → strip_zero_width → strip_control → strip_zalgo
///           → confusables → collapse_whitespace
///
/// Designed for web developers who want to accept multilingual input in its
/// original script while preventing malicious abuse:
/// - **NFKC**: collapses fullwidth bypasses, ligatures, superscripts
/// - **strip_bidi / zero-width / control**: removes invisibles *first* so they
///   cannot split a run of combining marks (keeps the zalgo cap idempotent)
/// - **strip_zalgo**: caps combining marks at 2 per base character, preventing
///   stacked diacritical abuse while preserving legitimate diacritics (é, ñ, ệ)
/// - **confusables**: neutralizes cross-script homoglyph attacks
/// - **collapse_whitespace**: final whitespace-run normalization
///
/// Unlike `security_clean`, this pipeline strips zalgo text.  Unlike
/// `catalog_key`/`search_key`, it does *not* transliterate — the original
/// script is preserved.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _sanitize_user_input(text: &str) -> PyResult<String> {
    // 1. NFKC normalization
    let buf = nfkc_normalize(text);
    // 2. Strip invisibles FIRST (bidi/format + zero-width + control) so they
    //    cannot split a run of combining marks; otherwise removing them later
    //    would merge two short runs into one long run that a second pass would
    //    cap differently (zalgo-capping would not be idempotent). Control chars
    //    other than \n/\t are removed at the final cleanup step regardless, so
    //    removing them here too is behaviour-preserving and keeps the cap
    //    idempotent — e.g. "\u{301}\u{301}\0\u{301}" must not become a longer
    //    contiguous run once the NUL is stripped.
    let buf = strip_bidi(&buf);
    let buf = whitespace::strip_zero_width_chars(&buf);
    let buf = whitespace::strip_control_chars(&buf);
    // 3. Cap combining marks at 2 per base character (zalgo)
    let buf = zalgo::_strip_zalgo(&buf, 2);
    // 4. Confusables → Latin (neutralizes cross-script homoglyphs)
    let buf = confusables::_normalize_confusables(&buf, "latin")?;
    // 5. Collapse whitespace + strip control + strip zero-width
    let buf = whitespace::_collapse_whitespace(&buf, true, true);
    // 6. Path-safety guarantee (#248): the output of a function named to
    //    *sanitize* untrusted input must be safe to use as a path component —
    //    no synthesised '/', '\', or '..' traversal.
    Ok(neutralize_path_separators(&buf))
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

/// Maximum-strength text deobfuscation pipeline.
///
/// Pipeline: NFKC → strip_zalgo(max_marks=0) → strip_bidi → strip_zero_width
///          → demojize → normalize_confusables → strip_accents
///          → collapse_whitespace
///
/// `normalize_confusables` runs *after* `demojize` so typographic punctuation in
/// emoji names (e.g. the `’` in "woman’s hat") is folded too; otherwise the
/// output would not be idempotent.
///
/// Strips ALL combining marks, resolves homoglyph spoofing via TR39
/// confusable mapping (visual similarity), expands emoji to text, removes
/// accents, and collapses whitespace. **Preserves case** — case is not
/// deception (proper nouns, acronyms, sentence boundaries are meaningful).
/// Chain with `fold_case()` if lowercasing is also needed.
///
/// NFKC handles ligature decomposition (ﬁ→fi, ﬀ→ff) without case folding.
///
/// **Does NOT transliterate.** Confusable normalization maps by visual
/// similarity (Cyrillic р→p, с→c, В→B), not phonetic value (р→r, с→s, В→V).
/// Users who also need transliteration should chain explicitly:
/// `strip_obfuscation(text) → transliterate(result)`.
///
/// Use cases: content moderation, anti-phishing, spam detection, hate speech
/// detection, social media NLP preprocessing.
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _strip_obfuscation(text: &str) -> PyResult<String> {
    // 1. NFKC normalization (collapses fullwidth, ligatures, superscripts)
    let buf = nfkc_normalize(text);
    // 2. Strip ALL combining marks (max_marks=0) — removes zalgo AND accents early
    let buf = zalgo::_strip_zalgo(&buf, 0);
    // 3. Strip bidi overrides, isolates, marks, and soft hyphens
    let buf = strip_bidi(&buf);
    // 4. Strip zero-width chars (ZWS, ZWNJ, ZWJ, WJ, BOM)
    let buf = whitespace::strip_zero_width_chars(&buf);
    // 5. Demojize — expand emoji to text names with spacing
    let buf = emoji::demojize_rust(&buf, false);
    // 6. Confusables → Latin (TR39 visual mapping: Cyrillic р→p, с→c, В→B).
    //    Runs AFTER demojize so that typographic punctuation in emoji names
    //    (e.g. the ’ in "woman’s hat") is folded too; otherwise a second pass
    //    would fold it and strip_obfuscation would not be idempotent.
    let buf = confusables::_normalize_confusables(&buf, "latin")?;
    // 7. Strip accents (NFD decompose + strip combining marks)
    let buf = transliterate::_strip_accents(&buf);
    // 8. Collapse whitespace (final cleanup) — case is NOT folded
    Ok(whitespace::_collapse_whitespace(&buf, true, true))
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── neutralize_path_separators: path-safety guarantee for security presets (#248) ──
    #[test]
    fn test_neutralize_path_separators() {
        // Separators (whatever their origin) become '_'.
        assert_eq!(neutralize_path_separators("etc/passwd"), "etc_passwd");
        assert_eq!(neutralize_path_separators("a\\b"), "a_b");
        // No '/' or '\' survives, so '../'-style traversal is impossible; dot
        // runs collapse so no `..` token remains either.
        assert_eq!(neutralize_path_separators("../../etc"), "._._etc");
        assert_eq!(neutralize_path_separators("a..b"), "a.b");
        // Single dots and benign text are preserved.
        assert_eq!(neutralize_path_separators("file.tar.gz"), "file.tar.gz");
        assert_eq!(neutralize_path_separators("hello world"), "hello world");
        assert!(!neutralize_path_separators("x⁄y/z\\w").contains(['/', '\\']));
    }

    #[test]
    fn test_neutralize_path_separators_idempotent() {
        for s in ["etc/passwd", "../../x", "a..b/c\\d", "plain text"] {
            let once = neutralize_path_separators(s);
            assert_eq!(
                neutralize_path_separators(&once),
                once,
                "not idempotent: {s:?}"
            );
        }
    }

    // ── nfkc_normalize: ASCII fast path must equal full NFKC (#198) ──
    // The fast path returns the ASCII input borrowed (no copy); this guards
    // that the optimization is output-preserving against the reference `nfkc()`
    // pass across ASCII, fullwidth, ligature, superscript, and combining-mark
    // inputs.
    #[test]
    fn test_nfkc_normalize_matches_reference() {
        let cases = [
            "",                   // empty
            "hello world 123",    // pure ASCII (fast path)
            "!@#$%^&*()_+-=[]{}", // ASCII punctuation (fast path)
            "\u{007F}\u{0000}",   // ASCII control bounds (fast path)
            "Ｆｕｌｌｗｉｄｔｈ", // fullwidth → ASCII (slow path changes it)
            "ﬁ ﬂ ﬃ",              // ligatures → fi/fl/ffi
            "x²y³",               // superscripts → x2y3
            "café e\u{0301}",     // precomposed + combining acute
            "ⅣⅧ",                 // Roman numerals → IV / VIII
            "Москва 日本語 αβγ",  // non-ASCII, mostly unchanged by NFKC
        ];
        for s in cases {
            let reference: String = s.nfkc().collect();
            assert_eq!(
                nfkc_normalize(s).as_ref(),
                reference.as_str(),
                "nfkc_normalize diverged from nfkc() on {s:?}"
            );
        }
    }

    // The ASCII fast path must *borrow* (zero-copy), not allocate; non-ASCII
    // input must take the owned NFKC path (#198, #202 review).
    #[test]
    fn test_nfkc_normalize_borrows_ascii_owns_nonascii() {
        assert!(matches!(nfkc_normalize("plain ascii"), Cow::Borrowed(_)));
        assert!(matches!(nfkc_normalize(""), Cow::Borrowed(_)));
        assert!(matches!(nfkc_normalize("Ｆｕｌｌ"), Cow::Owned(_)));
        assert!(matches!(nfkc_normalize("café"), Cow::Owned(_)));
    }

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
    fn test_key_functions_strip_bidi_and_soft_hyphen() {
        // #93: a value stored with an invisible bidi/format char must produce
        // the SAME key as its clean equivalent, or dedup/lookup silently misses.
        for (stored, clean) in [
            ("pass\u{00AD}word", "password"), // soft hyphen
            ("user\u{202E}txt", "usertxt"),   // RLO override
            ("a\u{200E}b", "ab"),             // LRM
            ("x\u{061C}y", "xy"),             // Arabic Letter Mark
        ] {
            assert_eq!(
                _search_key(stored, None).unwrap(),
                _search_key(clean, None).unwrap(),
                "search_key must collide for {stored:?} vs {clean:?}"
            );
            assert_eq!(
                _catalog_key(stored, None, false).unwrap(),
                _catalog_key(clean, None, false).unwrap(),
                "catalog_key must collide for {stored:?} vs {clean:?}"
            );
            assert_eq!(
                _sort_key(stored, None).unwrap(),
                _sort_key(clean, None).unwrap(),
                "sort_key must collide for {stored:?} vs {clean:?}"
            );
        }
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
        // Legitimate diacritics are preserved — no transliteration or accent stripping
        assert_eq!(_sanitize_user_input("café").unwrap(), "café");
        assert_eq!(_sanitize_user_input("résumé").unwrap(), "résumé");
    }

    #[test]
    fn test_sanitize_user_input_homoglyph() {
        // Cyrillic а in "pаypal" → Latin a
        let result = _sanitize_user_input("p\u{0430}ypal").unwrap();
        assert_eq!(result, "paypal");
    }

    /// Property-based security invariants for the defense pipelines.
    ///
    /// Asserts the THREAT_MODEL.md guarantees across the full Unicode input
    /// space: no panic on any input, idempotence (a stable fixed point), and
    /// that bidi/format controls never survive a pipeline whose definition
    /// includes a bidi-stripping step.
    mod proptest_properties {
        use super::*;
        use proptest::prelude::*;

        /// Characters the defense pipelines specifically target — bidi/format
        /// controls, zero-width/invisible chars, zalgo combining marks,
        /// confusables, and an emoji. Mixed into the generator so the "no bidi
        /// survives" properties actually exercise these (a plain `\PC*` strategy
        /// would never produce category-C controls, making them vacuous).
        const SPECIAL: &[char] = &[
            // bidi / format controls
            '\u{200E}',
            '\u{200F}',
            '\u{202A}',
            '\u{202B}',
            '\u{202C}',
            '\u{202D}',
            '\u{202E}',
            '\u{061C}',
            '\u{2066}',
            '\u{2067}',
            '\u{2068}',
            '\u{2069}',
            '\u{00AD}',
            // zero-width / invisible
            '\u{200B}',
            '\u{200C}',
            '\u{200D}',
            '\u{2060}',
            '\u{FEFF}',
            // zalgo combining marks
            '\u{0301}',
            '\u{0300}',
            '\u{0489}',
            // confusables (Cyrillic а р с е о) + a fullwidth char + an emoji
            '\u{0430}',
            '\u{0440}',
            '\u{0441}',
            '\u{0435}',
            '\u{043E}',
            '\u{FF41}',
            '\u{1F452}',
        ];

        /// Adversarial input: arbitrary scalar values heavily salted with the
        /// attack characters above.
        fn adversarial() -> impl Strategy<Value = String> {
            let special = proptest::sample::select(SPECIAL.to_vec());
            proptest::collection::vec(
                prop_oneof![4 => any::<char>(), 3 => special, 2 => prop::char::range('a', 'z')],
                0..40,
            )
            .prop_map(|cs| cs.into_iter().collect())
        }

        /// Compare under NFC: NFKC can reorder combining marks of equal
        /// canonical combining class, which is canonically equivalent.
        fn nfc(s: &str) -> String {
            s.nfc().collect()
        }

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            #[test]
            fn security_clean_idempotent(s in adversarial()) {
                let once = _security_clean(&s).unwrap();
                let twice = _security_clean(&once).unwrap();
                prop_assert_eq!(nfc(&once), nfc(&twice));
            }

            #[test]
            fn strip_obfuscation_idempotent(s in adversarial()) {
                let once = _strip_obfuscation(&s).unwrap();
                let twice = _strip_obfuscation(&once).unwrap();
                prop_assert_eq!(nfc(&once), nfc(&twice));
            }

            #[test]
            fn sanitize_user_input_idempotent(s in adversarial()) {
                let once = _sanitize_user_input(&s).unwrap();
                let twice = _sanitize_user_input(&once).unwrap();
                prop_assert_eq!(nfc(&once), nfc(&twice));
            }

            #[test]
            fn strip_bidi_idempotent(s in adversarial()) {
                let once = _strip_bidi(&s);
                prop_assert_eq!(&once, &_strip_bidi(&once));
            }

            // No bidi/format control survives a pipeline that strips bidi.
            #[test]
            fn no_bidi_after_strip_bidi(s in adversarial()) {
                prop_assert!(!_strip_bidi(&s).chars().any(is_bidi_or_format));
            }

            #[test]
            fn no_bidi_after_security_clean(s in adversarial()) {
                prop_assert!(!_security_clean(&s).unwrap().chars().any(is_bidi_or_format));
            }

            #[test]
            fn no_bidi_after_strip_obfuscation(s in adversarial()) {
                prop_assert!(!_strip_obfuscation(&s).unwrap().chars().any(is_bidi_or_format));
            }

            #[test]
            fn no_bidi_after_sanitize_user_input(s in adversarial()) {
                prop_assert!(!_sanitize_user_input(&s).unwrap().chars().any(is_bidi_or_format));
            }
        }
    }
}
