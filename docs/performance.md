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
| **Tooling** | pyperf 2.10, `--fast` mode (10 runs × 2 values) |
| **Python** | 3.10 (CPython) |
| **Build** | `maturin develop --release` (optimised profile) |

!!! note
    Numbers will differ on your hardware. Clone the repo and run
    `python benchmarks/bench_pyperf.py -o results.json` to get results for your
    environment. Always benchmark against a release build
    (`maturin develop --release`).


## Transliteration

The core value proposition. translit's `transliterate()` does more work per
character than the pure-Python alternatives — flat-array BMP lookups across 37
language tables, CJK decomposition, and script-transition spacing — yet
the compiled Rust code is faster across all scripts and input sizes.

### Latin diacritics

| Library | Short (42 chars) | Long (~1.7 KB) |
|---|---|---|
| **translit** | **0.43 µs** | **2.52 µs** |
| Unidecode | 4.41 µs | 133 µs |
| text-unidecode | 1.86 µs | 61.0 µs |
| anyascii | 2.22 µs | 61.1 µs |

translit is **10× faster** than Unidecode on short Latin input and
**53× faster** at document scale. It is **24× faster** than
text-unidecode and anyascii on long input.

### Cyrillic

| Library | Short (45 chars) | Long (~1.5 KB) |
|---|---|---|
| **translit** | **0.54 µs** | **7.25 µs** |
| Unidecode | 6.49 µs | 188 µs |
| text-unidecode | 2.36 µs | 68.1 µs |
| anyascii | 4.00 µs | 119 µs |

translit is **26× faster** than Unidecode and **9.4× faster** than
text-unidecode on long Cyrillic text.

### CJK (Chinese)

| Library | Short (12 chars) | Long (~0.8 KB) |
|---|---|---|
| **translit** | **0.54 µs** | **8.17 µs** |
| Unidecode | 2.04 µs | 75.8 µs |
| text-unidecode | 0.67 µs | 25.6 µs |
| anyascii | 1.28 µs | 49.1 µs |

translit is **9.3× faster** than Unidecode and **3.1× faster** than
text-unidecode on long CJK input. Note that translit produces
higher-quality Pinyin output via a dedicated Hanzi→Pinyin table.

### Mixed scripts

| Library | 50 chars |
|---|---|
| **translit** | **0.47 µs** |
| Unidecode | 4.95 µs |
| text-unidecode | 2.13 µs |
| anyascii | 2.66 µs |

**10.5× faster** than Unidecode on typical mixed-script web content.


## Slugification

`translit.slugify()` vs `python-slugify`:

| Input | translit | python-slugify | Speedup |
|---|---|---|---|
| Short title (52 chars) | **1.26 µs** | 9.88 µs | **7.8×** |
| Long title (148 chars) | **1.71 µs** | 22.7 µs | **13.3×** |
| Long + options¹ | **2.32 µs** | 23.9 µs | **10.3×** |

¹ `separator='_', max_length=30, stopwords=['the', 'a', 'and']`

translit's slugify is **8–13× faster** than python-slugify across all
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

`translit.normalize()` vs `unicodedata.normalize()` (CPython C extension):

| Input | translit | unicodedata | Ratio |
|---|---|---|---|
| Short (17 chars, NFC) | 0.08 µs | 0.03 µs | **2.6× slower** |
| Long (440 chars, NFC) | 0.37 µs | 0.32 µs | **1.2× slower** |

`unicodedata.normalize()` is a C extension that operates directly on
CPython's internal string representation with zero-copy fast-path
semantics. For standalone calls, `translit.normalize()` delegates to
`unicodedata.normalize()` to avoid unnecessary PyO3 boundary-crossing
overhead. The Rust normalisation implementation is still used internally by
precompiled pipelines (`security_clean`, `ml_normalize`, `catalog_key`,
`TextPipeline`) and the batch API, where it runs inside Rust without
repeated Python↔Rust boundary crossings.

The remaining 2.6× gap on short input is Python function-call overhead
(the `translit.normalize()` wrapper and the `text.isascii()` fast-path
check). At document scale the gap is negligible.


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

| Input | translit | str.casefold() | Ratio |
|---|---|---|---|
| Short (42 chars) | 0.29 µs | 0.14 µs | **2.1× slower** |
| Long (~1.7 KB) | 4.98 µs | 3.82 µs | **1.3× slower** |

`str.casefold()` is a CPython C builtin with zero allocation overhead.
translit's `fold_case()` is within 2× on short input and nearly equivalent
on long input. The gap narrows because translit's Rust case-folding
computation dominates the fixed PyO3 boundary cost at larger sizes.

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

| Operation | Batch | Loop | Speedup | vs. Unidecode loop |
|---|---|---|---|---|
| transliterate | **22.8 µs** | 53.8 µs | **2.4×** | **19.6×** |
| slugify | **50.9 µs** | 134 µs | **2.6×** | — |

The batch API eliminates ~310 ns of PyO3 boundary-crossing overhead per
string for transliteration (31 µs saved over 100 strings). The advantage
grows linearly with batch size — for N=1000, the overhead saving is ~310 µs.

Use the batch API whenever you have a list of strings to process — it is
always at least as fast as the loop, and measurably faster for short strings
where PyO3 overhead is a significant fraction of total work.


## Summary

| Operation | vs. Competitor | Speedup |
|---|---|---|
| Transliteration (Latin, long) | Unidecode | **53×** |
| Transliteration (Latin, long) | text-unidecode | **24×** |
| Transliteration (Cyrillic, long) | Unidecode | **26×** |
| Transliteration (CJK, long) | Unidecode | **9.3×** |
| Slugification (long) | python-slugify | **13×** |
| Filename sanitization | pathvalidate | **10–16×** |
| Accent stripping | Python NFD+filter | **3.8–4.4×** |
| Normalization (NFC) | unicodedata | 1.2–2.6× slower |
| Case folding | str.casefold() | 1.3–2.1× slower |
| Batch transliterate (100) | Unidecode loop | **19.6×** |

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
transliteration went from **34× faster** than Unidecode (with PHF) to **53×
faster** (with the flat array). Cyrillic improved from **12× to 26×**.

### 2. Python-side ASCII fast-path

`transliterate()`, `strip_accents()`, and `normalize()` now check
`text.isascii()` (~30–50 ns CPython C call) before crossing the PyO3 boundary
(~400–800 ns). Pure-ASCII strings are returned immediately without entering
Rust. This makes the common case (already-ASCII text) effectively free:

| Function | With fast-path | Without |
|---|---|---|
| `transliterate("hello")` | **51 ns** | 430 ns |
| `strip_accents("hello")` | **36 ns** | 805 ns |

### 3. Batch APIs

`transliterate_batch()`, `slugify_batch()`, `normalize_batch()`, and
`strip_accents_batch()` accept a list of strings and process them in a single
PyO3 boundary crossing, amortising the ~310 ns per-call overhead across N
strings. For 100 mixed-script strings, batch transliteration is **2.4× faster**
than calling `transliterate()` in a Python loop and **19.6× faster** than
calling `Unidecode.unidecode()` in a loop.

### 4. Range-dispatch in lookup_default()

Before consulting the general transliteration table, `lookup_default()`
dispatches by codepoint range: CJK Unified Ideographs (U+3400–U+9FFF,
U+F900–U+FAFF) go directly to the Hanzi→Pinyin table; Hangul syllables
(U+AC00–U+D7AF) and compatibility jamo (U+3131–U+3163) go directly to the
algorithmic romanizer. This avoids probing the 65K-entry flat array for scripts
that have dedicated, higher-quality tables.

### 5. CPython delegation for normalization

`translit.normalize()` delegates to CPython's `unicodedata.normalize()` for
standalone calls. CPython's C extension operates directly on Python's internal
string buffer (PEP 393 compact representation) with zero-copy fast-path
semantics for already-normalized text — there is no scenario where crossing the
PyO3 boundary to do the same work in Rust is faster. The Rust `_normalize`
implementation is still used internally by precompiled pipelines
(`security_clean`, `ml_normalize`, `catalog_key`, `TextPipeline`) and the batch
API, where normalization runs inside Rust without repeated boundary crossings.

This reduced the normalization gap from **16–18× slower** to **1.2–2.6×
slower**, with the long-text case now within measurement noise of CPython.

### 6. Full Unicode case folding via PHF

`fold_case()` uses a compile-time PHF table generated from all 1,557 status-C
and status-F entries in Unicode 16.0 CaseFolding.txt, replacing the previous
8-entry hand-coded match + `to_lowercase()` fallback. The three-tier dispatch:

1. **Pure-ASCII fast path**: `text.is_ascii()` → `to_ascii_lowercase()` with no
   PHF probe.
2. **Per-character ASCII check**: inline `(ch as u8 + 32) as char` for A–Z — no
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
