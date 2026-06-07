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

use std::collections::HashMap;
use std::sync::OnceLock;

/// Arabic diacritical marks (tashkeel) to strip for skeleton extraction.
const ARABIC_DIACRITICS: &[char] = &[
    '\u{064B}', // FATHATAN
    '\u{064C}', // DAMMATAN
    '\u{064D}', // KASRATAN
    '\u{064E}', // FATHA
    '\u{064F}', // DAMMA
    '\u{0650}', // KASRA
    '\u{0651}', // SHADDA
    '\u{0652}', // SUKUN
    '\u{0653}', // MADDAH ABOVE
    '\u{0654}', // HAMZA ABOVE
    '\u{0655}', // HAMZA BELOW
    '\u{0670}', // SUPERSCRIPT ALEF
];

/// Hebrew niqqud (vowel points) to strip for skeleton extraction.
const HEBREW_NIQQUD: &[char] = &[
    '\u{05B0}', // SHEVA
    '\u{05B1}', // HATAF SEGOL
    '\u{05B2}', // HATAF PATAH
    '\u{05B3}', // HATAF QAMATS
    '\u{05B4}', // HIRIQ
    '\u{05B5}', // TSERE
    '\u{05B6}', // SEGOL
    '\u{05B7}', // PATAH
    '\u{05B8}', // QAMATS
    '\u{05B9}', // HOLAM
    '\u{05BA}', // HOLAM HASER
    '\u{05BB}', // QUBUTS
    '\u{05BC}', // DAGESH
    '\u{05BD}', // METEG
    '\u{05BF}', // RAFE
    '\u{05C1}', // SHIN DOT
    '\u{05C2}', // SIN DOT
    '\u{05C4}', // UPPER DOT
    '\u{05C5}', // LOWER DOT
];

/// Tatweel (kashida) — decorative elongation in Arabic.
const TATWEEL: char = '\u{0640}';

/// Binary dictionary format magic bytes.
const MAGIC: &[u8; 4] = b"TRLD";

/// Capacity-hint clamp for `ContextDict::from_bytes` (#116): a corrupt header
/// count must not drive a huge `HashMap` pre-allocation. Using `data.len()` as
/// the cap over-reserved buckets; 1,000,000 is a generous upper bound for any
/// real dictionary while still bounding a bogus count (e.g. `u32::MAX`).
const MAX_DICT_ENTRIES: usize = 1_000_000;

/// Context dictionary with unigram and bigram tables.
pub struct ContextDict {
    /// Skeleton → list of (diacritized form, frequency), sorted by frequency desc.
    unigrams: HashMap<String, Vec<(String, u32)>>,
    /// prev_skeleton → (curr_skeleton → best diacritized form). Nested so that
    /// `resolve` can look up with `&str` keys and avoid allocating an owned
    /// `(String, String)` tuple on every token in the hot path.
    bigrams: HashMap<String, HashMap<String, String>>,
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

/// Read a UTF-8 string of `len` bytes at `pos`, bounds-checked (see [`read_u16`]).
fn read_str(data: &[u8], pos: usize, len: usize) -> Result<String, String> {
    let end = pos.checked_add(len).ok_or("dictionary offset overflow")?;
    let slice = data
        .get(pos..end)
        .ok_or("unexpected end of dictionary data")?;
    String::from_utf8(slice.to_vec()).map_err(|e| e.to_string())
}

impl ContextDict {
    /// Load a context dictionary from the binary format produced by
    /// `scripts/build_arabic_dict.py`.
    ///
    /// Every read is bounds-checked: a truncated or malformed buffer yields an
    /// `Err` instead of an out-of-bounds panic.
    pub fn from_bytes(data: &[u8]) -> Result<Self, String> {
        if data.len() < 24 {
            return Err("Dictionary too small".into());
        }
        if &data[0..4] != MAGIC {
            return Err("Invalid dictionary magic".into());
        }
        let version = read_u32(data, 4)?;
        if version != 1 {
            return Err(format!("Unsupported dictionary version: {version}"));
        }
        let unigram_count = read_u32(data, 8)? as usize;
        let bigram_count = read_u32(data, 12)? as usize;
        let unigram_offset = read_u32(data, 16)? as usize;
        let bigram_offset = read_u32(data, 20)? as usize;
        // Section offsets must point past the 24-byte header. Reads are already
        // bounds-checked (no panic), but rejecting offsets that start inside the
        // header avoids silently returning Ok(...) for a clearly malformed
        // buffer whose sections would overlap the header fields.
        if unigram_offset < 24 || bigram_offset < 24 {
            return Err("Dictionary section offset overlaps header".into());
        }

        let mut unigrams = HashMap::with_capacity(unigram_count.min(MAX_DICT_ENTRIES));
        let mut pos = unigram_offset;
        for _ in 0..unigram_count {
            let skel_len = read_u16(data, pos)? as usize;
            pos += 2;
            let skeleton = read_str(data, pos, skel_len)?;
            pos += skel_len;

            let num_forms = read_u16(data, pos)? as usize;
            pos += 2;

            let mut forms = Vec::with_capacity(num_forms.min(data.len()));
            for _ in 0..num_forms {
                let form_len = read_u16(data, pos)? as usize;
                pos += 2;
                let form = read_str(data, pos, form_len)?;
                pos += form_len;
                let freq = read_u32(data, pos)?;
                pos += 4;
                forms.push((form, freq));
            }
            unigrams.insert(skeleton, forms);
        }

        // Parse bigrams (#116: same MAX_DICT_ENTRIES cap as unigrams)
        let mut bigrams: HashMap<String, HashMap<String, String>> =
            HashMap::with_capacity(bigram_count.min(MAX_DICT_ENTRIES));
        pos = bigram_offset;
        for _ in 0..bigram_count {
            let prev_len = read_u16(data, pos)? as usize;
            pos += 2;
            let prev = read_str(data, pos, prev_len)?;
            pos += prev_len;

            let curr_len = read_u16(data, pos)? as usize;
            pos += 2;
            let curr = read_str(data, pos, curr_len)?;
            pos += curr_len;

            let form_len = read_u16(data, pos)? as usize;
            pos += 2;
            let form = read_str(data, pos, form_len)?;
            pos += form_len;

            bigrams.entry(prev).or_default().insert(curr, form);
        }

        Ok(ContextDict { unigrams, bigrams })
    }

    /// Resolve a word using bigram context, then unigram fallback.
    ///
    /// Returns the best diacritized form, or None if not in dictionary.
    pub fn resolve(&self, prev_skeleton: Option<&str>, curr_skeleton: &str) -> Option<&str> {
        // Tier 1: bigram lookup (borrowed &str keys — no per-token allocation)
        if let Some(prev) = prev_skeleton {
            if let Some(form) = self.bigrams.get(prev).and_then(|m| m.get(curr_skeleton)) {
                return Some(form.as_str());
            }
        }

        // Tier 2: unigram lookup (most frequent form)
        if let Some(forms) = self.unigrams.get(curr_skeleton) {
            if let Some((form, _)) = forms.first() {
                return Some(form.as_str());
            }
        }

        // Tier 3: not in dictionary — caller uses context-free transliteration
        None
    }

    /// Return dictionary statistics: (unigram count, total bigram count).
    pub fn stats(&self) -> (usize, usize) {
        let bigram_count = self.bigrams.values().map(HashMap::len).sum();
        (self.unigrams.len(), bigram_count)
    }
}

/// Strip Arabic diacritics (tashkeel) and tatweel from a word.
pub fn strip_arabic_diacritics(word: &str) -> String {
    word.chars()
        .filter(|&c| !ARABIC_DIACRITICS.contains(&c) && c != TATWEEL)
        .collect()
}

/// Strip Hebrew niqqud (vowel points) from a word.
pub fn strip_hebrew_niqqud(word: &str) -> String {
    word.chars()
        .filter(|&c| !HEBREW_NIQQUD.contains(&c))
        .collect()
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

/// Tokenize text into words and non-word spans (whitespace, punctuation).
pub fn tokenize(text: &str) -> Vec<Token> {
    let mut tokens = Vec::new();
    let mut current = String::new();
    let mut in_word = false;

    for c in text.chars() {
        // #108: replaced O(N) slice scans with O(1) codepoint range/mask checks.
        // Arabic diacritics are exactly U+064B–U+0655 plus U+0670 (SUPERSCRIPT ALEF).
        // Hebrew niqqud are U+05B0–U+05C5 minus U+05BE (MAQAF), U+05C0 (PASEQ), U+05C3 (SOF PASUQ).
        let is_arabic_diacritic = matches!(c as u32, 0x064B..=0x0655 | 0x0670);
        let is_hebrew_niqqud =
            matches!(c as u32, 0x05B0..=0x05C5) && !matches!(c as u32, 0x05BE | 0x05C0 | 0x05C3);
        let is_word_char = is_arabic_char(c)
            || is_hebrew_char(c)
            || is_arabic_diacritic
            || is_hebrew_niqqud
            || c == TATWEEL;

        if is_word_char {
            if !in_word && !current.is_empty() {
                // #109: mem::take moves the buffer (no clone + separate clear).
                tokens.push(Token {
                    text: std::mem::take(&mut current),
                    is_word: false,
                });
            }
            in_word = true;
            current.push(c);
        } else {
            if in_word && !current.is_empty() {
                // #109: mem::take moves the buffer (no clone + separate clear).
                tokens.push(Token {
                    text: std::mem::take(&mut current),
                    is_word: true,
                });
            }
            in_word = false;
            current.push(c);
        }
    }

    if !current.is_empty() {
        tokens.push(Token {
            text: current,
            is_word: in_word,
        });
    }

    tokens
}

/// A token from Arabic/Hebrew text tokenization.
#[derive(Debug, Clone)]
pub struct Token {
    /// The token text (a word or whitespace/punctuation span).
    pub text: String,
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
fn load_embedded_dict(name: &str, data: &[u8]) -> DictState {
    match ContextDict::from_bytes(data) {
        Ok(dict) => DictState::Ok(dict),
        Err(e) => {
            let msg = format!("translit: failed to load embedded {name} dict: {e}");
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
/// 1. `$TRANSLIT_DICT_DIR/{name}_dict.bin` — explicit opt-in for installed
///    wheels. Build the dictionaries with `scripts/bootstrap_dicts.sh` and
///    point `TRANSLIT_DICT_DIR` at the output directory. **A relative
///    `TRANSLIT_DICT_DIR` is rejected** (warn + ignore): a relative value would
///    reintroduce exactly the CWD-relative dictionary loading #61 removed, just
///    via the env var. The directory must be an absolute path.
/// 2. `$CARGO_MANIFEST_DIR/data/{name}_dict.bin` — source/development builds
///    only; a compile-time absolute path baked into the binary.
#[cfg(not(feature = "embed-dicts"))]
fn dict_search_paths(name: &str) -> Vec<std::path::PathBuf> {
    let mut paths: Vec<std::path::PathBuf> = Vec::new();
    if let Some(dir) = std::env::var_os("TRANSLIT_DICT_DIR") {
        let dir = std::path::Path::new(&dir);
        if dir.is_absolute() {
            paths.push(dir.join(format!("{name}_dict.bin")));
        } else {
            // #106: route through shared helper so Python applications can capture
            // this diagnostic via warnings/logging rather than having it go directly
            // to stderr, invisible to Python's warnings module.
            crate::emit_warning_stderr(&format!(
                "translit: ignoring relative TRANSLIT_DICT_DIR={:?}; an absolute path is \
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
            match ContextDict::from_bytes(&data) {
                Ok(dict) => return DictState::Ok(dict),
                Err(e) => {
                    // File exists but is malformed — a distinct error from "not found".
                    // #106: route through shared helper so Python applications can capture
                    // this diagnostic via warnings/logging.
                    crate::emit_warning_stderr(&format!(
                        "translit: failed to load {name} dict from {}: {e}",
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

    #[test]
    fn test_context_dict_resolve() {
        let mut unigrams = HashMap::new();
        unigrams.insert(
            "كتب".to_string(),
            vec![
                ("كَتَبَ".to_string(), 100), // kataba (most frequent)
                ("كُتُب".to_string(), 80),  // kutub
            ],
        );

        let mut bigrams: HashMap<String, HashMap<String, String>> = HashMap::new();
        bigrams.entry("ال".to_string()).or_default().insert(
            "كتب".to_string(),
            "كُتُب".to_string(), // after article → kutub (books)
        );

        let dict = ContextDict { unigrams, bigrams };

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
        let mut unigrams = HashMap::new();
        unigrams.insert("كتب".to_string(), vec![("كَتَبَ".to_string(), 100)]); // default: kataba
        let mut bigrams: HashMap<String, HashMap<String, String>> = HashMap::new();
        bigrams
            .entry("ال".to_string())
            .or_default()
            .insert("كتب".to_string(), "كُتُب".to_string()); // after "ال" → kutub
        let dict = ContextDict { unigrams, bigrams };

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

    /// Build a minimal but valid dictionary buffer: one unigram ("ab" → [("AB", 5)])
    /// and one bigram (("ab", "cd") → "X").
    fn build_valid_dict() -> Vec<u8> {
        let mut unigram_section = Vec::new();
        unigram_section.extend_from_slice(&2u16.to_le_bytes()); // skel_len
        unigram_section.extend_from_slice(b"ab");
        unigram_section.extend_from_slice(&1u16.to_le_bytes()); // num_forms
        unigram_section.extend_from_slice(&2u16.to_le_bytes()); // form_len
        unigram_section.extend_from_slice(b"AB");
        unigram_section.extend_from_slice(&5u32.to_le_bytes()); // freq

        let mut bigram_section = Vec::new();
        bigram_section.extend_from_slice(&2u16.to_le_bytes()); // prev_len
        bigram_section.extend_from_slice(b"ab");
        bigram_section.extend_from_slice(&2u16.to_le_bytes()); // curr_len
        bigram_section.extend_from_slice(b"cd");
        bigram_section.extend_from_slice(&1u16.to_le_bytes()); // form_len
        bigram_section.extend_from_slice(b"X");

        let unigram_offset = 24u32;
        let bigram_offset = 24 + unigram_section.len() as u32;

        let mut data = Vec::new();
        data.extend_from_slice(MAGIC);
        data.extend_from_slice(&1u32.to_le_bytes()); // version
        data.extend_from_slice(&1u32.to_le_bytes()); // unigram_count
        data.extend_from_slice(&1u32.to_le_bytes()); // bigram_count
        data.extend_from_slice(&unigram_offset.to_le_bytes());
        data.extend_from_slice(&bigram_offset.to_le_bytes());
        data.extend_from_slice(&unigram_section);
        data.extend_from_slice(&bigram_section);
        data
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
        // TRANSLIT_DICT_DIR is rejected at the source, so no env value can
        // smuggle in a CWD-relative candidate.
        assert!(
            paths.iter().all(|p| p.is_absolute()),
            "all dict search paths must be absolute; got {paths:?}"
        );
    }
}
