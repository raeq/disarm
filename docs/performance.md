# Performance

This page presents disarm's performance numbers, how to read them, and where
they are recorded. Internals (why it is fast) live in
[Architecture: Performance](architecture/performance.md); how to run and extend
the suite lives in [Benchmarks](benchmarks.md). Every figure here is a recorded,
fingerprinted measurement — absolutes are non-comparable across hardware, and
only the ratios are durable claims.

## Results

Two regimes, quoted separately because they stress different things. **Long
text** (documents, batch pipelines) is dominated by per-character lookup cost;
**short strings** (one field per call — a name, a title, a slug) are dominated
by the fixed Python→Rust crossing, which disarm pays exactly once, returning
already-ASCII input as the original `str` object.

**Long text — document-scale throughput** (vs Unidecode unless noted):

| Operation | Throughput | Speedup |
|---|---|---|
| Transliterate (Latin) | ~450M chars/sec | **~38×** |
| Transliterate (Cyrillic) | ~106M chars/sec | **~15×** |
| Slugify | ~712K slugs/sec | **~10–24×** vs python-slugify |
| Batch transliterate (100 strings) | ~2.8× vs Python loop | — |

**Short strings — per-call, ~70–85 character inputs** (vs Unidecode):

| Input | Speedup |
|---|---|
| Latin | **~17×** |
| Mixed scripts | **~14×** |
| Cyrillic / Greek | **~13×** |
| ASCII passthrough (~65 ns) | returns the original object |

**Slugify and filename sanitisation** (per call, vs the dedicated library):

| Operation | Comparator | Speedup | Note |
|---|---|---|---|
| `slugify` | python-slugify | **~10–24×** | also transliterates accented words |
| `sanitize_filename` | pathvalidate | **~10–16×** | also transliterates, collapses dot-runs, sanitises extensions |

**Unidecode's own four-cell benchmark** — disarm wins every cell of the
cross-product of Unidecode's two entry points (`unidecode_expect_ascii`,
`unidecode_expect_nonascii`) and its two sample inputs:

| Cell | Ratio (Unidecode time / disarm time) |
|---|---|
| `expect_ascii` / ASCII input | **1.34×** (65.1 ns vs 87.6 ns) |
| `expect_ascii` / non-ASCII input | **8.87×** |
| `expect_nonascii` / ASCII input | **24.58×** |
| `expect_nonascii` / non-ASCII input | **6.31×** |

The narrowest cell (1.34×) is Unidecode's strongest case — pure ASCII through
its ASCII-optimised entry point — and disarm still wins it via the
return-original-object fast path. The clean-room replication is in
[`benchmarks/bench_unidecode_own.py`](https://github.com/raeq/disarm/blob/main/benchmarks/bench_unidecode_own.py)
(only the methodology is reused; the GPL benchmark file is not copied).

## How to read these numbers

- **Ratios are the durable claim; absolutes are presentation.** Absolute
  ns / chars-per-sec figures are fingerprinted and **not comparable across
  hardware**.
- **Fresh-string regime.** Every timed call receives a newly constructed `str`,
  as production traffic does, rather than re-running one cached object (which
  would understate the pure-Python comparators). Recorded as
  `regime: fresh-string/v2` (#303).
- **Interleaved, median-of-N, pinned comparators.** Each measurement times
  disarm and the comparator back-to-back per round and takes the median, so
  transient scheduler noise cancels in the ratio. CI installs the exact versions
  in [`requirements/bench.txt`](https://github.com/raeq/disarm/blob/main/requirements/bench.txt)
  with `--require-hashes`. Our figures are rounded **down**, comparators' **up**.
- **Not a like-for-like race.** A `transliterate()` call also consults language
  override tables, applies the requested error-handling mode, and checks the
  replacement registry — work a context-free transliterator does not do. ftfy is
  a mojibake repairer, not a transliterator, and never appears in a transliterate
  ratio.

## Where disarm is slower

Visible admission of losses is the strongest defence against cherry-picking.
Both are against CPython C builtins that operate directly on the internal string
buffer — disarm cannot and does not try to beat them:

| Operation | Faster tool | Why disarm trades it away |
|---|---|---|
| NFC / NFKC normalisation | `unicodedata.normalize` (C, single string) | `normalize()` uses one Unicode version (16.0) across every code path, so results never differ between CPython's bundled tables and the Rust crate's — consistency over speed |
| Case folding | `str.casefold()` (C builtin, zero-alloc) | `fold_case()` is within a small factor and dominated by the boundary crossing; use `str.casefold()` for a single string on CPython's Unicode version |

## Absolute numbers (fingerprinted, non-comparable)

Absolute figures are **not comparable across hardware**. The short-string
figures below were recorded in the fresh-string regime (#303) on an AMD EPYC
7763 CI bucket (CPython 3.12, pinned comparators from `requirements/bench.txt`,
median-of-7 interleaved); **your numbers will differ**.

| Input (per call) | vs Unidecode |
|---|---|
| Latin diacritics (~70–85 chars) | **~17×** |
| Mixed scripts | **~14×** |
| Greek | **~13.6×** |
| Cyrillic | **~13.4×** |
| ASCII passthrough (~65 ns) | returns original object |

Document-scale throughput (same bucket): **~450M chars/sec** Latin (**~38×**),
**~106M chars/sec** Cyrillic (**~15×**), slugify **~712K slugs/sec**
(**~10–24×**). These match the figures in the project README. Emit the full
environment fingerprint — CPU microarchitecture, CPython version and build,
comparator versions, rustc version, git commit, date — that any absolute belongs
to with:

```bash
python scripts/perf_fingerprint.py --json
```

## More

- **Why it is fast** (flat BMP array, single boundary crossing, borrowed `Cow`,
  range dispatch, GIL-released batch loops): [Architecture:
  Performance](architecture/performance.md).
- **Running and extending the suite** (Criterion, pyperf, corpora, methodology):
  [Benchmarks](benchmarks.md).
- **Reproduce the headline ratios:**

```bash
pip install disarm[bench]                      # pinned, hash-locked comparators
python benchmarks/bench_ratio.py              # short-string ratios, per script
python benchmarks/bench_unidecode_own.py      # Unidecode's four-cell benchmark
python benchmarks/bench_vs_unidecode.py       # document-scale throughput
python scripts/perf_fingerprint.py --json     # record the environment
```
