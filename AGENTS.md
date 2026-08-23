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
- `tests/` — Rust integration tests (incl. `exhaustive_transliterate`) + Python pytest suite (`test_*.py`)
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
- **build.rs compile-time assertions**: always-on, zero runtime cost — generated
  table values must be ASCII, including the `tr39` digit-policy overrides (#587)
- **Drift gates**: four checks compare a generated or published artifact against its
  source of truth rather than testing behaviour — the committed `disarm.h` (#580),
  `tests/test_doc_table_counts.py` over 11 documented row counts (#591), the build.rs
  ASCII assertions (#587), and `JvmSignatureTest` over the published Kotlin JVM
  signatures (#588). Two read a *build product*, not source text, which is why they
  catch what source-level assertions miss. Detail in CONTRIBUTING.md → "Drift gates"

### Tier 2: Hypothesis / property-based (developer worktree only)
- ~440 tests marked `@pytest.mark.hypothesis` — property/fuzz testing across the
  full Unicode input space
- Run: `pytest -m hypothesis` (plain `pytest` includes them). Excluded from CI:
  slow (~42s), non-deterministic, costly.

### Tier 3: Formal / pre-release (gated, opt-in)
- **Rust exhaustive domain tests**: 16 tests marked `#[ignore]` (all 11,172
  Hangul syllables, full BMP, all CJK ideographs, 15 Indic blocks) —
  `cargo test --no-default-features --test exhaustive_transliterate -- --ignored`
- **Rust exhaustive confusables**: the BMP crossed with composing marks on the
  Layer-2 API, for idempotence and residual confusability (#586) —
  `cargo test --no-default-features --release --test exhaustive_confusables -- --ignored`.
  Deliberately separate from the lib-level sweep, which tests Layer 1: testing the
  layer beneath the one the bindings call is how #586 went unnoticed for a year
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
5. Wait for the required checks — "All checks passed", "DCO sign-off" and "iai
   estimated-cycles gate" — to go green. "All checks passed" is a roll-up of the
   whole matrix (#583); the former per-language contexts no longer exist
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
python3 scripts/audit_language_consistency.py
```

Acceptance gate (#38) — the pure dependency tree must carry no pyo3:

```bash
cargo tree -e no-dev | grep -qi pyo3 && echo "pyo3 leaked!" && exit 1 || true
```

### Doc gates

CI executes the examples in `docs/` against the freshly built library, per language.
A prose change that documents a wrong result fails on its own PR, so run these
whenever you touch `docs/`, a docstring, or a public signature:

```bash
python3 scripts/check_doc_claims.py          # anti-rot doc-claim lint (#156)
python3 scripts/check_doc_rust_examples.py   # Rust examples (#50)
python3 scripts/run_doc_tests.py             # Python cookbook, per-file isolated
mkdocs build --strict                       # broken internal links, missing nav
```

`mkdocs build --strict` resolves links **relative to the docs site**, so a
`docs/`-prefixed link that works on GitHub fails here and vice versa. The
CHANGELOG convention is to name a doc path as inline code with no link, which
reads correctly in both places.

### Binding gates

Each binding is built against the **in-repo** core, not the published crate, via a
CI-injected `[patch.crates-io]` redirect (#374 drift gate). Without it you are
testing your change against the last release and a new core API will not resolve.
Inject it the same way CI does — append to the manifest, run, then revert:

```bash
# Node — the redirect goes in bindings/node/Cargo.toml
cd bindings/node
printf '\n[patch.crates-io]\ndisarm = { path = "../.." }\n' >> Cargo.toml
npm ci && npm run lint && npm run build:debug && npm test
cd ../.. && node scripts/check_doc_node_examples.mjs   # runs from the repo root
git checkout bindings/node/Cargo.toml

# Ruby — the redirect goes in the GEM ROOT workspace manifest, not ext/disarm
cd bindings/ruby
printf '\n[patch.crates-io]\ndisarm = { path = "../.." }\n' >> Cargo.toml
bundle exec rake compile && bundle exec rspec && bundle exec rubocop
cd ../.. && ruby scripts/check_doc_ruby_examples.rb
git checkout bindings/ruby/Cargo.toml

# C ABI — redirect in bindings/cabi/Cargo.toml; then the C smoke test
# Java/Kotlin — redirect in bindings/java/rust/Cargo.toml; then ./gradlew test
```

`scripts/check_doc_node_examples.mjs` evaluates each `// =>` line as a
**standalone expression** — there is no shared scope between lines, so a `const`
bound on one line is not visible to the next. Inline the call on every asserted
line.

A cheap first pass, when you only changed a core signature and want to know
whether the glue still compiles, is `cargo check` in each binding directory with
the redirect applied. That catches the common breakage without a toolchain for
every language.

### The C ABI is a committed contract

`bindings/cabi/disarm.h` is generated, and **committed** (#580). Regenerating it is part
of any change to the C surface:

```bash
cd bindings/cabi
printf '\n[patch.crates-io]\ndisarm = { path = "../.." }\n' >> Cargo.toml
cargo test --features headers -- generate_headers
git checkout Cargo.toml && git add disarm.h
```

Then read the diff. **Additive is fine; widening is not.** Adding a parameter to an
exported function breaks every caller already linked against the library — they fail at
link time, and a rebuild fails to compile. Add a new `_opts` entry point and keep the
original delegating to it, the shape `disarm_transliterate` / `disarm_transliterate_opts`
and `disarm_normalize_confusables` / `_opts` already use.

The smoke test does **not** catch this: it regenerates the header and compiles `smoke.c`
against it in the same step, so a signature change plus a matching call-site change is
self-consistent and passes. That is how a widened `disarm_normalize_confusables` reached
review on #574 with every check green. The committed header is what makes the change
visible.

### Sign-off

`DCO sign-off` is a **required** status check: every non-merge commit needs a
`Signed-off-by:` trailer matching its author. Use `git commit -s`, or
`git rebase --signoff origin/main` for commits already made. An AI assistant must
never add that trailer — see CONTRIBUTING.md → "Attribute the assistant".

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
