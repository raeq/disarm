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
pub mod hangul;
mod hanzi_pinyin;
mod transliteration;

use std::borrow::Cow;
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::RwLock;

use std::sync::LazyLock;

use crate::unicode_ranges as ur;

/// Number of precomposed Hangul syllables (U+AC00–U+D7A3).
const HANGUL_SYLLABLE_COUNT: usize = 11_172;

/// Pre-computed romanizations for all 11,172 precomposed Hangul syllables,
/// packed into a single contiguous blob with an offset array (#237 item 3).
///
/// The previous `OnceLock<Vec<String>>` *retained* 11,172 separate small
/// `String` allocations (~700 KB heap incl. per-`String` slop), held for the
/// process lifetime, plus a pointer-chase per lookup. This packs them into
/// **one** `String` blob + **one** `[u32]` offset array — so the **retained**
/// heap is two allocations instead of 11,173, contiguous in memory (adjacent
/// syllables share cache lines), with a flat indexed slice per lookup.
/// (Construction still calls `romanize_hangul` per syllable, which allocates a
/// transient `String` that is dropped immediately after it is copied into the
/// blob; the win is the retained footprint and locality, not the one-time
/// construction allocations.) The returned `&'static str` slices borrow from
/// this `OnceLock` storage, which lives for the process lifetime, so no
/// `Box::leak`.
struct HangulRomanizations {
    /// All romanizations concatenated, in syllable order.
    blob: String,
    /// `HANGUL_SYLLABLE_COUNT + 1` offsets: syllable `i`'s romanization is
    /// `blob[offsets[i]..offsets[i + 1]]`.
    offsets: Vec<u32>,
}

static HANGUL_ROMANIZATIONS: std::sync::OnceLock<HangulRomanizations> = std::sync::OnceLock::new();

/// Return a `'static` reference to the packed Hangul romanization table.
fn hangul_romanizations() -> &'static HangulRomanizations {
    HANGUL_ROMANIZATIONS.get_or_init(|| {
        // Average romanization is ~6–7 ASCII bytes; reserve generously once.
        let mut blob = String::with_capacity(HANGUL_SYLLABLE_COUNT * 7);
        let mut offsets = Vec::with_capacity(HANGUL_SYLLABLE_COUNT + 1);
        offsets.push(0u32);
        // 0xAC00 = Hangul base, 0xD7A3 = last precomposed syllable.
        for i in 0..HANGUL_SYLLABLE_COUNT as u32 {
            let ch = char::from_u32(0xAC00 + i).expect("all Hangul syllable codepoints are valid");
            blob.push_str(&hangul::romanize_hangul(ch).unwrap_or_default());
            offsets.push(u32::try_from(blob.len()).expect("Hangul blob fits in u32"));
        }
        HangulRomanizations { blob, offsets }
    })
}

/// Global user-registered language tables protected by RwLock.
/// Reads (lookups) take a read lock — zero contention.
/// Writes (registration) take a write lock — rare, only during setup.
static LANG_TABLES: LazyLock<RwLock<HashMap<String, HashMap<char, String>>>> =
    LazyLock::new(|| RwLock::new(HashMap::new()));

static GLOBAL_REPLACEMENTS: LazyLock<RwLock<HashMap<String, String>>> =
    LazyLock::new(|| RwLock::new(HashMap::new()));

/// A compiled longest-match replacement automaton plus the replacement value for
/// each pattern id (#242 item 1). `find_iter` with `LeftmostLongest` reproduces
/// the former O(n·distinct-key-lengths) [`replace_longest_match`] scan in O(n)
/// with no per-position hash probing, advancing past each match (so output is
/// never rescanned), which is exactly the documented semantics.
struct ReplacementAutomaton {
    ac: aho_corasick::AhoCorasick,
    /// `values[pattern_id]` is the replacement for the key registered as that id.
    values: Vec<String>,
}

/// The longest-match automaton for [`GLOBAL_REPLACEMENTS`], rebuilt by every
/// mutator while it holds the table write lock so the two never diverge. `None`
/// when the table is empty. Read (only) by [`apply_replacements`].
static GLOBAL_REPLACEMENTS_AC: LazyLock<RwLock<Option<ReplacementAutomaton>>> =
    LazyLock::new(|| RwLock::new(None));

/// Build a `LeftmostLongest` replacement automaton from `map`, or `None` if the
/// map has no non-empty keys. Patterns are sorted for a deterministic,
/// reproducible build (length, not order, decides longest-match).
fn build_replacement_automaton(map: &HashMap<String, String>) -> Option<ReplacementAutomaton> {
    let mut keys: Vec<&String> = map.keys().filter(|k| !k.is_empty()).collect();
    keys.sort();
    if keys.is_empty() {
        return None;
    }
    let ac = aho_corasick::AhoCorasick::builder()
        .match_kind(aho_corasick::MatchKind::LeftmostLongest)
        .build(keys.iter().map(|k| k.as_str()))
        .expect("replacement keys are valid aho-corasick patterns");
    let values = keys.iter().map(|k| map[*k].clone()).collect();
    Some(ReplacementAutomaton { ac, values })
}

/// Rebuild [`GLOBAL_REPLACEMENTS_AC`] from `map`. Call while holding the
/// `GLOBAL_REPLACEMENTS` write lock (the consistent lock order: table then
/// automaton) so the automaton stays in sync with the table.
fn rebuild_replacement_automaton(map: &HashMap<String, String>) {
    let built = build_replacement_automaton(map);
    let mut slot = crate::recover_lock(GLOBAL_REPLACEMENTS_AC.write(), "GLOBAL_REPLACEMENTS_AC");
    *slot = built;
}

/// Fast "is the replacement table non-empty?" flag. Lets `apply_replacements`
/// short-circuit with a single relaxed atomic load on the (overwhelmingly
/// common) no-replacements-registered path, avoiding an `RwLock` read on every
/// transliterate call. Kept in sync by every mutator below.
static HAS_REPLACEMENTS: AtomicBool = AtomicBool::new(false);

/// Fast "are any user language tables registered?" flag, mirroring
/// [`HAS_REPLACEMENTS`]. The built-in language override maps are *tiny*
/// (1–26 entries), so for real text nearly every character misses the override
/// map and falls through to the user-registered check. Without this gate that
/// check acquires `LANG_TABLES.read()` **per character** even when no language
/// has ever been registered (the overwhelmingly common case). A single Acquire
/// load lets the per-char path skip the lock entirely (#235 item 1); the
/// Acquire pairs with the Release store in [`register_lang`] so a reader that
/// observes `true` also observes the inserted entries.
/// Kept in sync by [`register_lang`] (the only `LANG_TABLES` mutator).
static HAS_REGISTERED_LANGS: AtomicBool = AtomicBool::new(false);

/// Once sealed, the registration tables (langs + replacements) are frozen so an
/// application can configure registrations at startup and then prevent any later
/// code (a request handler, an imported library) from mutating the
/// process-global canonicalization that every caller shares (#64). One-way latch.
///
/// Enforcement note: this flag is the *state*; rejection of register/remove/
/// clear is currently performed by the PyO3 entry points (`check_not_sealed` in
/// `transliterate.rs`), which are the only callers of the mutators below. The
/// `tables::` mutators themselves do **not** consult this flag, so a future
/// direct-Rust API (the core split, #38) must add the seal check at that new
/// boundary — do not assume sealing is enforced at this layer.
static REGISTRATIONS_SEALED: AtomicBool = AtomicBool::new(false);

/// Seal the global registration tables: subsequent register/remove/clear calls
/// fail. Idempotent and irreversible (by design — sealing is a security latch).
pub fn seal_registrations() {
    REGISTRATIONS_SEALED.store(true, Ordering::Release);
    tl_info!("registrations sealed");
}

/// True if [`seal_registrations`] has been called.
pub fn registrations_sealed() -> bool {
    REGISTRATIONS_SEALED.load(Ordering::Acquire)
}

// Resource limits live in `crate::limits` (#256); re-exported here so the
// long-standing `tables::MAX_REPLACEMENTS` / `tables::MAX_REGISTERED_LANGS`
// paths used by the registration enforcement (and the public Rust API) keep
// resolving to the single canonical definition.
pub use crate::limits::{MAX_REGISTERED_LANGS, MAX_REPLACEMENTS};

/// Return the number of user-registered language profiles.
pub fn registered_lang_count() -> usize {
    crate::recover_lock(LANG_TABLES.read(), "LANG_TABLES").len()
}

/// True if the given language code has been user-registered.
pub fn has_registered_lang(code: &str) -> bool {
    crate::recover_lock(LANG_TABLES.read(), "LANG_TABLES").contains_key(code)
}

/// Accepted BCP-47 language aliases that resolve to a built-in table but are not
/// listed by `list_langs()` (Norwegian Bokmål/Nynorsk and Danish share the
/// Norwegian overrides — see `lookup_lang`). Must be kept in sync with the alias
/// arms there.
const LANG_ALIASES: &[&str] = &["nb", "nn", "da"];

/// True if `code` is a known language: a built-in profile, an accepted alias, or
/// a user-registered one. Does not include the special `"auto"` detection mode
/// (callers handle it).
pub fn is_valid_lang(code: &str) -> bool {
    // `BUILTIN_LANGS` is sorted (guarded by `builtin_langs_is_sorted`), so
    // binary-search it: O(log n) vs the former O(n) linear scan over 85 entries
    // (#235 item 10). `LANG_ALIASES` is tiny (3 entries) — linear is fine there.
    BUILTIN_LANGS.binary_search(&code).is_ok()
        || LANG_ALIASES.contains(&code)
        || has_registered_lang(code)
}

/// All built-in language codes, sorted.
const BUILTIN_LANGS: &[&str] = &[
    "am",
    "ar",
    "as",
    "ban", // Balinese
    "bax", // Bamum
    "bg",
    "bn",
    "bo",
    "bug", // Buginese (Lontara)
    "ca",
    "chr", // Cherokee
    "cjm", // Cham
    "cop", // Coptic
    "cs",
    "cy",
    "da",
    "de",
    "dv",
    "el",
    "es",
    "et",
    "fa",
    "fi",
    "fr",
    "ga",
    "gu",
    "he",
    "hi",
    "hr",
    "hu",
    "hy",
    "is",
    "it",
    "ja",
    "ja-kunrei",
    "jv",
    "ka",
    "khb", // Tai Lue (New Tai Lue script)
    "km",
    "kn",
    "ko",
    "lis", // Lisu (Fraser script)
    "lo",
    "lt",
    "lv",
    "ml",
    "mn",
    "mni", // Meitei (Meetei Mayek script)
    "mr",
    "mt",
    "my",
    "ne",
    "nl",
    "no",
    "nod", // Northern Thai (Tai Tham/Lanna script)
    "nqo", // N'Ko
    "or",
    "pa",
    "pl",
    "pt",
    "ro",
    "ru",
    "sa",
    "sat", // Santali (Ol Chiki script)
    "si",
    "sk",
    "sl",
    "sq",
    "sr",
    "su", // Sundanese
    "sv",
    "syr", // Syriac
    "ta",
    "tdd", // Tai Le
    "te",
    "th",
    "tl", // Tagalog
    "tr",
    "tzm", // Tamazight/Berber (Tifinagh script)
    "uk",
    "vai", // Vai
    "vi",
    "zh",
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

/// Like `lookup_default`, but returns toned pinyin (with diacritics) for CJK.
/// Falls through to toneless for characters without toned data.
#[inline]
pub fn lookup_default_toned(ch: char) -> Option<&'static str> {
    let cp = ch as u32;

    if ur::CJK_EXT_A.contains(&cp) || ur::CJK_UNIFIED.contains(&cp) || ur::CJK_COMPAT.contains(&cp)
    {
        return hanzi_pinyin::lookup_hanzi_toned(ch).or_else(|| transliteration::lookup(ch));
    }

    if ur::HANGUL_SYLLABLES.contains(&cp) || ur::HANGUL_COMPAT_JAMO.contains(&cp) {
        return lookup_hangul_static(ch).or_else(|| transliteration::lookup(ch));
    }

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
        // Flat indexed slice into the packed blob (#237 item 3). `offsets` has
        // `HANGUL_SYLLABLE_COUNT + 1` entries, so `idx` and `idx + 1` are always
        // in bounds for a valid syllable; `get`s keep an unexpected future
        // out-of-bounds returning `None` rather than panicking.
        let table = hangul_romanizations();
        let start = *table.offsets.get(idx)? as usize;
        let end = *table.offsets.get(idx + 1)? as usize;
        table.blob.get(start..end)
    } else {
        hangul::lookup_compat_jamo(ch)
    }
}

/// Look up a character in the scholarly ASCII Cyrillic table (O(1) PHF).
/// NOTE: this is an ASCII (digraph-based) transliteration, NOT the diacritic
/// ISO 9:1995 standard — tables are ASCII-only by design (see #94).
/// Returns None if the table has no override for this character, in which
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
    lookup_registered(lang, ch)
}

/// Resolve a language code to its built-in PHF override map, once, before the
/// per-character loop (#235 item 1). The hot path then probes the returned map
/// directly and only falls back to [`lookup_registered`] on a miss.
#[inline]
pub fn resolve_lang_map(lang: &str) -> Option<&'static phf::Map<char, &'static str>> {
    transliteration::resolve_lang_map(lang)
}

/// Look up `ch` in the user-registered table for `lang`, if any.
///
/// Gated behind [`HAS_REGISTERED_LANGS`]: when no language has been registered
/// (the common case) this is a single Acquire atomic load and **never** touches
/// `LANG_TABLES.read()`, so the per-character hot path pays no lock. When a
/// language *is* registered the string is cloned (not leaked), so memory stays
/// bounded regardless of how many distinct characters are looked up.
#[inline]
pub fn lookup_registered(lang: &str, ch: char) -> Option<Cow<'static, str>> {
    if !HAS_REGISTERED_LANGS.load(Ordering::Acquire) {
        return None;
    }
    let table = crate::recover_lock(LANG_TABLES.read(), "LANG_TABLES");
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

/// Resolve a `target_script` to its confusables PHF map, once, so a per-char
/// loop can probe the map directly instead of re-dispatching `target_script`
/// every character (#236 / #233 review item).
#[inline]
pub fn resolve_confusable_map(
    target_script: &str,
) -> Option<&'static phf::Map<char, &'static str>> {
    confusables_data::resolve_map(target_script)
}

/// Return all available language codes.
pub fn list_langs() -> Vec<String> {
    let mut langs: Vec<String> = BUILTIN_LANGS.iter().map(|s| (*s).to_string()).collect();

    // Add user-registered languages. Registered keys are unique (HashMap), so a
    // key can only collide with a builtin — BUILTIN_LANGS is sorted (guarded by
    // `builtin_langs_is_sorted`), so binary-search it: O(log n) per key, no
    // per-call allocation, vs the former O(builtins) linear scan (#252 O5.5).
    let table = crate::recover_lock(LANG_TABLES.read(), "LANG_TABLES");
    for key in table.keys() {
        if BUILTIN_LANGS.binary_search(&key.as_str()).is_err() {
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
///
/// # Seal
///
/// This mutator does **not** consult `REGISTRATIONS_SEALED`.  Seal
/// enforcement is the **caller's responsibility** — the PyO3 entry points in
/// `transliterate.rs` call `check_not_sealed` before invoking this function.
/// Any future direct-Rust API (e.g. the core split planned in #38) must add
/// the same guard at its own boundary. (#123)
///
/// # Concurrency — poison recovery (#117/#251)
///
/// The write lock is *recovered*, not propagated, if a thread previously
/// panicked while holding it (`recover_lock`). A panic *mid-write* can therefore
/// leave a partially-applied registration visible to later readers — recovery
/// deliberately favours availability over aborting the process (#64/#117). Once
/// configuration is complete, seal the registrations (the `_seal_registrations`
/// entry point) to freeze a known-good table and reject further mutations.
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
    // #208: metadata only — the lang code (a config identifier) and the mapping
    // count, never the mappings themselves (user-provided content). The var is
    // cfg-gated so it costs nothing when the `log` feature is off.
    #[cfg(feature = "log")]
    let mapping_count = char_map.len();
    let mut table = crate::recover_lock(LANG_TABLES.write(), "LANG_TABLES");
    table.insert(code.to_owned(), char_map);
    // Release so a reader's Acquire load that observes `true` also observes the
    // insert above (same configure-then-use contract as `HAS_REPLACEMENTS`).
    HAS_REGISTERED_LANGS.store(!table.is_empty(), Ordering::Release);
    tl_info!("register_lang: code={code:?} mappings={mapping_count}");
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
///
/// # Seal
///
/// This mutator does **not** consult `REGISTRATIONS_SEALED`.  Seal
/// enforcement is the **caller's responsibility** — the PyO3 entry points in
/// `transliterate.rs` call `check_not_sealed` before invoking this function.
/// Any future direct-Rust API (e.g. the core split planned in #38) must add
/// the same guard at its own boundary. (#123)
///
/// # Concurrency — poison recovery (#117/#251)
///
/// The write lock is *recovered*, not propagated, if a thread previously
/// panicked while holding it (`recover_lock`). A panic *mid-write* can therefore
/// leave a partially-applied registration visible to later readers — recovery
/// deliberately favours availability over aborting the process (#64/#117). Once
/// configuration is complete, seal the registrations (the `_seal_registrations`
/// entry point) to freeze a known-good table and reject further mutations.
pub fn register_replacements(replacements: HashMap<String, String>) -> Result<(), usize> {
    let mut table = crate::recover_lock(GLOBAL_REPLACEMENTS.write(), "GLOBAL_REPLACEMENTS");
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
    // Rebuild the longest-match automaton (#242 item 1) while still holding the
    // table write lock, so the automaton and table never diverge.
    rebuild_replacement_automaton(&table);
    // Release so a reader's Acquire load that observes `true` also observes the
    // table mutation above. (Note: this does not make register-concurrent-with-
    // transliterate fully ordered — a reader may still observe a stale `false`
    // and skip; the contract is configure-then-use.)
    HAS_REPLACEMENTS.store(!table.is_empty(), Ordering::Release);
    // #208: total entry count only — never the replacement keys/values (content).
    tl_info!("register_replacements: total={}", table.len());
    Ok(())
}

/// Remove a single global pre-transliteration replacement by key.
///
/// Returns `true` if the key was present and removed, `false` otherwise.
///
/// # Seal
///
/// This mutator does **not** consult `REGISTRATIONS_SEALED`.  Seal
/// enforcement is the **caller's responsibility** — the PyO3 entry points in
/// `transliterate.rs` call `check_not_sealed` before invoking this function.
/// Any future direct-Rust API (e.g. the core split planned in #38) must add
/// the same guard at its own boundary. (#123)
pub fn remove_replacement(key: &str) -> bool {
    let mut table = crate::recover_lock(GLOBAL_REPLACEMENTS.write(), "GLOBAL_REPLACEMENTS");
    let removed = table.remove(key).is_some();
    rebuild_replacement_automaton(&table);
    HAS_REPLACEMENTS.store(!table.is_empty(), Ordering::Release);
    removed
}

/// Clear all global pre-transliteration replacements.
///
/// # Seal
///
/// This mutator does **not** consult `REGISTRATIONS_SEALED`.  Seal
/// enforcement is the **caller's responsibility** — the PyO3 entry points in
/// `transliterate.rs` call `check_not_sealed` before invoking this function.
/// Any future direct-Rust API (e.g. the core split planned in #38) must add
/// the same guard at its own boundary. (#123)
pub fn clear_replacements() {
    let mut table = crate::recover_lock(GLOBAL_REPLACEMENTS.write(), "GLOBAL_REPLACEMENTS");
    table.clear();
    rebuild_replacement_automaton(&table);
    HAS_REPLACEMENTS.store(false, Ordering::Release);
}

/// Apply the registered global pre-transliteration replacements to `text`.
///
/// Performs a single left-to-right pass with **longest-match-at-each-position**
/// semantics: at each character boundary the longest registered key that
/// matches is emitted as its replacement and the scan jumps past it; matched
/// output is never re-scanned, so replacements cannot cascade into each other.
///
/// Returns `Ok(Cow::Borrowed)` (zero allocation) when no replacements are
/// registered or none match. Returns `Err(size)` if the replaced text would
/// exceed `max_len` bytes: replacement *values* are caller-controlled and
/// unbounded in length, so a small input with a large registered value could
/// otherwise expand past the transliterate() input cap and defeat it. The
/// output is bounded during construction, so the over-limit allocation is
/// capped rather than realised in full.
pub fn apply_replacements(text: &str, max_len: usize) -> Result<Cow<'_, str>, usize> {
    // Fast path: no replacements registered (single Acquire atomic load,
    // pairing with the Release stores in the mutators).
    if !HAS_REPLACEMENTS.load(Ordering::Acquire) {
        return Ok(Cow::Borrowed(text));
    }
    // #242 item 1: O(n) longest-match via the prebuilt automaton instead of the
    // former per-position length scan. The automaton is rebuilt with the table.
    let guard = crate::recover_lock(GLOBAL_REPLACEMENTS_AC.read(), "GLOBAL_REPLACEMENTS_AC");
    match guard.as_ref() {
        Some(automaton) => replace_with_automaton(text, automaton, max_len),
        None => Ok(Cow::Borrowed(text)),
    }
}

/// Apply a prebuilt longest-match [`ReplacementAutomaton`] to `text` (#242 item
/// 1). Output is byte-identical to [`replace_longest_match`] (enforced by
/// `automaton_matches_longest_scan`): `LeftmostLongest` `find_iter` yields the
/// non-overlapping longest match at each position and advances past it, so the
/// replacement output is never rescanned. Allocates lazily on the first match
/// (no match → borrowed, zero allocation); `Err(size)` once it would exceed
/// `max_len`.
fn replace_with_automaton<'a>(
    text: &'a str,
    automaton: &ReplacementAutomaton,
    max_len: usize,
) -> Result<Cow<'a, str>, usize> {
    let mut out: Option<String> = None;
    let mut last = 0;
    for mat in automaton.ac.find_iter(text) {
        let buf = out.get_or_insert_with(|| String::with_capacity(text.len()));
        buf.push_str(&text[last..mat.start()]);
        buf.push_str(&automaton.values[mat.pattern().as_usize()]);
        if buf.len() > max_len {
            return Err(buf.len());
        }
        last = mat.end();
    }
    match out {
        Some(mut buf) => {
            buf.push_str(&text[last..]);
            if buf.len() > max_len {
                return Err(buf.len());
            }
            Ok(Cow::Owned(buf))
        }
        None => Ok(Cow::Borrowed(text)),
    }
}

/// Pure longest-match substring replacement — the former algorithm behind
/// [`apply_replacements`], retained as the **reference oracle** that the
/// `aho-corasick` automaton (#242 item 1) is checked byte-for-byte against
/// (`automaton_matches_longest_scan`). The output buffer is allocated lazily on
/// the first match (no match → borrowed, zero allocation); `Err(size)` once the
/// output would exceed `max_len` bytes.
#[cfg(test)]
fn replace_longest_match<'a>(
    text: &'a str,
    table: &HashMap<String, String>,
    max_len: usize,
) -> Result<Cow<'a, str>, usize> {
    // Distinct key byte-lengths, longest first, so we try the longest possible
    // match at each position. Zero-length keys are ignored (would not advance).
    let mut lengths: Vec<usize> = table.keys().map(String::len).filter(|&l| l > 0).collect();
    lengths.sort_unstable_by(|a, b| b.cmp(a));
    lengths.dedup();
    if lengths.is_empty() {
        return Ok(Cow::Borrowed(text));
    }

    // `out` is allocated only once a replacement actually fires; `last` marks the
    // start of the input region not yet copied into it.
    let mut out: Option<String> = None;
    let mut last = 0;
    let mut i = 0;
    while i < text.len() {
        let mut matched = false;
        for &len in &lengths {
            let end = i + len;
            if end > text.len() || !text.is_char_boundary(end) {
                continue;
            }
            if let Some(rep) = table.get(&text[i..end]) {
                let buf = out.get_or_insert_with(|| String::with_capacity(text.len()));
                buf.push_str(&text[last..i]);
                buf.push_str(rep);
                if buf.len() > max_len {
                    return Err(buf.len());
                }
                i = end;
                last = end;
                matched = true;
                break;
            }
        }
        if !matched {
            // `i` is always at a char boundary (we advance by whole chars or
            // whole matched keys), so `chars().next()` yields a char.
            let ch = text[i..].chars().next().unwrap();
            i += ch.len_utf8();
        }
    }

    match out {
        Some(mut buf) => {
            buf.push_str(&text[last..]);
            if buf.len() > max_len {
                return Err(buf.len());
            }
            Ok(Cow::Owned(buf))
        }
        None => Ok(Cow::Borrowed(text)),
    }
}

// --- Emoji lookups ---

/// Look up a single-codepoint emoji (O(1) PHF).
#[inline]
pub fn lookup_emoji_single(ch: char) -> Option<&'static str> {
    emoji_data::EMOJI_SINGLE.get(&ch).copied()
}

/// Look up a multi-codepoint emoji sequence by its hex-underscore key (O(1) PHF).
/// **Test-only**: the production matcher walks the code-point trie
/// (`match_emoji_sequence`); this is retained as the equivalence oracle (#242
/// item 4), so the PHF is excluded from the shipped binary.
#[cfg(test)]
pub fn lookup_emoji_multi(key: &str) -> Option<&'static str> {
    emoji_data::EMOJI_MULTI.get(key).copied()
}

/// Walk the multi-codepoint emoji trie (#242 item 4) for the longest sequence
/// starting at `window[0]`, returning `(name, codepoints_consumed)`.
///
/// Byte-identical to the former per-length hex-key PHF probe (verified by
/// `emoji_trie_matches_phf` against [`lookup_emoji_multi`]). A sequence is a
/// match only at a terminal node of length ≥ 2 whose **last** code point is not
/// ZWJ/VS-15/VS-16 — replicating the original "skip incomplete sequences" rule
/// (a trailing variation selector or ZWJ is a presentation/joiner mark handled
/// by the surrounding loop, not part of the matched sequence).
pub fn match_emoji_sequence(window: &[char]) -> Option<(&'static str, usize)> {
    use emoji_data::{
        EMOJI_MULTI_TRIE_EDGE_CP as EDGE_CP, EMOJI_MULTI_TRIE_EDGE_START as EDGE_START,
        EMOJI_MULTI_TRIE_EDGE_TARGET as EDGE_TARGET, EMOJI_MULTI_TRIE_NODE_VALUE as NODE_VALUE,
        EMOJI_MULTI_TRIE_VALUES as VALUES,
    };
    const ZWJ: u32 = 0x200D;
    const VS15: u32 = 0xFE0E;
    const VS16: u32 = 0xFE0F;

    let mut node = 0usize;
    let mut best: Option<(&'static str, usize)> = None;
    for (i, &c) in window.iter().enumerate() {
        let cp = c as u32;
        let start = EDGE_START[node] as usize;
        let end = EDGE_START[node + 1] as usize;
        match EDGE_CP[start..end].binary_search(&cp) {
            Ok(idx) => node = EDGE_TARGET[start + idx] as usize,
            Err(_) => break,
        }
        // len = i + 1 (≥ 2 for any real sequence); skip a terminal whose last
        // code point is a trailing ZWJ/VS — those never end a complete key.
        if i >= 1 && cp != ZWJ && cp != VS15 && cp != VS16 {
            let vidx = NODE_VALUE[node];
            if vidx != u32::MAX {
                best = Some((VALUES[vidx as usize], i + 1));
            }
        }
    }
    best
}

/// Check if a codepoint can start a multi-codepoint emoji sequence.
#[inline]
pub fn is_emoji_multi_starter(ch: char) -> bool {
    emoji_data::EMOJI_MULTI_STARTERS.contains(&ch)
}

/// Maximum length of any multi-codepoint emoji sequence.
///
/// `const fn` so it can seed compile-time constants (e.g. `emoji::MAX_WINDOW`)
/// from this single source of truth rather than a duplicated literal.
#[inline]
pub const fn max_emoji_seq_len() -> usize {
    emoji_data::MAX_EMOJI_SEQ_LEN
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn packed_hangul_matches_romanize_hangul() {
        // #237 item 3: the packed blob + offset lookup must return exactly what
        // the arithmetic `romanize_hangul` produces, for every one of the 11,172
        // precomposed syllables (and the offsets must stay in bounds).
        for i in 0..HANGUL_SYLLABLE_COUNT as u32 {
            let ch = char::from_u32(0xAC00 + i).unwrap();
            let expected = hangul::romanize_hangul(ch).unwrap();
            assert_eq!(
                lookup_hangul_static(ch),
                Some(expected.as_str()),
                "packed Hangul lookup diverged at U+{:04X}",
                0xAC00 + i
            );
        }
    }

    #[test]
    fn builtin_langs_is_sorted() {
        // list_langs() binary-searches BUILTIN_LANGS (#252 O5.5); guard that it
        // stays sorted and unique so a future unsorted insertion can't silently
        // break the search.
        assert!(
            BUILTIN_LANGS.windows(2).all(|w| w[0] < w[1]),
            "BUILTIN_LANGS must be sorted and unique for binary_search"
        );
    }

    fn tbl(pairs: &[(&str, &str)]) -> HashMap<String, String> {
        pairs
            .iter()
            .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
            .collect()
    }

    // Convenience: run replace_longest_match with no size limit and unwrap.
    fn rlm<'a>(text: &'a str, t: &HashMap<String, String>) -> Cow<'a, str> {
        replace_longest_match(text, t, usize::MAX).expect("no size limit")
    }

    #[test]
    fn automaton_matches_longest_scan() {
        // #242 item 1: the aho-corasick LeftmostLongest automaton must produce
        // byte-identical output to the reference longest-match scan across a
        // range of tables (overlapping prefixes, no-cascade, zero-len key,
        // multibyte) and inputs — including the size-cap behaviour.
        let tables = [
            tbl(&[("ab", "X"), ("abc", "Y")]),
            tbl(&[("a", "b"), ("b", "c")]),
            tbl(&[("@", "(at)"), ("\u{3a9}", "OMEGA")]),
            tbl(&[("aa", "1"), ("a", "2"), ("aaa", "3")]),
            tbl(&[("", "skip"), ("x", "Y")]),
            tbl(&[("\u{5317}\u{4eac}", "beijing"), ("\u{5317}", "north")]),
            tbl(&[("the", "T"), ("he", "H"), ("t", "_")]),
        ];
        let inputs = [
            "",
            "abcd",
            "abx",
            "aaaa",
            "aaaaa",
            "ab",
            "x\u{5317}\u{4eac}y\u{5317}z",
            "the theatre",
            "@a@",
            "\u{3a9}\u{3a9}",
            "no match here",
            "aaabaaa",
            "ababab",
        ];
        for t in &tables {
            let automaton = build_replacement_automaton(t);
            for inp in inputs {
                let reference = replace_longest_match(inp, t, usize::MAX).expect("oracle");
                let got = match automaton.as_ref() {
                    Some(a) => replace_with_automaton(inp, a, usize::MAX).expect("automaton"),
                    None => Cow::Borrowed(inp),
                };
                assert_eq!(got, reference, "automaton != scan for input {inp:?}");
                // The size cap must also agree (Ok/Err and the reported size).
                assert_eq!(
                    automaton
                        .as_ref()
                        .map_or(Ok(Cow::Borrowed(inp)), |a| replace_with_automaton(
                            inp, a, 4
                        )),
                    replace_longest_match(inp, t, 4),
                    "size-cap disagreement for input {inp:?}"
                );
            }
        }
    }

    #[test]
    fn test_replace_longest_match_basic() {
        let t = tbl(&[("@", "(at)"), ("Ω", "OMEGA")]);
        assert_eq!(rlm("a@b", &t), "a(at)b");
        assert_eq!(rlm("xΩy", &t), "xOMEGAy");
    }

    #[test]
    fn test_replace_longest_match_prefers_longest() {
        // "abc" must win over "ab" at the same position; output is not rescanned.
        let t = tbl(&[("ab", "X"), ("abc", "Y")]);
        assert_eq!(rlm("abcd", &t), "Yd");
        assert_eq!(rlm("abx", &t), "Xx");
    }

    #[test]
    fn test_replace_longest_match_no_cascade() {
        // Replacing "a"->"b" must not then re-match "b"->"c".
        let t = tbl(&[("a", "b"), ("b", "c")]);
        assert_eq!(rlm("a", &t), "b");
        assert_eq!(rlm("aa", &t), "bb");
    }

    #[test]
    fn test_replace_longest_match_borrows_on_no_match() {
        // A non-empty table with no matching key must allocate nothing.
        let t = tbl(&[("zzz", "Q")]);
        assert!(matches!(rlm("hello", &t), Cow::Borrowed(_)));
    }

    #[test]
    fn test_replace_longest_match_empty_and_zero_len_key() {
        assert!(matches!(rlm("hi", &HashMap::new()), Cow::Borrowed(_)));
        // A zero-length key must be ignored (must not loop forever).
        let t = tbl(&[("", "X"), ("a", "Z")]);
        assert_eq!(rlm("ba", &t), "bZ");
    }

    #[test]
    fn test_replace_longest_match_multibyte_boundary_safe() {
        // A 2-byte key must not match starting inside a 3-byte char, and a key
        // whose byte length would land mid-char is skipped without panicking.
        let t = tbl(&[("é", "e"), ("好", "hao")]);
        assert_eq!(rlm("café 好", &t), "cafe hao");
        // Key "©" (2 bytes) vs input "★" (3 bytes): no spurious match, no panic.
        let t2 = tbl(&[("\u{00A9}", "(c)")]);
        assert_eq!(rlm("\u{2605}", &t2), "\u{2605}");
    }

    #[test]
    fn test_replace_longest_match_size_cap() {
        // A small input with a large replacement value is rejected once output
        // would exceed max_len, bounding allocation (DoS guard).
        let big = "X".repeat(100);
        let t = tbl(&[("a", big.as_str())]);
        assert!(replace_longest_match("aaaa", &t, 50).is_err());
        // Within the limit it succeeds.
        assert_eq!(replace_longest_match("a", &t, 1000).unwrap(), big);
        // No match never trips the cap even with a tiny limit (borrowed).
        assert!(matches!(
            replace_longest_match("zzz", &t, 1).unwrap(),
            Cow::Borrowed(_)
        ));
    }

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
    fn test_lang_override_tables_are_registered_and_dispatched() {
        // #74: every translit_lang_*.tsv override table must be (a) registered in
        // BUILTIN_LANGS and (b) reachable via lookup_lang — so dropping in a new override
        // file that isn't wired up fails loudly instead of silently doing nothing.
        // (build.rs auto-discovers the files; this guards the two hand-maintained sides:
        // the BUILTIN_LANGS list and the lookup_lang dispatch.)
        let data_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("src")
            .join("tables")
            .join("data");
        let mut checked = 0usize;
        for entry in std::fs::read_dir(&data_dir).expect("read data dir") {
            let fname = entry.unwrap().file_name().into_string().unwrap();
            let Some(stem) = fname
                .strip_prefix("translit_lang_")
                .and_then(|s| s.strip_suffix(".tsv"))
            else {
                continue;
            };
            let code = stem.replace('_', "-"); // file `lang_ja_kunrei` → code `ja-kunrei`
            assert!(
                BUILTIN_LANGS.contains(&code.as_str()),
                "translit_lang_{stem}.tsv exists but '{code}' is not in BUILTIN_LANGS"
            );
            // Reachability: the first override entry must resolve through lookup_lang.
            let content = std::fs::read_to_string(data_dir.join(&fname)).unwrap();
            let first = content
                .lines()
                .map(str::trim_start)
                .find(|l| !l.is_empty() && !l.starts_with('#'))
                .expect("override file has at least one entry");
            let hex = first.split('\t').next().unwrap().trim();
            let cp = u32::from_str_radix(hex, 16).expect("valid hex codepoint");
            let ch = char::from_u32(cp).expect("valid codepoint");
            assert!(
                lookup_lang(&code, ch).is_some(),
                "lookup_lang(\"{code}\", U+{cp:04X}) is None — translit_lang_{stem}.tsv not dispatched"
            );
            checked += 1;
        }
        assert!(
            checked >= 20,
            "expected ≥20 override tables, checked {checked}"
        );
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
