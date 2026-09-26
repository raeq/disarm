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

**Long text — document-scale throughput** (natural Wikipedia paragraphs, vs Unidecode):

| Script | Throughput | Speedup |
|---|---|---|
| Latin (German, French, Turkish, Vietnamese) | ~225M–1.3G chars/sec | **~24–116×** |
| Cyrillic (Russian, Ukrainian) | ~81M chars/sec | **~13×** |
| Greek, Arabic, Persian, Hebrew | ~69–80M chars/sec | **~12–13×** |
| Chinese, Japanese, Korean | ~46–79M chars/sec | **~9–13×** |
| Indic and Southeast Asian | ~13–27M chars/sec | **~2.4–4.8×** |

A list of 100 strings through one `transliterate` call is **~1.1–1.4×** faster than a
loop of single calls (mixed scripts to ASCII). The single call is already one crossing
that returns an unchanged `str` as itself, so the list form saves the per-call overhead
rather than work.

Latin text is fastest where the language needs fewest substitutions (German, French)
and slowest where nearly every word carries stacked diacritics (Vietnamese). Brahmic
scripts are the narrowest margin: their romanization tracks conjuncts, viramas and
vowel signs character by character, which is real work Unidecode does not do.

**Short strings — per-call, ~70–85 character inputs** (vs Unidecode):

| Input | Speedup |
|---|---|
| Latin | **~15×** |
| Mixed scripts | **~13×** |
| Greek | **~12×** |
| Cyrillic | **~11×** |
| ASCII passthrough (~57 ns) | returns the original object |

**Slugify and filename sanitisation** (per call, vs the dedicated library):

| Operation | Comparator | Speedup | Note |
|---|---|---|---|
| `slugify` | python-slugify | **~6–11×** | also transliterates accented words; ~390K slugs/sec on titles |
| `sanitize_filename` | pathvalidate | **~7–11×** | also transliterates, collapses dot-runs, sanitises extensions |

**Unidecode's own four-cell benchmark** — the cross-product of Unidecode's two entry
points (`unidecode_expect_ascii`, `unidecode_expect_nonascii`) and its two sample
inputs. disarm wins three cells and comes within 7% of the fourth:

| Cell | Ratio (Unidecode time / disarm time) |
|---|---|
| `expect_ascii` / ASCII input | **0.93×** (56.7 ns vs 53.2 ns) — Unidecode faster |
| `expect_ascii` / non-ASCII input | **8.0×** |
| `expect_nonascii` / ASCII input | **20.4×** |
| `expect_nonascii` / non-ASCII input | **5.6×** |

The cell disarm does not win is Unidecode's strongest case: pure ASCII through the
entry point that exists for it, which is one `str.encode("ascii")` in Python. disarm
answers it by returning the original object after a single call into Rust, and what
separates the two is the cost of that call. The page claimed a 1.34× win here until
2026-09; that figure predated the surrogate guard (#469), whose Python wrapper put the
cell at 0.41× until #1067 made the guard native. The clean-room replication is in
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
All of them are per-call costs on short strings, against CPython code that runs
without crossing into an extension:

| Operation | Faster tool | Why disarm trades it away |
|---|---|---|
| NFC / NFKC normalisation | `unicodedata.normalize` (C, single string) | `normalize()` uses one Unicode version (16.0) across every code path, so results never differ between CPython's bundled tables and the Rust crate's — consistency over speed |
| Case folding, short strings | `str.casefold()` (C builtin, zero-alloc) | the boundary crossing dominates a short call (~0.6× here); on a paragraph `fold_case()` is ~1.9× faster than `str.casefold()` |
| `transliterate` of pure ASCII, vs `unidecode_expect_ascii` | Unidecode (one `str.encode` in Python) | ~7% (56.7 ns vs 53.2 ns): the cost of one call into Rust, which returns the original object |

## Absolute numbers (fingerprinted, non-comparable)

Absolute figures are **not comparable across hardware**. Every figure on this page
was recorded on 2026-09-25 with the surrogate guard native (#1067) and the list
form borrowing its inputs (#1069), on one machine: an Intel Xeon at 2.10 GHz (`x86-fam6-mod207`, 4 vCPU,
cloud VM, unpinned), CPython 3.12.3 (Ubuntu build), a release build, and the pinned
comparators from `requirements/bench.txt` installed with `--require-hashes`.
Short-string ratios are the fresh-string regime (#303), median of 7 interleaved
repetitions (`benchmarks/bench_ratio.py`); the four-cell figures come from
`benchmarks/bench_unidecode_own.py`, document-scale throughput from
`benchmarks/bench_vs_unidecode.py`, and the slugify, filename and "slower" rows
from `benchmarks/bench_pyperf.py`, and the list-versus-loop figure from fresh strings
(pyperf reuses one set of `str` objects, whose cached UTF-8 flatters the loop).
**Your numbers will differ**; the ratios are the claim.

The figures published before 2026-09 came from an AMD EPYC 7763 CI bucket and are
not comparable with these. CI still records the short-string ratios in that bucket
on every push to main, on the `perf-results` branch. Emit the full environment
fingerprint — CPU microarchitecture, CPython version and build, comparator
versions, rustc version, git commit, date — that any absolute belongs to with:

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
