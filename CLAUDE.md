# disarm — Development Guide

## Build & Test (everyday)

```bash
# Rust (disable extension-module to avoid needing Python linkage)
PYO3_PYTHON=$(which python3) cargo test --no-default-features

# Python (requires `pip install -e .` first)
pytest
```

## Test Architecture

Tests are split into three tiers:

### Tier 1: CI (fast, deterministic)
- **Rust unit + integration**: ~630 tests — `cargo test --no-default-features`
- **Python pytest**: ~2,200 deterministic tests — `pytest -m "not formal and not hypothesis"`
- **Build.rs compile-time assertions**: always-on, zero runtime cost

### Tier 2: Hypothesis / property-based (developer worktree only)
- **Python Hypothesis tests**: ~440 tests marked `@pytest.mark.hypothesis`
  - Property-based/fuzz testing across the full Unicode input space
  - Run with: `pytest -m hypothesis` (or just `pytest` which includes them by default)
  - Excluded from CI because they are slow (~42s), non-deterministic, and costly

### Tier 3: Formal / pre-release (gated, opt-in)
- **Rust exhaustive domain tests**: 16 tests marked `#[ignore = "..."]`
  - Covers all 11,172 Hangul syllables, full BMP (63,488 chars), all CJK ideographs, 15 Indic script blocks
  - Run with: `cargo test --no-default-features --test exhaustive_transliterate -- --ignored`
- **Python formal invariant tests**: 12 tests marked `@pytest.mark.formal`
  - Verifies 7 formalized invariants (I1–I7) via exhaustive enumeration + Hypothesis
  - Run with: `pytest -m formal`

**Rule: Do NOT remove `#[ignore]`, `@pytest.mark.formal`, or `@pytest.mark.hypothesis`
from these tests.** They are excluded from CI intentionally. If you add new
property-based tests, mark them with `pytestmark = pytest.mark.hypothesis`.

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
3. Push and open a PR: `gh pr create --repo raeq/disarm`
4. Address review feedback and **resolve every review thread** — the "Conversations resolved" check (#55) is a hard merge gate and stays red while any conversation is open
5. Wait for all required status checks ("Rust checks passed", "Python checks passed", "Conversations resolved") to go green
6. Merge the PR

NEVER push directly to `main` — it will be rejected.

## Pre-Push Gate (MANDATORY)

**You MUST run all linters and tests locally and confirm they pass BEFORE pushing any commit.** Do not push first and wait for CI — catch failures locally.

### Step 0: Sync with upstream

```bash
# 0. Pull and rebase from origin main (avoid pushing stale branches)
git pull --rebase origin main
```

### Rust

```bash
# 1. Ensure toolchain components are present
rustup component add rustfmt clippy

# 2. Format all code (auto-fixes formatting issues)
cargo fmt --all

# 3. Check formatting is clean (gate; exits non-zero if fmt changed anything)
cargo fmt --all -- --check

# 4. Auto-fix compiler-detectable issues
cargo fix --edition --all-targets --all-features

# 5. Run Clippy with auto-fix for fixable lints
cargo clippy --fix --all-targets --all-features --allow-dirty --allow-staged

# 6. Run Clippy in report-only mode (treat warnings as errors)
cargo clippy --all-targets --all-features -- -D warnings

# 7. Build to confirm nothing is broken post-fix
cargo build --all-targets --all-features

# 8. Run tests to confirm behaviour is preserved
cargo test --all-targets --all-features
```

### Python

```bash
# 9. Auto-fix lint issues (safe fixes only)
ruff check --fix .

# 10. Apply unsafe fixes (import reordering, pyupgrade — review diff after)
ruff check --fix --unsafe-fixes .

# 11. Format code
ruff format .

# 12. Verify: lint check with no auto-fix (exit non-zero if issues remain)
ruff check .

# 13. Verify: format check (exit non-zero if formatting would change anything)
ruff format --check .

# 14. Type check
mypy python/disarm --ignore-missing-imports

# 15. Run tests
pytest

# 16. Language/script consistency audit
python scripts/audit_language_consistency.py
```

### Push

```bash
# 17. Only after all steps pass:
git push
```

If any step fails, fix it before pushing. No exceptions.

## Context Dictionaries (Arabic/Persian/Hebrew)

Context dictionaries enable `transliterate(text, context=True)` for abjad scripts.
They are NOT committed to git — they are built reproducibly from source corpora.

**Bootstrap from zero:**
```bash
bash scripts/bootstrap_dicts.sh        # download corpus + build + verify checksum
bash scripts/bootstrap_dicts.sh verify # verify existing dictionaries match expected checksums
```

**Requirements:** `pip install kaggle` + Kaggle API credentials configured.

**Reproducibility contract:** `scripts/bootstrap_dicts.sh` is the single source of truth
for all dictionary production. All parameters (corpus source, build flags, expected
checksums) are pinned in that script. The output is deterministic — same corpus +
same parameters = same binary = same SHA256. No manual edits to dictionary files, ever.

**Files (all gitignored):**
- `data/corpora/` — downloaded corpus files
- `data/arabic_dict.bin` — compiled Arabic unigrams + bigrams
- `data/arabic_dict_stats.json` — corpus statistics

## Code Conventions

- Crate name: `_disarm` (PyO3 cdylib + lib)
- Crate type requires `--no-default-features` for pure Rust test/build (extension-module links Python)
- TSV data lives in `src/tables/data/` — build.rs generates PHF tables from it
- `unsafe_code = "forbid"` — no unsafe anywhere
- All transliteration table values must be ASCII (enforced by build.rs at compile time)
- **Boy Scout / broken-windows rule:** if you touch an area and find something
  broken or sub-standard (incl. lints that only fire under `cargo clippy
  --all-targets`), fix it in the same change rather than stepping around it. See
  CONTRIBUTING.md → "Leave it better than you found it".
