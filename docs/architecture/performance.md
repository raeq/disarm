# Architecture: Performance

The optimization strategies behind disarm's speed against pure-Python alternatives: 24–116×
Unidecode on Latin-script text, ~13× on Cyrillic, Greek, Arabic and Hebrew, and ~2.4–4.8× on
the Indic and Southeast Asian scripts, whose romanization does work Unidecode does not
([Performance](../performance.md) has the figures and the machine they were recorded on).

## The PyO3 boundary problem

Every call from Python into Rust crosses the PyO3 boundary: argument conversion, the call itself, and result conversion back to a Python object. A native call on a short string costs a few tens of nanoseconds (`transliterate("hello")` is ~41 ns in total), so on short input the boundary, not the transliteration, is most of the cost, and anything layered on top of it shows. A Python wrapper function around the native call costs more than the call: the #469 surrogate guard, while it was one, added 70–84 ns to every call, and it is now native (#1067). Every optimization strategy below either reduces the time spent in the boundary or reduces the number of crossings.

## Optimization 1: One crossing, and the original object back

`transliterate()` is bound directly to its native entry point (#277): a call on a `str`
crosses into Rust once, with no Python function in between, and keyword defaults cost
nothing. When the engine leaves the text unchanged (pure ASCII, the common case in
English workloads) it returns the caller's own `str` object rather than a copy, so a
no-op allocates nothing. The check lives in the core, not in Python, so `lang` is still
validated on ASCII input (#197).

| Call (fresh `str` each time) | Cost |
|---|---|
| `transliterate("hello")` | ~41 ns |
| `strip_accents("hello")` | ~54 ns |

## Optimization 2: Flat BMP array

The default transliteration table covers U+0080–U+FFFF as a flat `[Option<&'static str>; 65408]` array indexed by `(codepoint - 0x80)`. Lookup is a bounds check and an array dereference — no hashing, no collision chain, no cache-unfriendly pointer chasing.

The array occupies ~512 KB in the `.rodata` section. The OS pages it in on demand; only the pages containing accessed codepoint ranges are resident in memory.

This replaced a PHF map for BMP lookups and delivered the single largest speedup: Latin transliteration went from 34× faster than Unidecode to 38× faster.

## Optimization 3: Range-based dispatch

Before consulting the flat BMP array, `lookup_default()` dispatches by codepoint range to dedicated handlers:

- CJK Unified Ideographs → Hanzi pinyin PHF table
- Hangul syllables and compatibility jamo → algorithmic romanization

This avoids probing the 65K-entry array for scripts that have their own higher-quality tables. It also means the flat array doesn't need entries for CJK/Hangul ranges, keeping it focused on Latin/Cyrillic/Arabic/Greek and other BMP scripts.

## Optimization 4: Cow<'a, str> return

`transliterate_impl()` returns `Cow<'a, str>`. When the input is pure ASCII (detected via `str::is_ascii()`), it returns `Borrowed` — a pointer to the input with no allocation. Non-ASCII input returns `Owned` with a pre-sized buffer. The Cow type is transparent to callers and avoids the cost of cloning strings that don't need modification.

## Optimization 5: Capacity pre-sizing

The output buffer is pre-sized based on the first non-ASCII character's script:

- CJK/Hangul/kana: **4×** input byte length (each character expands to a multi-letter syllable plus space)
- Everything else: **1×** input byte length (most characters map 1:1)

This heuristic eliminates reallocations for the two most common workload shapes. The cost of over-sizing (a few KB of unused capacity) is negligible compared to the cost of repeated reallocations that memcpy the entire buffer.

## Optimization 6: List input (batch processing)

`transliterate()`, `slugify()`, `normalize()`, and `strip_accents()` accept a `list[str]` and process all strings in a single PyO3 boundary crossing, with the GIL released for the compute loop. `transliterate` borrows each item's UTF-8 and hands an unchanged item back as the original object (#1069). Because a single call is already one cheap crossing, the list form saves the per-call overhead, not the work:

| `transliterate`, 100 fresh strings | List | Loop | Speedup |
|---|---|---|---|
| ASCII | 9.1 µs | 12.5 µs | 1.4× |
| Mixed scripts | 43.4 µs | 50.0 µs | 1.15× |

## Optimization 7: Consistent Rust-native normalization

`normalize()` uses the Rust `unicode-normalization` crate (Unicode 16.0) for
every input — single strings, list inputs and pipelines. The core returns ASCII
unchanged without running the normalizer (ASCII is invariant under all four forms),
and since #1064 it runs the normalizer only over the segments that can change. This
ensures consistent results across code paths and eliminates Unicode version
mismatches between CPython's `unicodedata` and the Rust crate's tables.

While CPython's `unicodedata.normalize()` is faster for single-string calls
(it operates directly on PEP 393 compact strings with zero-copy semantics),
the correctness tradeoff is worth the performance cost: using a single
Unicode version prevents subtle bugs where different code paths produce
different results for codepoints assigned between Unicode versions.

## Optimization 8: PHF for specialized data

All secondary lookup tables (Hanzi pinyin, confusables, case folding, emoji) use compile-time perfect hash functions via `phf_codegen`. PHF provides O(1) lookup with no runtime allocation, no collision handling, and deterministic performance. The tables are generated at build time by `build.rs` and embedded as static data.

## What disarm does NOT optimize

Two operations are inherently slower than their CPython C-builtin counterparts:

- **Normalization**: `unicodedata.normalize()` operates on CPython's internal string buffer without copying. disarm uses Rust for all normalization (consistency over speed — see Optimization 7).
- **Case folding**: `str.casefold()` is a CPython C builtin with zero allocation overhead. On a short string `fold_case()` is ~1.7× slower, the gap being the boundary crossing; on a paragraph it is ~1.9× faster, since #1066 answers an already-folded character from a bitmap instead of a table probe.

These gaps are acceptable because normalization and case folding are rarely the bottleneck in real workloads — transliteration and slugification dominate processing time, and disarm is ~6–11× faster than python-slugify and 2.4–116× faster than Unidecode, by script, for those.
