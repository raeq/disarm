# Architecture: Performance

The optimization strategies that make translit 10–53× faster than pure-Python alternatives.

## The PyO3 boundary problem

Every call from Python into Rust crosses the PyO3 boundary: argument conversion, GIL management, result conversion back to a Python object. This costs ~400–800 ns per call. For a function like `transliterate()` that processes a short string in ~430 ns of actual Rust work, the boundary overhead is the dominant cost. Every optimization strategy below either reduces the time spent in the boundary or reduces the number of crossings.

## Optimization 1: Python-side ASCII fast-path

The most effective optimization is never crossing the boundary at all. `transliterate()`, `strip_accents()`, and `normalize()` check `text.isascii()` on the Python side before calling into Rust. This is a ~30–50 ns CPython C call that scans the string's internal buffer. Pure-ASCII strings (the common case in English workloads) return immediately:

| Function | With fast-path | Without |
|---|---|---|
| `transliterate("hello")` | 51 ns | 430 ns |
| `strip_accents("hello")` | 36 ns | 805 ns |

This turns the common case from a ~400 ns function call into a ~50 ns no-op.

## Optimization 2: Flat BMP array

The default transliteration table covers U+0080–U+FFFF as a flat `[Option<&'static str>; 65408]` array indexed by `(codepoint - 0x80)`. Lookup is a bounds check and an array dereference — no hashing, no collision chain, no cache-unfriendly pointer chasing.

The array occupies ~512 KB in the `.rodata` section. The OS pages it in on demand; only the pages containing accessed codepoint ranges are resident in memory.

This replaced a PHF map for BMP lookups and delivered the single largest speedup: Latin transliteration went from 34× faster than Unidecode to 53× faster.

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

## Optimization 6: Batch APIs

`transliterate_batch()`, `slugify_batch()`, `normalize_batch()`, and `strip_accents_batch()` process a list of strings in a single PyO3 boundary crossing. For 100 strings, this saves ~31 µs of boundary overhead (310 ns × 100). The saving scales linearly with batch size.

| Operation (100 strings) | Batch | Loop | Speedup |
|---|---|---|---|
| transliterate | 22.8 µs | 53.8 µs | 2.4× |
| slugify | 50.9 µs | 134 µs | 2.6× |

## Optimization 7: CPython delegation

For standalone `normalize()` calls, translit delegates to CPython's `unicodedata.normalize()` rather than crossing into Rust. CPython's C extension operates directly on Python's PEP 393 compact string representation with zero-copy fast-path semantics for already-normalized text. No Rust implementation can beat this because it would need to cross the PyO3 boundary, copy the string, normalize in Rust, then copy back.

The Rust normalization code is still used inside `TextPipeline` and batch APIs, where it runs in a Rust context without Python boundary crossings.

This reduced the normalization gap from 16–18× slower than CPython to 1.2–2.6× slower.

## Optimization 8: PHF for specialized data

All secondary lookup tables (Hanzi pinyin, confusables, case folding, emoji) use compile-time perfect hash functions via `phf_codegen`. PHF provides O(1) lookup with no runtime allocation, no collision handling, and deterministic performance. The tables are generated at build time by `build.rs` and embedded as static data.

## What translit does NOT optimize

Two operations are inherently slower than their CPython C-builtin counterparts:

- **Normalization**: `unicodedata.normalize()` operates on CPython's internal string buffer without copying. translit's Rust normalizer must copy across the PyO3 boundary. Standalone calls delegate to CPython (see above); only pipeline/batch paths use Rust.
- **Case folding**: `str.casefold()` is a CPython C builtin with zero allocation overhead. translit's PHF-based `fold_case()` is within 2× on short input, closing to ~1.3× on long input as the Rust computation dominates fixed boundary cost.

These gaps are acceptable because normalization and case folding are rarely the bottleneck in real workloads — transliteration and slugification dominate processing time, and translit is 10–53× faster for those.
