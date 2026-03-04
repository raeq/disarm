//! Unicode data tables for transliteration, confusables, emoji, and script detection.
//!
//! This module manages:
//! - Default transliteration mappings (Unicode → ASCII) via flat BMP array
//! - Language-specific transliteration overrides via PHF
//! - User-registered language profiles and replacements (runtime HashMap)
//! - TR39 confusable character mappings via PHF
//! - Emoji annotations from Unicode CLDR via PHF

pub mod case_folding_data;
mod confusables_data;
pub mod emoji_data;
mod hangul;
mod hanzi_pinyin;
mod transliteration;

use std::collections::HashMap;
use std::sync::RwLock;

use once_cell::sync::Lazy;

/// Cache for Hangul romanization results to bound the number of `Box::leak` calls.
/// There are at most 11,172 precomposed Hangul syllables plus ~51 compatibility jamo,
/// so this cache is naturally bounded.
static HANGUL_CACHE: Lazy<RwLock<HashMap<char, &'static str>>> =
    Lazy::new(|| RwLock::new(HashMap::with_capacity(256)));

/// Global user-registered language tables protected by RwLock.
/// Reads (lookups) take a read lock — zero contention.
/// Writes (registration) take a write lock — rare, only during setup.
static LANG_TABLES: Lazy<RwLock<HashMap<String, HashMap<char, String>>>> =
    Lazy::new(|| RwLock::new(HashMap::new()));

/// Cache for user-registered language table lookups.  Without this cache,
/// every call to `lookup_lang` for a user-registered mapping would
/// `Box::leak` a fresh clone — an unbounded memory leak for long-running
/// servers that call `transliterate(lang=...)` in a loop.
///
/// Two-level structure: lang_code → (char → leaked &'static str).
/// The outer HashMap is keyed by String so lookups can borrow via `&str`
/// without allocating on the read path.
/// Invalidated on `register_lang` calls by removing the language entry.
static LANG_LEAK_CACHE: Lazy<RwLock<HashMap<String, HashMap<char, &'static str>>>> =
    Lazy::new(|| RwLock::new(HashMap::new()));

static GLOBAL_REPLACEMENTS: Lazy<RwLock<HashMap<String, String>>> =
    Lazy::new(|| RwLock::new(HashMap::new()));

/// All built-in language codes, sorted.
const BUILTIN_LANGS: &[&str] = &[
    "ar", "bg", "ca", "cs", "cy", "da", "de", "el", "es", "et", "fi", "fr", "ga", "hr", "hu", "is",
    "it", "ja", "ko", "lt", "lv", "mt", "nl", "no", "pl", "pt", "ro", "ru", "sk", "sl", "sq", "sr",
    "sv", "tr", "uk", "vi", "zh",
];

/// Look up a character in the default transliteration table.
///
/// Dispatches by codepoint range to avoid unnecessary table probes:
/// - CJK Unified Ideographs → Hanzi pinyin table directly
/// - Hangul syllables / jamo → algorithmic romanization directly
/// - Everything else → main PHF transliteration table
#[inline]
pub fn lookup_default(ch: char) -> Option<&'static str> {
    let cp = ch as u32;

    // CJK Unified Ideographs (U+3400–U+9FFF, U+F900–U+FAFF)
    if (0x3400..=0x9FFF).contains(&cp) || (0xF900..=0xFAFF).contains(&cp) {
        return hanzi_pinyin::lookup_hanzi(ch).or_else(|| transliteration::lookup(ch));
    }

    // Hangul Syllables (U+AC00–U+D7AF) and Compatibility Jamo (U+3131–U+3163)
    if (0xAC00..=0xD7AF).contains(&cp) || (0x3131..=0x3163).contains(&cp) {
        return lookup_hangul_static(ch).or_else(|| transliteration::lookup(ch));
    }

    // Default flat BMP array (Latin Extended, Cyrillic, Greek, symbols, etc.)
    transliteration::lookup(ch)
}

/// Hangul romanization returns an owned String (algorithmically composed),
/// so we leak it to get a `&'static str` for the lookup API.
///
/// Uses a cache to ensure each character is leaked at most once.
/// The cache is bounded by the Unicode Hangul syllable range (~11,172 entries).
fn lookup_hangul_static(ch: char) -> Option<&'static str> {
    // Fast path: check read lock first
    if let Ok(cache) = HANGUL_CACHE.read() {
        if let Some(&cached) = cache.get(&ch) {
            return Some(cached);
        }
    }

    // Slow path: compute, leak, and cache
    hangul::romanize_hangul(ch).map(|s| {
        let leaked: &'static str = Box::leak(s.into_boxed_str());
        if let Ok(mut cache) = HANGUL_CACHE.write() {
            cache.insert(ch, leaked);
        }
        leaked
    })
}

/// Look up a character in the ISO 9:1995 scholarly table (O(1) PHF).
/// Returns None if ISO 9 has no override for this character, in which
/// case the caller should fall through to the default table.
#[inline]
pub fn lookup_iso9(ch: char) -> Option<&'static str> {
    transliteration::lookup_iso9(ch)
}

/// Look up a character in a language-specific table.
/// Checks built-in PHF maps first, then user-registered runtime tables.
/// Returns None if no override exists for this language + character,
/// in which case the caller should fall through to the default table.
pub fn lookup_lang(lang: &str, ch: char) -> Option<&'static str> {
    // Check built-in PHF language maps first (O(1) per map)
    if let Some(result) = transliteration::lookup_lang(lang, ch) {
        return Some(result);
    }

    // Fast path: check the leak cache (read lock, no allocation).
    // Two-level lookup: first by &str (no allocation), then by char.
    if let Ok(cache) = LANG_LEAK_CACHE.read() {
        if let Some(char_cache) = cache.get(lang) {
            if let Some(&cached) = char_cache.get(&ch) {
                return Some(cached);
            }
        }
    }

    // Slow path: check user-registered language tables and cache the leak.
    // Clone the replacement string under a read lock, then acquire the
    // cache write lock to check-then-leak atomically (prevents duplicate
    // leaks under concurrent access).
    let replacement_clone: Option<String> = LANG_TABLES
        .read()
        .ok()
        .and_then(|table| {
            table
                .get(lang)
                .and_then(|char_map| char_map.get(&ch).cloned())
        });

    if let Some(replacement) = replacement_clone {
        // Acquire cache write lock *before* leaking to ensure at most one
        // thread leaks per (lang, char) pair.
        if let Ok(mut cache) = LANG_LEAK_CACHE.write() {
            // Double-check: another thread may have inserted while we waited
            if let Some(&existing) = cache.get(lang).and_then(|m| m.get(&ch)) {
                return Some(existing);
            }
            let leaked: &'static str = Box::leak(replacement.into_boxed_str());
            cache.entry(lang.to_owned()).or_default().insert(ch, leaked);
            return Some(leaked);
        }
    }

    None
}

/// Look up a confusable character mapping (O(1) PHF).
/// Returns the Latin prototype string if the character is a known confusable.
/// Multi-character targets are supported (e.g. some confusables map to "rn").
#[inline]
pub fn lookup_confusable(ch: char, target_script: &str) -> Option<&'static str> {
    confusables_data::lookup(ch, target_script)
}

/// Return all available language codes.
pub fn list_langs() -> Vec<String> {
    let mut langs: Vec<String> = BUILTIN_LANGS.iter().map(|s| s.to_string()).collect();

    // Add user-registered languages
    if let Ok(table) = LANG_TABLES.read() {
        for key in table.keys() {
            if !langs.contains(key) {
                langs.push(key.clone());
            }
        }
    }

    langs.sort();
    langs
}

/// Register a custom language mapping.
///
/// # Thread Safety
///
/// This function is safe to call from multiple threads.  Internally it
/// acquires write locks on both `LANG_LEAK_CACHE` and `LANG_TABLES`
/// atomically (in that order) to prevent TOCTOU races.  Reads via
/// `lookup_lang()` use separate read locks and are wait-free when the
/// write lock is not held.
///
/// After this call returns, all subsequent `lookup_lang()` calls for
/// the given language code will see the new mappings.
///
/// # Memory
///
/// Invalidates the leak cache for the given language code so that
/// subsequent lookups see the new mappings.  Previously leaked strings
/// for overwritten entries remain allocated (they are `&'static str`),
/// but no *new* leaks will occur for already-cached pairs.
pub fn register_lang(code: &str, mappings: HashMap<String, String>) {
    let mut char_map = HashMap::new();
    for (key, value) in mappings {
        if let Some(ch) = key.chars().next() {
            char_map.insert(ch, value);
        }
    }
    // Acquire both locks together to close the TOCTOU window:
    // without this, a reader could see the new LANG_TABLES entry
    // but still find stale LANG_LEAK_CACHE entries between the
    // two separate lock acquisitions.
    //
    // Lock order: LANG_LEAK_CACHE first, then LANG_TABLES.
    // This is the only place both locks are held simultaneously,
    // so deadlock is impossible as long as the order is consistent.
    if let Ok(mut cache) = LANG_LEAK_CACHE.write() {
        if let Ok(mut table) = LANG_TABLES.write() {
            table.insert(code.to_owned(), char_map);
        }
        // Invalidate cached leaks for this language so lookups pick up
        // the new mappings.  The old leaked strings are unreclaimable
        // (they are 'static), but this bounds future leaks to one per
        // unique (lang, char) pair per registration cycle.
        cache.remove(code);
    }
}

/// Register global pre-transliteration replacements.
///
/// # Thread Safety
///
/// This function is safe to call from multiple threads.  It acquires a
/// write lock on `GLOBAL_REPLACEMENTS` for the duration of the extend.
///
/// New entries are merged into the existing table.  Existing keys are
/// silently overwritten with the new value.  Use [`clear_replacements`]
/// to wipe the table, or [`remove_replacement`] to remove a single key.
pub fn register_replacements(replacements: HashMap<String, String>) {
    if let Ok(mut table) = GLOBAL_REPLACEMENTS.write() {
        table.extend(replacements);
    }
}

/// Remove a single global pre-transliteration replacement by key.
///
/// Returns `true` if the key was present and removed, `false` otherwise.
pub fn remove_replacement(key: &str) -> bool {
    if let Ok(mut table) = GLOBAL_REPLACEMENTS.write() {
        return table.remove(key).is_some();
    }
    false
}

/// Clear all global pre-transliteration replacements.
pub fn clear_replacements() {
    if let Ok(mut table) = GLOBAL_REPLACEMENTS.write() {
        table.clear();
    }
}

// --- Emoji lookups ---

/// Look up a single-codepoint emoji (O(1) PHF).
#[inline]
pub fn lookup_emoji_single(ch: char) -> Option<&'static str> {
    emoji_data::EMOJI_SINGLE.get(&ch).copied()
}

/// Look up a multi-codepoint emoji sequence (O(1) PHF).
/// The key is the codepoint sequence encoded as uppercase hex separated by underscores.
#[inline]
pub fn lookup_emoji_multi(key: &str) -> Option<&'static str> {
    emoji_data::EMOJI_MULTI.get(key).copied()
}

/// Check if a codepoint can start a multi-codepoint emoji sequence.
#[inline]
pub fn is_emoji_multi_starter(ch: char) -> bool {
    emoji_data::EMOJI_MULTI_STARTERS.contains(&ch)
}

/// Maximum length of any multi-codepoint emoji sequence.
#[inline]
pub fn max_emoji_seq_len() -> usize {
    emoji_data::MAX_EMOJI_SEQ_LEN
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lookup_default_ascii() {
        // ASCII characters should not be in the transliteration table
        assert!(lookup_default('a').is_none());
        assert!(lookup_default('Z').is_none());
    }

    #[test]
    fn test_lookup_default_latin_extended() {
        // Common accented chars should transliterate
        assert_eq!(lookup_default('é'), Some("e"));
        assert_eq!(lookup_default('ñ'), Some("n"));
    }

    #[test]
    fn test_lookup_default_hanzi() {
        // CJK characters should resolve via hanzi_pinyin
        assert_eq!(lookup_default('北'), Some("bei"));
        assert_eq!(lookup_default('京'), Some("jing"));
    }

    #[test]
    fn test_lookup_default_hangul() {
        // Hangul should resolve via algorithmic romanization
        let result = lookup_default('한');
        assert!(result.is_some());
        assert_eq!(result.unwrap(), "han");
    }

    #[test]
    fn test_hangul_cache_consistency() {
        // Calling twice should return the same pointer (from cache)
        let first = lookup_hangul_static('가');
        let second = lookup_hangul_static('가');
        assert_eq!(first, second);
        assert_eq!(first.unwrap(), "ga");
    }

    #[test]
    fn test_lookup_default_unmapped() {
        // CJK Extension B character — should not be in any table
        let ch = char::from_u32(0x20000).unwrap();
        assert!(lookup_default(ch).is_none());
    }

    #[test]
    fn test_lookup_confusable() {
        // Cyrillic 'а' (U+0430) is confusable with Latin 'a'
        let result = lookup_confusable('\u{0430}', "latin");
        assert_eq!(result, Some("a"));
    }

    #[test]
    fn test_lookup_confusable_non_latin_target() {
        // Should return None for non-latin target scripts
        assert!(lookup_confusable('\u{0430}', "cyrillic").is_none());
    }

    #[test]
    fn test_list_langs_contains_builtins() {
        let langs = list_langs();
        assert!(langs.contains(&"de".to_owned()));
        assert!(langs.contains(&"ja".to_owned()));
        assert!(langs.contains(&"zh".to_owned()));
        assert!(langs.len() >= BUILTIN_LANGS.len());
    }

    #[test]
    fn test_list_langs_sorted() {
        let langs = list_langs();
        let mut sorted = langs.clone();
        sorted.sort();
        assert_eq!(langs, sorted);
    }

    #[test]
    fn test_emoji_single_lookup() {
        // Smiley face U+1F600
        let result = lookup_emoji_single('\u{1F600}');
        assert!(result.is_some());
    }

    #[test]
    fn test_max_emoji_seq_len_positive() {
        assert!(max_emoji_seq_len() > 0);
    }

    #[test]
    fn test_max_emoji_seq_len_covers_all_sequences() {
        // Verify MAX_EMOJI_SEQ_LEN is >= the longest key in EMOJI_MULTI.
        // Keys are uppercase hex codepoints separated by underscores,
        // so the codepoint count = underscore count + 1.
        let limit = emoji_data::MAX_EMOJI_SEQ_LEN;
        let mut max_found = 0usize;
        for (key, _) in emoji_data::EMOJI_MULTI.entries() {
            let cp_count = key.split('_').count();
            if cp_count > max_found {
                max_found = cp_count;
            }
            assert!(
                cp_count <= limit,
                "Emoji sequence {key} has {cp_count} codepoints, exceeds MAX_EMOJI_SEQ_LEN={limit}"
            );
        }
        // MAX_EMOJI_SEQ_LEN should be tight — equal to the actual max, not inflated.
        assert_eq!(
            max_found, limit,
            "MAX_EMOJI_SEQ_LEN={limit} but longest sequence is {max_found} — consider tightening"
        );
    }

    #[test]
    fn test_register_lang_lookup_cached() {
        // Register a custom language and look up twice — second call
        // should return the same pointer from the cache, not leak again.
        let mut mappings = HashMap::new();
        mappings.insert("Ü".to_owned(), "Ue".to_owned());
        register_lang("_test_cache", mappings);

        let first = lookup_lang("_test_cache", 'Ü');
        let second = lookup_lang("_test_cache", 'Ü');
        assert_eq!(first, Some("Ue"));
        assert_eq!(second, Some("Ue"));
        // Both should be the same pointer (from cache)
        assert!(std::ptr::eq(first.unwrap(), second.unwrap()));
    }

    #[test]
    fn test_register_lang_invalidates_cache() {
        // Register, look up (populates cache), re-register with new value,
        // look up again — should see the new value.
        let mut m1 = HashMap::new();
        m1.insert("Ö".to_owned(), "Oe".to_owned());
        register_lang("_test_inval", m1);

        let first = lookup_lang("_test_inval", 'Ö');
        assert_eq!(first, Some("Oe"));

        let mut m2 = HashMap::new();
        m2.insert("Ö".to_owned(), "O".to_owned());
        register_lang("_test_inval", m2);

        let second = lookup_lang("_test_inval", 'Ö');
        assert_eq!(second, Some("O"));
    }
}
