# Performance

translit is implemented in Rust and exposed to Python via PyO3. This page
documents measured performance characteristics against the pure-Python
libraries that translit replaces.

All numbers on this page were produced by
[pyperf](https://pyperf.readthedocs.io/) — a rigorous Python benchmarking
framework that handles warmup, calibration, and statistical analysis
automatically. Raw results are reproducible with the script in
`benchmarks/bench_pyperf.py`.

## Test environment

| Detail | Value |
|---|---|
| **Tooling** | Criterion.rs 0.5 (Rust), timeit (Python quick), pyperf 2.10 (Python rigorous) |
| **Python** | 3.10 (CPython) |
| **Build** | `maturin develop --release` (optimised profile) |

!!! note
    Numbers will differ on your hardware. Clone the repo and run
    `python benchmarks/bench_pyperf.py -o results.json` to get results for your
    environment. Always benchmark against a release build
    (`maturin develop --release`).


## Transliteration

The core value proposition. translit's `transliterate()` does more work per
character than the pure-Python alternatives — flat-array BMP lookups across 60
language tables, CJK decomposition, and script-transition spacing — yet
the compiled Rust code is faster across all scripts and input sizes.

### Python-level (end-to-end)

| Input | translit | Throughput |
|---|---|---|
| ASCII short (11 chars) | **90 ns** | 11.1M ops/s |
| Latin diacritics (42 chars) | **615 ns** | 1.6M ops/s |
| Cyrillic (45 chars) | **705 ns** | 1.4M ops/s |
| CJK (12 chars) | **640 ns** | 1.6M ops/s |
| Mixed scripts (50 chars) | **650 ns** | 1.5M ops/s |
| ASCII fast-path | **71 ns** | 14.0M ops/s |

Sustained throughput: **450M chars/sec** (Latin), **130M chars/sec** (Cyrillic),
**92.9B chars/sec** (ASCII passthrough via `isascii()` fast-path).

### vs. competitors

| Library | Latin (short) | Cyrillic (short) | Mixed (50 chars) |
|---|---|---|---|
| **translit** | **615 ns** | **705 ns** | **650 ns** |
| Unidecode | 4.41 µs | 6.49 µs | 4.95 µs |
| text-unidecode | 1.86 µs | 2.36 µs | 2.13 µs |
| anyascii | 2.22 µs | 4.00 µs | 2.66 µs |

translit is **7–9× faster** than Unidecode and **3× faster** than
text-unidecode across scripts. Throughput benchmarks show **38× faster**
than Unidecode on Latin, **18× on Cyrillic**, and **22× on mixed** text
at document scale.

### Rust-level (Criterion microbenchmarks)

| Input | Time | Notes |
|---|---|---|
| ASCII short (11 chars) | 2.4 ns | Cow::Borrowed fast-path |
| ASCII long (120 chars) | 5.9 ns | is_ascii() → immediate return |
| Latin diacritics (26 chars) | 78.4 ns | Flat BMP array lookup |
| Cyrillic (23 chars) | 169.0 ns | Flat BMP array lookup |
| CJK (8 chars) | 132.7 ns | Hanzi→Pinyin PHF dispatch |
| Mixed scripts (18 chars) | 82.9 ns | Range-based dispatch |
| Cyrillic with `lang="ru"` | 370.4 ns | Language-specific table |

Per-character table lookup latency:

| Character | Time |
|---|---|
| Latin é (U+00E9) | 0.9 ns |
| Cyrillic ж (U+0436) | 0.9 ns |
| CJK 北 (U+5317) | 7.5 ns |
| Hangul 한 (U+D55C) | 1.3 ns |
| ASCII passthrough | 1.0 ns |


## Slugification

### Python-level

| Input | translit | Throughput |
|---|---|---|
| Default slugify | **1178 ns** | 849K slugs/s |
| With options¹ | **1070 ns** | 934K slugs/s |

¹ `separator='_', max_length=30, stopwords=['the', 'a', 'and']`

Sustained throughput: **849K slugs/sec** (basic), **934K ops/sec** (with options).

### Rust-level (Criterion)

| Input | Time |
|---|---|
| ASCII title (52 chars) | 113.2 ns |
| Unicode title (mixed) | 169.9 ns |
| Long text (120 chars) | 196.3 ns |
| Bounded (max_length=30, word boundary) | 160.4 ns |

### vs. python-slugify

| Input | translit | python-slugify | Speedup |
|---|---|---|---|
| Short title (52 chars) | **0.95 µs** | 9.88 µs | **10.4×** |
| Long title (148 chars) | **0.96 µs** | 22.7 µs | **23.6×** |

translit's slugify is **10–24× faster** than python-slugify across all
tested workloads, with the advantage growing on longer input.


## Filename sanitization

`translit.sanitize_filename()` vs `pathvalidate.sanitize_filename()`:

| Input | translit | pathvalidate | Speedup |
|---|---|---|---|
| Simple (`my<file>:name?.txt`) | **0.80 µs** | 13.0 µs | **16.3×** |
| Unicode (café + brackets) | **1.30 µs** | 13.5 µs | **10.4×** |
| Adversarial (`../../etc/passwd`) | **0.85 µs** | 12.7 µs | **14.9×** |

translit is **10–16× faster** for filename sanitization. It also includes
transliteration, dot-sequence collapsing, and extension sanitisation that
pathvalidate does not — see the
[security fixes](https://github.com/raeq/translit/commit/4769499) found by
property-based testing.


## Normalization

`translit.normalize()` uses the Rust `unicode-normalization` crate
(Unicode 16.0) for all calls — both standalone and batch. This ensures
consistent results across all code paths and avoids Unicode version
mismatches between CPython's `unicodedata` (Unicode 15.1) and the Rust
crate.

`unicodedata.normalize()` is a CPython C extension that operates directly
on Python's internal string representation with zero-copy fast-path
semantics, so it is faster for standalone calls. The tradeoff is
correctness: using a single Unicode version throughout eliminates subtle
bugs where `normalize()` and `normalize_batch()` produce different results
for codepoints assigned between Unicode versions.


## Accent stripping

`translit.strip_accents()` vs a pure-Python NFD + category filter:

| Input | translit | Python NFD | Speedup |
|---|---|---|---|
| Short (42 chars) | **0.81 µs** | 3.11 µs | **3.8×** |
| Long (~1.7 KB) | **21.7 µs** | 96.1 µs | **4.4×** |

translit's `strip_accents()` is **3.8–4.4× faster** than the common
Python NFD+filter approach, even though translit performs NFD decomposition,
combining-mark removal, and NFC recomposition in Rust.


## Case folding

`translit.fold_case()` vs `str.casefold()` (CPython C builtin):

### Python-level

| Input | translit | str.casefold() | Ratio |
|---|---|---|---|
| ASCII (11 chars) | 67 ns | — | — |
| German (Straße) | 178 ns | — | — |
| Mixed scripts | 322 ns | 85 ns | **3.8× slower** |

### Rust-level (Criterion)

| Input | Time |
|---|---|
| ASCII short (11 chars) | 14.6 ns |
| ASCII long (120 chars) | 20.5 ns |
| Latin diacritics (26 chars) | 79.5 ns |
| German eszett | 27.2 ns |
| Greek | 130.3 ns |
| Mixed scripts | 56.7 ns |

`str.casefold()` is a CPython C builtin with zero allocation overhead.
translit's `fold_case()` is within 4× at the Python level, with the gap
dominated by PyO3 boundary-crossing cost. At the Rust level, `fold_case`
runs in 16–131 ns depending on input — the PHF lookup itself is fast.

Both implementations use the full Unicode CaseFolding.txt (status C + F,
1,557 mappings). translit uses a compile-time PHF table generated from
Unicode 16.0 data covering Latin, Greek (including variant forms), Cyrillic,
Armenian, Georgian Mtavruli, Cherokee, Adlam, Deseret, Osage, Warang Citi,
fullwidth Latin, and all Latin ligature expansions. Pure-ASCII strings take
a branchless fast path that skips the PHF entirely.


## Batch processing

`transliterate_batch()`, `slugify_batch()`, `normalize_batch()`, and
`strip_accents_batch()` process a list of strings in a single PyO3
boundary crossing, amortising the per-call overhead across N strings.

100 mixed-script strings (Latin, Cyrillic, CJK, mixed):

| Operation | Batch | Loop | Speedup |
|---|---|---|---|
| transliterate | **18.1 µs** | 51.5 µs | **2.8×** |

The batch API eliminates PyO3 boundary-crossing overhead per string for
transliteration. The advantage grows linearly with batch size.

Use the batch API whenever you have a list of strings to process — it is
always at least as fast as the loop, and measurably faster for short strings
where PyO3 overhead is a significant fraction of total work.


## Precompiled pipelines

| Pipeline | Time | Throughput |
|---|---|---|
| `security_clean` | **504 ns** | 2.0M ops/s |
| `ml_normalize` | **1208 ns** | 828K ops/s |
| `display_clean` | **246 ns** | 4.1M ops/s |


## Grapheme operations

| Operation | Time | Throughput |
|---|---|---|
| `grapheme_len` (emoji) | 329 ns | 3.0M ops/s |
| `grapheme_len` (ASCII) | 244 ns | 4.1M ops/s |

Rust-level (Criterion):

| Operation | Time |
|---|---|
| `grapheme_len` (ASCII) | 98.0 ns |
| `grapheme_len` (emoji) | 252.4 ns |
| `grapheme_split` (ASCII) | 274.9 ns |
| `grapheme_split` (emoji) | 510.0 ns |


## Script detection

Rust-level (Criterion):

| Operation | Time |
|---|---|
| `detect_scripts` (ASCII) | 114.3 ns |
| `detect_scripts` (mixed 3 scripts) | 292.2 ns |
| `detect_scripts` (Cyrillic pure) | 368.9 ns |
| `detect_scripts` (CJK pure) | 120.4 ns |
| `is_mixed_script` (ASCII) | 37.8 ns |
| `is_mixed_script` (mixed 3 scripts) | 22.1 ns |
| `is_mixed_script` (Cyrillic pure) | 119.1 ns |
| `is_mixed_script` (CJK pure) | 46.9 ns |


## Whitespace collapsing

Rust-level (Criterion):

| Input | Time |
|---|---|
| Messy (full strip) | 78.6 ns |
| Messy (no strip) | 79.2 ns |
| Clean passthrough | 32.9 ns |


## Summary

| Operation | vs. Competitor | Speedup |
|---|---|---|
| Transliteration (Latin, throughput) | Unidecode | **38×** |
| Transliteration (Cyrillic, throughput) | Unidecode | **18×** |
| Transliteration (mixed, throughput) | Unidecode | **22×** |
| Slugification (long) | python-slugify | **24×** |
| Filename sanitization | pathvalidate | **10–16×** |
| Accent stripping | Python NFD+filter | **3.8–4.4×** |
| Normalization (NFC) | unicodedata | slower (consistency tradeoff) |
| Case folding | str.casefold() | ~3.8× slower |
| Batch transliterate (100) | Python loop | **2.8×** |

translit is faster than every pure-Python competitor for transliteration,
slugification, filename sanitization, and accent stripping. It is slower
only for normalization and case folding, where it competes against CPython
C builtins that operate on Python's internal string representation with
zero-copy semantics.


## Optimization techniques

translit achieves these numbers through five complementary optimizations in the
Rust core and the Python bindings.

### 1. Flat BMP array (default transliteration table)

The default Unicode→ASCII transliteration table covers codepoints U+0080–U+FFFF
(the Basic Multilingual Plane above ASCII). Rather than hash each codepoint
through a PHF map, the build script emits a flat
`[Option<&'static str>; 65408]` array indexed by `(codepoint - 0x80)`. Lookups
are a single bounds check and array dereference — no hashing, no collision
handling. The array occupies ~512 KB of static data but lives in a memory-mapped
`.rodata` section that the OS pages in on demand.

This optimization delivered the largest single improvement: Latin long-text
transliteration went from **34× faster** than Unidecode (with PHF) to **38×
faster** (with the flat array). Cyrillic improved from **12× to 18×**.

### 2. Python-side ASCII fast-path

`transliterate()`, `strip_accents()`, and `normalize()` now check
`text.isascii()` (~30–50 ns CPython C call) before crossing the PyO3 boundary
(~400–800 ns). Pure-ASCII strings are returned immediately without entering
Rust. This makes the common case (already-ASCII text) effectively free:

| Function | With fast-path | Without |
|---|---|---|
| `transliterate("hello")` | **71 ns** | 615 ns |
| `strip_accents("hello")` | **36 ns** | 805 ns |

### 3. Batch APIs

`transliterate_batch()`, `slugify_batch()`, `normalize_batch()`, and
`strip_accents_batch()` accept a list of strings and process them in a single
PyO3 boundary crossing, amortising per-call overhead across N strings. For
100 mixed-script strings, batch transliteration is **2.8× faster** than
calling `transliterate()` in a Python loop.

### 4. Range-dispatch in lookup_default()

Before consulting the general transliteration table, `lookup_default()`
dispatches by codepoint range: CJK Unified Ideographs (U+3400–U+9FFF,
U+F900–U+FAFF) go directly to the Hanzi→Pinyin table; Hangul syllables
(U+AC00–U+D7AF) and compatibility jamo (U+3131–U+3163) go directly to the
algorithmic romanizer. This avoids probing the 65K-entry flat array for scripts
that have dedicated, higher-quality tables.

### 5. Consistent Rust-native normalization

`translit.normalize()` uses the Rust `unicode-normalization` crate for all
calls. While CPython's `unicodedata.normalize()` is faster for standalone calls
(it operates directly on Python's internal string buffer with zero-copy
semantics), using Rust throughout ensures Unicode version consistency: both
`normalize()` and `normalize_batch()` use the same Unicode 16.0 tables,
eliminating subtle version-mismatch bugs for codepoints assigned between Unicode
15.1 and 16.0. The Rust implementation is used by all code paths — standalone
calls, batch APIs, and precompiled pipelines (`security_clean`, `ml_normalize`,
`catalog_key`, `TextPipeline`).

### 6. Full Unicode case folding via PHF

`fold_case()` uses a compile-time PHF table generated from all 1,557 status-C
and status-F entries in Unicode 16.0 CaseFolding.txt, replacing the previous
8-entry hand-coded match + `to_lowercase()` fallback. The three-tier dispatch:

1. **Pure-ASCII fast path**: `text.is_ascii()` → `to_ascii_lowercase()` with no
   PHF probe.
2. **Per-character ASCII check**: inline `ch.to_ascii_lowercase()` for A–Z — no
   table lookup.
3. **PHF lookup**: O(1) for all 1,557 Unicode case folding mappings.
4. **Identity fallback**: characters not in the table map to themselves — no
   `to_lowercase()` iterator allocation.

This covers 175 characters where `char::to_lowercase()` gives incorrect results
for case folding (µ→μ, ſ→s, ς→σ, Greek variant forms, etc.) and all 104
multi-character expansions (ß→ss, İ→i̇, ﬁ→fi, Armenian և→եւ, etc.).


## Running benchmarks

```bash
# Install dependencies
pip install pyperf Unidecode text-unidecode anyascii python-slugify pathvalidate

# Build in release mode (critical for accurate results)
maturin develop --release

# Full rigorous run (~15 min)
python benchmarks/bench_pyperf.py -o results.json

# Quick sanity check (~5 min)
python benchmarks/bench_pyperf.py --fast -o results.json

# View results
python -m pyperf stats results.json

# Compare two runs (e.g. before/after optimisation)
python -m pyperf compare_to baseline.json improved.json
```

The benchmark script (`benchmarks/bench_pyperf.py`) covers transliteration,
slugification, normalisation, filename sanitisation, accent stripping, and
case folding across multiple input sizes and scripts.


## Methodology

- **Framework**: [pyperf](https://pyperf.readthedocs.io/) with automatic
  calibration of loop count, warmup, and run count.
- **Statistical model**: Each benchmark reports mean ± standard deviation
  across multiple process invocations (not just in-process loops), reducing
  the impact of GC, JIT warmup, and OS scheduling.
- **Reproducibility**: Run `python -m pyperf system tune` before benchmarking
  for lowest-variance results. The `--fast` flag trades statistical
  confidence for speed during development.
- **Input selection**: Short inputs (12–52 chars) represent per-record
  processing; long inputs (0.8–1.7 KB) represent document/batch processing.
