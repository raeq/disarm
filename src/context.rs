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

/// Context dictionary with unigram and bigram tables.
pub struct ContextDict {
    /// Skeleton → list of (diacritized form, frequency), sorted by frequency desc.
    unigrams: HashMap<String, Vec<(String, u32)>>,
    /// (prev_skeleton, curr_skeleton) → best diacritized form.
    bigrams: HashMap<(String, String), String>,
}

impl ContextDict {
    /// Load a context dictionary from the binary format produced by
    /// `scripts/build_arabic_dict.py`.
    pub fn from_bytes(data: &[u8]) -> Result<Self, String> {
        if data.len() < 24 {
            return Err("Dictionary too small".into());
        }
        if &data[0..4] != MAGIC {
            return Err("Invalid dictionary magic".into());
        }
        let version = u32::from_le_bytes(data[4..8].try_into().unwrap());
        if version != 1 {
            return Err(format!("Unsupported dictionary version: {version}"));
        }
        let unigram_count = u32::from_le_bytes(data[8..12].try_into().unwrap()) as usize;
        let bigram_count = u32::from_le_bytes(data[12..16].try_into().unwrap()) as usize;
        let unigram_offset = u32::from_le_bytes(data[16..20].try_into().unwrap()) as usize;
        let bigram_offset = u32::from_le_bytes(data[20..24].try_into().unwrap()) as usize;

        // Parse unigrams
        let mut unigrams = HashMap::with_capacity(unigram_count);
        let mut pos = unigram_offset;
        for _ in 0..unigram_count {
            let skel_len = u16::from_le_bytes(data[pos..pos + 2].try_into().unwrap()) as usize;
            pos += 2;
            let skeleton =
                String::from_utf8(data[pos..pos + skel_len].to_vec()).map_err(|e| e.to_string())?;
            pos += skel_len;

            let num_forms = u16::from_le_bytes(data[pos..pos + 2].try_into().unwrap()) as usize;
            pos += 2;

            let mut forms = Vec::with_capacity(num_forms);
            for _ in 0..num_forms {
                let form_len = u16::from_le_bytes(data[pos..pos + 2].try_into().unwrap()) as usize;
                pos += 2;
                let form = String::from_utf8(data[pos..pos + form_len].to_vec())
                    .map_err(|e| e.to_string())?;
                pos += form_len;
                let freq = u32::from_le_bytes(data[pos..pos + 4].try_into().unwrap());
                pos += 4;
                forms.push((form, freq));
            }
            unigrams.insert(skeleton, forms);
        }

        // Parse bigrams
        let mut bigrams = HashMap::with_capacity(bigram_count);
        pos = bigram_offset;
        for _ in 0..bigram_count {
            let prev_len = u16::from_le_bytes(data[pos..pos + 2].try_into().unwrap()) as usize;
            pos += 2;
            let prev =
                String::from_utf8(data[pos..pos + prev_len].to_vec()).map_err(|e| e.to_string())?;
            pos += prev_len;

            let curr_len = u16::from_le_bytes(data[pos..pos + 2].try_into().unwrap()) as usize;
            pos += 2;
            let curr =
                String::from_utf8(data[pos..pos + curr_len].to_vec()).map_err(|e| e.to_string())?;
            pos += curr_len;

            let form_len = u16::from_le_bytes(data[pos..pos + 2].try_into().unwrap()) as usize;
            pos += 2;
            let form =
                String::from_utf8(data[pos..pos + form_len].to_vec()).map_err(|e| e.to_string())?;
            pos += form_len;

            bigrams.insert((prev, curr), form);
        }

        Ok(ContextDict { unigrams, bigrams })
    }

    /// Resolve a word using bigram context, then unigram fallback.
    ///
    /// Returns the best diacritized form, or None if not in dictionary.
    pub fn resolve(&self, prev_skeleton: Option<&str>, curr_skeleton: &str) -> Option<&str> {
        // Tier 1: bigram lookup
        if let Some(prev) = prev_skeleton {
            if let Some(form) = self
                .bigrams
                .get(&(prev.to_owned(), curr_skeleton.to_owned()))
            {
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

    /// Return dictionary statistics.
    pub fn stats(&self) -> (usize, usize) {
        (self.unigrams.len(), self.bigrams.len())
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
        let is_word_char = is_arabic_char(c)
            || is_hebrew_char(c)
            || ARABIC_DIACRITICS.contains(&c)
            || HEBREW_NIQQUD.contains(&c)
            || c == TATWEEL;

        if is_word_char {
            if !in_word && !current.is_empty() {
                tokens.push(Token {
                    text: current.clone(),
                    is_word: false,
                });
                current.clear();
            }
            in_word = true;
            current.push(c);
        } else {
            if in_word && !current.is_empty() {
                tokens.push(Token {
                    text: current.clone(),
                    is_word: true,
                });
                current.clear();
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
    pub text: String,
    pub is_word: bool,
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
            // Non-word (whitespace, punctuation) — pass through
            result.push_str(&token.text);
            prev_skeleton = None;
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

static ARABIC_DICT: OnceLock<Option<ContextDict>> = OnceLock::new();
static HEBREW_DICT: OnceLock<Option<ContextDict>> = OnceLock::new();

/// Try to load the Arabic context dictionary from the package data directory.
///
/// Returns None if the dictionary file is not found (not installed).
pub fn get_arabic_dict() -> Option<&'static ContextDict> {
    ARABIC_DICT
        .get_or_init(|| {
            // Look for dictionary in standard locations
            let paths = [
                // Relative to executable (development)
                std::path::PathBuf::from("data/arabic_dict.bin"),
                // Package data directory
                std::path::PathBuf::from(concat!(
                    env!("CARGO_MANIFEST_DIR"),
                    "/data/arabic_dict.bin"
                )),
            ];
            for path in &paths {
                if let Ok(data) = std::fs::read(path) {
                    match ContextDict::from_bytes(&data) {
                        Ok(dict) => return Some(dict),
                        Err(e) => {
                            eprintln!("Warning: failed to load Arabic dict: {e}");
                            return None;
                        }
                    }
                }
            }
            None
        })
        .as_ref()
}

/// Try to load the Hebrew context dictionary.
pub fn get_hebrew_dict() -> Option<&'static ContextDict> {
    HEBREW_DICT
        .get_or_init(|| {
            let paths = [
                std::path::PathBuf::from("data/hebrew_dict.bin"),
                std::path::PathBuf::from(concat!(
                    env!("CARGO_MANIFEST_DIR"),
                    "/data/hebrew_dict.bin"
                )),
            ];
            for path in &paths {
                if let Ok(data) = std::fs::read(path) {
                    match ContextDict::from_bytes(&data) {
                        Ok(dict) => return Some(dict),
                        Err(e) => {
                            eprintln!("Warning: failed to load Hebrew dict: {e}");
                            return None;
                        }
                    }
                }
            }
            None
        })
        .as_ref()
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

        let mut bigrams = HashMap::new();
        bigrams.insert(
            ("ال".to_string(), "كتب".to_string()),
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
}
