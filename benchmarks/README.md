# Performance harness — measurement guide & handoff

This branch (`perf/bench-harness`) adds document-scale benchmarks and a
hardware-counter harness to guide the optimization backlog. **Every
optimization PR should land with a before/after number from this harness.**

## Layout

| File | Purpose |
|------|---------|
| `benchmarks/bench_core.rs` | Pre-existing: short-string criterion benches (per-call constants) |
| `benchmarks/bench_personas.rs` | **New**: ~16 KiB document benches, one group per optimization finding |
| `benchmarks/persona_corpus.rs` | **New**: shared deterministic corpus (used by both criterion and perf-stat paths) |
| `examples/perf_workload.rs` | **New**: CLI workload binary for `perf stat` |
| `scripts/perf_stat.sh` | **New**: counter sweep → `target/perf-stat/` (IPC, branch-miss %, L1d-miss %) |
| `benchmarks/bench_pyperf.py` etc. | Pre-existing: Python-side / FFI-inclusive benchmarks |

## Step zero (not yet done — no Rust toolchain in the authoring sandbox)

```bash
PYO3_PYTHON=$(which python3) cargo check --no-default-features --benches --examples
```

Fix anything that surfaces (likely candidates: clippy pedantic nits, a
visibility gap). Then run the full pre-push gate from CLAUDE.md before pushing.

## Baseline workflow (criterion)

```bash
# Before a change — record the baseline:
PYO3_PYTHON=$(which python3) cargo bench --no-default-features \
    --bench bench_personas -- --save-baseline pre

# After the change — compare:
PYO3_PYTHON=$(which python3) cargo bench --no-default-features \
    --bench bench_personas -- --baseline pre
```

Criterion prints per-benchmark deltas with significance tests; HTML reports
land in `target/criterion/`.

## Hardware counters (Linux only)

```bash
scripts/perf_stat.sh            # default 2000 iters/run (~32 MB processed)
cat target/perf-stat/summary.txt
```

Record IPC, branch-miss %, and L1d-miss % per persona *before* starting the
processor-level work — those three numbers decide which of the
branch/cache findings actually bind on real hardware.

## Finding → benchmark mapping

| Optimization finding | Benchmark ID(s) | Counter signature to watch |
|---|---|---|
| Per-char lang dispatch + RwLock fallback | `lang_dispatch/ru_phf_mostly_miss`, `lang_dispatch/ar_no_override_table` | instructions/byte, L1d-miss |
| Registered-lang per-char `String` clone | `lang_dispatch/registered_lang_clone_path` | instructions/byte |
| `classify_char` early-exit / block table | `doc_transliterate/default/{cyrillic,greek,arabic}_doc` | branch-miss %, instructions/byte |
| ASCII-run bulk skipping | `doc_transliterate/default/{ascii_doc,mixed_web}` | branches/byte |
| Indic virama path | `doc_transliterate/default/devanagari_doc` | branch-miss % |
| Hanzi table repack (dense u16 IDs) | `doc_transliterate/default/cjk_doc` | L1d-miss %, LLC-miss |
| Hangul packed table / compute | `doc_transliterate/default/hangul_doc` | L1d-miss % |
| `DEFAULT_BMP` two-level trie + interning | `doc_transliterate/default/{latin,cyrillic,greek}_doc` | L1d-miss % |
| `replace_longest_match` length-sort per call (→ Aho-Corasick) | `replacements/registered_no_match`, `replacements/registered_with_matches` | wall time |
| Strict-mode collect-all + double pass | `strict_scan/find_untranslatable/*` | wall time |
| Slugify ASCII-identity copies | `slugify_doc/default/ascii_doc` | wall time, allocations |
| Scalar `_strip_accents` ASCII fast path | `strip_accents/scalar/ascii_doc` | wall time |
| Pipeline step-chain buffer reuse | `presets_doc/{security_clean,search_key}` | wall time, allocations |
| Per-call constants / FFI-adjacent | `short_per_call/*`, plus `benchmarks/bench_pyperf.py` | wall time |

## Known gaps / next steps for the implementer

1. **Compile-check first** (step zero above). The harness was written against
   verified signatures but has not been built.
2. **Allocation counts**: criterion measures time, not allocs. For the
   copy-elimination findings, consider a quick `dhat`-rs run or
   `valgrind --tool=dhat` on `perf_workload` to count allocations per persona.
3. **CI regression gate**: wall-clock criterion is too noisy for CI. Add
   `iai-callgrind` (instruction-count, deterministic) over a small subset of
   `bench_personas` in a Linux CI job. Not added here to keep the diff
   reviewable.
4. **Cold-start**: the Hangul `OnceLock` build and context-dict parse are
   first-call costs invisible to steady-state benches. Measure with
   `perf stat -- target/release/examples/perf_workload hangul_doc transliterate 1`
   vs `... 2` and subtract.
5. **FFI overhead**: `benchmarks/bench_pyperf.py` already exists for the
   Python boundary; run it alongside any change to entrypoint signatures.
6. **Global-state ordering**: `bench_personas` registers a test language
   (`x-bench`) and replacements (©/™/€) in-process. The `replacements` group
   runs last and `transliterate_impl` does not consult the replacement table
   (only the PyO3 wrappers do), so groups do not contaminate each other —
   preserve that ordering if you add groups.

## Provenance

Scaffolded 2026-06-09 from the optimization review (hot-path findings,
processor-level opportunities, space-complexity review). The corpus seeds are
synthetic but script-representative; swap in real corpus excerpts if license
permits — keep them deterministic.
