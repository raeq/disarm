# Performance harness — measurement methodology

This harness exists so optimization PRs make **logically valid** performance
claims, not just "a number." The governing rule (see issue #234, read body +
thread as one unit): an absolute measurement `T(machine, version)` is confounded
by *both* arguments, so **absolute timings never transfer across machines** —
they are valid only same-machine, same-session, pre/post. The cross-run unit is
a **ratio** (disarm vs a pinned comparator, or PR vs merge-base), measured in
one session, and even then comparable only **within an identical fingerprint
bucket** (same corpus, microarch, interpreter). Nothing absolute is ever
committed; measurements live on the orphan `perf-results` branch keyed by the
fingerprint.

## Layout

| File | Purpose |
|------|---------|
| `benchmarks/bench_core.rs` | short-string criterion benches (per-call constants) |
| `benchmarks/bench_personas.rs` | ~16 KiB document benches, one group per optimization finding |
| `benchmarks/persona_corpus.rs` | shared deterministic corpus + `corpus_digest()` (V6); imported byte-identically by the benches and the workload |
| `examples/perf_workload.rs` | `perf stat` workload binary; `--fingerprint` emits the Rust half of the fingerprint (V5/V6) |
| `scripts/perf_stat.sh` | Linux counter sweep → `target/perf-stat/` (IPC, branch-miss %, L1d-miss %) |
| `scripts/perf_fingerprint.py` | emits the full measurement fingerprint as one JSON record (V5) |
| `requirements/bench.txt` | hash-locked comparator environment (V7); install with `--require-hashes` |
| `benchmarks/bench_pyperf.py` etc. | Python-side / FFI-inclusive benchmarks |

## The validity model — four signals (capstone of #234)

Each signal answers a different question and has a different validity and role.
**Gate at doc scale**: a Rust-core win is a doc-scale phenomenon; short-string
numbers are FFI-dominated and must never gate a core cluster.

| Signal | Metric | Scale | Validity | Role |
|---|---|---|---|---|
| iai-callgrind (`--cache-sim`) | **estimated cycles** | doc-scale subset | deterministic; machine-independent *within an ISA* | **hard gate** — may fail a PR (V10) |
| disarm(PR) vs disarm(merge-base), interleaved one session | wall-clock | doc-scale | first-order noise-cancel; no comparator HW-sensitivity | **primary regression signal — flag only** (V13) |
| disarm vs pinned comparators, interleaved | wall-clock ratio | doc-scale, bucketed by microarch + CPython | cross-arch "claim" | **informational — flag only** (V14) |
| short-string per-call | wall-clock | short | FFI-dominated | **report-only; never a gate** (V15) |

- The hard gate is **directional**: it fails only on regression beyond
  threshold, never on improvement or a neutral change (V11). Raw instruction
  count is *not* the gated metric anywhere — estimated cycles (with cache
  simulation) is, so cache-layout work (cluster C / #237) is visible to the gate.
- The gate reference is `merge-base(origin/main, HEAD)`, **both sides built in
  the same job with the same rustc** (the crate is compiled twice; dependency
  caching is fine, the double build is not) (V12).
- `ftfy` is a normalizer, not a transliterator: it appears only on the
  `normalize` / `security_clean` axis, never in a transliterate-axis ratio (V16).

## Local loop (fast, same-machine — the engineering delta)

Keep it sub-minute or it rots. Criterion baselines live in `target/` (gitignored)
— they are **local only and never committed**:

```bash
# before a change — record a LOCAL baseline:
PYO3_PYTHON=$(which python3) cargo bench --no-default-features \
    --bench bench_personas -- --save-baseline pre
# after — compare on the SAME box:
PYO3_PYTHON=$(which python3) cargo bench --no-default-features \
    --bench bench_personas -- --baseline pre
```

This answers only "did it get faster on *this* box." It is not a cross-machine
claim and its numbers are not committed.

## Fingerprint (V5/V6) — every measurement is bucketed

```bash
# Rust half (runtime corpus digest + build target):
cargo run -q --release --no-default-features --example perf_workload -- --fingerprint
# full record (merges host / rustc / CPython / comparator versions):
python scripts/perf_fingerprint.py --json
```

The corpus digest is hashed from the *generated* bytes at run time (change one
seed → the digest changes), so a corpus-generator change can never masquerade as
a performance change. Two measurements are comparable only if their fingerprints
agree on corpus digest, build arch, CPU microarch, and CPython build.

## Hardware counters (Linux only) — mechanism attribution, not a delta

```bash
scripts/perf_stat.sh            # default 2000 iters/run
cat target/perf-stat/summary.txt
```

IPC, branch-miss %, and L1d-miss % explain *which mechanism paid*; they are
same-box diagnostics and are never compared across runs (a cache-miss rate is
even more machine-specific than wall-clock).

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

## Notes for implementers

- **Allocation counts** (cluster B / #236): criterion measures time, not allocs.
  Use `valgrind --tool=dhat` (Linux) or `dhat`-rs on `perf_workload` to count
  allocations per persona at short scale — a candidate deterministic hard-gate
  if alloc-gating is ever wanted (fifth signal row).
- **Cold-start**: the Hangul `OnceLock` build and context-dict parse are
  first-call costs invisible to steady-state benches. Measure with
  `perf stat -- target/release/examples/perf_workload hangul_doc transliterate 1`
  vs `... 2` and subtract.
- **Global-state ordering**: `bench_personas` registers a test language
  (`x-bench`) and replacements (©/™/€) in-process. The `replacements` group runs
  last and `transliterate_impl` does not consult the replacement table (only the
  PyO3 wrappers do), so groups do not contaminate each other — preserve that
  ordering if you add groups.

## Provenance

Corpus seeds are synthetic but script-representative; swap in real corpus
excerpts if license permits — keep them deterministic, and remember the digest
will change (which is the point). The cluster PRs (#235–#242, #252) cite the
#234 capstone as their measurement contract.
