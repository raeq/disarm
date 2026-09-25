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

/// The two joiners kept on the `allow_unicode` path (#712 §3).
///
/// `Cf`, like every other character #712 excludes — and the one deliberate exception,
/// because both are orthographically **required**: ZWNJ separates a Persian `می` prefix
/// from its verb and blocks a Devanagari conjunct; ZWJ forms one in Devanagari and
/// Bengali. Dropping them changes the word, not just its rendering.
///
/// They are kept only *between* two other kept characters. A joiner cannot start a token
/// (nothing to join to) and must not end one: `'👨\u{200D}'` and `'👨'` render identically
/// and are different byte strings, so two rows can collide visually while a uniqueness
/// check passes (#711).
const SLUG_JOINERS: [char; 2] = ['\u{200C}', '\u{200D}'];

/// Combining marks kept per base on the `allow_unicode` path (#712 §4).
///
/// The same cap the `Step::Zalgo(2)` presets use, and the same reason: Vietnamese `ệ`
/// carries two, and 30 stacked on one base is abuse rather than orthography. The ASCII
/// path never reaches this — `transliterate` has already removed the marks.
const MAX_SLUG_COMBINING_MARKS: usize = 2;

/// Whether `ch` may appear in an `allow_unicode` slug (#712).
///
/// Both public descriptions promise a category restriction — "keep non-ASCII **letters**"
/// (Python) and "keep Unicode **word characters**" (Rust) — and the filter applied none:
/// every non-ASCII, non-whitespace code point survived, whatever its category. A bidi
/// override reached the slug, and `slugify(title, allow_unicode=True)` is the natural call
/// for a site with non-Latin content and a user-supplied title. `'file\u{202E}gnp-exe'`
/// renders as `fileexe.png`. The default ASCII path screened all of it.
///
/// `L* | N* | M*` plus the two joiners, which is what the docstrings already promise.
/// Marks are needed or Devanagari and Arabic break. Everything else goes: `Cf` (bidi
/// controls, ZWSP, ZWNBSP, soft hyphen, the tag block), `Co` (private use), `Cn`
/// (noncharacters), `Cs`, `Zs`, `P*` and `S*`.
///
/// The letter-and-digit test is [`is_slug_alphanumeric`], not `char::is_alphanumeric`:
/// the latter is `Alphabetic | N*`, and `Alphabetic` takes in 130 symbols through
/// `Other_Alphabetic`, so `'\u{24B6}dmin'` kept its circled letter.
fn is_unicode_slug_char(ch: char) -> bool {
    is_slug_alphanumeric(ch)
        || unicode_normalization::char::is_combining_mark(ch)
        || SLUG_JOINERS.contains(&ch)
}

/// `L* | N*`, as far as a slug is concerned: `char::is_alphanumeric` without the symbols
/// it admits through `Other_Alphabetic`.
///
/// `char::is_alphanumeric` is the derived `Alphabetic` property plus `N*`, and
/// `Alphabetic` is `L* | Nl | Other_Alphabetic`. `Other_Alphabetic` is mostly combining
/// marks, which the `allow_unicode` path keeps anyway, and four blocks of `So` symbols:
/// the circled Latin letters and the squared, negative circled and negative squared Latin
/// capitals. Kept, they read as letters in a slug, and a slug is an identifier:
/// `slugify('\u{24B6}dmin', allow_unicode = true)` returned `'\u{24D0}dmin'`, which is not
/// `admin` but reads as it (Finding 4 of `formal/lean/Sanitizers`). They are symbols, and
/// symbols become the separator. The ranges are every `Other_Alphabetic` code point
/// outside `M*`; a test sweeps the scalar values against the general category.
fn is_slug_alphanumeric(ch: char) -> bool {
    ch.is_alphanumeric() && !is_alphabetic_symbol(ch)
}

/// The `So` code points `char::is_alphabetic` accepts (`Other_Alphabetic`): U+24B6-U+24E9
/// (circled Latin letters) and U+1F130-U+1F149, U+1F150-U+1F169, U+1F170-U+1F189
/// (squared, negative circled and negative squared Latin capitals). 130 in all.
fn is_alphabetic_symbol(ch: char) -> bool {
    matches!(
        ch,
        '\u{24B6}'..='\u{24E9}'
            | '\u{1F130}'..='\u{1F149}'
            | '\u{1F150}'..='\u{1F169}'
            | '\u{1F170}'..='\u{1F189}'
    )
}

/// The number of combining marks in `ch`'s own NFD (#712 §4).
///
/// Seeds the per-base mark budget so the cap matches `strip_zalgo(2)`, which counts over
/// NFD: `à` already carries one mark there, so 30 stacked on it must come back as two in
/// total rather than two *more*. Allocation-free, and the same shape as
/// `presets::decomposes_to_mark`.
fn base_mark_count(ch: char) -> usize {
    use unicode_normalization::char::is_combining_mark;
    use unicode_normalization::UnicodeNormalization;
    std::iter::once(ch)
        .nfd()
        .filter(|c| is_combining_mark(*c))
        .count()
}

/// The largest byte index `<= max` that is a grapheme-cluster boundary (#711).
///
/// `floor_char_boundary` lands on a *code point* boundary, which can fall inside a cluster:
/// `slugify("👨\u{200D}👩\u{200D}👧", max_length = 8, allow_unicode = true)` returned
/// `'👨\u{200D}'`, a slug ending in a bare zero-width joiner. A slug is an identifier that
/// ends up in a URL, a filename or a database key, and keeping invisible characters out of
/// exactly those places is what the rest of this library is for — so emitting one from the
/// truncation step is disarm producing the input it is built to reject. `'🇩'` is not a
/// truncated flag either; it is a different renderable character.
///
/// `max_length` stays measured in **bytes** (#711 §3): the unit is right for the filesystem
/// and URL limits it exists for. What changes is where the cut lands.
fn floor_grapheme_boundary(s: &str, max: usize) -> usize {
    if s.len() <= max {
        return s.len();
    }
    let mut end = 0;
    for cluster in crate::grapheme::clusters(s) {
        let next = end + cluster.len();
        if next > max {
            break;
        }
        end = next;
    }
    end
}

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
    ///
    /// Inserted as given. The words are held to the rules below and the separator is
    /// not, so a slug carries whatever its separator does: under `allow_unicode`, a
    /// separator holding U+24B6 puts one between the words, although no word keeps one.
    pub separator: String,
    /// Lowercase the result (default `true`).
    pub lowercase: bool,
    /// Truncate the slug to at most this many **bytes**; `0` (default) means no limit.
    ///
    /// With `allow_unicode` the cut lands on a **grapheme-cluster** boundary (#711), so it
    /// never splits a cluster: a Devanagari conjunct or a Hangul syllable is kept whole or
    /// dropped whole. A budget too small for the first cluster therefore yields an empty
    /// slug — the same outcome an all-stopword input already produces, and callers needing
    /// a non-empty result should check `is_empty()` or supply a default.
    ///
    /// A cut never leaves a trailing separator, whole or partial, or a trailing ZWJ or ZWNJ.
    pub max_length: usize,
    /// When truncating, cut at a word boundary rather than mid-word: the slug keeps the
    /// whole words that fit in `max_length`, up to the first that does not. When not even
    /// the first word fits, it is cut as if `word_boundary` were off.
    pub word_boundary: bool,
    /// Preserve relative word order when removing stopwords (see the type-level
    /// docs); `false` (default) removes all matching tokens.
    pub save_order: bool,
    /// Words removed from the slug, compared case-insensitively whether or not `lowercase`
    /// is set. With an empty `separator` the slug has no words, and nothing is removed.
    pub stopwords: Vec<String>,
    /// Custom regex of characters to treat as separators; `None` uses the
    /// built-in non-word pattern.
    pub regex_pattern: Option<regex::Regex>,
    /// Literal `(from, to)` substitutions applied before transliteration
    /// (e.g. `("&", "and")`).
    pub replacements: Vec<(String, String)>,
    /// Keep non-ASCII **letters, digits and combining marks** instead of transliterating
    /// to ASCII (#712).
    ///
    /// Everything else becomes a separator, as it does on the ASCII path: format
    /// characters (bidi controls, ZWSP, ZWNBSP, soft hyphen, the tag block), private use,
    /// noncharacters, surrogates, punctuation, symbols and emoji. That includes the
    /// letter-like symbols `char::is_alphabetic` accepts, such as the circled Latin letters
    /// (U+24B6), which are `So`. This matches
    /// `django.utils.text.slugify(allow_unicode=True)`, which keeps `\w`, with two
    /// deliberate additions Django does not make:
    ///
    /// - **Combining marks** (`M*`), capped at two per base. Django drops them, which
    ///   breaks Devanagari and Arabic; two is the cap the `Step::Zalgo(2)` presets use and
    ///   what Vietnamese `ệ` needs. The cap counts the base's own marks, over its
    ///   decomposition, as `strip_zalgo` does: `à` takes one more. A precomposed base that
    ///   already carries more than two, such as polytonic Greek U+1F82 with three, is kept
    ///   whole and takes none.
    /// - **ZWJ and ZWNJ**, between two other kept characters. Both are orthographically
    ///   required — ZWNJ separates a Persian `می` prefix from its verb, ZWJ forms a
    ///   Devanagari conjunct — so dropping them changes the word. Never emitted at the
    ///   start or end of a token, where they would be invisible padding.
    pub allow_unicode: bool,
    /// Transliteration language hint; `None` uses the default tables.
    /// [`api::try_slugify`](crate::api::try_slugify), which every binding calls, rejects
    /// an unknown code; the deprecated infallible [`api::slugify`](crate::api::slugify)
    /// does not validate it (best-effort).
    pub lang: Option<String>,
    /// Decode HTML named entities (e.g. `&amp;`) before slugifying.
    pub entities: bool,
    /// Decode HTML decimal numeric entities (e.g. `&#38;`).
    ///
    /// A numeric entity is `&#`, an optional `x`, a run of digits and an optional `;`.
    /// `&#` with no digit after it is not one and stays text; one naming a control
    /// character, a surrogate or no character at all is dropped, without the text after
    /// it (#1040).
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

    /// Truncate to at most this many bytes (`0` = no limit). With `allow_unicode` the cut
    /// lands on a grapheme-cluster boundary (#711); see the field docs.
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

    /// Words to remove from the slug, compared case-insensitively; see the field docs.
    #[must_use]
    pub fn with_stopwords<I, S>(mut self, stopwords: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.stopwords = stopwords.into_iter().map(Into::into).collect();
        self
    }

    /// Keep non-ASCII **letters, digits and combining marks** instead of transliterating
    /// to ASCII (#712).
    ///
    /// Everything else becomes a separator, as it does on the ASCII path: format
    /// characters (bidi controls, ZWSP, ZWNBSP, soft hyphen, the tag block), private use,
    /// noncharacters, surrogates, punctuation, symbols and emoji. That includes the
    /// letter-like symbols `char::is_alphabetic` accepts, such as the circled Latin letters
    /// (U+24B6), which are `So`. This matches
    /// `django.utils.text.slugify(allow_unicode=True)`, which keeps `\w`, with two
    /// deliberate additions Django does not make:
    ///
    /// - **Combining marks** (`M*`), capped at two per base. Django drops them, which
    ///   breaks Devanagari and Arabic; two is the cap the `Step::Zalgo(2)` presets use and
    ///   what Vietnamese `ệ` needs. The cap counts the base's own marks, over its
    ///   decomposition, as `strip_zalgo` does: `à` takes one more. A precomposed base that
    ///   already carries more than two, such as polytonic Greek U+1F82 with three, is kept
    ///   whole and takes none.
    /// - **ZWJ and ZWNJ**, between two other kept characters. Both are orthographically
    ///   required — ZWNJ separates a Persian `می` prefix from its verb, ZWJ forms a
    ///   Devanagari conjunct — so dropping them changes the word. Never emitted at the
    ///   start or end of a token, where they would be invisible padding.
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

    // Step 3: Transliterate (the ASCII path). The Unicode-preserving path composes instead,
    // after Step 4: see there.
    // #236 item 3: only reallocate when the step changed the text. ASCII input
    // returns Cow::Borrowed, so the former unconditional into_owned() allocated on
    // every plain-ASCII slug. Extract owned-ness first so the borrow of `value` ends
    // before we reassign it (#114).
    if !config.allow_unicode {
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

    // Step 6 reads an ASCII value a byte at a time and lowercases as it goes
    // (`tokenize_ascii`), so step 4 is folded into it — unless the step-5 regex has to
    // see the lowercased value first.
    let ascii_pass = config.regex_pattern.is_none() && value.is_ascii();

    // Step 4: Lowercase
    if config.lowercase && !ascii_pass {
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

    // Step 4b: compose, on the Unicode-preserving path only.
    if config.allow_unicode {
        // #477: the Unicode-preserving path skips transliterate, so compose here —
        // a decomposed homoglyph (`і` + combining diaeresis) must yield the same slug
        // as its precomposed form (`ї`). `compose_str` borrows when the input has no
        // combining mark, so the common ASCII/precomposed slug keeps its zero-alloc
        // path; it never decomposes a composition-excluded singleton. See
        // [`crate::compose`].
        //
        // AFTER lowercasing, not before (Finding 10 of `formal/lean/Sanitizers`).
        // Lowercasing can create a pair that composes: `T` + U+0308 has no precomposed
        // form, `t` + U+0308 does (U+1E97). Composing first returned `t\u{308}` for
        // `T\u{308}`, while `\u{1E97}` gave `\u{1E97}`: two slugs for one rendering, and
        // an output that changed when slugified again.
        let owned = match crate::compose::compose_str(&value) {
            Cow::Borrowed(_) => None,
            Cow::Owned(s) => Some(s),
        };
        if let Some(s) = owned {
            value = Cow::Owned(s);
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

    // Precompute safe_chars membership once: `String::contains(char)` is an O(k)
    // substring scan, so the per-char check was O(n·k) for any non-empty
    // safe_chars (#252 O5.1). Collecting an empty safe_chars (the default) does not
    // allocate, and both passes skip the per-char probe when the set is empty (O3).
    let safe_set: HashSet<char> = config.safe_chars.chars().collect();
    let mut slug = if ascii_pass {
        tokenize_ascii(&value, config, &safe_set, config.lowercase)
    } else if value.is_ascii() {
        // Already lowercased by step 4 if that was asked for.
        tokenize_ascii(&value, config, &safe_set, false)
    } else {
        tokenize_chars(&value, config, &safe_set)
    };

    // Strip trailing separator
    if slug.ends_with(separator) && !separator.is_empty() {
        slug.truncate(slug.len() - separator.len());
    }

    // Step 6b: with no separator, compose again (#1040). Step 4b composed each word, but
    // joining the words with nothing can put two characters that compose side by side:
    // `"\u{1100} \u{1161}"` gave the two conjoining jamo, which render as U+AC00 and which
    // the next call composed to it, and Kirat Rai U+16D67 does the same with itself. A
    // mark never starts a word (the loop above drops one), so only these starters that
    // compose with the starter before them are affected; composing here gives the slug
    // that already reads as one, and a second call has nothing left to compose.
    if config.allow_unicode && separator.is_empty() {
        if let Cow::Owned(composed) = crate::compose::compose_str(&slug) {
            slug = composed;
        }
    }

    // Step 7: Remove stopwords
    // Note: if *all* words match the stopword list the result will be an empty
    // string.  This is intentional — callers that need a non-empty fallback
    // should check `slug.is_empty()` and supply one (e.g. a hash of the input).
    //
    // With an empty separator there are no words: the tokens were joined with nothing
    // between them, and `split("")` yields single characters, so `stopwords=["b"]` turned
    // `abc` into `ac` (Finding 8 of `formal/lean/Sanitizers`). The filter is skipped.
    if !config.stopwords.is_empty() && !separator.is_empty() {
        // Use the caller-supplied set when available (e.g. _Slugifier caches it
        // at construction), otherwise build a temporary set from config. Either way
        // it is built by `build_stopset`, which lowercases.
        let tmp_stopset;
        let stopset: &HashSet<String> = if let Some(s) = prebuilt_stopset {
            s
        } else {
            tmp_stopset = build_stopset(&config.stopwords);
            &tmp_stopset
        };
        slug = filter_stopwords(
            &slug,
            separator,
            stopset,
            config.save_order,
            !config.lowercase,
        );
    }

    // Step 8: Truncate to max_length (byte-length, cluster-boundary safe for
    // allow_unicode — #711). The ASCII path keeps the cheap code-point route, where the
    // two boundaries coincide anyway.
    if config.max_length > 0 && slug.len() > config.max_length {
        if config.word_boundary {
            // Truncate at word boundary
            slug = truncate_at_boundary(&slug, config.max_length, separator, config.allow_unicode);
        } else {
            let boundary = floor_slug_boundary(&slug, config.max_length, config.allow_unicode);
            slug.truncate(boundary);
            // Strip what the cut left at the end: a joiner the cluster kept (Finding 13),
            // then a partial separator as well as a whole one (Finding 5), as
            // `truncate_at_boundary` does.
            let end = trim_cut_tail(&slug, separator, config.allow_unicode).len();
            slug.truncate(end);
        }
    }

    slug
}

/// Step 6 of [`slugify_impl_with_stopset`]: keep word characters, and put one separator
/// where each run of anything else was. Leading separators are never written; a trailing
/// one is, and the caller strips it.
fn tokenize_chars(value: &str, config: &SlugConfig, safe_set: &HashSet<char>) -> String {
    let separator = &config.separator;
    let has_safe_chars = !safe_set.is_empty();
    let mut slug = String::with_capacity(value.len());
    let mut prev_was_sep = true; // avoid leading separator

    // #712: a joiner is held back until another kept character arrives, and marks are
    // capped per base. Both are `allow_unicode`-only state; the ASCII path below stays
    // byte-identical, because `transliterate` has already removed everything they read.
    let mut pending_joiner: Option<char> = None;
    let mut mark_run: usize = 0;
    // Separate from `prev_was_sep`, which means "a separator has already been emitted" and
    // is deliberately NOT set when `separator` is empty — there is nothing to emit. This
    // one means "a base is in scope", and a dropped character ends a token whether or not
    // anything was written in its place. Fusing the two let a joiner or a mark reattach
    // ACROSS a removed character with `separator = ""`: `slugify("a!\u{200D}b")` returned
    // `a\u{200D}b`, joining two characters that were never adjacent, and `slugify("a!\u{300}b")`
    // returned `àb`, moving the accent onto a letter that never carried it.
    let mut in_token = false;

    for ch in value.chars() {
        // Under `allow_unicode` a non-ASCII character is judged by `is_unicode_slug_char`
        // alone, which excludes the symbols `is_alphanumeric` admits (Finding 4). The
        // ASCII path keeps `is_alphanumeric`, byte for byte as before.
        let word_char = if config.allow_unicode && !ch.is_ascii() {
            is_unicode_slug_char(ch)
        } else {
            ch.is_alphanumeric()
        };
        if word_char || (has_safe_chars && safe_set.contains(&ch)) {
            if config.allow_unicode {
                if SLUG_JOINERS.contains(&ch) {
                    // Nothing to join to yet: a token cannot start with one.
                    if in_token {
                        pending_joiner = Some(ch);
                    }
                    continue;
                }
                if unicode_normalization::char::is_combining_mark(ch) {
                    // A defective combining sequence — no base in this token.
                    if !in_token {
                        continue;
                    }
                    mark_run += 1;
                    if mark_run > MAX_SLUG_COMBINING_MARKS {
                        continue;
                    }
                } else {
                    // Seed from the base's OWN marks so the cap matches `strip_zalgo(2)`,
                    // which counts over NFD: `à` already carries one there, and 30 stacked
                    // on it must not come back as three. ASCII has no decomposition.
                    mark_run = if ch.is_ascii() {
                        0
                    } else {
                        base_mark_count(ch)
                    };
                }
                // Reached only when a kept character follows, so a trailing joiner is
                // never emitted.
                if let Some(joiner) = pending_joiner.take() {
                    slug.push(joiner);
                }
            }
            // safe_chars are kept verbatim and treated as word characters, so a
            // separator is not inserted around them (awesome-slugify semantics, #230).
            slug.push(ch);
            prev_was_sep = false;
            in_token = true;
        } else {
            pending_joiner = None;
            mark_run = 0;
            in_token = false;
            if !prev_was_sep && !separator.is_empty() {
                slug.push_str(separator);
                prev_was_sep = true;
            }
        }
    }

    slug
}

/// A byte that is not part of a word in [`tokenize_ascii`]'s tables: outside `u8`, so no
/// output byte can collide with it (a safe character may be NUL).
const NOT_WORD: u16 = 0x100;

/// For each ASCII byte, what [`tokenize_ascii`] writes for it: the byte, lowercased when
/// `lowercase` is set, when it is alphanumeric or `safe`; [`NOT_WORD`] otherwise.
const fn ascii_word_table_const(lowercase: bool) -> [u16; 128] {
    let mut table = [NOT_WORD; 128];
    let mut b = 0u8;
    while b < 128 {
        if b.is_ascii_alphanumeric() {
            table[b as usize] = (if lowercase { b.to_ascii_lowercase() } else { b }) as u16;
        }
        b += 1;
    }
    table
}

/// [`ascii_word_table_const`] with safe characters, built per call when there are any.
fn ascii_word_table(lowercase: bool, safe: impl Fn(u8) -> bool) -> [u16; 128] {
    let mut table = ascii_word_table_const(lowercase);
    for (b, slot) in (0u8..128).zip(table.iter_mut()) {
        if *slot == NOT_WORD && safe(b) {
            // Kept verbatim: a safe character that is not alphanumeric has no case.
            *slot = u16::from(b);
        }
    }
    table
}

const ASCII_WORD: [u16; 128] = ascii_word_table_const(false);
const ASCII_WORD_LOWER: [u16; 128] = ascii_word_table_const(true);

/// Step 6 over a value that is wholly ASCII, a byte at a time, lowercasing on the way
/// when `lowercase` is set.
///
/// Writes exactly what step 4 and [`tokenize_chars`] write between them for such a value
/// (`ascii_token_pass_matches_the_char_pass`). Every ASCII character is one byte,
/// `char::is_alphanumeric` is `is_ascii_alphanumeric` on it, and the `allow_unicode`
/// rules act only on joiners and combining marks, none of which is ASCII. Case does not
/// change which bytes are word bytes, so lowercasing only the bytes that are kept is the
/// same as lowercasing the value first; the separator is written as given.
///
/// The char pass decoded, classified and re-encoded every character through
/// `String::push`, after step 4 had copied and lowercased the whole value: about 52
/// instructions a byte on the iai `slugify_doc ascii` document.
fn tokenize_ascii(
    value: &str,
    config: &SlugConfig,
    safe_set: &HashSet<char>,
    lowercase: bool,
) -> String {
    debug_assert!(value.is_ascii());
    // What each ASCII byte becomes: its output byte, or NOT_WORD. The two tables the
    // default configuration needs are built at compile time, so a short slug pays nothing
    // to set up; only a configuration with safe characters builds its own.
    let built;
    let table: &[u16; 128] = if safe_set.is_empty() {
        if lowercase {
            &ASCII_WORD_LOWER
        } else {
            &ASCII_WORD
        }
    } else {
        built = ascii_word_table(lowercase, |b| safe_set.contains(&char::from(b)));
        &built
    };
    let separator = config.separator.as_bytes();

    if let [sep] = *separator {
        return tokenize_ascii_one_byte_separator(value.as_bytes(), table, sep);
    }

    let mut slug: Vec<u8> = Vec::with_capacity(value.len());
    let mut prev_was_sep = true; // avoid leading separator
    for &b in value.as_bytes() {
        // `& 0x7F` is a no-op on ASCII and lets the compiler drop the bounds check.
        let out = table[usize::from(b & 0x7F)];
        if out != NOT_WORD {
            // Truncation is the intent: every entry but NOT_WORD is an ASCII byte.
            #[allow(clippy::cast_possible_truncation)]
            slug.push(out as u8);
            prev_was_sep = false;
        } else if !prev_was_sep && !separator.is_empty() {
            // Several bytes: the one-byte case returned above.
            slug.extend_from_slice(separator);
            prev_was_sep = true;
        }
    }
    // ASCII bytes and whole copies of a `&str` separator: always UTF-8.
    String::from_utf8(slug).expect("ASCII bytes and whole separators are UTF-8")
}

/// [`tokenize_ascii`] for the default shape, a one-byte separator, without a branch on
/// the byte.
///
/// Every input byte writes one byte (its table entry, or the separator) and the write
/// position moves past it when it should stay: always for a word byte, and for a non-word
/// byte only straight after a word, which is where a separator belongs. So a separator
/// can never make the slug longer than the value, the buffer is sized once, and the loop
/// has no data-dependent branch for the predictor to miss at every word boundary.
fn tokenize_ascii_one_byte_separator(bytes: &[u8], table: &[u16; 128], sep: u8) -> String {
    let mut out = vec![0u8; bytes.len()];
    let mut len = 0;
    let mut after_word = false;
    for (&b, _) in bytes.iter().zip(0..out.len()) {
        let entry = table[usize::from(b & 0x7F)];
        let word = entry != NOT_WORD;
        // Truncation is the intent: every entry but NOT_WORD is an ASCII byte.
        #[allow(clippy::cast_possible_truncation)]
        let byte = if word { entry as u8 } else { sep };
        // `len` never passes the index of the byte being read, so this stays in bounds.
        out[len] = byte;
        len += usize::from(word | after_word);
        after_word = word;
    }
    out.truncate(len);
    // ASCII bytes and an ASCII separator.
    String::from_utf8(out).expect("ASCII bytes and an ASCII separator are UTF-8")
}

/// Build the stopword set `slugify` compares against: every stopword lowercased.
///
/// Stopwords are documented as case-insensitive, and were compared verbatim with a slug
/// that had already been lowercased, so `stopwords=["The"]` could never match
/// (Finding 7 of `formal/lean/Sanitizers`). Lowercasing the set once here, and each word
/// only when the slug itself was not lowercased (`filter_stopwords`), makes the match
/// case-insensitive on both settings of `lowercase`. The binding-layer slugifiers that
/// cache a set build it with this function too, so every entry point agrees.
pub(crate) fn build_stopset(stopwords: &[String]) -> HashSet<String> {
    stopwords.iter().map(|w| w.to_lowercase()).collect()
}

/// Whether `word` is in `stopset` (already lowercased by [`build_stopset`]).
///
/// `fold` is `true` when the slug was not lowercased, so the word may carry upper case;
/// a lowercased slug is compared as it is, with no allocation.
fn is_stopword(word: &str, stopset: &HashSet<String>, fold: bool) -> bool {
    if !fold {
        return stopset.contains(word);
    }
    if word.is_ascii() {
        if word.bytes().any(|b| b.is_ascii_uppercase()) {
            stopset.contains(&word.to_ascii_lowercase())
        } else {
            stopset.contains(word)
        }
    } else {
        stopset.contains(&word.to_lowercase())
    }
}

/// Trim what a truncation can leave at the end of a slug.
///
/// First the joiners (`allow_unicode` only). Grapheme rule GB9 attaches ZWJ and ZWNJ to
/// the character before them, so a cluster-boundary cut keeps `a\u{200D}` of
/// `a\u{200D}b` whole, and the slug ended in a bare joiner, which #711 exists to prevent
/// (Finding 13 of `formal/lean/Sanitizers`). Then a trailing separator, whole or partial:
/// a cut inside a multi-character separator left its first half (Finding 5).
///
/// The order is safe: a joiner is only ever emitted between two kept characters, and a
/// separator only after one, so neither trim can expose the other.
fn trim_cut_tail<'a>(s: &'a str, separator: &str, allow_unicode: bool) -> &'a str {
    let s = if allow_unicode {
        s.trim_end_matches(SLUG_JOINERS)
    } else {
        s
    };
    strip_trailing_separator_prefix(s, separator)
}

/// The byte length a cut to `max` keeps of `s`: a cluster boundary under `allow_unicode`
/// (#711), a code-point boundary otherwise.
fn floor_slug_boundary(s: &str, max: usize, allow_unicode: bool) -> usize {
    if allow_unicode {
        floor_grapheme_boundary(s, max)
    } else {
        floor_char_boundary(s, max)
    }
}

/// Why [`unique_slug_candidate`] has no candidate for a counter.
#[derive(Debug, PartialEq, Eq)]
pub(crate) struct UniqueSlugTooShort {
    /// The smallest `max_length` that would have held this candidate: the base's first
    /// character (first cluster under `allow_unicode`), the separator and every digit.
    pub(crate) min_unique_len: usize,
}

/// The `counter`-th candidate `UniqueSlugifier` tries for `base` (#102, #242 item 3).
///
/// Counter 0 is `base` itself; counter `k >= 1` is `base{separator}k`. When that exceeds
/// `max_length`, the **base** is cut to make room, never the suffix, and the cut is the
/// slug's own: a cluster boundary under `allow_unicode`, then the tail cleaned by
/// [`trim_cut_tail`], so the head is a slug in its own right (Finding 9 of
/// `formal/lean/Sanitizers`). The former cut was a bare code-point cut: `ab-cd` at
/// `max_length = 5` gave `ab--1`, a doubled separator, and with `allow_unicode` it split a
/// cluster and left a ZWJ before the suffix.
///
/// A candidate keeps at least one character of the base. When the suffix leaves no room
/// for one there is no candidate (`Err`): returning the suffix alone gave `-1`, a slug
/// with a leading separator that every base shared, and cutting into the digits aliased
/// distinct counters. The digits are never cut, so distinct counters give distinct
/// candidates.
///
/// An empty `base` has no suffixed candidate either (`Err`): the caller returns the empty
/// slug as it is, `slugify`'s own documented result, rather than `-1`, `-2`, ... .
pub(crate) fn unique_slug_candidate(
    base: &str,
    counter: u64,
    config: &SlugConfig,
) -> Result<String, UniqueSlugTooShort> {
    if counter == 0 {
        return Ok(base.to_owned());
    }
    let sep = config.separator.as_str();
    let suffix = format!("{sep}{counter}");
    if base.is_empty() {
        return Err(UniqueSlugTooShort {
            min_unique_len: suffix.len() + 1,
        });
    }
    let max = config.max_length;
    if max == 0 || base.len() + suffix.len() <= max {
        return Ok(format!("{base}{suffix}"));
    }
    let head_end =
        floor_slug_boundary(base, max.saturating_sub(suffix.len()), config.allow_unicode);
    // `floor_*_boundary` returns a boundary `<= base.len()`, so the slice cannot panic.
    let head = trim_cut_tail(&base[..head_end], sep, config.allow_unicode);
    if head.is_empty() {
        // The shortest head is the first character (first cluster under `allow_unicode`).
        let first = if config.allow_unicode {
            crate::grapheme::clusters(base).next().map_or(1, str::len)
        } else {
            base.chars().next().map_or(1, char::len_utf8)
        };
        return Err(UniqueSlugTooShort {
            min_unique_len: first + suffix.len(),
        });
    }
    Ok(format!("{head}{suffix}"))
}

/// Remove stopwords from a slug, splitting and rejoining on the separator.
///
/// When `save_order` is `true`, only leading and trailing stopwords are
/// removed — interior stopwords are kept so the relative order of
/// non-stopword tokens is preserved exactly as in the input (matching the
/// python-slugify semantics for `save_order=True`). (#118)
///
/// `stopset` is lowercased ([`build_stopset`]); `fold` lowercases each word before the
/// lookup, for a slug that was not lowercased (Finding 7).
fn filter_stopwords(
    slug: &str,
    separator: &str,
    stopset: &HashSet<String>,
    save_order: bool,
    fold: bool,
) -> String {
    let is_stop = |w: &str| is_stopword(w, stopset, fold);
    if save_order {
        // Strip only leading and trailing stopword tokens; preserve interior ones.
        let words: Vec<&str> = slug.split(separator).collect();
        let start = words
            .iter()
            .position(|w| !is_stop(w))
            .unwrap_or(words.len());
        let end = words.iter().rposition(|w| !is_stop(w)).map_or(0, |i| i + 1);
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
            .filter(|w| !is_stop(w))
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

/// Truncate slug at a word boundary (separator), boundary-safe.
///
/// `allow_unicode` selects the *cluster* floor (#711): `word_boundary = true` was no help
/// on emoji, because this function reached the separator search with an already-split
/// cluster and then found no separator to fall back to.
fn truncate_at_boundary(
    slug: &str,
    max_length: usize,
    separator: &str,
    allow_unicode: bool,
) -> String {
    if slug.len() <= max_length {
        return slug.to_owned();
    }
    let boundary = floor_slug_boundary(slug, max_length, allow_unicode);
    let truncated = &slug[..boundary];
    // The cut landed exactly at the end of a word: keep that word (Finding 6 of
    // `formal/lean/Sanitizers`). The search below looks for a separator *inside* the cut,
    // so `very-long-title-here` at 9 bytes dropped `long`, although `very-long` is 9 bytes
    // and ends on a word. python-slugify's `smart_truncate` keeps it.
    if !separator.is_empty() && slug[boundary..].starts_with(separator) {
        return truncated.to_owned();
    }
    match truncated.rfind(separator) {
        // Everything before the last full separator: ends on a token boundary.
        // (`rfind("")` is the end of the cut: with no separator there are no words, and
        // the cut is cleaned like a plain one, below.)
        Some(pos) if !separator.is_empty() => truncated[..pos].to_owned(),
        // No full separator survived the cut, but `floor_char_boundary` can land
        // *inside* a multi-char separator, leaving a trailing partial separator
        // (e.g. separator "--", slug "ab--cd", max 3 → "ab-"). Strip it so the
        // slug never ends in a (partial or whole) separator (review M-C1), and strip a
        // joiner the cluster cut kept (Finding 13).
        _ => trim_cut_tail(truncated, separator, allow_unicode).to_owned(),
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

/// Decode a numeric HTML entity (`&#NNN;` / `&#xHHH;`) starting at `pos`, where
/// `text[pos..]` starts with `&#`.
///
/// `None` when there is no entity there: no digit follows `&#` (or `&#x`). The caller
/// then keeps the `&` as text, as an HTML parser does, so the characters after it are
/// read as ordinary text. Otherwise `Some((decoded, consumed))`, where `consumed` is
/// exactly the entity: `&#`, the `x`, the whole run of digits and one `;` if present.
/// `decoded` is `None` for a value that is not a character a slug may carry (zero, a
/// control character, a surrogate, anything above U+10FFFF), and the entity is then
/// dropped, but only the entity.
///
/// Until the fuzz findings of #1040 a failed decode also skipped up to 14 bytes of the
/// ASCII after the `&#`, stopping at the first non-ASCII byte: `"Q&#A session"` gave `q`,
/// `"issue &#12 fixed"` gave `issue`, and because the skip stopped at a composed letter
/// but not at its decomposition, `"&#a\u{301}"` gave `""` while its NFC gave `\u{e1}`.
///
/// An ASCII letter followed by a combining mark is read as the accented letter it
/// renders as, so it is neither the `x` nor a hex digit. That is what keeps the decode
/// the same for both normal forms: NFC composes `a` + U+0301 to `\u{e1}`, which is not a
/// hex digit, and NFD spells it `a` + U+0301, which would otherwise be one. Decimal
/// digits compose with nothing, so they need no such rule. The value is accumulated as
/// the digits are read, with no buffer and no cap on how many there are: leading zeros
/// are allowed, and a run too large for a scalar is dropped whole.
fn decode_numeric_entity(text: &str, pos: usize) -> Option<(Option<char>, usize)> {
    let bytes = text.as_bytes();
    // An ASCII letter at `i` that carries a combining mark is not an ASCII letter to
    // the reader (see above).
    let carries_mark = |i: usize| {
        text[i + 1..]
            .chars()
            .next()
            .is_some_and(unicode_normalization::char::is_combining_mark)
    };
    let mut i = pos + 2; // skip "&#"
    let is_hex = matches!(bytes.get(i), Some(b'x' | b'X')) && !carries_mark(i);
    if is_hex {
        i += 1;
    }
    let radix: u32 = if is_hex { 16 } else { 10 };
    let digits_start = i;
    let mut value: Option<u32> = Some(0);
    while let Some(&b) = bytes.get(i) {
        let Some(digit) = (b as char).to_digit(radix) else {
            break;
        };
        if b.is_ascii_alphabetic() && carries_mark(i) {
            break;
        }
        value = value
            .and_then(|v| v.checked_mul(radix))
            .and_then(|v| v.checked_add(digit));
        i += 1;
    }
    if i == digits_start {
        return None;
    }
    if bytes.get(i) == Some(&b';') {
        i += 1;
    }
    // Exclude control characters — they are never valid slug content.
    let decoded = value.and_then(char::from_u32).filter(|c| !c.is_control());
    Some((decoded, i - pos))
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
                if let Some((decoded, consumed)) = decode_numeric_entity(text, i) {
                    // `consumed` covers the entity whether or not it decoded (C3);
                    // push only on success.
                    if let Some(ch) = decoded {
                        result.push(ch);
                    }
                    i += consumed;
                } else {
                    // No digits: not an entity, so the `&` is text (#1040).
                    result.push('&');
                    i += 1;
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

    Cow::Owned(result)
}

// --- Tests ---

#[cfg(test)]
mod tests {
    use super::*;

    /// The byte pass over an ASCII value writes exactly what step 4 (lowercase) and the
    /// char pass write between them.
    ///
    /// Random strings over every ASCII byte, controls included, against every separator
    /// shape the char pass treats differently (empty, one byte, several bytes, a
    /// separator made of word characters, one with capitals that lowercasing must not
    /// touch), with and without safe characters, lowercasing on and off, on both the ASCII
    /// and the `allow_unicode` path.
    #[test]
    fn ascii_token_pass_matches_the_char_pass() {
        let mut state: u64 = 0x9E37_79B9_7F4A_7C15;
        let mut next = move || {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            state
        };
        let separators = ["-", "_", "", "--", "ab", " ", "AB"];
        let safe_chars = ["", "._", "a-", "\x00"];
        let mut compared = 0;
        for &separator in &separators {
            for &safe in &safe_chars {
                for (allow_unicode, lowercase) in
                    [(false, false), (false, true), (true, false), (true, true)]
                {
                    let config = SlugConfig {
                        separator: separator.to_owned(),
                        safe_chars: safe.to_owned(),
                        allow_unicode,
                        lowercase,
                        ..SlugConfig::default()
                    };
                    let safe_set: HashSet<char> = config.safe_chars.chars().collect();
                    for _ in 0..200 {
                        let len = (next() % 40) as usize;
                        // Biased toward the classes that matter: letters, digits, the
                        // separator's own bytes, and runs of punctuation and spaces.
                        let text: String = (0..len)
                            .map(|_| match next() % 6 {
                                0 => char::from(b'a' + (next() % 26) as u8),
                                1 => char::from(b'A' + (next() % 26) as u8),
                                2 => char::from(b'0' + (next() % 10) as u8),
                                3 => ['-', '_', ' ', '.'][(next() % 4) as usize],
                                _ => char::from((next() % 128) as u8),
                            })
                            .collect();
                        // Step 4 as the char path runs it, then the char pass.
                        let stepped = if lowercase {
                            text.to_ascii_lowercase()
                        } else {
                            text.clone()
                        };
                        assert_eq!(
                            tokenize_ascii(&text, &config, &safe_set, lowercase),
                            tokenize_chars(&stepped, &config, &safe_set),
                            "text={text:?} separator={separator:?} safe={safe:?} \
                             allow_unicode={allow_unicode} lowercase={lowercase}"
                        );
                        compared += 1;
                    }
                }
            }
        }
        assert_eq!(compared, 7 * 4 * 4 * 200);
    }

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
        // "&#xyz;" has no hex digit after the `x`, so it is not an entity and stays
        // text, as it does in HTML (#1040). It used to be dropped whole.
        assert_eq!(decode_entities("&#xyz;", true, true), "&#xyz;");
        // A run of digits is the entity; what follows it is text.
        assert_eq!(decode_entities("&#12 fixed", true, true), " fixed");
        assert_eq!(decode_entities("Q&#A session", true, true), "Q&#A session");
    }

    #[test]
    fn test_decode_malformed_entity_semicolon_preserved() {
        // Empty decimal and hex entities have no digits: text, `;` included (#1040).
        assert_eq!(decode_entities("&#;", true, true), "&#;");
        assert_eq!(decode_entities("&#x;", true, true), "&#x;");
        // Invalid codepoint (too large for Unicode): malformed, dropped silently.
        assert_eq!(decode_entities("&#xFFFFFFFF;", true, true), "");
        // U+0000 is a control character and is filtered; entity dropped silently.
        let result = decode_entities("&#0;", true, true);
        assert_eq!(result, "");
    }

    #[test]
    fn test_decode_entity_digit_limit() {
        // An extremely long run of digits is one entity, too large for a scalar, and is
        // dropped whole: none of its digits leak into the text (#1040).
        let long = format!("&#{}1;x", "9".repeat(100));
        assert_eq!(decode_entities(&long, true, true), "x");
        // Leading zeros are not a length problem: the value is what counts.
        let zeros = format!("&#{}65;", "0".repeat(100));
        assert_eq!(decode_entities(&zeros, true, true), "A");
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
        assert_eq!(truncate_at_boundary("abc", 10, "-", false), "abc");
    }

    #[test]
    fn test_truncate_at_boundary_with_separator() {
        // "hello-world-foo" has 15 chars; truncate to 12 gives "hello-world-"
        // rfind("-") at pos 11 → "hello-world"
        assert_eq!(
            truncate_at_boundary("hello-world-foo", 12, "-", false),
            "hello-world"
        );
    }

    #[test]
    fn test_truncate_at_boundary_no_separator_found() {
        assert_eq!(truncate_at_boundary("helloworld", 5, "-", false), "hello");
    }

    #[test]
    fn test_truncate_at_boundary_strips_partial_multichar_separator() {
        // Review M-C1: a multi-char separator cut mid-sequence must not leave a
        // trailing partial separator. "ab--cd" truncated to 3 → "ab-" → "ab".
        assert_eq!(truncate_at_boundary("ab--cd", 3, "--", false), "ab");
        // A clean full-separator cut still lands on the token boundary.
        assert_eq!(truncate_at_boundary("ab--cd", 4, "--", false), "ab");
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

    /// Finding 9 of `formal/lean/Sanitizers`: the `UniqueSlugifier` candidates. The loop
    /// that consumes them is binding-layer (`src/py/slugify.rs`); the candidates are here.
    mod unique_candidate {
        use super::*;

        fn cfg(separator: &str, max_length: usize, allow_unicode: bool) -> SlugConfig {
            SlugConfig::new()
                .with_separator(separator)
                .with_max_length(max_length)
                .with_allow_unicode(allow_unicode)
        }

        fn cand(base: &str, counter: u64, config: &SlugConfig) -> Result<String, usize> {
            unique_slug_candidate(base, counter, config).map_err(|e| e.min_unique_len)
        }

        #[test]
        fn counter_zero_is_the_base() {
            assert_eq!(
                cand("ab-cd", 0, &cfg("-", 5, false)),
                Ok("ab-cd".to_owned())
            );
            assert_eq!(cand("", 0, &cfg("-", 0, false)), Ok(String::new()));
        }

        #[test]
        fn a_suffix_that_fits_is_appended() {
            assert_eq!(
                cand("my-post", 1, &cfg("-", 0, false)),
                Ok("my-post-1".to_owned())
            );
            assert_eq!(cand("ab", 12, &cfg("_", 5, false)), Ok("ab_12".to_owned()));
        }

        #[test]
        fn the_head_is_cut_like_a_slug_not_mid_separator() {
            // `ab-cd` at 5: the head `ab-` is cleaned to `ab` before `-1`, not `ab--1`.
            let c = cfg("-", 5, false);
            assert_eq!(cand("ab-cd", 1, &c), Ok("ab-1".to_owned()));
            assert_eq!(cand("ab-cd", 2, &c), Ok("ab-2".to_owned()));
            // A multi-character separator cut in half.
            let c = cfg("--", 7, false);
            assert_eq!(cand("ab--cd", 1, &c), Ok("ab--1".to_owned()));
            let c = cfg("--", 6, false);
            assert_eq!(cand("ab--cd", 1, &c), Ok("ab--1".to_owned()));
            let c = cfg("--", 4, false);
            assert_eq!(cand("ab--cd", 1, &c), Ok("a--1".to_owned()));
        }

        #[test]
        fn never_the_suffix_alone() {
            // `ab` at 2 has no room for `-1` and a character of the base: the smallest
            // length that fits is one character, the separator and the digit.
            assert_eq!(cand("ab", 1, &cfg("-", 2, false)), Err(3));
            assert_eq!(cand("ab", 10, &cfg("-", 3, false)), Err(4));
            assert_eq!(cand("ab", 1, &cfg("-", 3, false)), Ok("a-1".to_owned()));
        }

        #[test]
        fn an_empty_base_has_no_suffixed_candidate() {
            assert!(cand("", 1, &cfg("-", 0, false)).is_err());
            assert!(cand("", 1, &cfg("-", 10, false)).is_err());
        }

        #[test]
        fn allow_unicode_cuts_on_a_cluster_and_drops_a_trailing_joiner() {
            // The finding: `a` + KA + VIRAMA + ZWJ + SSA at 13 gave `a` KA VIRAMA ZWJ `-1`.
            let base = "a\u{915}\u{94D}\u{200D}\u{937}";
            let got = cand(base, 1, &cfg("-", 13, true)).unwrap();
            assert!(got.len() <= 13);
            assert!(got.ends_with("-1"));
            let head = got.strip_suffix("-1").unwrap();
            assert!(!head.is_empty());
            assert!(!head.ends_with(['\u{200C}', '\u{200D}']), "{got:?}");
            assert!(base.starts_with(head));
            // A cluster is kept whole or dropped whole.
            // `a` + ZWJ is one cluster (GB9): at 6 it is kept and its joiner dropped; at 5
            // it does not fit beside `-1`.
            assert_eq!(
                cand("a\u{200D}b", 1, &cfg("-", 6, true)),
                Ok("a-1".to_owned())
            );
            assert_eq!(cand("a\u{200D}b", 1, &cfg("-", 5, true)), Err(6));
            // The first cluster does not fit: no candidate, and the length that would.
            let hangul = "\u{D55C}\u{AD6D}";
            assert_eq!(cand(hangul, 1, &cfg("-", 4, true)), Err(5));
            assert_eq!(
                cand(hangul, 1, &cfg("-", 5, true)),
                Ok("\u{D55C}-1".to_owned())
            );
        }

        #[test]
        fn distinct_counters_give_distinct_candidates() {
            let c = cfg("-", 6, false);
            let got: Vec<String> = (1..=200)
                .filter_map(|k| unique_slug_candidate("abcdef", k, &c).ok())
                .collect();
            let unique: HashSet<&String> = got.iter().collect();
            assert_eq!(unique.len(), got.len());
            // Every one is a slug: no doubled, leading or trailing separator.
            for g in &got {
                assert!(
                    !g.starts_with('-') && !g.ends_with('-') && !g.contains("--"),
                    "{g}"
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
