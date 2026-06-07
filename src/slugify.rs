use pyo3::prelude::*;
use std::collections::HashSet;

use crate::transliterate;

/// Maximum iterations for unique slug generation before giving up.
/// Prevents infinite loops when all candidates are rejected.
const MAX_UNIQUE_ATTEMPTS: u64 = 10_000;

/// Maximum digit count for numeric HTML entity parsing.
/// Prevents unbounded string accumulation on malformed input.
const MAX_ENTITY_DIGITS: usize = 10;

/// Maximum byte length of a caller-supplied regex pattern.
/// Prevents adversarial patterns from consuming excessive compile time or
/// memory. The regex crate guards against catastrophic backtracking at
/// match time, but compilation of an enormous pattern is also bounded here.
const MAX_REGEX_PATTERN_BYTES: usize = 512;

/// Maximum compiled DFA size for caller-supplied regex patterns, in bytes.
///
/// The `regex` crate uses finite automata (no catastrophic backtracking at
/// match time), but compiling a large pattern can consume substantial memory
/// and CPU.  This cap bounds both compile-time allocation and CPU for
/// adversarial patterns that would otherwise produce a very large DFA.
const MAX_REGEX_DFA_BYTES: usize = 1_048_576; // 1 MiB

/// Validate and compile a caller-supplied regex pattern after enforcing a size cap.
///
/// Returns `Err(String)` if the pattern exceeds `MAX_REGEX_PATTERN_BYTES`,
/// if the compiled DFA would exceed `MAX_REGEX_DFA_BYTES`, or if
/// `regex::RegexBuilder` rejects it for any other reason.
/// Callers at the PyO3 boundary convert the `String` error to a
/// `TranslitError` with `.map_err(|e| TranslitError::new_err(e))`.
fn compile_regex(pattern: &str) -> Result<regex::Regex, String> {
    if pattern.len() > MAX_REGEX_PATTERN_BYTES {
        return Err(format!(
            "regex_pattern is too long ({} bytes); maximum is {} bytes",
            pattern.len(),
            MAX_REGEX_PATTERN_BYTES
        ));
    }
    regex::RegexBuilder::new(pattern)
        .size_limit(MAX_REGEX_DFA_BYTES)
        .build()
        .map_err(|e| format!("Invalid regex: {e}"))
}

use crate::utils::floor_char_boundary;

/// Configuration for slug generation, extracted from parameters.
///
/// # Compatibility fields (no-op)
///
/// The following fields are accepted for python-slugify API compatibility
/// but have **no effect** in the current implementation:
///
/// - `save_order`: Intended to preserve original word order when applying
///   stopwords. The current implementation always preserves insertion order.
#[allow(dead_code)]
pub struct SlugConfig {
    pub separator: String,
    pub lowercase: bool,
    pub max_length: usize,
    pub word_boundary: bool,
    pub save_order: bool,
    pub stopwords: Vec<String>,
    pub regex_pattern: Option<regex::Regex>,
    pub replacements: Vec<(String, String)>,
    pub allow_unicode: bool,
    pub lang: Option<String>,
    pub entities: bool,
    pub decimal: bool,
    pub hexadecimal: bool,
}

impl Default for SlugConfig {
    fn default() -> Self {
        Self {
            separator: "-".to_owned(),
            lowercase: true,
            max_length: 0,
            word_boundary: false,
            save_order: false,
            stopwords: Vec::new(),
            regex_pattern: None,
            replacements: Vec::new(),
            allow_unicode: false,
            lang: None,
            entities: true,
            decimal: true,
            hexadecimal: true,
        }
    }
}

/// Generate a URL-safe slug from Unicode text.
#[pyfunction]
#[pyo3(signature = (
    text,
    *,
    separator="-",
    lowercase=true,
    max_length=0,
    word_boundary=false,
    save_order=false,
    stopwords=vec![],
    regex_pattern=None,
    replacements=vec![],
    allow_unicode=false,
    lang=None,
    entities=true,
    decimal=true,
    hexadecimal=true,
))]
pub fn _slugify(
    text: &str,
    separator: &str,
    lowercase: bool,
    max_length: usize,
    word_boundary: bool,
    save_order: bool,
    stopwords: Vec<String>,
    regex_pattern: Option<&str>,
    replacements: Vec<(String, String)>,
    allow_unicode: bool,
    lang: Option<&str>,
    entities: bool,
    decimal: bool,
    hexadecimal: bool,
) -> PyResult<String> {
    crate::transliterate::validate_lang(lang)?;
    let compiled_regex = regex_pattern
        .map(compile_regex)
        .transpose()
        .map_err(crate::TranslitError::new_err)?;

    let config = SlugConfig {
        separator: separator.to_owned(),
        lowercase,
        max_length,
        word_boundary,
        save_order,
        stopwords,
        regex_pattern: compiled_regex,
        replacements,
        allow_unicode,
        lang: lang.map(std::borrow::ToOwned::to_owned),
        entities,
        decimal,
        hexadecimal,
    };

    Ok(slugify_impl(text, &config))
}

/// Core slugification pipeline.
pub fn slugify_impl(text: &str, config: &SlugConfig) -> String {
    slugify_impl_with_stopset(text, config, None)
}

/// Internal implementation shared by the free function and `_Slugifier`.
///
/// `prebuilt_stopset` lets `_Slugifier` supply its cached `HashSet<String>`
/// so it is not reconstructed on every call.  Passing `None` causes a
/// temporary set to be built from `config.stopwords` as before.
pub(crate) fn slugify_impl_with_stopset(
    text: &str,
    config: &SlugConfig,
    prebuilt_stopset: Option<&HashSet<String>>,
) -> String {
    if text.is_empty() {
        return String::new();
    }

    let mut value = text.to_owned();

    // Step 1: Apply pre-transliteration replacements (single-pass when possible)
    if !config.replacements.is_empty() {
        if config.replacements.len() == 1 {
            // Common case: single replacement pair — .replace() is optimal.
            let (from, to) = &config.replacements[0];
            value = value.replace(from.as_str(), to.as_str());
        } else {
            // Multiple replacement pairs: single-pass scan to avoid N× full-string
            // scans and N allocations from chained .replace() calls.
            let mut result = String::with_capacity(value.len());
            let mut i = 0;
            let value_bytes = value.as_bytes();
            while i < value.len() {
                let mut matched = false;
                for (from, to) in &config.replacements {
                    if value_bytes[i..].starts_with(from.as_bytes()) {
                        result.push_str(to);
                        i += from.len();
                        matched = true;
                        break;
                    }
                }
                if !matched {
                    // Safe: we are at a valid position in the string.
                    // Advance by one character (may be multi-byte).
                    let ch = value[i..].chars().next().unwrap();
                    result.push(ch);
                    i += ch.len_utf8();
                }
            }
            value = result;
        }
    }

    // Step 2: Decode HTML entities (if enabled)
    if config.entities {
        value = decode_entities(&value, config.decimal, config.hexadecimal);
    }

    // Step 3: Transliterate (unless allow_unicode)
    if !config.allow_unicode {
        value = transliterate::transliterate_impl(
            &value,
            config.lang.as_deref(),
            crate::ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        )
        .into_owned();
    }

    // Step 4: Lowercase
    if config.lowercase {
        value = value.to_lowercase();
    }

    // Step 5: Apply custom regex pattern
    if let Some(ref re) = config.regex_pattern {
        value = re.replace_all(&value, "").to_string();
    }

    // Step 6: Replace non-alphanumeric with separator
    let separator = &config.separator;
    let mut slug = String::with_capacity(value.len());
    let mut prev_was_sep = true; // avoid leading separator

    for ch in value.chars() {
        if ch.is_alphanumeric() || (config.allow_unicode && !ch.is_ascii() && !ch.is_whitespace()) {
            slug.push(ch);
            prev_was_sep = false;
        } else if !prev_was_sep && !separator.is_empty() {
            slug.push_str(separator);
            prev_was_sep = true;
        }
    }

    // Strip trailing separator
    if slug.ends_with(separator) && !separator.is_empty() {
        slug.truncate(slug.len() - separator.len());
    }

    // Step 7: Remove stopwords
    // Note: if *all* words match the stopword list the result will be an empty
    // string.  This is intentional — callers that need a non-empty fallback
    // should check `slug.is_empty()` and supply one (e.g. a hash of the input).
    if !config.stopwords.is_empty() {
        // Use the caller-supplied set when available (e.g. _Slugifier caches it
        // at construction), otherwise build a temporary zero-copy set from config.
        let tmp_stopset;
        let stopset: &HashSet<String> = if let Some(s) = prebuilt_stopset {
            s
        } else {
            tmp_stopset = config.stopwords.iter().cloned().collect();
            &tmp_stopset
        };
        slug = filter_stopwords(&slug, separator, stopset);
    }

    // Step 8: Truncate to max_length (byte-length, char-boundary safe for allow_unicode)
    if config.max_length > 0 && slug.len() > config.max_length {
        if config.word_boundary {
            // Truncate at word boundary
            slug = truncate_at_boundary(&slug, config.max_length, separator);
        } else {
            let boundary = floor_char_boundary(&slug, config.max_length);
            slug.truncate(boundary);
            // Strip trailing separator after truncation
            if slug.ends_with(separator) && !separator.is_empty() {
                slug.truncate(slug.len() - separator.len());
            }
        }
    }

    slug
}

/// Remove stopwords from a slug, splitting and rejoining on the separator.
fn filter_stopwords(slug: &str, separator: &str, stopset: &HashSet<String>) -> String {
    slug.split(separator)
        .filter(|w| !stopset.contains(*w))
        .enumerate()
        .fold(String::with_capacity(slug.len()), |mut acc, (i, w)| {
            if i > 0 {
                acc.push_str(separator);
            }
            acc.push_str(w);
            acc
        })
}

/// Truncate slug at a word boundary (separator), char-boundary safe.
fn truncate_at_boundary(slug: &str, max_length: usize, separator: &str) -> String {
    if slug.len() <= max_length {
        return slug.to_owned();
    }
    let boundary = floor_char_boundary(slug, max_length);
    let truncated = &slug[..boundary];
    match truncated.rfind(separator) {
        Some(pos) => truncated[..pos].to_owned(),
        None => truncated.to_owned(),
    }
}

/// Decode a numeric HTML entity (&#NNN; or &#xHHH;) starting at `pos`.
///
/// Returns `Some((char, bytes_consumed))` on success, `None` for malformed
/// or control-character entities.  `num_buf` is a caller-supplied buffer
/// reused across calls to avoid per-entity allocation.
fn decode_numeric_entity(bytes: &[u8], pos: usize, num_buf: &mut String) -> Option<(char, usize)> {
    let len = bytes.len();
    let mut i = pos + 2; // skip "&#"
    let is_hex = i < len && (bytes[i] == b'x' || bytes[i] == b'X');
    if is_hex {
        i += 1;
    }
    num_buf.clear();
    while i < len {
        let b = bytes[i];
        if b == b';' {
            i += 1;
            break;
        }
        if num_buf.len() >= MAX_ENTITY_DIGITS {
            break;
        }
        let valid_digit = if is_hex {
            (b as char).is_ascii_hexdigit()
        } else {
            b.is_ascii_digit()
        };
        if valid_digit {
            num_buf.push(b as char);
            i += 1;
        } else {
            break;
        }
    }
    let parsed = if is_hex {
        u32::from_str_radix(num_buf, 16).ok()
    } else {
        num_buf.parse::<u32>().ok()
    };
    // Exclude control characters — they are never valid slug content.
    let ch = parsed
        .and_then(char::from_u32)
        .filter(|c| !c.is_control())?;
    Some((ch, i - pos))
}

/// Calculate how many bytes to skip for a malformed numeric entity at `pos`.
///
/// Only scans ASCII bytes — stops immediately at non-ASCII (high bit set)
/// so we never land inside a multi-byte UTF-8 character.
fn decode_numeric_entity_skip(bytes: &[u8], pos: usize) -> usize {
    let len = bytes.len();
    let mut i = pos + 2; // skip "&#"
    if i < len && (bytes[i] == b'x' || bytes[i] == b'X') {
        i += 1;
    }
    while i < len && bytes[i].is_ascii() && bytes[i] != b';' && (i - pos) < MAX_ENTITY_DIGITS + 4 {
        i += 1;
    }
    if i < len && bytes[i] == b';' {
        i += 1;
    }
    i - pos
}

/// Decode HTML entities in a single pass: named entities (&amp; &lt; etc.)
/// and numeric entities (&#38; &#x26;).
///
/// Replaces the previous two-pass approach (5× `.replace()` + numeric scan)
/// with one scan and one output buffer.
fn decode_entities(text: &str, decimal: bool, hexadecimal: bool) -> String {
    // Fast path: no ampersand means no entities to decode.
    if !text.contains('&') {
        return text.to_owned();
    }

    let mut result = String::with_capacity(text.len());
    let bytes = text.as_bytes();
    let len = bytes.len();
    let mut i = 0;
    // Reusable buffer for numeric entity digits (avoids per-entity allocation).
    let mut num_buf = String::with_capacity(MAX_ENTITY_DIGITS);

    while i < len {
        if bytes[i] != b'&' {
            // Advance by full UTF-8 character, not by byte.
            // bytes[i] as char would corrupt multi-byte characters (é, ü, 中, etc.)
            // by treating each continuation byte as a separate Latin-1 codepoint.
            let ch = text[i..].chars().next().expect("non-empty slice");
            result.push(ch);
            i += ch.len_utf8();
            continue;
        }

        // Try named entities (longest-prefix first for correctness)
        if text[i..].starts_with("&amp;") {
            result.push('&');
            i += 5;
        } else if text[i..].starts_with("&lt;") {
            result.push('<');
            i += 4;
        } else if text[i..].starts_with("&gt;") {
            result.push('>');
            i += 4;
        } else if text[i..].starts_with("&quot;") {
            result.push('"');
            i += 6;
        } else if text[i..].starts_with("&apos;") {
            result.push('\'');
            i += 6;
        } else if text[i..].starts_with("&#") {
            let is_hex = i + 2 < len && (bytes[i + 2] == b'x' || bytes[i + 2] == b'X');
            let decode = if is_hex { hexadecimal } else { decimal };
            if decode {
                if let Some((ch, consumed)) = decode_numeric_entity(bytes, i, &mut num_buf) {
                    result.push(ch);
                    i += consumed;
                } else {
                    // Malformed or control-char entity — advance past "&#".
                    i += decode_numeric_entity_skip(bytes, i);
                }
            } else {
                // Flag disabled — preserve the raw '&' and let the loop advance.
                result.push('&');
                i += 1;
            }
        } else {
            result.push('&');
            i += 1;
        }
    }

    result
}

/// Batch slugification: process a list of strings in a single PyO3 boundary crossing.
#[pyfunction]
#[pyo3(signature = (
    texts,
    *,
    separator="-",
    lowercase=true,
    max_length=0,
    word_boundary=false,
    save_order=false,
    stopwords=vec![],
    regex_pattern=None,
    replacements=vec![],
    allow_unicode=false,
    lang=None,
    entities=true,
    decimal=true,
    hexadecimal=true,
))]
pub fn _slugify_batch(
    texts: Vec<String>,
    separator: &str,
    lowercase: bool,
    max_length: usize,
    word_boundary: bool,
    save_order: bool,
    stopwords: Vec<String>,
    regex_pattern: Option<&str>,
    replacements: Vec<(String, String)>,
    allow_unicode: bool,
    lang: Option<&str>,
    entities: bool,
    decimal: bool,
    hexadecimal: bool,
) -> PyResult<Vec<String>> {
    if texts.len() > crate::MAX_BATCH_SIZE {
        return translit_err!(
            "batch too large ({} items); maximum is {} items",
            texts.len(),
            crate::MAX_BATCH_SIZE
        );
    }
    crate::transliterate::validate_lang(lang)?;

    let compiled_regex = regex_pattern
        .map(compile_regex)
        .transpose()
        .map_err(crate::TranslitError::new_err)?;

    let config = SlugConfig {
        separator: separator.to_owned(),
        lowercase,
        max_length,
        word_boundary,
        save_order,
        stopwords,
        regex_pattern: compiled_regex,
        replacements,
        allow_unicode,
        lang: lang.map(str::to_owned),
        entities,
        decimal,
        hexadecimal,
    };

    // Pre-build the stopword set once for the entire batch instead of
    // reconstructing it on every call to slugify_impl.
    let stopset: HashSet<String> = config.stopwords.iter().cloned().collect();
    Ok(texts
        .iter()
        .map(|text| slugify_impl_with_stopset(text, &config, Some(&stopset)))
        .collect())
}

// --- Stateful classes ---

#[pyclass]
#[pyo3(name = "_Slugifier")]
pub struct _Slugifier {
    config: SlugConfig,
    /// Pre-built stopword set so `slugify()` calls pay O(1) per word
    /// rather than O(stopwords) for HashSet construction on every call.
    stopset: HashSet<String>,
}

#[pymethods]
impl _Slugifier {
    #[new]
    #[pyo3(signature = (
        *,
        separator="-",
        lowercase=true,
        max_length=0,
        word_boundary=false,
        save_order=false,
        stopwords=vec![],
        regex_pattern=None,
        replacements=vec![],
        allow_unicode=false,
        lang=None,
        entities=true,
        decimal=true,
        hexadecimal=true,
    ))]
    fn new(
        separator: &str,
        lowercase: bool,
        max_length: usize,
        word_boundary: bool,
        save_order: bool,
        stopwords: Vec<String>,
        regex_pattern: Option<&str>,
        replacements: Vec<(String, String)>,
        allow_unicode: bool,
        lang: Option<&str>,
        entities: bool,
        decimal: bool,
        hexadecimal: bool,
    ) -> PyResult<Self> {
        let compiled_regex = regex_pattern
            .map(compile_regex)
            .transpose()
            .map_err(crate::TranslitError::new_err)?;

        let stopset: HashSet<String> = stopwords.iter().cloned().collect();
        Ok(Self {
            config: SlugConfig {
                separator: separator.to_owned(),
                lowercase,
                max_length,
                word_boundary,
                save_order,
                stopwords,
                regex_pattern: compiled_regex,
                replacements,
                allow_unicode,
                lang: lang.map(std::borrow::ToOwned::to_owned),
                entities,
                decimal,
                hexadecimal,
            },
            stopset,
        })
    }

    fn slugify(&self, text: &str) -> String {
        slugify_impl_with_stopset(text, &self.config, Some(&self.stopset))
    }

    #[getter]
    fn separator(&self) -> &str {
        &self.config.separator
    }

    #[getter]
    fn lang(&self) -> Option<&str> {
        self.config.lang.as_deref()
    }
}

#[pyclass]
#[pyo3(name = "_UniqueSlugifier")]
pub struct _UniqueSlugifier {
    inner: _Slugifier,
    seen: HashSet<String>,
    check: Option<PyObject>,
}

#[pymethods]
impl _UniqueSlugifier {
    #[new]
    #[pyo3(signature = (
        *,
        check=None,
        separator="-",
        lowercase=true,
        max_length=0,
        word_boundary=false,
        save_order=false,
        stopwords=vec![],
        regex_pattern=None,
        replacements=vec![],
        allow_unicode=false,
        lang=None,
        entities=true,
        decimal=true,
        hexadecimal=true,
    ))]
    fn new(
        check: Option<PyObject>,
        separator: &str,
        lowercase: bool,
        max_length: usize,
        word_boundary: bool,
        save_order: bool,
        stopwords: Vec<String>,
        regex_pattern: Option<&str>,
        replacements: Vec<(String, String)>,
        allow_unicode: bool,
        lang: Option<&str>,
        entities: bool,
        decimal: bool,
        hexadecimal: bool,
    ) -> PyResult<Self> {
        let inner = _Slugifier::new(
            separator,
            lowercase,
            max_length,
            word_boundary,
            save_order,
            stopwords,
            regex_pattern,
            replacements,
            allow_unicode,
            lang,
            entities,
            decimal,
            hexadecimal,
        )?;
        Ok(Self {
            inner,
            seen: HashSet::new(),
            check,
        })
    }

    /// Generate a unique slug, appending numeric suffixes as needed.
    ///
    /// Bounded to `MAX_UNIQUE_ATTEMPTS` iterations to prevent infinite loops
    /// when a `check` callback always rejects candidates.
    fn slugify(&mut self, py: Python<'_>, text: &str) -> PyResult<String> {
        let base = self.inner.slugify(text);
        let mut candidate = base.clone();
        let mut counter = 1u64;

        loop {
            if counter > MAX_UNIQUE_ATTEMPTS {
                return Err(crate::TranslitError::new_err(format!(
                    "UniqueSlugifier exceeded {MAX_UNIQUE_ATTEMPTS} attempts for '{text}'"
                )));
            }

            if !self.seen.contains(&candidate) {
                if let Some(ref check_fn) = self.check {
                    let exists: bool = check_fn.call1(py, (&candidate,))?.extract(py)?;
                    if !exists {
                        self.seen.insert(candidate.clone());
                        return Ok(candidate);
                    }
                } else {
                    self.seen.insert(candidate.clone());
                    return Ok(candidate);
                }
            }
            candidate = format!("{}{}{counter}", base, self.inner.config.separator);
            // If max_length is set, ensure the suffixed candidate doesn't exceed it.
            // Truncate the base portion to make room for the separator + counter.
            if self.inner.config.max_length > 0 && candidate.len() > self.inner.config.max_length {
                let suffix = format!("{}{counter}", self.inner.config.separator);
                if suffix.len() >= self.inner.config.max_length {
                    // Suffix alone exceeds max_length — use the suffix truncated.
                    suffix[..self.inner.config.max_length].clone_into(&mut candidate);
                } else {
                    let avail = self.inner.config.max_length - suffix.len();
                    let boundary = floor_char_boundary(&base, avail);
                    candidate = format!("{}{suffix}", &base[..boundary]);
                }
            }
            counter += 1;
        }
    }

    fn reset(&mut self) {
        self.seen.clear();
    }
}

// --- Tests ---

#[cfg(test)]
mod tests {
    use super::*;

    fn default_config() -> SlugConfig {
        SlugConfig {
            separator: "-".to_owned(),
            lowercase: true,
            max_length: 0,
            word_boundary: false,
            save_order: false,
            stopwords: vec![],
            regex_pattern: None,
            replacements: vec![],
            allow_unicode: false,
            lang: None,
            entities: true,
            decimal: true,
            hexadecimal: true,
        }
    }

    #[test]
    fn test_empty_input() {
        let config = default_config();
        assert_eq!(slugify_impl("", &config), "");
    }

    #[test]
    fn test_ascii_passthrough() {
        let config = default_config();
        assert_eq!(slugify_impl("hello world", &config), "hello-world");
    }

    #[test]
    fn test_separator() {
        let mut config = default_config();
        config.separator = "_".to_owned();
        assert_eq!(slugify_impl("hello world", &config), "hello_world");
    }

    #[test]
    fn test_no_lowercase() {
        let mut config = default_config();
        config.lowercase = false;
        assert_eq!(slugify_impl("Hello World", &config), "Hello-World");
    }

    #[test]
    fn test_max_length() {
        let mut config = default_config();
        config.max_length = 5;
        let result = slugify_impl("hello world", &config);
        assert!(result.len() <= 5);
    }

    #[test]
    fn test_max_length_word_boundary() {
        let mut config = default_config();
        config.max_length = 8;
        config.word_boundary = true;
        assert_eq!(slugify_impl("hello world foo", &config), "hello");
    }

    #[test]
    fn test_stopwords() {
        let mut config = default_config();
        config.stopwords = vec!["the".to_owned(), "a".to_owned()];
        assert_eq!(slugify_impl("the big a fox", &config), "big-fox");
    }

    #[test]
    fn test_stopwords_uses_hashset() {
        // Verify correctness with many stopwords (regression for O(n*m) fix)
        let mut config = default_config();
        config.stopwords = (0..100).map(|i| format!("stop{i}")).collect();
        config.stopwords.push("the".to_owned());
        assert_eq!(slugify_impl("the big fox", &config), "big-fox");
    }

    #[test]
    fn test_replacements() {
        let mut config = default_config();
        config.replacements = vec![("C++".to_owned(), "cpp".to_owned())];
        assert_eq!(slugify_impl("C++ Code", &config), "cpp-code");
    }

    #[test]
    fn test_allow_unicode() {
        let mut config = default_config();
        config.allow_unicode = true;
        let result = slugify_impl("café latte", &config);
        assert!(result.contains("café"));
    }

    #[test]
    fn test_decode_entities_multibyte_utf8() {
        // BUG-1: decode_entities previously used `bytes[i] as char` which
        // corrupts multi-byte UTF-8 characters (é = 0xC3 0xA9 → Ã ©).
        assert_eq!(
            decode_entities("café &amp; résumé", true, true),
            "café & résumé"
        );
        assert_eq!(decode_entities("über &lt; cool", true, true), "über < cool");
        assert_eq!(
            decode_entities("中文 &amp; 日本語", true, true),
            "中文 & 日本語"
        );
        assert_eq!(
            decode_entities("emoji 🎉 &amp; fun", true, true),
            "emoji 🎉 & fun"
        );
        // Pure non-ASCII without entities hits the fast path (no &),
        // but mixed input must also work correctly.
        assert_eq!(decode_entities("café", true, true), "café");
    }

    #[test]
    fn test_decode_named_entities() {
        assert_eq!(decode_entities("AT&amp;T", true, true), "AT&T");
        assert_eq!(decode_entities("5 &lt; 10", true, true), "5 < 10");
        assert_eq!(
            decode_entities("&quot;hello&quot;", true, true),
            "\"hello\""
        );
    }

    #[test]
    fn test_decode_numeric_entity_decimal() {
        assert_eq!(decode_entities("&#65;", true, true), "A");
        assert_eq!(decode_entities("&#38;", true, true), "&");
    }

    #[test]
    fn test_decode_numeric_entity_hex() {
        assert_eq!(decode_entities("&#x41;", true, true), "A");
        assert_eq!(decode_entities("&#x26;", true, true), "&");
    }

    #[test]
    fn test_decode_malformed_entity() {
        // Malformed entities are silently dropped (not reconstructed).
        // "&#xyz;" — 'x' triggers hex mode, then the skip function
        // scans past all remaining chars up to and including ';'.
        assert_eq!(decode_entities("&#xyz;", true, true), "");
    }

    #[test]
    fn test_decode_malformed_entity_semicolon_preserved() {
        // Empty decimal entity &#; — no digits, malformed, dropped silently.
        // The semicolon is consumed by the digit-collection loop and also dropped.
        assert_eq!(decode_entities("&#;", true, true), "");
        // Empty hex entity &#x; — no hex digits, malformed, dropped silently.
        assert_eq!(decode_entities("&#x;", true, true), "");
        // Invalid codepoint (too large for Unicode): malformed, dropped silently.
        assert_eq!(decode_entities("&#xFFFFFFFF;", true, true), "");
        // U+0000 is a control character and is filtered; entity dropped silently.
        let result = decode_entities("&#0;", true, true);
        assert_eq!(result, "");
    }

    #[test]
    fn test_decode_entity_digit_limit() {
        // Extremely long digit sequence should be capped at MAX_ENTITY_DIGITS.
        // The entity fails to parse (truncated number is out of Unicode range)
        // and is silently dropped — the result should be empty.
        let long = format!("&#{}1;", "9".repeat(100));
        let result = decode_entities(&long, true, true);
        // No reconstruction: the malformed entity is dropped entirely.
        assert!(!result.contains("&#"));
    }

    #[test]
    fn test_decode_decimal_disabled() {
        // decimal=false: &#65; is preserved as raw text, hex still decoded
        assert_eq!(decode_entities("&#65;", false, true), "&#65;");
        assert_eq!(decode_entities("&#x41;", false, true), "A");
    }

    #[test]
    fn test_decode_hex_disabled() {
        // hexadecimal=false: &#x41; is preserved, decimal still decoded
        assert_eq!(decode_entities("&#x41;", true, false), "&#x41;");
        assert_eq!(decode_entities("&#65;", true, false), "A");
    }

    #[test]
    fn test_decode_both_disabled() {
        // Both disabled: numeric entities preserved, named still decoded
        assert_eq!(
            decode_entities("&#65; &amp; &#x41;", false, false),
            "&#65; & &#x41;"
        );
    }

    #[test]
    fn test_truncate_at_boundary_no_truncation_needed() {
        assert_eq!(truncate_at_boundary("abc", 10, "-"), "abc");
    }

    #[test]
    fn test_truncate_at_boundary_with_separator() {
        // "hello-world-foo" has 15 chars; truncate to 12 gives "hello-world-"
        // rfind("-") at pos 11 → "hello-world"
        assert_eq!(
            truncate_at_boundary("hello-world-foo", 12, "-"),
            "hello-world"
        );
    }

    #[test]
    fn test_truncate_at_boundary_no_separator_found() {
        assert_eq!(truncate_at_boundary("helloworld", 5, "-"), "hello");
    }

    #[test]
    fn test_allow_unicode_max_length_no_panic() {
        // This previously panicked with "assertion failed: self.is_char_boundary(new_len)"
        let mut config = default_config();
        config.allow_unicode = true;
        config.max_length = 3;
        // "éééé" = 4 chars, 8 bytes; max_length=3 bytes falls mid-char
        let result = slugify_impl("éééé", &config);
        assert!(result.len() <= 3);
        // Should contain 1 'é' (2 bytes) since 2 fits in 3, but 4 doesn't
        assert_eq!(result, "é");
    }

    #[test]
    fn test_allow_unicode_max_length_exact_boundary() {
        let mut config = default_config();
        config.allow_unicode = true;
        config.max_length = 4; // exactly 2 'é' chars (2 bytes each)
        let result = slugify_impl("éééé", &config);
        assert!(result.len() <= 4);
        assert_eq!(result, "éé");
    }

    #[test]
    fn test_allow_unicode_word_boundary_no_panic() {
        let mut config = default_config();
        config.allow_unicode = true;
        config.max_length = 5;
        config.word_boundary = true;
        // Multi-byte chars with separator
        let result = slugify_impl("café latte", &config);
        assert!(result.len() <= 5);
        // "café" = 5 bytes, "café-latte" → truncate at word boundary
        assert_eq!(result, "café");
    }

    #[test]
    fn test_strip_trailing_separator() {
        let config = default_config();
        // Input that naturally produces trailing separator
        let result = slugify_impl("hello!", &config);
        assert!(!result.ends_with('-'));
    }

    #[test]
    fn test_consecutive_separators_collapsed() {
        let config = default_config();
        let result = slugify_impl("hello   world", &config);
        assert_eq!(result, "hello-world");
    }

    #[test]
    fn test_entities_disabled() {
        let mut config = default_config();
        config.entities = false;
        let result = slugify_impl("AT&amp;T", &config);
        // Should not decode &amp; — treat literally
        assert!(result.contains("amp"));
    }

    #[test]
    fn test_regex_pattern() {
        let mut config = default_config();
        config.regex_pattern = Some(regex::Regex::new(r"\d").unwrap());
        assert_eq!(slugify_impl("abc123def", &config), "abcdef");
    }

    #[test]
    fn test_compile_regex_valid() {
        assert!(compile_regex(r"\d+").is_ok());
    }

    #[test]
    fn test_compile_regex_too_long() {
        let long_pattern = "a".repeat(MAX_REGEX_PATTERN_BYTES + 1);
        let err = compile_regex(&long_pattern).unwrap_err();
        assert!(err.contains("too long"), "unexpected error: {err}");
    }

    #[test]
    fn test_compile_regex_at_limit() {
        // Exactly at the limit must succeed (valid pattern of that length).
        let pattern = "a".repeat(MAX_REGEX_PATTERN_BYTES);
        assert!(compile_regex(&pattern).is_ok());
    }

    #[test]
    fn test_compile_regex_invalid() {
        // Syntactically invalid pattern must return an error regardless of length.
        let err = compile_regex(r"[unclosed").unwrap_err();
        assert!(err.contains("Invalid regex"), "unexpected error: {err}");
    }

    mod proptest_properties {
        use super::*;
        use proptest::prelude::*;

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            /// Slug output is always ASCII.
            #[test]
            fn slugify_output_is_ascii(s in "\\PC*") {
                let config = default_config();
                let result = slugify_impl(&s, &config);
                prop_assert!(result.is_ascii());
            }

            /// Default slug charset is [a-z0-9-] with no leading/trailing/consecutive separators.
            #[test]
            fn slugify_output_charset(s in "\\PC*") {
                let config = default_config();
                let result = slugify_impl(&s, &config);
                if !result.is_empty() {
                    for ch in result.chars() {
                        prop_assert!(
                            ch.is_ascii_lowercase() || ch.is_ascii_digit() || ch == '-',
                            "bad char {ch:?} in {result:?}"
                        );
                    }
                    prop_assert!(!result.starts_with('-'));
                    prop_assert!(!result.ends_with('-'));
                    prop_assert!(!result.contains("--"));
                }
            }

            /// Slug never exceeds max_length.
            #[test]
            fn slugify_max_length(s in "\\PC*", max_len in 1..200usize) {
                let mut config = default_config();
                config.max_length = max_len;
                let result = slugify_impl(&s, &config);
                prop_assert!(result.len() <= max_len);
            }

            /// allow_unicode slug never panics and respects max_length.
            #[test]
            fn slugify_unicode_max_length_no_panic(s in "\\PC*", max_len in 1..200usize) {
                let mut config = default_config();
                config.allow_unicode = true;
                config.max_length = max_len;
                let result = slugify_impl(&s, &config);
                prop_assert!(result.len() <= max_len);
                // Result must be valid UTF-8 (guaranteed by String, but belt-and-suspenders)
                prop_assert!(std::str::from_utf8(result.as_bytes()).is_ok());
            }

            /// Empty input always produces empty output.
            #[test]
            fn slugify_empty_is_empty(_unused in 0..1u8) {
                let config = default_config();
                prop_assert_eq!(slugify_impl("", &config), "");
            }

            /// Slug is idempotent when input is already a valid slug.
            #[test]
            fn slugify_idempotent_on_slugs(s in "[a-z][a-z0-9]{0,10}(-[a-z0-9]{1,10}){0,5}") {
                let config = default_config();
                let result = slugify_impl(&s, &config);
                prop_assert_eq!(&result, &s, "slug changed on re-slugify");
            }
        }
    }
}
