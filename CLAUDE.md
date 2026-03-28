# translit — Development Guide

## Build & Test (everyday)

```bash
# Rust (disable extension-module to avoid needing Python linkage)
PYO3_PYTHON=$(which python3) cargo test --no-default-features

# Python (requires `pip install -e .` first)
pytest
```

## Test Architecture

Tests are split into two tiers:

### Tier 1: Everyday (runs by default)
- **Rust unit + integration**: 635 tests — `cargo test --no-default-features`
- **Python pytest**: 2,256 tests — `pytest`
- **Build.rs compile-time assertions**: always-on, zero runtime cost

### Tier 2: Formal / pre-release (gated, opt-in)
- **Rust exhaustive domain tests**: 16 tests marked `#[ignore]`
  - Covers all 11,172 Hangul syllables, full BMP (63,488 chars), all CJK ideographs, 15 Indic script blocks
  - Run with: `cargo test --no-default-features --test exhaustive_transliterate -- --ignored`
- **Python formal invariant tests**: 12 tests marked `@pytest.mark.formal`
  - Verifies 7 formalized invariants (I1–I7) via exhaustive enumeration + Hypothesis
  - Run with: `pytest -m formal`

**Rule: Do NOT remove `#[ignore]` or `@pytest.mark.formal` from these tests.**
They are excluded from default runs intentionally. If you add new exhaustive or
formal tests, gate them the same way.

### Pre-release verification (all tiers)

```bash
PYO3_PYTHON=$(which python3) cargo test --no-default-features              # tier 1 Rust
PYO3_PYTHON=$(which python3) cargo test --no-default-features --test exhaustive_transliterate -- --ignored  # tier 2 Rust
pytest                                                                      # tier 1 Python
pytest -m formal                                                            # tier 2 Python
```

## Git Workflow

**All changes go through pull requests.** Direct pushes to `main` are blocked by branch protection.

1. Create a feature branch: `git checkout -b <branch-name>`
2. Commit your changes on the branch
3. Push and open a PR: `gh pr create --repo raeq/translit`
4. Wait for required status checks ("Rust checks passed", "Python checks passed") to go green
5. Merge the PR

NEVER push directly to `main` — it will be rejected.

## Pre-Push Gate (MANDATORY)

**You MUST run all linters and tests locally and confirm they pass BEFORE pushing any commit.** Do not push first and wait for CI — catch failures locally.

```bash
# 1. Rust format
cargo fmt --check

# 2. Python lint
ruff check python/ tests/

# 3. Type check
mypy python/translit --ignore-missing-imports

# 4. Python tests (at minimum the two coverage-gate files)
pytest tests/test_dynamic_coverage.py tests/test_transliterate.py -x -q

# 5. Only after all four pass:
git push
```

If any step fails, fix it before pushing. No exceptions.

## Code Conventions

- Crate name: `_translit` (PyO3 cdylib + lib)
- Crate type requires `--no-default-features` for pure Rust test/build (extension-module links Python)
- TSV data lives in `src/tables/data/` — build.rs generates PHF tables from it
- `unsafe_code = "forbid"` — no unsafe anywhere
- All transliteration table values must be ASCII (enforced by build.rs at compile time)
