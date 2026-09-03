# Architecture: Data Tables, PHF & Caching

How disarm stores, generates, and caches its Unicode lookup tables.

## Build-time PHF generation

All static lookup tables are generated at build time by `build.rs`, avoiding proc-macro overhead from `phf_macros`. The build script reads TSV data files from `src/tables/data/`, computes perfect hash functions via `phf_codegen`, and writes Rust source to `$OUT_DIR`. Source modules then `include!()` the generated code.

Cargo caches build script output. Incremental rebuilds that touch only Rust source files skip PHF generation entirely — `build.rs` only re-runs when data files change.

### Data file format

All data files are simple TSV:

- **char→str maps**: `HEXCODEPOINT\tvalue` (e.g., `00E9\te` for é→e)
- **str→str maps**: `key\tvalue` (e.g., `1F468_200D_2695_FE0F\tman health worker`)
- **char sets**: one `HEXCODEPOINT` per line

## Flat BMP array (default transliteration)

The default Unicode→ASCII table covers U+0080–U+FFFF (the Basic Multilingual Plane above ASCII). Instead of a PHF map, the build script emits a flat `[Option<&'static str>; 65408]` array indexed by `(codepoint - 0x80)`. Lookup is a bounds check and a pointer dereference — no hashing, no collision handling.

The array occupies ~512 KB of static data in the `.rodata` section, which the OS pages in on demand. This delivered the largest single performance improvement: Latin transliteration went from 34× faster than Unidecode (with PHF) to 53× faster (with the flat array).

## PHF maps for specialized data

Data that doesn't map cleanly to a flat array uses `phf::Map` — or `phf::Set` where
membership is the whole question and there is no value to store:

| Table | Key type | Entries | Purpose |
|---|---|---|---|
| Hanzi pinyin | `char` | ~21K | CJK ideograph → pinyin |
| Confusables (Latin) | `char` | 2,356 | TR39 + supplement (#342) + measured-visual (#738) + attested (#597) + ICANN LGR (#831) → Latin |
| Confusables (Cyrillic) | `char` | ~1,352 | TR39 confusable → Cyrillic |
| Upstream confusable sources | `char` (set) | 6,565 | Coverage denominator (#563) |
| Case folding | `char` | 1,557 | Unicode CaseFolding.txt |
| Emoji single | `char` | 1,727 | Single-codepoint emoji → name |
| Emoji multi | `&str` | 2,553 | Multi-codepoint sequences → name |
| Language tables | `char` | varies | 16 language-specific overrides |

All PHF lookups are O(1) with zero runtime allocation.

### The coverage denominator is a set, not a map

`UPSTREAM_CONFUSABLE_SOURCES` holds every *source* codepoint in the bundled upstream
`confusables.txt` — the whole 6,565, not just the ones that survive folding.
`scripts/gen_confusables.py` already read that file and discarded what it could not fold;
emitting the discard-inclusive source set turns "which confusables does disarm not fold?"
into a question the library can answer about itself.

The answer is **derived, not stored**: `unmapped_confusables(target)` is the source set
minus the resolved target map's keys, computed per call. That is deliberate. One
denominator serves both target tables, closing a gap in either table automatically
shrinks the reported exposure, and there is no second artifact that can go stale against
the table it describes. It costs an allocation and a sort per call, which is the right
trade for an introspection entry point that is never on a hot path.

## Hangul romanization

Hangul syllables (U+AC00–U+D7AF) are romanized algorithmically using the Unicode decomposition formula, not table lookups. Each precomposed syllable decomposes into choseong (initial), jungseong (medial), and jongseong (final) indices, which map to Latin strings.

Results are cached via `Box::leak` into `&'static str` and stored in a `RwLock<HashMap<char, &'static str>>`. The cache is naturally bounded at ~11,172 precomposed Hangul syllables plus ~51 compatibility jamo — no eviction policy is needed.

**Design tradeoff**: the romanization is context-free (syllable-by-syllable only). Inter-syllable phonological rules like nasalization and palatalization are not applied. This is adequate for URLs and filenames but not phonetically accurate for Korean text.

## User-registered language tables

`register_lang()` stores user-provided char→string mappings in `LANG_TABLES`, a `RwLock<HashMap<String, HashMap<char, String>>>`. Reads take a read lock (zero contention in steady state); writes take a write lock (rare, typically at startup only).

### Leak cache with double-check pattern

Looking up a user-registered mapping returns `&'static str` for API compatibility with the rest of the table system. This requires `Box::leak` to convert the owned `String` to a static reference. Without caching, every call would leak a fresh clone — an unbounded memory leak in long-running servers.

The two-level cache `LANG_LEAK_CACHE` (lang → char → `&'static str`) prevents duplicate leaks:

1. **Read path** (fast): acquire read lock on cache, look up `(lang, char)`. If found, return immediately — zero allocation.
2. **Slow path**: acquire write lock, double-check that another thread didn't populate the entry while we waited, then read from `LANG_TABLES`, leak, and store.

The double-check ensures at most one thread leaks per `(lang, char)` pair under concurrent access.

### Cache invalidation

`register_lang()` acquires both locks atomically (cache lock first, then table lock) and removes the language's cache entry. This prevents a TOCTOU race where a reader could see stale cached values after re-registration.

## Global replacements

`register_replacements()` stores pre-transliteration substitution pairs in `GLOBAL_REPLACEMENTS`. These are applied as a pre-processing step before character-by-character lookup. `remove_replacement()` and `clear_replacements()` mutate the same map.
