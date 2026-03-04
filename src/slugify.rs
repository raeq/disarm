use pyo3::prelude::*;
use std::collections::HashSet;

use crate::transliterate;

/// Maximum iterations for unique slug generation before giving up.
/// Prevents infinite loops when all candidates are rejected.
const MAX_UNIQUE_ATTEMPTS: u64 = 10_000;

/// Maximum digit count for numeric HTML entity parsing.
/// Prevents unbounded string accumulation on malformed input.
const MAX_ENTITY_DIGITS: usize = 10;

/// Find the largest byte index `<= index` that lies on a UTF-8 char boundary.
///
/// Equivalent to the nightly-only `str::floor_char_boundary()`.
/// Returns `s.len()` when `index >= s.len()`.
fn floor_char_boundary(s: &str, index: usize) -> usize {
    if index >= s.len() {
        s.len()
    } else {
        let mut i = index;
        while i > 0 && !s.is_char_boundary(i) {
            i -= 1;
        }
        i
    }
}

/// Configuration for slug generation, extracted from parameters.
///
/// Fields `save_order`, `decimal`, and `hexadecimal` are accepted for
/// python-slugify parameter compatibility but not yet used in the Rust
/// implementation. They are retained to preserve API compatibility.
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
    let compiled_regex = regex_pattern
        .map(regex::Regex::new)
        .transpose()
        .map_err(|e| crate::TranslitError::new_err(format!("Invalid regex: {e}")))?;

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
        lang: lang.map(|s| s.to_owned()),
        entities,
        decimal,
        hexadecimal,
    };

    Ok(slugify_impl(text, &config))
}

/// Core slugification pipeline.
pub fn slugify_impl(text: &str, config: &SlugConfig) -> String {
    if text.is_empty() {
        return String::new();
    }

    let mut value = text.to_owned();

    // Step 1: Apply pre-transliteration replacements
    for (from, to) in &config.replacements {
        value = value.replace(from.as_str(), to.as_str());
    }

    // Step 2: Decode HTML entities (if enabled)
    if config.entities {
        value = decode_entities(&value);
    }

    // Step 3: Transliterate (unless allow_unicode)
    if !config.allow_unicode {
        value = transliterate::transliterate_impl(
            &value,
            config.lang.as_deref(),
            transliterate::ErrorMode::Ignore,
            "",
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
        let stopset: HashSet<&str> = config.stopwords.iter().map(String::as_str).collect();
        let filtered: Vec<&str> = slug
            .split(separator.as_str())
            .filter(|w| !stopset.contains(w))
            .collect();
        slug = filtered.join(separator);
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

/// Decode HTML entities: named entities (&amp; &lt; &gt; &quot; &apos;)
/// and numeric entities (&#38; &#x26;).
fn decode_entities(text: &str) -> String {
    // First pass: named entities
    let mut result = text
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&apos;", "'");

    // Second pass: numeric entities (decimal &#NNN; and hex &#xHHH;)
    if result.contains("&#") {
        result = decode_numeric_entities(&result);
    }

    result
}

/// Decode numeric HTML entities: &#38; (decimal) and &#x26; (hex).
///
/// Caps digit collection at `MAX_ENTITY_DIGITS` to prevent unbounded
/// string accumulation on malformed input.
fn decode_numeric_entities(text: &str) -> String {
    let mut result = String::with_capacity(text.len());
    let mut chars = text.chars().peekable();

    while let Some(ch) = chars.next() {
        if ch == '&' {
            // Peek for '#'
            if chars.peek() == Some(&'#') {
                chars.next(); // consume '#'
                let mut num_str = String::new();
                let is_hex = chars.peek() == Some(&'x') || chars.peek() == Some(&'X');
                if is_hex {
                    chars.next(); // consume 'x'/'X'
                }
                // Collect digits (bounded), track whether ';' was consumed
                let mut saw_semicolon = false;
                while let Some(&d) = chars.peek() {
                    if d == ';' {
                        chars.next(); // consume ';'
                        saw_semicolon = true;
                        break;
                    }
                    if num_str.len() >= MAX_ENTITY_DIGITS {
                        break; // malformed — too many digits
                    }
                    if is_hex && d.is_ascii_hexdigit() {
                        num_str.push(d);
                        chars.next();
                    } else if !is_hex && d.is_ascii_digit() {
                        num_str.push(d);
                        chars.next();
                    } else {
                        break; // malformed — stop collecting
                    }
                }
                // Try to parse and convert to char
                let parsed = if is_hex {
                    u32::from_str_radix(&num_str, 16).ok()
                } else {
                    num_str.parse::<u32>().ok()
                };
                // filter(|c| !c.is_control()) excludes NUL (U+0000) and other
                // control characters — they are never valid slug content.
                if let Some(cp) = parsed.and_then(char::from_u32).filter(|c| !c.is_control()) {
                    result.push(cp);
                } else {
                    // Malformed entity (or decoded to control char) — pass through
                    // literally, including the semicolon if it was consumed.
                    result.push('&');
                    result.push('#');
                    if is_hex {
                        result.push('x');
                    }
                    result.push_str(&num_str);
                    if saw_semicolon {
                        result.push(';');
                    }
                }
            } else {
                result.push(ch);
            }
        } else {
            result.push(ch);
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
    let compiled_regex = regex_pattern
        .map(regex::Regex::new)
        .transpose()
        .map_err(|e| crate::TranslitError::new_err(format!("Invalid regex: {e}")))?;

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

    Ok(texts
        .iter()
        .map(|text| slugify_impl(text, &config))
        .collect())
}

// --- Stateful classes ---

#[pyclass]
#[pyo3(name = "_Slugifier")]
pub struct _Slugifier {
    config: SlugConfig,
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
            .map(regex::Regex::new)
            .transpose()
            .map_err(|e| crate::TranslitError::new_err(format!("Invalid regex: {e}")))?;

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
                lang: lang.map(|s| s.to_owned()),
                entities,
                decimal,
                hexadecimal,
            },
        })
    }

    fn slugify(&self, text: &str) -> String {
        slugify_impl(text, &self.config)
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
    fn test_decode_named_entities() {
        assert_eq!(decode_entities("AT&amp;T"), "AT&T");
        assert_eq!(decode_entities("5 &lt; 10"), "5 < 10");
        assert_eq!(decode_entities("&quot;hello&quot;"), "\"hello\"");
    }

    #[test]
    fn test_decode_numeric_entity_decimal() {
        assert_eq!(decode_numeric_entities("&#65;"), "A");
        assert_eq!(decode_numeric_entities("&#38;"), "&");
    }

    #[test]
    fn test_decode_numeric_entity_hex() {
        assert_eq!(decode_numeric_entities("&#x41;"), "A");
        assert_eq!(decode_numeric_entities("&#x26;"), "&");
    }

    #[test]
    fn test_decode_malformed_entity() {
        // Malformed entities pass through literally
        // "&#xyz;" — 'x' triggers hex mode, then 'y' and 'z' are not hex digits
        // so we get "&#x" then "yz;" handled as normal chars
        assert_eq!(decode_numeric_entities("&#xyz;"), "&#xyz;");
    }

    #[test]
    fn test_decode_malformed_entity_semicolon_preserved() {
        // Empty decimal entity: &#; should pass through as &#;
        assert_eq!(decode_numeric_entities("&#;"), "&#;");
        // Empty hex entity: &#x; should pass through as &#x;
        assert_eq!(decode_numeric_entities("&#x;"), "&#x;");
        // Invalid codepoint (too large for Unicode) with semicolon
        assert_eq!(decode_numeric_entities("&#xFFFFFFFF;"), "&#xFFFFFFFF;");
        // Valid format but zero codepoint (U+0000): NUL is a control character,
        // so it is filtered out and the entity is passed through literally.
        let result = decode_numeric_entities("&#0;");
        assert_eq!(result, "&#0;");
    }

    #[test]
    fn test_decode_entity_digit_limit() {
        // Extremely long digit sequence should be capped at MAX_ENTITY_DIGITS
        let long = format!("&#{}1;", "9".repeat(100));
        let result = decode_numeric_entities(&long);
        // Should not accumulate 100 digits — capped and fails to parse
        assert!(result.contains("&#"));
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
    fn test_floor_char_boundary() {
        // ASCII: every byte is a char boundary
        assert_eq!(floor_char_boundary("hello", 3), 3);
        assert_eq!(floor_char_boundary("hello", 10), 5); // beyond len
        assert_eq!(floor_char_boundary("hello", 0), 0);

        // "café" = [99, 97, 102, 195, 169] — 'é' is 2 bytes at index 3–4
        let s = "café";
        assert_eq!(floor_char_boundary(s, 5), 5); // full string
        assert_eq!(floor_char_boundary(s, 4), 3); // mid-'é', rounds down to before it
        assert_eq!(floor_char_boundary(s, 3), 3); // start of 'é'

        // "日本" = 6 bytes (3 per char)
        let s = "日本";
        assert_eq!(floor_char_boundary(s, 6), 6);
        assert_eq!(floor_char_boundary(s, 5), 3); // mid-second char
        assert_eq!(floor_char_boundary(s, 4), 3);
        assert_eq!(floor_char_boundary(s, 3), 3);
        assert_eq!(floor_char_boundary(s, 2), 0); // mid-first char
        assert_eq!(floor_char_boundary(s, 1), 0);
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
