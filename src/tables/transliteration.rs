//! Default Unicode → ASCII transliteration mappings.
//!
//! The default table uses a flat array indexed by `(codepoint - 0x80)` for
//! O(1) lookups with zero hashing overhead. This covers the entire BMP
//! (U+0080–U+FFFF) in ~512 KB — well within L2 cache.
//!
//! SMP characters (U+10000+) — ancient and historic scripts like Gothic,
//! Old Persian, and Linear B — are served by a separate PHF map.
//!
//! Language-specific override maps use compile-time perfect hash maps (`phf`)
//! since they are tiny (1–26 entries each) and PHF overhead is negligible.
//!
//! Covers: Latin-1 Supplement, Latin Extended-A, Latin Extended-B,
//! Latin Extended Additional (Vietnamese, Welsh, medievalist),
//! Cyrillic, Greek, Ogham, Runic, currency/symbols, typographic characters,
//! Gothic, Old Persian Cuneiform, and Linear B Syllabary.

// Default transliteration table — flat array for BMP, O(1) via index.
include!(concat!(env!("OUT_DIR"), "/translit_default_flat.rs"));

// Default SMP transliteration — PHF for ancient/historic scripts above U+FFFF.
include!(concat!(env!("OUT_DIR"), "/translit_default_smp_phf.rs"));

// ===== Language-specific override maps =====
//
// Only languages that actually differ from the default table get a PHF map.
// Languages not listed here fall through to the default table.
include!(concat!(env!("OUT_DIR"), "/translit_langs_phf.rs"));

/// Look up default transliteration for a character.
#[inline]
pub fn lookup(ch: char) -> Option<&'static str> {
    let cp = ch as u32;
    if (0x80..0x10000).contains(&cp) {
        // BMP: two-level page trie (#237 item 1), two indexed loads, no hashing.
        // `PAGES[cp >> 8]` is the base of this page's 256 cells in `ENTRIES`
        // (unpopulated pages alias the shared empty page at base 0). A cell of
        // `u32::MAX` is None; otherwise `(offset << 8) | len` slices the blob,
        // with `len == 0` yielding `Some("")` (drop the char).
        let base = DEFAULT_BMP_PAGES[(cp >> 8) as usize] as usize;
        let cell = DEFAULT_BMP_ENTRIES[base + (cp & 0xFF) as usize];
        if cell == u32::MAX {
            None
        } else {
            let off = (cell >> 8) as usize;
            let len = (cell & 0xFF) as usize;
            Some(&DEFAULT_BMP_BLOB[off..off + len])
        }
    } else if cp >= 0x10000 {
        // SMP: ancient/historic scripts — PHF lookup
        DEFAULT_SMP.get(&ch).copied()
    } else {
        // ASCII (<0x80) needs no transliteration
        None
    }
}

/// Look up a character in the ISO 9:1995 scholarly override table.
#[inline]
pub fn lookup_iso9(ch: char) -> Option<&'static str> {
    ISO9.get(&ch).copied()
}

/// Look up a character in the GOST R 7.0.34-2014 override table.
#[inline]
pub fn lookup_gost7034(ch: char) -> Option<&'static str> {
    GOST7034.get(&ch).copied()
}

/// Resolve a language code to its built-in PHF override map, once.
///
/// Hoisting this ~24-arm `match lang` out of the per-character loop (#235 item 1)
/// lets the hot path probe the resolved map directly (`map.get(&ch)`) instead of
/// re-running the match for every character. Returns `None` for languages with
/// no built-in overrides (they fall through to the default table).
#[inline]
pub fn resolve_lang_map(lang: &str) -> Option<&'static phf::Map<char, &'static str>> {
    let table: Option<&phf::Map<char, &'static str>> = match lang {
        "de" => Some(&LANG_DE),
        // Norwegian Bokmål (nb) and Nynorsk (nn) are aliases for Norwegian (no).
        // They share the same Å→Aa, Ø→Oe, Æ→Ae overrides.
        // Danish (da) also uses identical override rules.
        // nb/nn are NOT in BUILTIN_LANGS (list_langs() returns "no" only) but
        // are accepted here so callers passing BCP 47 codes get correct results.
        "no" | "nb" | "nn" | "da" => Some(&LANG_NO),
        "sv" => Some(&LANG_SV),
        // Finnish: ä/ö are independent phonemes, NOT ae/oe variants like in
        // Swedish/German. Finnish falls through to default table (ä→a, ö→o).
        "is" => Some(&LANG_IS),
        "et" => Some(&LANG_ET),
        "fr" => Some(&LANG_FR),
        "es" => Some(&LANG_ES),
        "pt" => Some(&LANG_PT),
        "it" => Some(&LANG_IT),
        "tr" => Some(&LANG_TR),
        "nl" => Some(&LANG_NL),
        "ca" => Some(&LANG_CA),
        "vi" => Some(&LANG_VI),
        "el" => Some(&LANG_EL),
        "bg" => Some(&LANG_BG),
        "uk" => Some(&LANG_UK),
        "ru" => Some(&LANG_RU),
        "sr" => Some(&LANG_SR),
        "ja" => Some(&LANG_JA),
        "ja-kunrei" => Some(&LANG_JA_KUNREI),
        "fa" => Some(&LANG_FA), // Persian (Farsi)
        "am" => Some(&LANG_AM), // Amharic (ጸ/ፀ merger + pharyngeal marking)
        // Languages that need no overrides — default table handles them correctly:
        // cs, sk, pl, hu, ro, hr, sl, sq, mt, ga, cy, lv, lt, ar
        // CJK languages (zh, ko) are handled by dedicated modules (hanzi_pinyin, hangul)
        // that are called from lookup_default() in mod.rs
        _ => None,
    };
    table
}

/// Look up a character in a language-specific PHF map.
/// Returns None if the language has no override for this character.
#[inline]
pub fn lookup_lang(lang: &str, ch: char) -> Option<&'static str> {
    resolve_lang_map(lang).and_then(|t| t.get(&ch).copied())
}
