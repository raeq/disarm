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

use std::borrow::Cow;
use std::collections::HashMap;
use std::sync::RwLock;

use std::sync::LazyLock;

use crate::unicode_ranges as ur;

/// Pre-computed romanizations for all 11,172 precomposed Hangul syllables
/// (U+AC00–U+D7A3).  Indexed by `codepoint - 0xAC00`.
///
/// Using a `OnceCell<Vec<String>>` (initialised on first access) avoids
/// `Box::leak` entirely: the returned `&'static str` slices borrow directly
/// from this static storage, which lives for the lifetime of the process.
static HANGUL_ROMANIZATIONS: std::sync::OnceLock<Vec<String>> = std::sync::OnceLock::new();

/// Return a `'static` reference to the pre-computed Hangul romanization table.
fn hangul_romanizations() -> &'static Vec<String> {
    HANGUL_ROMANIZATIONS.get_or_init(|| {
        // 0xAC00 = Hangul base, 0xD7A3 = last precomposed syllable (11172 entries).
        (0u32..11_172)
            .map(|i| {
                let ch =
                    char::from_u32(0xAC00 + i).expect("all Hangul syllable codepoints are valid");
                hangul::romanize_hangul(ch).unwrap_or_default()
            })
            .collect()
    })
}

/// Global user-registered language tables protected by RwLock.
/// Reads (lookups) take a read lock — zero contention.
/// Writes (registration) take a write lock — rare, only during setup.
static LANG_TABLES: LazyLock<RwLock<HashMap<String, HashMap<char, String>>>> =
    LazyLock::new(|| RwLock::new(HashMap::new()));

static GLOBAL_REPLACEMENTS: LazyLock<RwLock<HashMap<String, String>>> =
    LazyLock::new(|| RwLock::new(HashMap::new()));

/// Maximum number of entries allowed in `GLOBAL_REPLACEMENTS`.
///
/// Prevents unbounded memory growth from untrusted callers supplying very
/// large replacement tables.
pub const MAX_REPLACEMENTS: usize = 10_000;

/// Maximum number of user-registered language profiles.
///
/// Prevents unbounded memory growth from untrusted callers repeatedly
/// registering new language codes.  Re-registering an existing code
/// (overwrite) does not count toward this limit.
pub const MAX_REGISTERED_LANGS: usize = 100;

/// Return the number of user-registered language profiles.
pub fn registered_lang_count() -> usize {
    crate::recover_lock(LANG_TABLES.read()).len()
}

/// True if the given language code has been user-registered.
pub fn has_registered_lang(code: &str) -> bool {
    crate::recover_lock(LANG_TABLES.read()).contains_key(code)
}

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

    // CJK Unified Ideographs (Extension A + Unified + Compat)
    if ur::CJK_EXT_A.contains(&cp) || ur::CJK_UNIFIED.contains(&cp) || ur::CJK_COMPAT.contains(&cp)
    {
        return hanzi_pinyin::lookup_hanzi(ch).or_else(|| transliteration::lookup(ch));
    }

    // Hangul Syllables and Compatibility Jamo
    if ur::HANGUL_SYLLABLES.contains(&cp) || ur::HANGUL_COMPAT_JAMO.contains(&cp) {
        return lookup_hangul_static(ch).or_else(|| transliteration::lookup(ch));
    }

    // Default flat BMP array (Latin Extended, Cyrillic, Greek, symbols, etc.)
    transliteration::lookup(ch)
}

/// Look up the romanization for a Hangul syllable or compatibility jamo.
///
/// For precomposed syllables (U+AC00–U+D7A3) this is an O(1) index into
/// the pre-computed `HANGUL_ROMANIZATIONS` table — no allocation, no lock,
/// no `Box::leak`.  For compatibility jamo (U+3131–U+3163) it delegates to
/// the static `COMPAT_JAMO` table in `hangul`.
fn lookup_hangul_static(ch: char) -> Option<&'static str> {
    let code = ch as u32;

    if (0xAC00..=0xD7A3).contains(&code) {
        let idx = (code - 0xAC00) as usize;
        // `hangul_romanizations()` returns `&'static Vec<String>` (OnceCell).
        // `.get(idx)` is used instead of direct indexing so that an unexpected
        // out-of-bounds (e.g. after a future range-check refactor) returns
        // `None` rather than panicking.
        let roms: &'static Vec<String> = hangul_romanizations();
        roms.get(idx).map(String::as_str)
    } else {
        hangul::lookup_compat_jamo(ch)
    }
}

/// Look up a character in the ISO 9:1995 scholarly table (O(1) PHF).
/// Returns None if ISO 9 has no override for this character, in which
/// case the caller should fall through to the default table.
#[inline]
pub fn lookup_iso9(ch: char) -> Option<&'static str> {
    transliteration::lookup_iso9(ch)
}

/// Look up a character in the GOST R 7.0.34-2014 table (O(1) PHF).
/// Returns None if GOST 7.0.34 has no override for this character, in which
/// case the caller should fall through to the default table.
#[inline]
pub fn lookup_gost7034(ch: char) -> Option<&'static str> {
    transliteration::lookup_gost7034(ch)
}

/// Look up a character in a language-specific table.
///
/// Returns `Cow::Borrowed` for built-in PHF language maps (zero allocation),
/// and `Cow::Owned` for user-registered runtime tables (clones the stored
/// `String` under a read lock).
///
/// Returning `Cow` instead of a leaked `&'static str` keeps heap usage fully
/// bounded: previously the caller-supplied mapping required a `Box::leak` per
/// unique `(lang, char)` pair, which grew forever in long-running processes.
///
/// Returns `None` if no override exists for this language + character; the
/// caller should fall through to the default table.
pub fn lookup_lang(lang: &str, ch: char) -> Option<Cow<'static, str>> {
    // Check built-in PHF language maps first (O(1) per map, zero allocation).
    if let Some(result) = transliteration::lookup_lang(lang, ch) {
        return Some(Cow::Borrowed(result));
    }

    // Check user-registered language tables under a read lock.
    // We clone the replacement string rather than leaking it, so memory usage
    // is bounded regardless of how many distinct characters are looked up.
    let table = crate::recover_lock(LANG_TABLES.read());
    table
        .get(lang)
        .and_then(|char_map| char_map.get(&ch).cloned())
        .map(Cow::Owned)
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
    let mut langs: Vec<String> = BUILTIN_LANGS.iter().map(|s| (*s).to_string()).collect();

    // Add user-registered languages
    let table = crate::recover_lock(LANG_TABLES.read());
    for key in table.keys() {
        if !langs.contains(key) {
            langs.push(key.clone());
        }
    }

    langs.sort();
    langs
}

/// Register a custom language mapping.
///
/// Returns `Err` if any mapping key is not exactly one Unicode scalar value.
/// Valid keys must contain exactly one `char`; multi-character strings (e.g.
/// grapheme clusters written as two or more codepoints) and empty strings are
/// rejected so that callers receive an explicit diagnostic rather than having
/// their entry silently discarded.
///
/// # Thread Safety
///
/// This function is safe to call from multiple threads.  It acquires a write
/// lock on `LANG_TABLES` for the duration of the insert.  Reads via
/// `lookup_lang()` acquire a separate read lock and are wait-free when no
/// write is in progress.
///
/// After this call returns, all subsequent `lookup_lang()` calls for the
/// given language code will see the new mappings.
pub fn register_lang(code: &str, mappings: HashMap<String, String>) -> Result<(), Vec<String>> {
    let mut char_map = HashMap::new();
    let mut bad_keys: Vec<String> = Vec::new();
    for (key, value) in mappings {
        let mut chars = key.chars();
        match (chars.next(), chars.next()) {
            (Some(ch), None) => {
                char_map.insert(ch, value);
            }
            _ => bad_keys.push(key),
        }
    }
    if !bad_keys.is_empty() {
        return Err(bad_keys);
    }
    let mut table = crate::recover_lock_or_clear(LANG_TABLES.write());
    table.insert(code.to_owned(), char_map);
    Ok(())
}

/// Register global pre-transliteration replacements.
///
/// Returns `Err(count)` if the new entries would push the total number of
/// replacements beyond [`MAX_REPLACEMENTS`], where `count` is the number of
/// entries in the table after any existing keys are overwritten.  No entries
/// are written in the error case.
///
/// # Thread Safety
///
/// This function is safe to call from multiple threads.  It acquires a
/// write lock on `GLOBAL_REPLACEMENTS` for the duration of the extend.
///
/// New entries are merged into the existing table.  Existing keys are
/// silently overwritten with the new value.  Use [`clear_replacements`]
/// to wipe the table, or [`remove_replacement`] to remove a single key.
pub fn register_replacements(replacements: HashMap<String, String>) -> Result<(), usize> {
    let mut table = crate::recover_lock_or_clear(GLOBAL_REPLACEMENTS.write());
    // Compute worst-case size after merge: existing + all-new (ignoring overlap).
    // This is conservative but avoids the cost of set-difference computation.
    let new_keys: usize = replacements
        .keys()
        .filter(|k| !table.contains_key(*k))
        .count();
    let projected = table.len() + new_keys;
    if projected > MAX_REPLACEMENTS {
        return Err(projected);
    }
    table.extend(replacements);
    Ok(())
}

/// Remove a single global pre-transliteration replacement by key.
///
/// Returns `true` if the key was present and removed, `false` otherwise.
pub fn remove_replacement(key: &str) -> bool {
    let mut table = crate::recover_lock_or_clear(GLOBAL_REPLACEMENTS.write());
    table.remove(key).is_some()
}

/// Clear all global pre-transliteration replacements.
pub fn clear_replacements() {
    let mut table = crate::recover_lock_or_clear(GLOBAL_REPLACEMENTS.write());
    table.clear();
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
        // Calling twice should return the same value (from pre-computed table)
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
    fn test_register_lang_lookup() {
        // Register a custom language and verify the mapping is returned.
        let mut mappings = HashMap::new();
        mappings.insert("Ü".to_owned(), "Ue".to_owned());
        register_lang("_test_cow_lookup", mappings).unwrap();

        let first = lookup_lang("_test_cow_lookup", 'Ü');
        let second = lookup_lang("_test_cow_lookup", 'Ü');
        // Both calls must return the correct value (Cow::Owned clone each time).
        assert_eq!(first.as_deref(), Some("Ue"));
        assert_eq!(second.as_deref(), Some("Ue"));
    }

    #[test]
    fn test_register_lang_rejects_multi_char_key() {
        // Keys that are not exactly one Unicode scalar value must be rejected.
        let mut mappings = HashMap::new();
        mappings.insert("AB".to_owned(), "ab".to_owned());
        let result = register_lang("_test_bad_key", mappings);
        assert!(result.is_err());
        let bad = result.unwrap_err();
        assert_eq!(bad, vec!["AB".to_owned()]);
    }

    #[test]
    fn test_register_lang_rejects_empty_key() {
        let mut mappings = HashMap::new();
        mappings.insert(String::new(), "x".to_owned());
        let result = register_lang("_test_empty_key", mappings);
        assert!(result.is_err());
    }

    #[test]
    fn test_register_lang_invalidates_on_reregister() {
        // Register, look up, re-register with new value, look up again —
        // should see the new value immediately.
        let mut m1 = HashMap::new();
        m1.insert("Ö".to_owned(), "Oe".to_owned());
        register_lang("_test_inval2", m1).unwrap();

        let first = lookup_lang("_test_inval2", 'Ö');
        assert_eq!(first.as_deref(), Some("Oe"));

        let mut m2 = HashMap::new();
        m2.insert("Ö".to_owned(), "O".to_owned());
        register_lang("_test_inval2", m2).unwrap();

        let second = lookup_lang("_test_inval2", 'Ö');
        assert_eq!(second.as_deref(), Some("O"));
    }

    #[test]
    fn test_lookup_lang_builtin_is_borrowed() {
        // Built-in PHF results should come back as Cow::Borrowed.
        let result = lookup_lang("de", 'ü');
        if let Some(cow) = result {
            assert!(
                matches!(cow, Cow::Borrowed(_)),
                "built-in PHF result should be Cow::Borrowed"
            );
        }
    }

    #[test]
    fn test_lookup_lang_user_registered_is_owned() {
        // User-registered results should come back as Cow::Owned (cloned string).
        let mut m = HashMap::new();
        m.insert("X".to_owned(), "ex".to_owned());
        register_lang("_test_owned", m).unwrap();

        let result = lookup_lang("_test_owned", 'X');
        if let Some(cow) = result {
            assert!(
                matches!(cow, Cow::Owned(_)),
                "user-registered result should be Cow::Owned"
            );
        } else {
            panic!("expected Some from registered lang");
        }
    }
}
