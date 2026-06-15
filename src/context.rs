//! Context-aware transliteration for abjad scripts (Arabic, Persian, Hebrew).
//!
//! Uses dictionary-based vowel restoration with bigram context disambiguation.
//! The dictionary maps consonant skeletons (unpointed text) to diacritized
//! forms, which are then transliterated by the existing character-by-character
//! engine.
//!
//! Three-tier fallback:
//! 1. Bigram lookup: (previous_word_skeleton, current_word_skeleton) → best form
//! 2. Unigram lookup: current_word_skeleton → most frequent form
//! 3. Context-free: existing character-by-character transliteration

use std::borrow::Cow;
use std::sync::OnceLock;

/// Tatweel (kashida) — decorative elongation in Arabic.
const TATWEEL: char = '\u{0640}';

/// Binary dictionary format magic bytes.
const MAGIC: &[u8; 4] = b"TRLD";

// `MAX_DICT_ENTRIES` (the `from_bytes` capacity-hint clamp, #116) is centralized
// in `crate::limits` (#256).
use crate::limits::MAX_DICT_ENTRIES;

/// A `(offset, len)` slice into the backing dictionary bytes. `u32` is ample:
/// dictionaries are a few MB and the on-disk format already uses `u32` offsets.
#[derive(Clone, Copy)]
struct Span {
    off: u32,
    len: u32,
}

/// One unigram: its consonant skeleton and its single best (most frequent)
/// diacritized form. Entries are sorted by skeleton bytes for binary search.
#[derive(Clone, Copy)]
struct UniEntry {
    skel: Span,
    form: Span,
}

/// One bigram entry within a previous-word group: the current-word skeleton and
/// the diacritized form to use. Sorted by `curr` bytes within the group.
#[derive(Clone, Copy)]
struct BiEntry {
    curr: Span,
    form: Span,
}

/// A previous-word group: every bigram entry sharing this `prev` skeleton
/// occupies the contiguous `[start, start + len)` range of `bi_entries`. Groups
/// are sorted by `prev` bytes. This nesting preserves the cheap two-step
/// prev → curr lookup — `resolve` probes with borrowed `&str` keys and never
/// allocates an owned `(prev, curr)` tuple per token (#238 guardrail).
#[derive(Clone, Copy)]
struct BiGroup {
    prev: Span,
    start: u32,
    len: u32,
}

/// Context dictionary backed directly by the raw `.bin` bytes (#238).
///
/// The dictionary strings live exactly **once** — in `data` (borrowed `'static`
/// from the embedded `.rodata` table, or owned from a filesystem read). The
/// lookup indices below hold only `(offset, len)` spans into `data`, so no
/// skeleton or form is duplicated on the heap. Resident cost is the file size
/// plus the fixed-size index vectors, replacing the former nested
/// `HashMap<String, …>` that copied every string a second time (the 2×→1×
/// residency win). Lookup is binary search (`O(log n)`) instead of hashing
/// (`O(1)`) — an accepted trade for this opt-in context path.
pub struct ContextDict {
    /// The whole dictionary file: borrowed `'static` (embedded) or owned (fs).
    data: Cow<'static, [u8]>,
    /// Unigram entries, sorted by skeleton bytes.
    unigrams: Vec<UniEntry>,
    /// Bigram previous-word groups, sorted by `prev` bytes.
    bi_groups: Vec<BiGroup>,
    /// Bigram entries, partitioned by `BiGroup` range and sorted by `curr` within each.
    bi_entries: Vec<BiEntry>,
}

/// Read a little-endian u16 at `pos`, returning an error rather than panicking
/// if the slice is too short. (`forbid(unsafe_code)` is in force, so an OOB
/// index would panic and abort the process — these helpers turn a malformed or
/// truncated dictionary into a recoverable `Err`.)
fn read_u16(data: &[u8], pos: usize) -> Result<u16, String> {
    let end = pos.checked_add(2).ok_or("dictionary offset overflow")?;
    let slice = data
        .get(pos..end)
        .ok_or("unexpected end of dictionary data")?;
    Ok(u16::from_le_bytes(
        slice.try_into().unwrap(), // infallible: slice is exactly 2 bytes (bounds-checked above)
    ))
}

/// Read a little-endian u32 at `pos`, bounds-checked (see [`read_u16`]).
fn read_u32(data: &[u8], pos: usize) -> Result<u32, String> {
    let end = pos.checked_add(4).ok_or("dictionary offset overflow")?;
    let slice = data
        .get(pos..end)
        .ok_or("unexpected end of dictionary data")?;
    Ok(u32::from_le_bytes(
        slice.try_into().unwrap(), // infallible: slice is exactly 4 bytes (bounds-checked above)
    ))
}

/// Validate that `data[pos..pos + len]` is in bounds and valid UTF-8, returning
/// its span (offset + length) — no allocation. Bounds-checked like [`read_u16`];
/// errors (never panics) on a truncated or non-UTF-8 region. The span's bytes
/// stay valid for the lifetime of `data`, which the [`ContextDict`] owns.
fn read_str_span(data: &[u8], pos: usize, len: usize) -> Result<Span, String> {
    let end = pos.checked_add(len).ok_or("dictionary offset overflow")?;
    let slice = data
        .get(pos..end)
        .ok_or("unexpected end of dictionary data")?;
    std::str::from_utf8(slice).map_err(|e| e.to_string())?;
    Ok(Span {
        off: u32::try_from(pos).map_err(|_| "dictionary offset exceeds u32".to_string())?,
        len: u32::try_from(len).map_err(|_| "string length exceeds u32".to_string())?,
    })
}

impl ContextDict {
    /// Load a context dictionary from a borrowed buffer, copying it once into an
    /// owned backing store. Used by tests and any caller without `'static` data;
    /// the dictionary strings still live exactly once (inside the copy).
    ///
    /// Every read is bounds-checked: a truncated or malformed buffer yields an
    /// `Err` instead of an out-of-bounds panic.
    // Exercised by the unit tests; the runtime loaders use `from_owned`/`from_static`.
    #[cfg_attr(not(test), allow(dead_code))]
    pub fn from_bytes(data: &[u8]) -> Result<Self, String> {
        Self::build(Cow::Owned(data.to_vec()))
    }

    /// Load a context dictionary directly from `'static` bytes (the embedded
    /// `.rodata` table). True zero-copy — the bytes are borrowed, never copied.
    // Only the `embed-dicts` loader calls this; allowed-unused otherwise.
    #[cfg_attr(not(feature = "embed-dicts"), allow(dead_code))]
    pub fn from_static(data: &'static [u8]) -> Result<Self, String> {
        Self::build(Cow::Borrowed(data))
    }

    /// Load a context dictionary taking ownership of a buffer (e.g. a filesystem
    /// read), reusing it as the backing store without an extra copy.
    pub fn from_owned(data: Vec<u8>) -> Result<Self, String> {
        Self::build(Cow::Owned(data))
    }

    /// Build the zero-copy index over `data` (#238): parse the binary format
    /// produced by `scripts/build_*_dict.py` once, recording `(offset, len)`
    /// spans into `data` rather than copying strings onto the heap. The index
    /// vectors are sorted so `resolve` can binary-search them.
    fn build(data: Cow<'static, [u8]>) -> Result<Self, String> {
        // A bigram record before grouping: parsed flat, then sorted into groups.
        struct RawBi {
            prev: Span,
            curr: Span,
            form: Span,
        }

        let bytes: &[u8] = &data;
        if bytes.len() < 24 {
            return Err("Dictionary too small".into());
        }
        if &bytes[0..4] != MAGIC {
            return Err("Invalid dictionary magic".into());
        }
        let version = read_u32(bytes, 4)?;
        if version != 1 {
            return Err(format!("Unsupported dictionary version: {version}"));
        }
        let unigram_count = read_u32(bytes, 8)? as usize;
        let bigram_count = read_u32(bytes, 12)? as usize;
        let unigram_offset = read_u32(bytes, 16)? as usize;
        let bigram_offset = read_u32(bytes, 20)? as usize;
        // Section offsets must point past the 24-byte header. Reads are already
        // bounds-checked (no panic), but rejecting offsets that start inside the
        // header avoids silently returning Ok(...) for a clearly malformed
        // buffer whose sections would overlap the header fields.
        if unigram_offset < 24 || bigram_offset < 24 {
            return Err("Dictionary section offset overlaps header".into());
        }

        // Borrow the span's bytes for ordering comparisons. Spans are produced by
        // `read_str_span` against this same `bytes`, so the range is always valid.
        let span_bytes = |s: Span| &bytes[s.off as usize..s.off as usize + s.len as usize];

        // --- Unigrams: skeleton -> best (first, most-frequent) form span ---
        // `min(MAX_DICT_ENTRIES)` clamps only the *pre-reservation* (#116/#200) so a
        // bogus huge `unigram_count` header cannot drive a giant up-front alloc; it
        // is NOT an entry cap — a genuine dict with more entries still grows past it
        // as the loop pushes, bounded by the actual buffer bytes each entry consumes.
        let mut unigrams: Vec<UniEntry> = Vec::with_capacity(unigram_count.min(MAX_DICT_ENTRIES));
        let mut pos = unigram_offset;
        for _ in 0..unigram_count {
            let skel_len = read_u16(bytes, pos)? as usize;
            pos += 2;
            let skel = read_str_span(bytes, pos, skel_len)?;
            pos += skel_len;

            let num_forms = read_u16(bytes, pos)? as usize;
            pos += 2;

            let mut best: Option<Span> = None;
            for i in 0..num_forms {
                let form_len = read_u16(bytes, pos)? as usize;
                pos += 2;
                let form = read_str_span(bytes, pos, form_len)?;
                pos += form_len;
                let _freq = read_u32(bytes, pos)?;
                pos += 4;
                // Forms are stored most-frequent-first, and `resolve` only ever
                // wants the best one, so keep just the first and skip the rest.
                if i == 0 {
                    best = Some(form);
                }
            }
            // A unigram with zero forms yields nothing resolvable — omit it.
            if let Some(form) = best {
                unigrams.push(UniEntry { skel, form });
            }
        }

        // --- Bigrams: flat (prev, curr, form), parsed then sorted and grouped ---
        // As above (C6): the clamp bounds the pre-reservation only, not the entry
        // count; growth past it is bounded by the buffer bytes.
        let mut raw: Vec<RawBi> = Vec::with_capacity(bigram_count.min(MAX_DICT_ENTRIES));
        pos = bigram_offset;
        for _ in 0..bigram_count {
            let prev_len = read_u16(bytes, pos)? as usize;
            pos += 2;
            let prev = read_str_span(bytes, pos, prev_len)?;
            pos += prev_len;

            let curr_len = read_u16(bytes, pos)? as usize;
            pos += 2;
            let curr = read_str_span(bytes, pos, curr_len)?;
            pos += curr_len;

            let form_len = read_u16(bytes, pos)? as usize;
            pos += 2;
            let form = read_str_span(bytes, pos, form_len)?;
            pos += form_len;

            raw.push(RawBi { prev, curr, form });
        }

        // Sort unigrams by skeleton bytes (UTF-8 byte order == code-point order,
        // so byte comparison is a valid total order for binary search). Dedup any
        // duplicate skeletons — the builders emit unique keys, so this only makes
        // a malformed dict deterministic rather than changing real behaviour.
        unigrams.sort_by(|a, b| span_bytes(a.skel).cmp(span_bytes(b.skel)));
        unigrams.dedup_by(|a, b| span_bytes(a.skel) == span_bytes(b.skel));

        // Sort bigrams by (prev, curr) bytes, then partition into prev-groups.
        raw.sort_by(|a, b| {
            span_bytes(a.prev)
                .cmp(span_bytes(b.prev))
                .then_with(|| span_bytes(a.curr).cmp(span_bytes(b.curr)))
        });
        raw.dedup_by(|a, b| {
            span_bytes(a.prev) == span_bytes(b.prev) && span_bytes(a.curr) == span_bytes(b.curr)
        });

        let mut bi_entries: Vec<BiEntry> = Vec::with_capacity(raw.len());
        let mut bi_groups: Vec<BiGroup> = Vec::new();
        let mut i = 0usize;
        while i < raw.len() {
            let prev = raw[i].prev;
            let start = bi_entries.len();
            let mut j = i;
            while j < raw.len() && span_bytes(raw[j].prev) == span_bytes(prev) {
                bi_entries.push(BiEntry {
                    curr: raw[j].curr,
                    form: raw[j].form,
                });
                j += 1;
            }
            bi_groups.push(BiGroup {
                prev,
                start: u32::try_from(start).map_err(|_| "bigram index exceeds u32".to_string())?,
                len: u32::try_from(bi_entries.len() - start)
                    .map_err(|_| "bigram group exceeds u32".to_string())?,
            });
            i = j;
        }

        Ok(ContextDict {
            data,
            unigrams,
            bi_groups,
            bi_entries,
        })
    }

    /// Bytes of a span. Spans are bounds-validated at build time against this
    /// same `data`, which is immutable thereafter, so the index never panics.
    #[inline]
    fn span_slice(&self, span: Span) -> &[u8] {
        &self.data[span.off as usize..span.off as usize + span.len as usize]
    }

    /// The span as `&str`. UTF-8 was validated at build time; re-validate cheaply
    /// and fall back to `""` rather than risk a panic if that invariant is ever
    /// broken by a future change.
    #[inline]
    fn span_str(&self, span: Span) -> &str {
        std::str::from_utf8(self.span_slice(span)).unwrap_or("")
    }

    /// Resolve a word using bigram context, then unigram fallback.
    ///
    /// Returns the best diacritized form, or `None` if not in the dictionary.
    /// Comparisons are on raw bytes (UTF-8 byte order matches the sort order), so
    /// the binary searches never re-validate UTF-8; only the matched form is
    /// decoded to `&str` once, on the way out.
    pub fn resolve(&self, prev_skeleton: Option<&str>, curr_skeleton: &str) -> Option<&str> {
        let curr = curr_skeleton.as_bytes();

        // Tier 1: bigram lookup — two-step prev -> curr, both borrowed &str keys,
        // no per-token owned-key allocation (#238 guardrail preserved).
        if let Some(prev) = prev_skeleton {
            let prev_bytes = prev.as_bytes();
            if let Ok(gi) = self
                .bi_groups
                .binary_search_by(|g| self.span_slice(g.prev).cmp(prev_bytes))
            {
                let g = self.bi_groups[gi];
                let entries = &self.bi_entries[g.start as usize..(g.start + g.len) as usize];
                if let Ok(ei) = entries.binary_search_by(|e| self.span_slice(e.curr).cmp(curr)) {
                    return Some(self.span_str(entries[ei].form));
                }
            }
        }

        // Tier 2: unigram lookup (most frequent form).
        if let Ok(ui) = self
            .unigrams
            .binary_search_by(|e| self.span_slice(e.skel).cmp(curr))
        {
            return Some(self.span_str(self.unigrams[ui].form));
        }

        // Tier 3: not in dictionary — caller uses context-free transliteration.
        None
    }

    /// Return dictionary statistics: (unigram count, total bigram entry count).
    // Used by the unit tests to assert dictionary parsing.
    #[cfg_attr(not(test), allow(dead_code))]
    pub fn stats(&self) -> (usize, usize) {
        (self.unigrams.len(), self.bi_entries.len())
    }
}

/// Strip Arabic diacritics (tashkeel) and tatweel from a word.
pub fn strip_arabic_diacritics(word: &str) -> String {
    word.chars()
        .filter(|&c| !is_arabic_diacritic(c) && c != TATWEEL)
        .collect()
}

/// Strip Hebrew niqqud (vowel points) from a word.
pub fn strip_hebrew_niqqud(word: &str) -> String {
    word.chars().filter(|&c| !is_hebrew_niqqud(c)).collect()
}

/// Strip diacritics appropriate for the given language.
pub fn strip_diacritics(word: &str, lang: Option<&str>) -> String {
    match lang {
        Some("he") => strip_hebrew_niqqud(word),
        _ => strip_arabic_diacritics(word), // Arabic and Persian use same diacritics
    }
}

/// Check if a character is Arabic script.
fn is_arabic_char(c: char) -> bool {
    matches!(c as u32,
        0x0600..=0x06FF |
        0x0750..=0x077F |
        0x08A0..=0x08FF |
        0xFB50..=0xFDFF |
        0xFE70..=0xFEFF
    )
}

/// Check if a character is Hebrew script.
fn is_hebrew_char(c: char) -> bool {
    matches!(c as u32, 0x0590..=0x05FF | 0xFB1D..=0xFB4F)
}

/// True if `c` is an Arabic diacritic (tashkeel): U+064B–U+0655 plus U+0670
/// (SUPERSCRIPT ALEF). O(1) range check rather than a linear scan (#108/#200).
#[inline]
fn is_arabic_diacritic(c: char) -> bool {
    matches!(c as u32, 0x064B..=0x0655 | 0x0670)
}

/// True if `c` is Hebrew niqqud (vowel point): U+05B0–U+05C5 minus U+05BE
/// (MAQAF), U+05C0 (PASEQ), and U+05C3 (SOF PASUQ). O(1) range check (#108/#200).
#[inline]
fn is_hebrew_niqqud(c: char) -> bool {
    matches!(c as u32, 0x05B0..=0x05C5) && !matches!(c as u32, 0x05BE | 0x05C0 | 0x05C3)
}

/// Tokenize text into words and non-word spans (whitespace, punctuation).
pub fn tokenize(text: &str) -> Vec<Token<'_>> {
    // #115: each token is a contiguous run of same-class characters, so it is a
    // borrowed slice of the input — no per-token String allocation. We track the
    // current run's start byte offset and emit `Cow::Borrowed(&text[start..i])`
    // when the class flips.
    #[inline]
    fn is_word_char(c: char) -> bool {
        // #108: O(1) codepoint range/mask checks (not O(N) slice scans). The
        // diacritic/niqqud predicates are shared with the strip_* functions so
        // the ranges have a single definition (#200).
        is_arabic_char(c)
            || is_hebrew_char(c)
            || is_arabic_diacritic(c)
            || is_hebrew_niqqud(c)
            || c == TATWEEL
    }

    let mut tokens = Vec::new();
    let mut span_start = 0usize;
    let mut in_word = false;
    let mut started = false;

    for (i, c) in text.char_indices() {
        let word = is_word_char(c);
        if !started {
            span_start = i;
            in_word = word;
            started = true;
        } else if word != in_word {
            // Class flip — emit the completed run [span_start..i) as a borrowed slice.
            tokens.push(Token {
                text: Cow::Borrowed(&text[span_start..i]),
                is_word: in_word,
            });
            span_start = i;
            in_word = word;
        }
    }

    if started {
        tokens.push(Token {
            text: Cow::Borrowed(&text[span_start..]),
            is_word: in_word,
        });
    }

    tokens
}

/// A token from Arabic/Hebrew text tokenization.
///
/// `text` is a `Cow<str>`: [`tokenize`] always returns `Cow::Borrowed` slices of
/// the input (#115) — tokenization never rewrites characters, so it allocates
/// nothing per token — but the type also lets callers construct or transform a
/// `Token` holding `Cow::Owned` text when needed.
#[derive(Debug, Clone)]
pub struct Token<'a> {
    /// The token text — a word or whitespace/punctuation span. Borrowed from the
    /// input by [`tokenize`]; may be owned if a caller constructs the token.
    pub text: Cow<'a, str>,
    /// True if this token is a word (Arabic/Hebrew script), false for non-word spans.
    pub is_word: bool,
}

/// A "hard" boundary that resets bigram context (#101): newlines and
/// sentence-final punctuation. A plain inter-word space is deliberately *not* a
/// boundary, so the bigram disambiguation tier fires across adjacent words.
fn is_context_boundary(text: &str) -> bool {
    text.chars().any(|c| {
        matches!(c, '\n' | '\r' | '.' | '!' | '?') || matches!(c as u32, 0x061F | 0x06D4)
        // ؟ Arabic question mark, ۔ Arabic full stop
    })
}

/// Context-aware transliteration: resolve words via dictionary, then
/// transliterate the diacritized forms using the existing engine.
pub fn transliterate_context(
    text: &str,
    lang: Option<&str>,
    dict: &ContextDict,
    transliterate_fn: impl Fn(&str, Option<&str>) -> String,
) -> String {
    let tokens = tokenize(text);
    let mut result = String::with_capacity(text.len());
    let mut prev_skeleton: Option<String> = None;

    for token in &tokens {
        if !token.is_word {
            // Non-word (whitespace, punctuation) — pass through.
            result.push_str(&token.text);
            // #101: a plain inter-word space must NOT clear bigram context, or
            // the bigram disambiguation tier is unreachable in normal
            // (space-separated) prose. Only a hard boundary — a newline or
            // sentence-final punctuation — resets the previous-word context.
            if is_context_boundary(&token.text) {
                prev_skeleton = None;
            }
            continue;
        }

        let skeleton = strip_diacritics(&token.text, lang);

        // Try dictionary resolution (bigram → unigram → fallback)
        let resolved = dict.resolve(prev_skeleton.as_deref(), &skeleton);

        match resolved {
            Some(diacritized) => {
                // Dictionary found a diacritized form — transliterate it
                result.push_str(&transliterate_fn(diacritized, lang));
            }
            None => {
                // Not in dictionary — use context-free transliteration on original
                result.push_str(&transliterate_fn(&token.text, lang));
            }
        }

        prev_skeleton = Some(skeleton);
    }

    result
}

// ---------------------------------------------------------------------------
// Global dictionary singletons (loaded lazily)
// ---------------------------------------------------------------------------

/// Outcome of a dictionary load attempt. (#107)
///
/// Distinguished so that `_transliterate_context` can surface a "corrupt"
/// error message that differs from the "not found / run bootstrap_dicts.sh"
/// message — a corrupt dict requires a different remediation than an absent one.
pub enum DictState {
    /// Dictionary loaded successfully.
    Ok(ContextDict),
    /// No dictionary file was found in any search path.
    Absent,
    /// A file was found but could not be parsed; includes the error message.
    Corrupt(String),
}

static ARABIC_DICT: OnceLock<DictState> = OnceLock::new();
static PERSIAN_DICT: OnceLock<DictState> = OnceLock::new();
static HEBREW_DICT: OnceLock<DictState> = OnceLock::new();

// With embed-dicts, dictionaries are compiled into the binary.
// Without it, they're loaded from the filesystem at runtime.
#[cfg(feature = "embed-dicts")]
static ARABIC_DATA: &[u8] = include_bytes!("../data/arabic_dict.bin");
#[cfg(feature = "embed-dicts")]
static PERSIAN_DATA: &[u8] = include_bytes!("../data/persian_dict.bin");
#[cfg(feature = "embed-dicts")]
static HEBREW_DATA: &[u8] = include_bytes!("../data/hebrew_dict.bin");

/// Parse an embedded dictionary. (#107: returns `DictState` to distinguish
/// parse errors from absence; #106: routes diagnostics through `emit_warning_stderr`.)
#[cfg(feature = "embed-dicts")]
fn load_embedded_dict(name: &str, data: &'static [u8]) -> DictState {
    // Zero-copy: borrow the embedded `.rodata` bytes directly (#238).
    match ContextDict::from_static(data) {
        Ok(dict) => DictState::Ok(dict),
        Err(e) => {
            let msg = format!("disarm: failed to load embedded {name} dict: {e}");
            // #106: route through shared helper so Python applications can capture
            // this diagnostic via warnings/logging.
            crate::emit_warning_stderr(&msg);
            DictState::Corrupt(e)
        }
    }
}

/// Candidate filesystem locations for a context dictionary, in priority order.
///
/// Security (#61): dictionaries are **never** loaded from a current-working-
/// directory-relative path. A process whose CWD an attacker can influence — or
/// where an attacker can drop `./data/` — could otherwise inject an
/// attacker-controlled dictionary and silently change transliteration output.
/// Both returned paths are absolute and not attacker-influenceable:
///
/// 1. `$DISARM_DICT_DIR/{name}_dict.bin` — explicit opt-in for installed
///    wheels. Build the dictionaries with `scripts/bootstrap_dicts.sh` and
///    point `DISARM_DICT_DIR` at the output directory. **A relative
///    `DISARM_DICT_DIR` is rejected** (warn + ignore): a relative value would
///    reintroduce exactly the CWD-relative dictionary loading #61 removed, just
///    via the env var. The directory must be an absolute path.
/// 2. `$CARGO_MANIFEST_DIR/data/{name}_dict.bin` — source/development builds
///    only; a compile-time absolute path baked into the binary.
#[cfg(not(feature = "embed-dicts"))]
fn dict_search_paths(name: &str) -> Vec<std::path::PathBuf> {
    let mut paths: Vec<std::path::PathBuf> = Vec::new();
    if let Some(dir) = std::env::var_os("DISARM_DICT_DIR") {
        let dir = std::path::Path::new(&dir);
        if dir.is_absolute() {
            paths.push(dir.join(format!("{name}_dict.bin")));
        } else {
            // #106: route through shared helper so Python applications can capture
            // this diagnostic via warnings/logging rather than having it go directly
            // to stderr, invisible to Python's warnings module.
            crate::emit_warning_stderr(&format!(
                "disarm: ignoring relative DISARM_DICT_DIR={:?}; an absolute path is \
                 required (security #61: no CWD-relative dictionary loading).",
                dir.display()
            ));
        }
    }
    paths.push(std::path::PathBuf::from(format!(
        "{}/data/{name}_dict.bin",
        env!("CARGO_MANIFEST_DIR")
    )));
    paths
}

/// Load a context dictionary from the first existing [`dict_search_paths`]
/// location. (#107: returns `DictState` to distinguish "file absent" from
/// "file present but corrupt"; #106: routes diagnostics through `emit_warning_stderr`.)
#[cfg(not(feature = "embed-dicts"))]
fn load_dict_from_fs(name: &str) -> DictState {
    let paths = dict_search_paths(name);
    for path in &paths {
        if let Ok(data) = std::fs::read(path) {
            // Reuse the read buffer as the backing store — no extra copy (#238).
            match ContextDict::from_owned(data) {
                Ok(dict) => return DictState::Ok(dict),
                Err(e) => {
                    // File exists but is malformed — a distinct error from "not found".
                    // #106: route through shared helper so Python applications can capture
                    // this diagnostic via warnings/logging.
                    crate::emit_warning_stderr(&format!(
                        "disarm: failed to load {name} dict from {}: {e}",
                        path.display()
                    ));
                    return DictState::Corrupt(format!(
                        "{name} dictionary at {} is corrupt: {e}",
                        path.display()
                    ));
                }
            }
        }
    }
    DictState::Absent
}

/// Try to load the Arabic context dictionary.
///
/// Returns:
/// - `Ok(Some(dict))` — loaded successfully
/// - `Ok(None)` — no dictionary file found (run `bootstrap_dicts.sh`)
/// - `Err(msg)` — file found but corrupt (#107)
pub fn get_arabic_dict() -> Result<Option<&'static ContextDict>, &'static str> {
    match ARABIC_DICT.get_or_init(|| {
        #[cfg(feature = "embed-dicts")]
        {
            load_embedded_dict("arabic", ARABIC_DATA)
        }
        #[cfg(not(feature = "embed-dicts"))]
        {
            load_dict_from_fs("arabic")
        }
    }) {
        DictState::Ok(d) => Ok(Some(d)),
        DictState::Absent => Ok(None),
        DictState::Corrupt(msg) => Err(msg.as_str()),
    }
}

/// Try to load the Persian context dictionary.
///
/// Returns:
/// - `Ok(Some(dict))` — loaded successfully
/// - `Ok(None)` — no dictionary file found (run `bootstrap_dicts.sh`)
/// - `Err(msg)` — file found but corrupt (#107)
pub fn get_persian_dict() -> Result<Option<&'static ContextDict>, &'static str> {
    match PERSIAN_DICT.get_or_init(|| {
        #[cfg(feature = "embed-dicts")]
        {
            load_embedded_dict("persian", PERSIAN_DATA)
        }
        #[cfg(not(feature = "embed-dicts"))]
        {
            load_dict_from_fs("persian")
        }
    }) {
        DictState::Ok(d) => Ok(Some(d)),
        DictState::Absent => Ok(None),
        DictState::Corrupt(msg) => Err(msg.as_str()),
    }
}

/// Try to load the Hebrew context dictionary.
///
/// Returns:
/// - `Ok(Some(dict))` — loaded successfully
/// - `Ok(None)` — no dictionary file found (run `bootstrap_dicts.sh`)
/// - `Err(msg)` — file found but corrupt (#107)
pub fn get_hebrew_dict() -> Result<Option<&'static ContextDict>, &'static str> {
    match HEBREW_DICT.get_or_init(|| {
        #[cfg(feature = "embed-dicts")]
        {
            load_embedded_dict("hebrew", HEBREW_DATA)
        }
        #[cfg(not(feature = "embed-dicts"))]
        {
            load_dict_from_fs("hebrew")
        }
    }) {
        DictState::Ok(d) => Ok(Some(d)),
        DictState::Absent => Ok(None),
        DictState::Corrupt(msg) => Err(msg.as_str()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_strip_arabic_diacritics() {
        // كَتَبَ (kataba) → كتب (ktb)
        assert_eq!(strip_arabic_diacritics("كَتَبَ"), "كتب");
        // درَّسَ (darrasa, with shadda) → درس
        assert_eq!(strip_arabic_diacritics("دَرَّسَ"), "درس");
    }

    #[test]
    fn test_strip_hebrew_niqqud() {
        // שָׁלוֹם (shalom with niqqud) → שלום
        assert_eq!(strip_hebrew_niqqud("שָׁלוֹם"), "שלום");
    }

    #[test]
    fn test_strip_tatweel() {
        assert_eq!(strip_arabic_diacritics("كـتـاب"), "كتاب");
    }

    #[test]
    fn test_tokenize_arabic() {
        let tokens = tokenize("كتب العربية");
        assert_eq!(tokens.len(), 3); // word, space, word
        assert!(tokens[0].is_word);
        assert!(!tokens[1].is_word);
        assert!(tokens[2].is_word);
    }

    #[test]
    fn test_tokenize_mixed() {
        let tokens = tokenize("hello كتب world");
        // "hello " is non-word, "كتب" is word, " world" is non-word
        assert!(tokens.len() >= 3);
    }

    /// Serialize unigrams (`skeleton -> [(form, freq)]`) and bigrams
    /// (`(prev, curr, form)`) into the on-disk binary format, exercising the real
    /// `from_bytes` zero-copy build path (#238) instead of constructing the
    /// private index directly.
    fn build_dict_bytes(
        unigrams: &[(&str, &[(&str, u32)])],
        bigrams: &[(&str, &str, &str)],
    ) -> Vec<u8> {
        let mut uni = Vec::new();
        for (skel, forms) in unigrams {
            uni.extend_from_slice(&(skel.len() as u16).to_le_bytes());
            uni.extend_from_slice(skel.as_bytes());
            uni.extend_from_slice(&(forms.len() as u16).to_le_bytes());
            for (form, freq) in *forms {
                uni.extend_from_slice(&(form.len() as u16).to_le_bytes());
                uni.extend_from_slice(form.as_bytes());
                uni.extend_from_slice(&freq.to_le_bytes());
            }
        }
        let mut bi = Vec::new();
        for (prev, curr, form) in bigrams {
            bi.extend_from_slice(&(prev.len() as u16).to_le_bytes());
            bi.extend_from_slice(prev.as_bytes());
            bi.extend_from_slice(&(curr.len() as u16).to_le_bytes());
            bi.extend_from_slice(curr.as_bytes());
            bi.extend_from_slice(&(form.len() as u16).to_le_bytes());
            bi.extend_from_slice(form.as_bytes());
        }
        let unigram_offset = 24u32;
        let bigram_offset = 24 + uni.len() as u32;
        let mut data = Vec::new();
        data.extend_from_slice(MAGIC);
        data.extend_from_slice(&1u32.to_le_bytes()); // version
        data.extend_from_slice(&(unigrams.len() as u32).to_le_bytes());
        data.extend_from_slice(&(bigrams.len() as u32).to_le_bytes());
        data.extend_from_slice(&unigram_offset.to_le_bytes());
        data.extend_from_slice(&bigram_offset.to_le_bytes());
        data.extend_from_slice(&uni);
        data.extend_from_slice(&bi);
        data
    }

    #[test]
    fn test_context_dict_resolve() {
        // كتب → [kataba (most frequent), kutub]; bigram (ال, كتب) → kutub.
        let bytes = build_dict_bytes(
            &[("كتب", &[("كَتَبَ", 100), ("كُتُب", 80)])],
            &[("ال", "كتب", "كُتُب")],
        );
        let dict = ContextDict::from_bytes(&bytes).expect("valid dict should parse");

        // Unigram: most frequent
        assert_eq!(dict.resolve(None, "كتب"), Some("كَتَبَ"));

        // Bigram: after "ال" → kutub
        assert_eq!(dict.resolve(Some("ال"), "كتب"), Some("كُتُب"));

        // Unknown word
        assert_eq!(dict.resolve(None, "xyz"), None);
    }

    #[test]
    fn test_bigram_fires_across_space() {
        // #101: bigram disambiguation must fire for normal space-separated prose.
        // A plain inter-word space must NOT reset the previous-word context.
        let bytes = build_dict_bytes(
            &[("كتب", &[("كَتَبَ", 100)])], // default: kataba
            &[("ال", "كتب", "كُتُب")],     // after "ال" → kutub
        );
        let dict = ContextDict::from_bytes(&bytes).expect("valid dict should parse");

        // Space between the two words: the bigram tier sees prev="ال" → kutub.
        let out = transliterate_context("ال كتب", None, &dict, |s, _| s.to_string());
        assert!(
            out.contains("كُتُب"),
            "space must preserve bigram context: {out}"
        );
        assert!(
            !out.contains("كَتَبَ"),
            "must not fall back to the unigram: {out}"
        );

        // A hard boundary (newline) between the words resets context → unigram.
        let out2 = transliterate_context("ال\nكتب", None, &dict, |s, _| s.to_string());
        assert!(
            out2.contains("كَتَبَ"),
            "newline must reset to the unigram: {out2}"
        );
    }

    #[test]
    fn test_resolve_many_entries_binary_search() {
        // #238: feed entries in NON-sorted input order across multiple skeletons
        // and multiple prev-groups, so the build must sort them and `resolve`
        // must binary-search correctly — not just hit a single-entry index.
        let bytes = build_dict_bytes(
            &[
                // skeletons deliberately out of sorted order
                ("dog", &[("DOG", 9)]),
                ("ant", &[("ANT", 7)]),
                ("cat", &[("CAT-best", 5), ("CAT-alt", 4)]),
                ("bee", &[("BEE", 3)]),
            ],
            &[
                // two prev-groups ("the", "a"), entries out of order within/among
                ("the", "dog", "the-DOG"),
                ("a", "cat", "a-CAT"),
                ("the", "ant", "the-ANT"),
                ("the", "cat", "the-CAT"),
            ],
        );
        let dict = ContextDict::from_bytes(&bytes).expect("valid dict should parse");

        // Unigram tier: every skeleton resolves to its best (first) form.
        assert_eq!(dict.resolve(None, "ant"), Some("ANT"));
        assert_eq!(dict.resolve(None, "bee"), Some("BEE"));
        assert_eq!(dict.resolve(None, "cat"), Some("CAT-best"));
        assert_eq!(dict.resolve(None, "dog"), Some("DOG"));
        assert_eq!(dict.resolve(None, "zzz"), None);

        // Bigram tier: two-step prev → curr across both groups.
        assert_eq!(dict.resolve(Some("the"), "dog"), Some("the-DOG"));
        assert_eq!(dict.resolve(Some("the"), "ant"), Some("the-ANT"));
        assert_eq!(dict.resolve(Some("the"), "cat"), Some("the-CAT"));
        assert_eq!(dict.resolve(Some("a"), "cat"), Some("a-CAT"));
        // Bigram miss falls through to the unigram form.
        assert_eq!(dict.resolve(Some("the"), "bee"), Some("BEE"));
        // Unknown prev → unigram tier.
        assert_eq!(dict.resolve(Some("nope"), "cat"), Some("CAT-best"));

        // (4 unigrams, 4 bigram entries.)
        assert_eq!(dict.stats(), (4, 4));
    }

    /// Build a minimal but valid dictionary buffer: one unigram ("ab" → [("AB", 5)])
    /// and one bigram (("ab", "cd") → "X").
    fn build_valid_dict() -> Vec<u8> {
        build_dict_bytes(&[("ab", &[("AB", 5)])], &[("ab", "cd", "X")])
    }

    #[test]
    fn test_from_bytes_valid_roundtrip() {
        let dict = ContextDict::from_bytes(&build_valid_dict()).expect("valid dict should parse");
        assert_eq!(dict.resolve(None, "ab"), Some("AB"));
        assert_eq!(dict.resolve(Some("ab"), "cd"), Some("X"));
    }

    #[test]
    fn test_from_bytes_rejects_small_and_bad_magic() {
        assert!(ContextDict::from_bytes(&[]).is_err());
        assert!(ContextDict::from_bytes(&[0u8; 10]).is_err());
        let mut bad = build_valid_dict();
        bad[0] = b'X'; // corrupt magic
        assert!(ContextDict::from_bytes(&bad).is_err());
    }

    #[test]
    fn test_from_bytes_truncation_never_panics() {
        // A truncated buffer at any prefix length must return Err, never panic
        // (regression: the parser previously indexed data[pos..pos+N] directly).
        let full = build_valid_dict();
        for n in 0..full.len() {
            let _ = ContextDict::from_bytes(&full[..n]); // must not panic
        }
        // Full buffer still parses.
        assert!(ContextDict::from_bytes(&full).is_ok());
    }

    #[test]
    fn test_from_bytes_bogus_counts_do_not_panic() {
        // Declare an absurd unigram_count with no backing data: must Err, not
        // panic or OOM via a giant capacity allocation.
        let mut data = Vec::new();
        data.extend_from_slice(MAGIC);
        data.extend_from_slice(&1u32.to_le_bytes()); // version
        data.extend_from_slice(&u32::MAX.to_le_bytes()); // unigram_count = 4 billion
        data.extend_from_slice(&0u32.to_le_bytes()); // bigram_count
        data.extend_from_slice(&24u32.to_le_bytes()); // unigram_offset
        data.extend_from_slice(&24u32.to_le_bytes()); // bigram_offset
        assert!(ContextDict::from_bytes(&data).is_err());
    }

    #[test]
    fn test_from_bytes_offset_out_of_range() {
        let mut data = build_valid_dict();
        // Point unigram_offset past the end of the buffer.
        let bad_offset = (data.len() as u32 + 100).to_le_bytes();
        data[16..20].copy_from_slice(&bad_offset);
        assert!(ContextDict::from_bytes(&data).is_err());
    }

    #[test]
    fn test_from_bytes_offset_inside_header_rejected() {
        let mut data = build_valid_dict();
        // Point unigram_offset inside the 24-byte header.
        data[16..20].copy_from_slice(&8u32.to_le_bytes());
        assert!(ContextDict::from_bytes(&data).is_err());
    }

    #[cfg(not(feature = "embed-dicts"))]
    #[test]
    fn test_dict_search_paths_never_cwd_relative() {
        // #61: dictionaries must never be loaded from a CWD-relative path, which
        // an attacker who controls the working directory could populate.
        let paths = dict_search_paths("arabic");
        // The always-present dev fallback (CARGO_MANIFEST_DIR) must be absolute.
        let manifest = paths.last().expect("at least the manifest-dir candidate");
        assert!(
            manifest.is_absolute(),
            "dev dict path must be absolute, got {manifest:?}"
        );
        // No candidate may be the bare CWD-relative form.
        let cwd_relative = std::path::Path::new("data/arabic_dict.bin");
        assert!(
            !paths.iter().any(|p| p == cwd_relative),
            "must not probe the CWD-relative data/ path; got {paths:?}"
        );
        // Stronger invariant: *every* candidate is absolute. A relative
        // DISARM_DICT_DIR is rejected at the source, so no env value can
        // smuggle in a CWD-relative candidate.
        assert!(
            paths.iter().all(|p| p.is_absolute()),
            "all dict search paths must be absolute; got {paths:?}"
        );
    }
}
