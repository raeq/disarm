# Benchmarks

How to reproduce and extend the disarm benchmark suite.

For published results and analysis, see [Performance](performance.md).


## Benchmark suite overview

The `benchmarks/` directory contains three tiers of benchmarks:

| Script | Framework | Purpose | Typical runtime |
|---|---|---|---|
| `bench_core.rs` | [Criterion.rs](https://bheisler.github.io/criterion.rs/book/) | Pure-Rust microbenchmarks — measures core transforms without PyO3 overhead | ~2 min |
| `bench_pyperf.py` | [pyperf](https://pyperf.readthedocs.io/) | Rigorous Python-level benchmarks with statistical analysis — disarm vs competitors | ~15 min |
| `bench_quick.py` | stdlib `timeit` | Quick sanity-check timing — no external dependencies beyond disarm | ~30 sec |

Additional focused scripts:

| Script | Measures |
|---|---|
| `bench_transliterate.py` | Transliteration across scripts and input sizes |
| `bench_slugify.py` | Slugification with various option combinations |
| `bench_vs_unidecode.py` | Head-to-head comparison against Unidecode |


## Quick start

```bash
# Build in release mode (critical for accurate results)
maturin develop --release

# Quick sanity check — no extra deps needed
python benchmarks/bench_quick.py

# Full rigorous suite
pip install pyperf Unidecode text-unidecode anyascii python-slugify pathvalidate
python benchmarks/bench_pyperf.py -o results.json

# View results
python -m pyperf stats results.json
```


## Rust benchmarks (Criterion)

`bench_core.rs` measures the Rust implementation functions directly, bypassing PyO3. This isolates the algorithmic performance from boundary-crossing overhead.

Benchmark groups:

- **transliterate** — ASCII passthrough, Latin diacritics, Cyrillic, CJK, mixed-script, language-specific (`lang="ru"`)
- **table_lookup** — per-character lookup latency for Latin extended, Cyrillic, CJK, Hangul, ASCII
- **slugify** — default config, bounded with word boundary
- **fold_case** — ASCII, Latin diacritics, German eszett, Greek, mixed-script
- **whitespace** — messy input with control chars and zero-width, clean passthrough
- **scripts** — script detection and mixed-script classification
- **grapheme** — grapheme cluster length and splitting for ASCII and emoji

```bash
# Run all Criterion benchmarks
cargo bench --no-default-features

# Run a specific group
cargo bench --no-default-features -- transliterate

# Generate HTML reports (written to target/criterion/)
cargo bench --no-default-features
open target/criterion/report/index.html
```

Criterion automatically generates HTML reports with statistical analysis, violin plots, and regression detection. Reports are written to `target/criterion/` and can be served locally.

To compare before/after an optimization, run the baseline first, make changes, then run again — Criterion automatically compares against the previous run and reports regressions.


## Python benchmarks (pyperf)

`bench_pyperf.py` is the primary Python benchmark script. It uses pyperf for rigorous statistical methodology: separate process invocations per benchmark, automatic warmup calibration, and mean ± std dev across multiple runs.

Benchmark groups:

- **transliterate** — disarm vs Unidecode, text-unidecode, anyascii across Latin (short/long), Cyrillic (short/long), CJK (short/long), and mixed scripts
- **slugify** — disarm vs python-slugify with default, long-text, and options-heavy configurations
- **normalize** — disarm vs `unicodedata.normalize()` (CPython C extension)
- **filename** — disarm vs pathvalidate for simple, Unicode, and adversarial inputs
- **strip_accents** — disarm vs pure-Python NFD + category filter
- **fold_case** — disarm vs `str.casefold()` (CPython C builtin)
- **batch** — `transliterate(list)` and `slugify(list)` vs equivalent Python loops

```bash
# Full suite (~15 min, high confidence)
python benchmarks/bench_pyperf.py -o results.json

# Quick mode (~5 min, lower confidence)
python benchmarks/bench_pyperf.py --fast -o results.json

# Compare two runs (before/after optimization)
python -m pyperf compare_to baseline.json improved.json

# Detailed stats
python -m pyperf stats results.json
```


## Input corpora

Both Python and Rust benchmarks use consistent input corpora designed to exercise different code paths:

| Input | Script | Length | Exercises |
|---|---|---|---|
| Latin short | French diacritics | 42 chars | Flat BMP array lookup, accent handling |
| Latin long | French repeated ×10 | ~1.7 KB | Throughput at document scale |
| Cyrillic short | Russian text | 45 chars | Cyrillic transliteration table |
| Cyrillic long | Russian repeated ×10 | ~1.5 KB | Cyrillic throughput |
| CJK short | Chinese addresses | 12 chars | Hanzi→Pinyin PHF, script-transition spacing |
| CJK long | Chinese repeated ×10 | ~0.8 KB | CJK throughput with space insertion |
| Mixed | Latin + Cyrillic + CJK + diacritics | 50 chars | Script detection, table switching |
| ASCII | Pure English text | 11–120 chars | Fast-path bypass (no Rust entry) |

Short inputs (12–52 chars) represent per-record processing in databases and APIs. Long inputs (0.8–1.7 KB) represent document and batch processing. Both are essential — short inputs expose per-call overhead, long inputs expose algorithmic throughput.


## Methodology

- **pyperf**: Each benchmark runs in a separate process to eliminate cross-benchmark interference. pyperf automatically calibrates loop count, warmup iterations, and run count. Results report mean ± standard deviation across process invocations (not just in-process loops), reducing the impact of GC, JIT warmup, and OS scheduling.
- **Criterion**: Statistical analysis with configurable confidence intervals (default 95%). Automatic comparison against previous runs with noise threshold filtering. Violin plots show distribution shape, not just mean.
- **System tuning**: Run `python -m pyperf system tune` before Python benchmarks for lowest-variance results. For Rust, ensure `--release` profile is used.
- **Build mode**: Always benchmark release builds. `maturin develop` (without `--release`) produces debug builds that are 10–50× slower and not representative of production performance.


## Adding new benchmarks

**Python** (pyperf): Add a function `add_<name>_benchmarks(runner)` in `bench_pyperf.py` following the existing pattern, then call it from `main()`. Use the `runner.timeit()` API with pre-imported globals to avoid measuring import overhead.

**Rust** (Criterion): Add a benchmark function `bench_<name>(c: &mut Criterion)` in `bench_core.rs`, create a benchmark group, and add it to the `criterion_group!` macro. Use `black_box()` on inputs to prevent compiler optimization from eliminating the computation.
