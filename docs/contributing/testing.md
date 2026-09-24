# Test architecture

Tests are organized into three tiers. **CI runs Tier 1 only** — it is fast and
deterministic. Tiers 2 and 3 are heavier and run in a developer worktree or before a
release. Please run at least Tier 1 locally before opening a PR.

## Tier 1 — CI (fast, deterministic)

What every PR must pass. Mirrors `.github/workflows/ci.yml`.

```bash
# Rust unit + integration (~1,025 tests across 23 binaries plus 12 doctests).
# --no-default-features disables the Python-linking extension-module feature.
PYO3_PYTHON=$(which python3) cargo test --no-default-features

# Python deterministic tests (~4,490). Since #658 this is what bare `pytest` runs.
pytest

# The serial tier: wall-clock parallelism tests that cannot share the box (#997 review).
pytest -m serial -n 0
```

CI's own command is `pytest tests/ --ignore=tests/test_typing.py -m "not formal and
not hypothesis and not serial"`, followed by the serial tier in a step of its own, so
the two marker expressions are **not** identical — the local default also carries
`not slow`. Nothing in that tier executes under CI conditions
regardless: measured with `CI=1` and no `bench` extra, all five slow tests skip. The
executed set matches; the expression does not, and a green local run means what a
green CI run means for that reason rather than by definition.

Counts were stale in both directions before #658 and are worth stating measured
rather than approximated, because they are how a reader notices a tier stopped
running. The three opt-in tiers below are excluded from the default by `addopts`
and each is one command away.

`build.rs` compile-time assertions are always on at zero runtime cost: they assert that
every transliteration table value is ASCII, that the `tr39` digit-policy override values
are ASCII (#587), and that entry counts match expectations. If one fails, `cargo build`
fails.

### Drift gates

Four checks in Tier 1 guard something a normal test cannot: they compare a *generated or
published artifact* against the source of truth, so they fail when the two drift apart
rather than when behaviour is wrong. Each exists because the drift they catch happened.

| Gate | Guards | Fails when |
|---|---|---|
| `bindings/cabi/disarm.h` diff (`C ABI (safer-ffi)` job) | The committed C header | An exported signature changes without the header being regenerated (#580) |
| `tests/test_doc_table_counts.py` | 32 documented row counts across 16 files | A table is regenerated and prose still quotes the old figure (#591) |
| `build.rs` ASCII assertions | Generated table values | A generated value is non-ASCII, against #341's contract (#587) |
| `JvmSignatureTest` (`Java binding (JDK …)` job) | Published JVM signatures | A Kotlin default argument deletes an arity that shipped (#588) |

Two of them read a build product rather than source text, which is the point:
`JvmSignatureTest` reflects over the compiled facade, and the header gate diffs the
regenerated header. Source-level assertions would not have caught either defect.

**When you regenerate a table, read the data diff, not just the test output.** A change to
`gen_confusables.py` can silently *remove* rows, and a passing suite does not prove it
did not — that is how an over-broad filter deleted `Ç → C` during #593.

## Tier 2 — Hypothesis / property-based (opt-in)

Property-based / fuzz tests across the Unicode input space. **587 tests, ~67s on a
release build** — the figures here read "~440 / ~40s" until #658 measured them.

```bash
pytest -m hypothesis
```

Bare `pytest` used to include these, which meant a contributor paid the tier on
every local run while no CI job ran it. `nightly-hypothesis.yml` runs it at 03:17
UTC with a freshly generated seed and a 10× oracle budget, which explores more
input space than one more fixed-seed pass ever did. Run it locally when you touch
the input-handling boundary; the nightly is the safety net.

Until the #997 review the nightly was a fixed-seed pass, twice over.
`--hypothesis-seed=random` is not a request for a random seed: Hypothesis tries
`int()` on it and, failing, seeds with the string `"random"` — the same every night.
And on GitHub Actions no seed would have helped: Hypothesis loads its own `ci` profile
whenever `CI` is set, and that profile's `derandomize=True` makes every test ignore
`--hypothesis-seed`. The workflow now generates a seed, logs it (and quotes it in the
failure issue), and runs under a `nightly` profile registered in `tests/conftest.py` —
the `ci` settings minus `derandomize`. To reproduce a nightly failure:

```bash
pytest -m hypothesis --hypothesis-profile=nightly --hypothesis-seed=<seed from the log>
```

## Tier 2b — Expensive, opt-in (`slow`)

```bash
pytest -m slow
```

The `slow` marker existed, described itself as deselectable, and nothing deselected
it (#658) — so it had no effect and everyone paid it. Both things it covers are
gated elsewhere:

- `test_cabi_header_drift` mirrors the `cabi` CI job and skips under `CI`. It costs
  a cold `cargo` build — about 25s — on the first run after a Rust change, and it
  appends a `[patch.crates-io]` block to `bindings/cabi/Cargo.toml` that an
  interrupted run leaves behind.
- `test_performance_claims`' ratio floors need the pinned comparators from the
  `bench` extra and skip without them. They also fail against a debug
  `maturin develop` build, which is a false alarm rather than a regression.

## The suite runs in parallel by default

`-n auto --dist loadfile` is in `addopts`, so bare `pytest` already uses every core.
Pass `-n 0` to turn it off when you want a debugger, or a stable test order — or when
you are running one small file. Worker startup is about 0.6s on four cores, which a
whole suite repays many times over and a single file does not: `tests/test_slugify.py`
is 1.1s under `-n auto` and 0.5s under `-n 0`. (An earlier version of this section
said a single file was, if anything, faster in parallel; it was measured on a file
heavy enough to hide the startup.)

**`--dist loadfile` is not optional.** `register_lang` mutates process-global state
that cannot be undone, so tests must stay grouped by file; per-file distribution
preserves that.

Measured on four cores, without coverage:

| | serial | `-n 2` | `-n auto` |
|---|---:|---:|---:|
| whole suite | 93.4s | 65.2s | **35.1s** |

An earlier version of this section reported serial 6.1s and concluded `auto`
over-provisions and CI should stay serial. That was true of a six-second suite and
stopped being true as it grew — the advice outlived its measurement by enough to cost
about a minute a run. If you change the suite's shape, re-measure this table rather
than trusting it.

`--dist loadgroup`, pinning only the modules that touch process-global state so the rest
distribute per test, looks like it should beat `loadfile` and does not: 45.0s, and it
fails `test_docs_index_drift`, whose tests depend on sharing a worker.

**Coverage, not the test count, is most of CI's wall clock.** `COVERAGE_CORE=sysmon`
puts coverage.py on CPython 3.12's `sys.monitoring` rather than its `settrace` hook —
120.4s against 34.6s here, with the measurement identical to the statement. CI sets it
on the test job; it needs 3.12, so it is not set in `pyproject.toml`, where a
contributor on 3.10 would meet a fallback warning.

**Anything that spawns pytest per file must pass `-n 0`.** `scripts/run_doc_tests.py`
runs one pytest process per doc page, several at once; each inherited `-n auto` and
started a full set of workers to run a handful of examples — 34.8s for the whole run,
against 5.8s with `-n 0`. Use `-n 0`, not `-p no:xdist`: unloading the plugin leaves
the `-n auto` in `addopts` as an unrecognised option.

### The `serial` tier

A test that measures wall-clock parallelism cannot run beside xdist workers. #70's
GIL-release guard asserts that two threads finish two batches faster than one thread
can, which needs an idle core, and under `-n auto` every core has a worker on it. It
used to skip itself in that case — correct, and it meant CI, which runs `-n auto`, never
ran it at all.

Those tests are marked `@pytest.mark.serial`. `addopts` deselects them, CI's parallel
step deselects them in its own `-m`, and a separate CI step runs `pytest -m serial -n 0`
with the runner to itself. `tests/test_serial_tier.py` fails if any of the three goes
missing. Locally, run `pytest -m serial -n 0`. The guard counts the cores in the
process's affinity mask (`taskset`, a container's cpuset), not the host's, and still
skips below two.

## Don't let a stray virtualenv into the corpus

Two modules walk the whole tree — `test_code_context_profile` and
`test_tree_invisible_characters` — and both filter it through `conftest.in_skipped_dir`,
which finds virtual environments by `pyvenv.cfg` rather than by the name `.venv`.
(`test_scan` also mentions `.venv`, but it exercises the shipped scanner's own skip list
inside a `tmp_path` and never touches the repository.) An environment called `venv/`,
`env/`, `.tox/` or `.venv312/` would otherwise put site-packages in the corpus: slower,
and a false positive waiting for the first dependency that ships a literal bidi control
in a fixture.

Three details, each of which was once wrong:

- An environment is a **path**, not a name. A file is skipped when one of the detected
  directories contains it, so tox's `.tox/docs` does not take this repository's `docs/`
  with it.
- Skip names are matched against the path **inside the repository**, never the absolute
  one. Matching the absolute path emptied the corpus of any checkout under a directory
  called `build`, `tmp` or `pkg`.
- `.venv` is still skipped **by name** at any depth, alongside the marker: a conda
  environment has no `pyvenv.cfg`, and the marker search only goes two levels down.

`tests/test_corpus_excludes_virtualenvs.py` runs each module's own collector over
synthetic trees for all of this, so it checks the property on every run — including CI,
where there is no virtual environment in the checkout to catch.

## Tier 3 — Formal / pre-release (gated, opt-in)

Exhaustive enumeration — every Hangul syllable (11,172), the full BMP (63,488 code
points) both bare and crossed with composing marks, all CJK ideographs, 15 Indic blocks
— plus the seven formalized invariants (I1–I7). `.github/workflows/tier3.yml` runs the
same set.

Three of these now run in **PR CI** rather than only here (#658): the
transliterate, grapheme and width targets cost 0.62s against a profile the `test`
job has already built, so a regression in them surfaces on the pull request that
caused it. `width_conformance` was in no workflow and no documented gate before
that, so nothing had ever run it.

The three of them in one invocation, which is how CI runs them — each
`cargo test` repeats metadata resolution, so three invocations cost more than
three times the test time suggests:

```bash
# exhaustive_transliterate (16 tests), exhaustive_grapheme (#174, 4),
# width_conformance (#224, 1). All #[ignore]d; all also run in PR CI.
cargo test --no-default-features \
  --test exhaustive_transliterate \
  --test exhaustive_grapheme \
  --test width_conformance \
  -- --ignored

# Confusables on the Layer-2 API: the BMP crossed with composing marks, checked for
# idempotence and for output that is still confusable (#586). Deliberately separate
# from the lib-level sweep below, which tests Layer 1 — testing the layer beneath the
# one the bindings call is how #586 survived a year. The same file sweeps
# `skeleton_key` for idempotence over every scalar, and over the BMP crossed with
# every composing mark with and without a control between (F1 of the Lean model in
# formal/lean/Confusables). Under --release that is about a minute; the fold sweeps
# alone take about a second.
cargo test --no-default-features --release \
  --test exhaustive_confusables -- --ignored

# The anomaly detector gives NFC and NFD spellings one verdict, over every Unicode scalar
# alone and in seven contexts (Finding 3 of the Lean model in formal/lean/Detection).
# PR CI runs the normalization-active subset from the same file. --release keeps it
# near 20s.
cargo test --no-default-features --release \
  --test exhaustive_anomalies -- --ignored

# Lib-level ignored tests: the Layer-1 fold∘compose gate (#522) and the presets
# non-ASCII fast-path sweep, both unreachable from an integration test.
cargo test --no-default-features --release --lib -- --ignored

# Python formal invariant tests (12 tests)
pytest -m formal

# Docs site — --strict fails on broken internal links and missing-nav pages.
# CI's docs.yml runs this too, but is path-filtered (docs/**, mkdocs.yml,
# python/disarm/**), so a version-bump-only release PR never triggers it.
pip install --require-hashes -r requirements/docs.txt
mkdocs build --strict
```

> **Please don't remove** `#[ignore]`, `@pytest.mark.formal`, or
> `@pytest.mark.hypothesis` from these tests — they are excluded from CI intentionally.
> If you add new property-based tests, mark them with
> `pytestmark = pytest.mark.hypothesis`.

## Fuzzing, coverage and mutation testing (report only)

Three tools that measure the suites above rather than add to them. None is in *All checks
passed*: each is a search or a measurement, and a red result is a report for a human.
The baselines are in `docs/architecture/testing-guarantees.md`.

### Fuzzing

`fuzz/` is a cargo-fuzz crate outside the root package (its own `[workspace]`; the root
`include` list keeps it out of `cargo package`). Ten targets, one per surface:
`decode_bytes` takes raw bytes; the others take `TEXT [0xFF OPTIONS]`, lossy-decoded,
with `0xFE` as a three-byte escape into ranges the library treats specially
(`fuzz/src/lib.rs`). Every target asserts documented properties, not just the absence of
a panic: idempotence where it holds, `has_anomalies` against `inspect_anomalies`, the
`sanitize_filename` postconditions, the carrier round trips of `decode_smuggled`, I1-I3
and I7, strict decoding against lenient. Where a model in `formal/` found a property
false and the finding is open, the target says so and does not assert it.

```bash
rustup toolchain install nightly-2026-09-01 --profile minimal
cargo install cargo-fuzz --version 0.13.2 --locked
RUSTUP_TOOLCHAIN=nightly-2026-09-01 bash fuzz/run.sh             # every target, 60 s each
RUSTUP_TOOLCHAIN=nightly-2026-09-01 FUZZ_SECONDS=600 bash fuzz/run.sh presets
```

`fuzz/run.sh` reads the committed seeds (`fuzz/seeds/unicode`, `fuzz/seeds/bytes`,
regenerated by `python3 fuzz/gen_seeds.py` from the key-stability corpus and the formal
findings' witnesses) and writes the corpus it grows and any failing input under
`fuzz/corpus/` and `fuzz/artifacts/`, both gitignored. Replay a failure with
`RUSTUP_TOOLCHAIN=nightly-2026-09-01 cargo fuzz run <target> fuzz/artifacts/<target>/<file>`,
then reproduce it through the public API before calling it a bug. An oracle that turns
out to overclaim is weakened in its target with a comment naming the finding, never
deleted silently. `fuzz.yml` runs every target for 60 s on a pull
request that touches `src/`, `build.rs`, `Cargo.toml` or `fuzz/`, and for 15 minutes each
nightly, uploading `fuzz/artifacts/` when one fails.

### Coverage

```bash
rustup component add llvm-tools-preview --toolchain nightly-2026-09-01
cargo install cargo-llvm-cov --version 0.9.1 --locked
cargo +nightly-2026-09-01 llvm-cov --no-default-features --branch --lcov --output-path lcov.info
python3 scripts/coverage_summary.py lcov.info    # Markdown, lowest-covered module first
```

Branch coverage needs nightly; on stable, drop `--branch`. `coverage.yml` runs this on
pull requests that touch the core and on `main`, writing the table to the job summary
and uploading `lcov.info`. The Python package is measured where it already was, by
`pytest-cov` in the `test` job of `ci.yml`, which writes its table to that job's
summary. No threshold: set one, if ever, from a few weeks of reports.

### Mutation testing

```bash
cargo install cargo-mutants --version 27.1.0 --locked
cargo mutants -f src/hostname.rs --jobs 2       # one module; the whole crate takes hours
```

`.cargo/mutants.toml` excludes the generated tables and the PyO3 shims and sets the
timeouts. `mutants.yml` runs weekly and on demand over `anomalies`, `invisibles`,
`confusables`, `filename`, `smuggled` and `hostname`, one job each, and reports caught,
missed and timed-out mutants in the job summary. A missed mutant is a line no Rust test
asserts; read `mutants.out/missed.txt` before writing the test, since some are
equivalent mutants that no test could kill. cargo-mutants runs `cargo test` only, so
behaviour asserted by nothing but the Python suite shows up as missed: that is a
finding too, since the Node, Ruby, Java and C bindings reach the same code without it.
