//! Layer 1 (pure-Rust core): slugification. No pyo3.
//!
//! Shims (incl. the `_Slugifier` / `_UniqueSlugifier` stateful classes) live
//! in `src/py/slugify.rs`; crates.io surface is `crate::api::{slugify, SlugConfig}`.

use std::borrow::Cow;
use std::collections::{HashMap, HashSet};
use std::sync::{Arc, LazyLock, RwLock};

use crate::transliterate;

// Resource limits are centralized in `crate::limits` (#256).
use crate::limits::{MAX_REGEX_DFA_BYTES, MAX_REGEX_PATTERN_BYTES};

/// Maximum digit count for numeric HTML entity parsing.
/// Prevents unbounded string accumulation on malformed input.
const MAX_ENTITY_DIGITS: usize = 10;

/// Validate and compile a caller-supplied regex pattern after enforcing a size cap.
///
/// Returns `Err(crate::ErrorRepr)` if the pattern exceeds `MAX_REGEX_PATTERN_BYTES`,
/// if the compiled DFA would exceed `MAX_REGEX_DFA_BYTES`, or if
/// `regex::RegexBuilder` rejects it for any other reason.
/// Callers at the PyO3 boundary convert the error to a `DisarmError` via the
/// `From<ErrorRepr> for PyErr` boundary impl (#181).
fn compile_regex(pattern: &str) -> Result<regex::Regex, crate::ErrorRepr> {
    if pattern.len() > MAX_REGEX_PATTERN_BYTES {
        return Err(crate::ErrorRepr::RegexTooLong {
            len: pattern.len(),
            max: MAX_REGEX_PATTERN_BYTES,
        });
    }
    regex::RegexBuilder::new(pattern)
        // Bound both the compiled-program size and the match-time lazy-DFA cache by
        // the project constant (S-1). Without `dfa_size_limit` the match-time cache
        // used the regex-crate default, not our limit — symmetry hardening on the one
        // caller-supplied-regex path.
        .size_limit(MAX_REGEX_DFA_BYTES)
        .dfa_size_limit(MAX_REGEX_DFA_BYTES)
        .build()
        .map_err(|e| crate::ErrorRepr::RegexCompile {
            pattern: pattern.to_owned(),
            source: e,
        })
}

/// Maximum number of distinct compiled patterns held in [`REGEX_CACHE`].
const REGEX_CACHE_MAX: usize = 32;

/// Bounded cache of compiled `regex_pattern`s, keyed by the pattern string.
///
/// The free `slugify()` function recompiles its `regex_pattern` on every call
/// (`from_pyargs` → `compile_regex`), which is a per-call latency cliff that
/// throughput benchmarks never surface (#236 / #233 review item). `regex::Regex`
/// is internally `Arc`-backed, so a cache hit returns a cheap clone instead of
/// rebuilding the DFA. Bounded to [`REGEX_CACHE_MAX`] entries; the table is
/// cleared wholesale when full (patterns are few and reused, so a true LRU is
/// not worth its cost). `_Slugifier` already amortizes compilation by holding
/// one `SlugConfig`, so only the free function and batch paths benefit here.
static REGEX_CACHE: LazyLock<RwLock<HashMap<String, regex::Regex>>> =
    LazyLock::new(|| RwLock::new(HashMap::new()));

/// Compile `pattern`, reusing a cached `regex::Regex` when the same pattern was
/// compiled before. Errors are never cached. See [`REGEX_CACHE`].
fn compile_regex_cached(pattern: &str) -> Result<regex::Regex, crate::ErrorRepr> {
    // Fast path: a read lock and a cheap Arc clone on a hit.
    if let Some(re) = crate::recover_lock(REGEX_CACHE.read(), "REGEX_CACHE").get(pattern) {
        return Ok(re.clone());
    }
    // Miss: compile outside the write lock (validation + DFA build can be slow).
    let re = compile_regex(pattern)?;
    let mut cache = crate::recover_lock(REGEX_CACHE.write(), "REGEX_CACHE");
    // Bound growth: clear when full rather than evicting one entry (cheap, rare).
    if cache.len() >= REGEX_CACHE_MAX && !cache.contains_key(pattern) {
        cache.clear();
    }
    cache.insert(pattern.to_owned(), re.clone());
    Ok(re)
}

use crate::utils::floor_char_boundary;

/// A compiled **first-match** replacement automaton for the slugify
/// pre-transliteration replacements (#242 item 2). Unlike the global longest
/// match table, this step's semantics are *first registered pair wins at each
/// position* (the original scan tried pairs in list order), so the automaton is
/// built with `MatchKind::LeftmostFirst` — which, at a tie, prefers the pattern
/// added earliest, reproducing that order exactly. Output is checked
/// byte-for-byte against the reference scan by `slug_automaton_matches_scan`.
struct SlugReplacementAutomaton {
    ac: aho_corasick::AhoCorasick,
    /// `values[pattern_id]` is the replacement for the pair at that position.
    values: Vec<String>,
}

/// Build a `LeftmostFirst` automaton from the replacement pairs, preserving list
/// order (so pattern ids — and the tie-break priority — match the original
/// per-position first-match scan). Empty `from` keys are skipped (the former
/// scan would have spun on them). Returns `None` when fewer than two non-empty
/// pairs remain (the single-pair case keeps `str::replace`).
fn build_slug_replacement_automaton(
    pairs: &[(String, String)],
) -> Option<SlugReplacementAutomaton> {
    let mut patterns: Vec<&str> = Vec::with_capacity(pairs.len());
    let mut values: Vec<String> = Vec::with_capacity(pairs.len());
    for (from, to) in pairs {
        if from.is_empty() {
            continue;
        }
        patterns.push(from.as_str());
        values.push(to.clone());
    }
    if patterns.len() < 2 {
        return None;
    }
    let ac = aho_corasick::AhoCorasick::builder()
        .match_kind(aho_corasick::MatchKind::LeftmostFirst)
        .build(&patterns)
        .expect("slug replacement keys are valid aho-corasick patterns");
    Some(SlugReplacementAutomaton { ac, values })
}

/// Maximum number of distinct replacement automata held in
/// [`REPLACEMENT_AUTOMATON_CACHE`].
const REPLACEMENT_AUTOMATON_CACHE_MAX: usize = 32;

/// Bounded cache of compiled replacement automata, keyed by the replacement
/// pairs (M2). Like [`REGEX_CACHE`], the free `slugify()` and batch paths
/// otherwise rebuild the aho-corasick automaton on *every* call — an O(pattern
/// bytes) DFA build that throughput benchmarks never surface — while `_Slugifier`
/// amortizes it. The automaton is held in an `Arc`, so a cache hit returns a
/// cheap pointer clone instead of rebuilding. Bounded to
/// [`REPLACEMENT_AUTOMATON_CACHE_MAX`]; cleared wholesale when full.
#[allow(clippy::type_complexity)]
static REPLACEMENT_AUTOMATON_CACHE: LazyLock<
    RwLock<HashMap<Vec<(String, String)>, Arc<SlugReplacementAutomaton>>>,
> = LazyLock::new(|| RwLock::new(HashMap::new()));

/// Return the replacement automaton for `pairs`, reusing a cached one when the
/// same pairs were seen before. `None` mirrors [`build_slug_replacement_automaton`]
/// (fewer than two non-empty pairs) and is never cached. See
/// [`REPLACEMENT_AUTOMATON_CACHE`].
fn cached_slug_replacement_automaton(
    pairs: &[(String, String)],
) -> Option<Arc<SlugReplacementAutomaton>> {
    // Fast path: a read lock and a cheap Arc clone on a hit.
    if let Some(a) = crate::recover_lock(
        REPLACEMENT_AUTOMATON_CACHE.read(),
        "REPLACEMENT_AUTOMATON_CACHE",
    )
    .get(pairs)
    {
        return Some(a.clone());
    }
    // Miss: build outside the write lock (the DFA build can be slow).
    let automaton = Arc::new(build_slug_replacement_automaton(pairs)?);
    let mut cache = crate::recover_lock(
        REPLACEMENT_AUTOMATON_CACHE.write(),
        "REPLACEMENT_AUTOMATON_CACHE",
    );
    // Bound growth: clear when full rather than evicting one entry (cheap, rare).
    if cache.len() >= REPLACEMENT_AUTOMATON_CACHE_MAX && !cache.contains_key(pairs) {
        cache.clear();
    }
    cache.insert(pairs.to_vec(), automaton.clone());
    Some(automaton)
}

/// Apply a prebuilt first-match replacement automaton to `text`, writing into a
/// freshly allocated buffer (#242 item 2). Byte-identical to the former
/// per-position list-order scan.
fn slug_replace_with_automaton(text: &str, automaton: &SlugReplacementAutomaton) -> String {
    let mut result = String::with_capacity(text.len());
    let mut last = 0;
    for mat in automaton.ac.find_iter(text) {
        result.push_str(&text[last..mat.start()]);
        result.push_str(&automaton.values[mat.pattern().as_usize()]);
        last = mat.end();
    }
    result.push_str(&text[last..]);
    result
}

/// Configuration for slug generation.
///
/// Construct with [`SlugConfig::new`] (or [`SlugConfig::default`]) and the
/// chainable `with_*` setters; the fields are readable but, because the struct is
/// `#[non_exhaustive]`, a new slug option can be added in a future release without
/// breaking callers. `save_order` controls whether stopword removal is applied to
/// interior tokens (`false`, default — all matching tokens removed) or only to
/// leading/trailing tokens (`true` — python-slugify semantics that preserves
/// relative word order). (#118)
#[non_exhaustive]
pub struct SlugConfig {
    /// String inserted between words (default `"-"`).
    pub separator: String,
    /// Lowercase the result (default `true`).
    pub lowercase: bool,
    /// Truncate the slug to at most this many bytes on a word boundary; `0`
    /// (default) means no limit.
    pub max_length: usize,
    /// When truncating, cut only at a word boundary rather than mid-word.
    pub word_boundary: bool,
    /// Preserve relative word order when removing stopwords (see the type-level
    /// docs); `false` (default) removes all matching tokens.
    pub save_order: bool,
    /// Words removed from the slug (case-insensitive).
    pub stopwords: Vec<String>,
    /// Custom regex of characters to treat as separators; `None` uses the
    /// built-in non-word pattern.
    pub regex_pattern: Option<regex::Regex>,
    /// Literal `(from, to)` substitutions applied before transliteration
    /// (e.g. `("&", "and")`).
    pub replacements: Vec<(String, String)>,
    /// Keep Unicode word characters instead of transliterating to ASCII.
    pub allow_unicode: bool,
    /// Transliteration language hint; `None` uses the default tables. Not
    /// validated by the infallible Rust API (best-effort).
    pub lang: Option<String>,
    /// Decode HTML named entities (e.g. `&amp;`) before slugifying.
    pub entities: bool,
    /// Decode HTML decimal numeric entities (e.g. `&#38;`).
    pub decimal: bool,
    /// Decode HTML hexadecimal numeric entities (e.g. `&#x26;`).
    pub hexadecimal: bool,
    /// Characters preserved through slugification instead of becoming the
    /// separator (awesome-slugify `safe_chars`). They act as word characters,
    /// so they keep their position (e.g. `.`/`-` in filenames). (#230)
    pub safe_chars: String,
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
            safe_chars: String::new(),
        }
    }
}

impl SlugConfig {
    /// Build a `SlugConfig` from the 13 parameters shared by all four PyO3
    /// entrypoints (`_slugify`, `_slugify_batch`, `_Slugifier::new`,
    /// `_UniqueSlugifier::new`).
    ///
    /// Returns `Err(crate::ErrorRepr)` if the regex pattern is invalid — callers at
    /// the PyO3 boundary convert the error to a `DisarmError`. (#119)
    pub(crate) fn from_pyargs(
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
    ) -> Result<Self, crate::ErrorRepr> {
        let compiled_regex = regex_pattern.map(compile_regex_cached).transpose()?;
        Ok(Self {
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
            // safe_chars is not a free-function slugify() option; the awesome-slugify
            // compat classes set it on the returned config (#230).
            safe_chars: String::new(),
        })
    }

    // ── Chainable builder methods (#352) ──────────────────────────────────────
    // `SlugConfig::new().with_separator("_").with_max_length(40)` reads the
    // same way as the `Transliterate` builder, instead of mutating public fields.
    // The setters cover every field a free-function caller configures, so the
    // fluent style is a complete alternative to struct-literal construction.

    /// A `SlugConfig` with the default settings — the entry point for the
    /// chainable builder (equivalent to [`SlugConfig::default`]).
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Set the word separator (default `"-"`).
    #[must_use]
    pub fn with_separator(mut self, separator: impl Into<String>) -> Self {
        self.separator = separator.into();
        self
    }

    /// Lowercase the result (default `true`).
    #[must_use]
    pub fn with_lowercase(mut self, lowercase: bool) -> Self {
        self.lowercase = lowercase;
        self
    }

    /// Truncate to at most this many bytes (`0` = no limit).
    #[must_use]
    pub fn with_max_length(mut self, max_length: usize) -> Self {
        self.max_length = max_length;
        self
    }

    /// Cut only on a word boundary when truncating.
    #[must_use]
    pub fn with_word_boundary(mut self, word_boundary: bool) -> Self {
        self.word_boundary = word_boundary;
        self
    }

    /// Preserve relative word order when removing stopwords.
    #[must_use]
    pub fn with_save_order(mut self, save_order: bool) -> Self {
        self.save_order = save_order;
        self
    }

    /// Words to remove from the slug (case-insensitive).
    #[must_use]
    pub fn with_stopwords<I, S>(mut self, stopwords: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.stopwords = stopwords.into_iter().map(Into::into).collect();
        self
    }

    /// Keep Unicode word characters instead of transliterating to ASCII.
    #[must_use]
    pub fn with_allow_unicode(mut self, allow_unicode: bool) -> Self {
        self.allow_unicode = allow_unicode;
        self
    }

    /// Transliteration language hint (best-effort; not validated).
    #[must_use]
    pub fn with_lang(mut self, lang: impl Into<String>) -> Self {
        self.lang = Some(lang.into());
        self
    }

    /// Characters preserved through slugification instead of becoming the
    /// separator (awesome-slugify `safe_chars`).
    #[must_use]
    pub fn with_safe_chars(mut self, safe_chars: impl Into<String>) -> Self {
        self.safe_chars = safe_chars.into();
        self
    }

    /// Literal `(from, to)` substitutions applied before transliteration
    /// (e.g. `[("&", "and")]`).
    #[must_use]
    pub fn with_replacements<I, F, T>(mut self, replacements: I) -> Self
    where
        I: IntoIterator<Item = (F, T)>,
        F: Into<String>,
        T: Into<String>,
    {
        self.replacements = replacements
            .into_iter()
            .map(|(from, to)| (from.into(), to.into()))
            .collect();
        self
    }

    /// Decode HTML named entities (e.g. `&amp;`) before slugifying (default `true`).
    #[must_use]
    pub fn with_entities(mut self, entities: bool) -> Self {
        self.entities = entities;
        self
    }

    /// Decode HTML decimal numeric entities (e.g. `&#38;`) (default `true`).
    #[must_use]
    pub fn with_decimal(mut self, decimal: bool) -> Self {
        self.decimal = decimal;
        self
    }

    /// Decode HTML hexadecimal numeric entities (e.g. `&#x26;`) (default `true`).
    #[must_use]
    pub fn with_hexadecimal(mut self, hexadecimal: bool) -> Self {
        self.hexadecimal = hexadecimal;
        self
    }
}

/// Core slugification pipeline.
pub(crate) fn slugify_impl(text: &str, config: &SlugConfig) -> String {
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

    // #114: start as Cow::Borrowed(text) — no allocation until a mutating step
    // actually changes the content, mirroring the pattern used in transliterate_impl.
    let mut value: Cow<str> = Cow::Borrowed(text);

    // Step 1: Apply pre-transliteration replacements (single-pass when possible)
    if !config.replacements.is_empty() {
        if config.replacements.len() == 1 {
            // Common case: single replacement pair — .replace() is optimal.
            let (from, to) = &config.replacements[0];
            let replaced = value.replace(from.as_str(), to.as_str());
            value = Cow::Owned(replaced);
        } else if let Some(automaton) = cached_slug_replacement_automaton(&config.replacements) {
            // Multiple pairs (#242 item 2): first-match via an aho-corasick
            // automaton — O(n + pattern bytes) total instead of the O(n·pairs)
            // per-position scan below. The automaton is cached by pairs (M2), so
            // the free/batch paths no longer rebuild it on every call.
            value = Cow::Owned(slug_replace_with_automaton(&value, &automaton));
        } else {
            // Fallback for the degenerate case the automaton declines (fewer than
            // two non-empty `from` keys): the original per-position first-match
            // scan, preserving its exact behaviour (incl. empty-key handling).
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
            value = Cow::Owned(result);
        }
    }

    // Step 2: Decode HTML entities (if enabled)
    // #236 item 1: pass `value` through unchanged when there are no entities to
    // decode (decode_entities borrows in that case). Extract owned-ness first so
    // the borrow of `value` ends before we reassign it.
    if config.entities {
        let owned = match decode_entities(&value, config.decimal, config.hexadecimal) {
            Cow::Borrowed(_) => None,
            Cow::Owned(s) => Some(s),
        };
        if let Some(s) = owned {
            value = Cow::Owned(s);
        }
    }

    // Step 3: Transliterate, or — on the Unicode-preserving path — compose.
    // #236 item 3: only reallocate when the step changed the text. ASCII input
    // returns Cow::Borrowed, so the former unconditional into_owned() allocated on
    // every plain-ASCII slug. Extract owned-ness first so the borrow of `value` ends
    // before we reassign it (#114).
    if config.allow_unicode {
        // #477: the Unicode-preserving path skips transliterate, so compose here —
        // a decomposed homoglyph (`і` + combining diaeresis) must yield the same slug
        // as its precomposed form (`ї`). `compose_str` borrows when the input has no
        // combining mark, so the common ASCII/precomposed slug keeps its zero-alloc
        // path; it never decomposes a composition-excluded singleton. See
        // [`crate::compose`].
        let owned = match crate::compose::compose_str(&value) {
            Cow::Borrowed(_) => None,
            Cow::Owned(s) => Some(s),
        };
        if let Some(s) = owned {
            value = Cow::Owned(s);
        }
    } else {
        let owned = match transliterate::transliterate_impl(
            &value,
            config.lang.as_deref(),
            crate::ErrorMode::Ignore,
            "",
            false,
            false,
            false,
        ) {
            Cow::Borrowed(_) => None,
            Cow::Owned(s) => Some(s),
        };
        if let Some(s) = owned {
            value = Cow::Owned(s);
        }
    }

    // Step 4: Lowercase
    if config.lowercase {
        // #236 item 4: ASCII-lowercase in place (skipping the allocation when
        // already lowercase) only when the value is wholly ASCII. Built-in
        // transliteration tables emit ASCII (build.rs enforces it), but
        // `allow_unicode` preserves the original script AND `register_lang()`
        // can register custom profiles with non-ASCII values — both can leave
        // non-ASCII here, which needs full Unicode lowercasing to match the
        // previous behaviour (caught in review of #280).
        if value.is_ascii() {
            if value.bytes().any(|b| b.is_ascii_uppercase()) {
                let mut s = value.into_owned();
                s.make_ascii_lowercase();
                value = Cow::Owned(s);
            }
        } else {
            value = Cow::Owned(value.to_lowercase());
        }
    }

    // Step 5: Apply custom regex pattern. `replace_all` returns `Cow::Borrowed`
    // when the pattern doesn't match, so only take ownership on an actual
    // replacement — a no-match no longer force-allocates (review L-P1).
    if let Some(ref re) = config.regex_pattern {
        if let Cow::Owned(replaced) = re.replace_all(&value, "") {
            value = Cow::Owned(replaced);
        }
    }

    // Step 6: Replace non-alphanumeric with separator
    let separator = &config.separator;
    let mut slug = String::with_capacity(value.len());
    let mut prev_was_sep = true; // avoid leading separator

    // Precompute safe_chars membership once: `String::contains(char)` is an O(k)
    // substring scan, so the per-char check was O(n·k) for any non-empty
    // safe_chars (#252 O5.1). Empty safe_chars (the default) → skip the set build
    // and the per-char hash probe entirely (O3). `HashSet::new()` does not allocate.
    let has_safe_chars = !config.safe_chars.is_empty();
    let safe_set: HashSet<char> = if has_safe_chars {
        config.safe_chars.chars().collect()
    } else {
        HashSet::new()
    };

    for ch in value.chars() {
        if ch.is_alphanumeric()
            || (config.allow_unicode && !ch.is_ascii() && !ch.is_whitespace())
            || (has_safe_chars && safe_set.contains(&ch))
        {
            // safe_chars are kept verbatim and treated as word characters, so a
            // separator is not inserted around them (awesome-slugify semantics, #230).
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
        slug = filter_stopwords(&slug, separator, stopset, config.save_order);
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
///
/// When `save_order` is `true`, only leading and trailing stopwords are
/// removed — interior stopwords are kept so the relative order of
/// non-stopword tokens is preserved exactly as in the input (matching the
/// python-slugify semantics for `save_order=True`). (#118)
fn filter_stopwords(
    slug: &str,
    separator: &str,
    stopset: &HashSet<String>,
    save_order: bool,
) -> String {
    if save_order {
        // Strip only leading and trailing stopword tokens; preserve interior ones.
        let words: Vec<&str> = slug.split(separator).collect();
        let start = words
            .iter()
            .position(|w| !stopset.contains(*w))
            .unwrap_or(words.len());
        let end = words
            .iter()
            .rposition(|w| !stopset.contains(*w))
            .map_or(0, |i| i + 1);
        let kept = if start < end { &words[start..end] } else { &[] };
        kept.iter()
            .enumerate()
            .fold(String::with_capacity(slug.len()), |mut acc, (i, w)| {
                if i > 0 {
                    acc.push_str(separator);
                }
                acc.push_str(w);
                acc
            })
    } else {
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
}

/// Truncate slug at a word boundary (separator), char-boundary safe.
fn truncate_at_boundary(slug: &str, max_length: usize, separator: &str) -> String {
    if slug.len() <= max_length {
        return slug.to_owned();
    }
    let boundary = floor_char_boundary(slug, max_length);
    let truncated = &slug[..boundary];
    match truncated.rfind(separator) {
        // Everything before the last full separator: ends on a token boundary.
        Some(pos) => truncated[..pos].to_owned(),
        // No full separator survived the cut, but `floor_char_boundary` can land
        // *inside* a multi-char separator, leaving a trailing partial separator
        // (e.g. separator "--", slug "ab--cd", max 3 → "ab-"). Strip it so the
        // slug never ends in a (partial or whole) separator (review M-C1).
        None => strip_trailing_separator_prefix(truncated, separator).to_owned(),
    }
}

/// Strip the longest suffix of `s` that is a non-empty prefix of `separator`.
///
/// Used to clean a trailing *partial* separator left by a mid-separator
/// truncation. Safe for the slug domain: the separator characters are never
/// allowed content characters, so a trailing run matching a separator prefix can
/// only be a cut separator, not content.
fn strip_trailing_separator_prefix<'a>(s: &'a str, separator: &str) -> &'a str {
    if separator.is_empty() {
        return s;
    }
    let max = separator.len().min(s.len());
    for len in (1..=max).rev() {
        let start = s.len() - len;
        if s.is_char_boundary(start) && separator.starts_with(&s[start..]) {
            return &s[..start];
        }
    }
    s
}

/// Decode a numeric HTML entity (`&#NNN;` / `&#xHHH;`) starting at `pos`.
///
/// Returns `(decoded, consumed)`: `decoded` is the character on success (`None`
/// for a malformed or control-character entity), and `consumed` is **always** the
/// number of bytes the entity occupies, so the caller advances the same amount
/// either way (C3 — folds the former separate `decode_numeric_entity_skip` into
/// one place so the success and skip scans can no longer drift their bounds).
/// `num_buf` is a caller-supplied buffer reused across calls to avoid per-entity
/// allocation.
fn decode_numeric_entity(bytes: &[u8], pos: usize, num_buf: &mut String) -> (Option<char>, usize) {
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
    if let Some(ch) = parsed.and_then(char::from_u32).filter(|c| !c.is_control()) {
        return (Some(ch), i - pos);
    }

    // Malformed or control-char entity: skip the whole bad entity rather than
    // re-scanning its tail as literal text. Only scans ASCII bytes — stops at
    // non-ASCII (high bit set) so we never land inside a multi-byte char.
    let mut j = pos + 2;
    if j < len && (bytes[j] == b'x' || bytes[j] == b'X') {
        j += 1;
    }
    while j < len && bytes[j].is_ascii() && bytes[j] != b';' && (j - pos) < MAX_ENTITY_DIGITS + 4 {
        j += 1;
    }
    if j < len && bytes[j] == b';' {
        j += 1;
    }
    (None, j - pos)
}

/// Decode HTML entities in a single pass: named entities (&amp; &lt; etc.)
/// and numeric entities (&#38; &#x26;).
///
/// Replaces the previous two-pass approach (5× `.replace()` + numeric scan)
/// with one scan and one output buffer.
fn decode_entities(text: &str, decimal: bool, hexadecimal: bool) -> Cow<'_, str> {
    // Fast path (#236 item 1): no ampersand means no entities — borrow the input
    // unchanged, no allocation.
    let Some(first) = text.find('&') else {
        return Cow::Borrowed(text);
    };

    let mut result = String::with_capacity(text.len());
    // Bulk-copy the entity-free prefix in one memcpy.
    result.push_str(&text[..first]);
    let bytes = text.as_bytes();
    let len = bytes.len();
    let mut i = first;
    // Reusable buffer for numeric entity digits (avoids per-entity allocation).
    let mut num_buf = String::with_capacity(MAX_ENTITY_DIGITS);

    while i < len {
        if bytes[i] != b'&' {
            // #236 item 2: bulk-copy the whole run up to the next '&' in one
            // `push_str` (memcpy) instead of decoding and pushing per character.
            // The run is a valid UTF-8 sub-slice (it starts and ends on '&'
            // boundaries, both ASCII), so no multi-byte char is split.
            let rel = text[i..].find('&').unwrap_or(len - i);
            result.push_str(&text[i..i + rel]);
            i += rel;
            continue;
        }

        // Try named entities (longest-prefix first for correctness). Advance by
        // the matched literal's own length (P6) so the byte count can never drift
        // from the pattern it consumes.
        if text[i..].starts_with("&amp;") {
            result.push('&');
            i += "&amp;".len();
        } else if text[i..].starts_with("&lt;") {
            result.push('<');
            i += "&lt;".len();
        } else if text[i..].starts_with("&gt;") {
            result.push('>');
            i += "&gt;".len();
        } else if text[i..].starts_with("&quot;") {
            result.push('"');
            i += "&quot;".len();
        } else if text[i..].starts_with("&apos;") {
            result.push('\'');
            i += "&apos;".len();
        } else if text[i..].starts_with("&#") {
            let is_hex = i + 2 < len && (bytes[i + 2] == b'x' || bytes[i + 2] == b'X');
            let decode = if is_hex { hexadecimal } else { decimal };
            if decode {
                // `consumed` is returned in both cases (C3); push only on success.
                let (decoded, consumed) = decode_numeric_entity(bytes, i, &mut num_buf);
                if let Some(ch) = decoded {
                    result.push(ch);
                }
                i += consumed;
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

    Cow::Owned(result)
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
            safe_chars: String::new(),
        }
    }

    #[test]
    fn test_empty_input() {
        let config = default_config();
        assert_eq!(slugify_impl("", &config), "");
    }

    #[test]
    fn slug_automaton_matches_scan() {
        // #242 item 2: the LeftmostFirst automaton must be byte-identical to the
        // original per-position first-match-by-order scan — including the
        // order-sensitive cases where an earlier, shorter pair must win over a
        // later, longer one.
        fn scan(text: &str, pairs: &[(String, String)]) -> String {
            let mut result = String::with_capacity(text.len());
            let mut i = 0;
            let b = text.as_bytes();
            while i < text.len() {
                let mut matched = false;
                for (from, to) in pairs {
                    if !from.is_empty() && b[i..].starts_with(from.as_bytes()) {
                        result.push_str(to);
                        i += from.len();
                        matched = true;
                        break;
                    }
                }
                if !matched {
                    let ch = text[i..].chars().next().unwrap();
                    result.push(ch);
                    i += ch.len_utf8();
                }
            }
            result
        }
        let pair = |a: &str, b: &str| (a.to_owned(), b.to_owned());
        let lists = [
            vec![pair("ab", "X"), pair("a", "Y")], // longer pair listed first → wins
            vec![pair("a", "Y"), pair("ab", "X")], // shorter pair listed first → wins (order!)
            vec![pair("the", "T"), pair("he", "H")],
            vec![pair("&", "and"), pair("@", "at"), pair("%", "pct")],
            vec![pair("\u{5317}", "N"), pair("\u{5317}\u{4eac}", "BJ")], // 北 first → 北 wins
        ];
        let inputs = [
            "",
            "abc",
            "ab",
            "abab",
            "the heat",
            "a&b@c%d",
            "\u{5317}\u{4eac}\u{5e02}",
            "no-op",
            "aaa",
        ];
        for pairs in &lists {
            let automaton = build_slug_replacement_automaton(pairs);
            for inp in inputs {
                let reference = scan(inp, pairs);
                let got = automaton
                    .as_ref()
                    .map_or_else(|| scan(inp, pairs), |a| slug_replace_with_automaton(inp, a));
                assert_eq!(got, reference, "slug automaton != scan for input {inp:?}");
            }
        }
    }

    #[test]
    fn test_ascii_passthrough() {
        let config = default_config();
        assert_eq!(slugify_impl("hello world", &config), "hello-world");
    }

    #[test]
    fn custom_lang_non_ascii_value_is_lowercased() {
        // Regression (#280 review): the lowercase step's ASCII fast path must
        // not skip Unicode lowercasing when a registered profile emits non-ASCII.
        // Built-in tables are ASCII (build.rs-enforced); register_lang() ones
        // need not be. A non-ASCII key is required — ASCII keys bypass
        // transliteration via the ASCII fast path. (Rust-side so it does not
        // pollute the Python "all langs produce ASCII" enumeration.)
        let mut mappings = std::collections::HashMap::new();
        mappings.insert("\u{03A9}".to_owned(), "\u{03A8}".to_owned()); // Ω → Ψ
        crate::tables::register_lang("slugtest_psi_rs", mappings).unwrap();

        let config = SlugConfig {
            lang: Some("slugtest_psi_rs".to_owned()),
            ..default_config()
        };
        // Ψ is alphanumeric (survives the separator step); it must be folded to ψ.
        assert_eq!(slugify_impl("\u{03A9}", &config), "\u{03C8}"); // ψ
    }

    #[test]
    fn test_separator() {
        let mut config = default_config();
        config.separator = "_".to_owned();
        assert_eq!(slugify_impl("hello world", &config), "hello_world");
    }

    #[test]
    fn test_safe_chars_preserved_in_place() {
        // #230: safe_chars are kept verbatim and act as word characters, so they
        // keep their position instead of collapsing into the separator.
        let mut config = default_config();
        config.lowercase = false;
        config.separator = "_".to_owned();
        config.safe_chars = "-.".to_owned();
        assert_eq!(slugify_impl("My Report.pdf", &config), "My_Report.pdf");
        assert_eq!(slugify_impl("Foo-Bar Baz.txt", &config), "Foo-Bar_Baz.txt");
    }

    #[test]
    fn test_safe_chars_empty_is_default_behavior() {
        // Without safe_chars, dots/dashes collapse to the separator as before.
        let config = default_config();
        assert_eq!(slugify_impl("My Report.pdf", &config), "my-report-pdf");
    }

    #[test]
    fn test_slugify_rejects_negative_max_length() {
        // #231: the non-negative contract is enforced in the core, raising
        // InvalidArgumentError rather than a PyO3 OverflowError. The signed
        // entrypoints route through this shared helper.
        let err = crate::error::checked_max_length(-1).unwrap_err();
        assert!(err
            .to_string()
            .contains("max_length must be non-negative, got -1"));
        assert_eq!(crate::error::checked_max_length(0).unwrap(), 0);
        assert_eq!(crate::error::checked_max_length(255).unwrap(), 255);
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
    fn test_truncate_at_boundary_strips_partial_multichar_separator() {
        // Review M-C1: a multi-char separator cut mid-sequence must not leave a
        // trailing partial separator. "ab--cd" truncated to 3 → "ab-" → "ab".
        assert_eq!(truncate_at_boundary("ab--cd", 3, "--"), "ab");
        // A clean full-separator cut still lands on the token boundary.
        assert_eq!(truncate_at_boundary("ab--cd", 4, "--"), "ab");
        // End-to-end through slugify with a custom multi-char separator.
        let cfg = SlugConfig::new()
            .with_separator("--")
            .with_max_length(3)
            .with_word_boundary(true);
        let out = slugify_impl("ab cd", &cfg);
        assert!(
            !out.ends_with('-'),
            "slug {out:?} must not end in a partial separator"
        );
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
        let err = compile_regex(&long_pattern).unwrap_err().to_string();
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
        let err = compile_regex(r"[unclosed").unwrap_err().to_string();
        // The error echoes the offending pattern (#186) plus the engine's detail.
        assert!(err.contains("regex_pattern"), "unexpected error: {err}");
        assert!(err.contains("[unclosed"), "pattern not echoed: {err}");
    }

    /// Tier-3 exhaustive gate for the slug *codomain* over every code point.
    ///
    /// A slug's character set is a per-code-point property: every output char comes from
    /// transliterating one input char to ASCII and slug-filtering it, so if every single
    /// code point slugs to `[a-z0-9-]` (ASCII), so does every string. That makes this a
    /// **complete proof** of `slugify_output_is_ascii` and the charset-membership half of
    /// `slugify_output_charset`, where the `\PC*` proptests only sample. (The separator-
    /// *position* rules — no leading/trailing/`--` — are cross-char and stay with the
    /// proptests.) `#[ignore]` (Tier 3); run via `--lib -- --ignored`.
    #[test]
    #[ignore = "exhaustive: every code point through slugify; run in Tier 3 / pre-release"]
    fn exhaustive_slug_codomain() {
        let config = default_config();
        for cp in 0u32..=0x0010_FFFF {
            let Some(ch) = char::from_u32(cp) else {
                continue; // surrogates
            };
            let result = slugify_impl(&ch.to_string(), &config);
            assert!(
                result.is_ascii(),
                "non-ASCII slug for U+{cp:04X}: {result:?}"
            );
            for c in result.chars() {
                assert!(
                    c.is_ascii_lowercase() || c.is_ascii_digit() || c == '-',
                    "slug of U+{cp:04X} has out-of-charset {c:?}: {result:?}"
                );
            }
        }
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

            /// Review M-C1: with a custom multi-char separator and word-boundary
            /// truncation, the slug must never end in a partial or whole
            /// separator (the default-separator proptests can't reach this).
            #[test]
            fn slugify_multichar_separator_no_trailing_separator(
                s in "\\PC*",
                max_len in 1..60usize,
            ) {
                let mut config = default_config();
                config.separator = "--".to_owned();
                config.max_length = max_len;
                config.word_boundary = true;
                let result = slugify_impl(&s, &config);
                prop_assert!(result.len() <= max_len);
                prop_assert!(
                    result.is_empty() || !result.ends_with('-'),
                    "slug {:?} ends in a (partial) separator",
                    result
                );
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
