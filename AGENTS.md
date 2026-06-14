# AGENTS.md — disarm

> Canonical guidance for AI coding agents (and humans) working in this repo.
> This is the single source of truth. Tool-specific entrypoints (e.g. a root
> `CLAUDE.md`) should be symlinks to this file so guidance never drifts.

## Project overview

disarm is a Unicode canonicalization and UTS-39 confusable-analysis library:
building blocks for text-security pipelines (homoglyph / bidi / zalgo /
invisible-character handling) plus standards-based transliteration.

This is a **monorepo**: a single pure-Rust core (`_disarm`) plus per-language
bindings that live alongside it. Python is the first binding (a PyO3 extension
exposing the `disarm` package), and **more language bindings will be added**.
Keeping the core and all bindings in one repo is a deliberate choice to stop the
bindings drifting from each other. The rules that follow from that:

- The **Rust core is the single source of truth.** Behaviour lives in the core,
  not in a binding; each binding is a thin, faithful surface over it.
- All bindings share the same generated tables/data and must uphold the same
  invariants (I1–I7).
- When you add or change behaviour, change the core and update **every** binding
  (plus its tests) in the **same** PR — never let one language get ahead of the
  others.

## Repository map

- `src/` — Rust core (`api.rs`, `confusables.rs`, `context.rs`, `emoji.rs`,
  `encoders.rs`, `case_fold.rs`, …)
- `src/tables/` — generated lookup tables; `src/tables/data/*.tsv` are the
  **source** TSVs that `build.rs` compiles into PHF tables at build time
- `build.rs` — generates the PHF tables from the TSVs and runs compile-time
  assertions
- `python/disarm/` — Python binding (package + type stubs); `_core.abi3.so` is
  the built extension. Future language bindings get their own sibling top-level
  dir (e.g. `node/`, `ruby/`), each a thin surface over the same Rust core.
- `scripts/` — `bootstrap_dicts.sh`, `audit_language_consistency.py`,
  `build_{arabic,persian,hebrew}_dict.py`, `extract_phf_data.py`, …
- `data/` — **gitignored** built context dictionaries (`*_dict.bin`) plus
  corpora / CLDR sources
- `tests/` — Rust integration tests (incl. `exhaustive_transliterate`)
- `benchmarks/`, `fuzz/`, `docs/`, `examples/` — perf, fuzzing, docs, usage

## Build & Test (everyday)

Since #38/#42 the **default build is the pure Rust core** (`default = []`, no
pyo3, no libpython). The Python extension is opt-in behind the
`extension-module` feature (maturin / pyproject set it).

```bash
# Rust — pure crates.io core (no pyo3 needed; this is the default now)
cargo test                          # or: cargo test --no-default-features (identical)

# Python extension — built/linked by maturin (which enables extension-module)
maturin develop && pytest           # pytest needs maturin develop first
```

Do **not** run `cargo build` / `cargo test --features extension-module`
directly: that links the cdylib without libpython and fails at the link step
(pyo3's extension-module mode expects the interpreter to provide the symbols).
Use maturin for the extension.

## Test architecture

Three tiers (full detail in **CONTRIBUTING.md → "Test architecture"**):

### Tier 1: CI (fast, deterministic)
- **Rust unit + integration**: ~630 tests — `cargo test --no-default-features`
- **Python pytest**: ~2,200 deterministic tests —
  `pytest -m "not formal and not hypothesis"`
- **build.rs compile-time assertions**: always-on, zero runtime cost

### Tier 2: Hypothesis / property-based (developer worktree only)
- ~440 tests marked `@pytest.mark.hypothesis` — property/fuzz testing across the
  full Unicode input space
- Run: `pytest -m hypothesis` (plain `pytest` includes them). Excluded from CI:
  slow (~42s), non-deterministic, costly.

### Tier 3: Formal / pre-release (gated, opt-in)
- **Rust exhaustive domain tests**: 16 tests marked `#[ignore]` (all 11,172
  Hangul syllables, full BMP, all CJK ideographs, 15 Indic blocks) —
  `cargo test --no-default-features --test exhaustive_transliterate -- --ignored`
- **Python formal invariant tests**: 12 tests marked `@pytest.mark.formal`
  (invariants I1–I7) — `pytest -m formal`

**Rule: do NOT remove `#[ignore]`, `@pytest.mark.formal`, or
`@pytest.mark.hypothesis` from these tests.** They are excluded from CI
intentionally. New property-based tests must be marked
`pytestmark = pytest.mark.hypothesis`.

### Pre-release verification (all tiers)
```bash
PYO3_PYTHON=$(which python3) cargo test --no-default-features
PYO3_PYTHON=$(which python3) cargo test --no-default-features --test exhaustive_transliterate -- --ignored
pytest
pytest -m formal
```

## Git workflow

**All changes go through pull requests.** Direct pushes to `main` are blocked by
branch protection.

1. Branch: `git checkout -b <branch-name>`
2. Commit on the branch
3. `gh pr create --repo raeq/disarm`
4. Resolve **every** review thread — GitHub's "Require conversation resolution
   before merging" blocks the merge while any thread is open
5. Wait for required checks ("Rust checks passed", "Python checks passed") to go
   green
6. Merge

Never push directly to `main` — it will be rejected.

## Pre-push gate (run locally before pushing)

CI rejects anything that fails these — run them locally first, don't push and
wait. The full step-by-step (auto-fix passes, ordering, rationale) lives in
**CONTRIBUTING.md → "Linting and formatting" / "Submitting changes"**.

```bash
git pull --rebase origin main           # 0. sync before pushing a stale branch

# Rust — lint BOTH feature sets; build/test the pure core, extension via maturin
cargo fmt --all -- --check
cargo clippy --all-targets -- -D warnings                       # pure core
cargo clippy --all-targets --features extension-module -- -D warnings  # bindings
cargo test
maturin develop && pytest

# Python
ruff check . && ruff format --check .
mypy python/disarm --ignore-missing-imports
python scripts/audit_language_consistency.py
```

Acceptance gate (#38) — the pure dependency tree must carry no pyo3:

```bash
cargo tree -e no-dev | grep -qi pyo3 && echo "pyo3 leaked!" && exit 1 || true
```

## Context dictionaries (Arabic / Persian / Hebrew)

Enable `transliterate(text, context=True)` for abjad scripts. **Not committed** —
built reproducibly from source corpora.

```bash
bash scripts/bootstrap_dicts.sh         # download corpus + build + verify checksum
bash scripts/bootstrap_dicts.sh verify  # verify existing dicts match expected checksums
```

Requires `pip install kaggle` + Kaggle API credentials.
`scripts/bootstrap_dicts.sh` is the single source of truth for dictionary
production: same corpus + same parameters = same binary = same SHA256. Never
hand-edit dictionary files. All outputs (`data/corpora/`, `data/*_dict.bin`,
`data/*_dict_stats.json`) are gitignored.

## Code conventions

- Crate name: `_disarm` (PyO3 cdylib + lib)
- `default = []` is the pure Rust core (no pyo3); the Python extension is the
  `extension-module` feature (links libpython — build via maturin, #38/#42)
- TSV data lives in `src/tables/data/`; build.rs generates PHF tables from it
- `unsafe_code = "forbid"` — no unsafe anywhere
- All transliteration table values must be ASCII (enforced by build.rs at
  compile time)
- **Boy Scout / broken-windows rule:** if you touch an area and find something
  broken or sub-standard (incl. lints that only fire under
  `cargo clippy --all-targets`), fix it in the same change rather than stepping
  around it. See CONTRIBUTING.md → "Leave it better than you found it".
