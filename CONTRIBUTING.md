# Contributing to disarm

Thank you for your interest in contributing! disarm is maintained by a small
team, and thoughtful contributions are genuinely welcome. This guide explains what
we're looking for, how the project is built and tested, and how to get a change
merged.

## What we're looking for

We'd love your help, especially with:

- **Domain-specific extensions and new use cases.** disarm is a kit of canonicalization
  and transliteration building blocks. If you work in a domain we haven't designed
  for — a library catalog, a moderation pipeline, an IDN registrar check, a search
  index, a data-cleaning ETL step, a linguistics workflow — and disarm *almost* does
  what you need, tell us. The most valuable feature requests come from real workflows
  we hadn't pictured. Use the **💡 Extension idea / new use case** issue form.
- **Language profiles.** Profiles apply sparse overrides on top of the default table
  (e.g. German `ü` → `ue`). Adding or refining a profile for a language you know well
  is a high-value, self-contained contribution. See
  [Language support](https://docs.disarm.dev/user-guide/language-support.html).
- **A new language binding** (distinct from a profile above). disarm's pure-Rust core
  is wrapped per programming-language ecosystem — Ruby is live; Node, Go, Java, PHP, and
  R are planned (#43–#48). A binding for an ecosystem you know well is high-value, but it
  must *feel native* to that language, not be a re-export of the Rust/Python API. Read
  [BINDINGS.md](BINDINGS.md) — the per-binding definition of done — and use
  `bindings/ruby/` as the template before you start.
- **Coverage requests.** A confusable pair, a script, or a code point we don't yet map
  is a *known limitation* (see the [Threat Model](THREAT_MODEL.md)), not a vulnerability —
  but it is exactly how this layer improves. Use the **🗺️ Coverage / confusable-gap**
  issue form; a single missing pair is a perfectly good issue.
- **Genuine feature requests and fixes.** Bug reports with a minimal reproduction, and
  PRs that come with a test, are always welcome.

If you're not sure whether an idea fits, open an issue and ask. We would rather
discuss a half-formed idea than have you not raise it.

## Leave it better than you found it

This project follows the **Boy Scout rule** and the **broken-windows** principle:
if you touch an area and notice something broken, stale, or sub-standard — a lint
that only fires under `--all-targets`, a stale doc claim, a flaky test, a
misleading comment — **fix it as part of your change**, even if you didn't cause
it. Broken windows accumulate fast: one tolerated defect signals that defects are
acceptable, and quality erodes. A small, in-scope cleanup alongside your work is
always welcome (call it out in the PR description so reviewers can see what's
incidental). When a fix is too large to fold in, open an issue so it isn't lost.

## Naming public entry points (#654)

**A public name may describe the operation, never the outcome.** `canonicalize`,
not `clean`. `strip_bidi`, not `make_safe`. No public name may imply a safety
guarantee.

The reason is in `canonicalize`'s own docstring, which denies the guarantee a name
like `clean` would imply. NFKC unmasking makes the output *more* dangerous to emit
than the input — fullwidth `＜` folds to a live `<` — so a name promising safety
would be actively wrong rather than merely vague. `mysql_real_escape_string` is the
worked example of what happens when a name outlives its caveats.

Write the rule down here so the next `clean()` proposal meets a written rule rather
than an argument.

**One shipped name sits outside it.** `ml_normalize` is named for a use case, and
readers pick it by that use case. It is also the transform that passes bidi
controls, private-use characters and homoglyphs straight through, so it is exactly
the name the rule exists to prevent. It stays, and its docstring carries the
warning instead. Recording that the exception is known matters more than resolving
it.

## Logging rules (#208)

Diagnostic logging lives behind the opt-in `log` feature via the `tl_*!` macros
in `src/obs.rs`. Two hard rules, enforced by tests:

- **Never log content.** Default-level records (ERROR/WARN/INFO/DEBUG) carry only
  metadata — lengths, language, mode, flags, counts, durations, `Error::code` —
  never input or output text. A sentinel test (`tests/logging.rs`) fails the
  build if any default-level record contains the input. Truncated content
  samples are reachable only via `tl_trace_content!` (the `log-content` feature,
  TRACE).
- **Never log in an inner loop.** Instrument core *boundaries* only. The
  per-codepoint loop in `transliterate_impl_inner` and the per-token loop in
  `context::resolve` must contain no `tl_*!`/`log::` call — guarded by
  `tests/hot_path_guard.rs`. Variables that exist only to feed a record are
  `#[cfg(feature = "log")]`-gated so they cost nothing when the feature is off.

## Reporting bugs and requesting features

Please use the [issue forms](https://github.com/raeq/disarm/issues/new/choose) — they
ask for the few things we need to act on a report (a version, a minimal reproduction,
expected vs. actual output). A report we can reproduce in under a minute gets fixed far
faster than one we have to interrogate.

**Security issues are different:** do **not** open a public issue. Follow
[SECURITY.md](SECURITY.md) for private disclosure, and read the
[Threat Model](THREAT_MODEL.md) first — it defines precisely what counts as a
vulnerability versus an out-of-scope limitation.

## A note on AI-assisted contributions

AI tools are fine to use — many of us use them. The bar is simple and it's the same
bar that has always applied: **you must be able to reproduce and stand behind what you
submit.**

- For a **bug or security report**, that means a minimal reproduction that actually
  runs against the current release, and identifying the specific documented behavior or
  invariant you believe is wrong.
- For a **pull request**, that means a test that *fails before* your change and *passes
  after*, and that the full CI suite is green.

Reports or PRs that are clearly machine-generated, can't be reproduced, and whose author
can't answer follow-up questions will be closed without extended back-and-forth. This
isn't hostility toward AI — it's the cost of a maintainer's time. Speculative
"there might be a buffer overflow here" reports with no reproduction are the one thing
that genuinely drains a small project.

### Attribute the assistant

If an AI coding **agent** helped produce a commit, that commit **must** carry an
`Assisted-by:` trailer naming the agent and model, following the Linux kernel's
[coding-assistants guidance](https://docs.kernel.org/process/coding-assistants.html).
Using an assistant is welcome and encouraged; **not disclosing it is not** — the
attribution is required, not optional.

The format is `Assisted-by: AGENT_NAME:MODEL_VERSION [analysis-tools]`, alongside your
own DCO sign-off:

```
Signed-off-by: Jane Developer <jane@example.com>
Assisted-by: Claude:claude-3-opus coccinelle sparse
```

Use the **actual** agent and the model version you used (model ids change — record the
one in effect for that commit), and append specialised analysis tools if relevant
(e.g. `coccinelle`, `sparse`). Do **not** list ordinary tools like git, the compiler,
or your editor.

An assistant **must never** add a `Signed-off-by:` or `Co-developed-by:` trailer — only a
human can certify the [DCO](#sign-your-work-developer-certificate-of-origin). You, the
human submitter, review the change, add your own `Signed-off-by:`, and take full
responsibility for it. In short: **`Assisted-by:` is attribution; `Signed-off-by:` is
accountability** — every AI-assisted commit needs both, and they are never the same line.

## Prerequisites

- Rust stable toolchain (>= 1.70): `rustup update stable`
- Python 3.10+
- `maturin` for building the Python extension: `pip install maturin[patchelf]`

## Development setup

```bash
git clone https://github.com/raeq/disarm.git
cd disarm
python -m venv .venv && source .venv/bin/activate
maturin develop          # build Rust extension in-place
pip install -e ".[dev]"  # installs test + dev dependencies
pre-commit install       # set up pre-commit hooks
```

## Test architecture

Tests are organized into three tiers. **CI runs Tier 1 only** — it is fast and
deterministic. Tiers 2 and 3 are heavier and run in a developer worktree or before a
release. Please run at least Tier 1 locally before opening a PR.

### Tier 1 — CI (fast, deterministic)

What every PR must pass. Mirrors `.github/workflows/ci.yml`.

```bash
# Rust unit + integration (~1,025 tests across 23 binaries plus 12 doctests).
# --no-default-features disables the Python-linking extension-module feature.
PYO3_PYTHON=$(which python3) cargo test --no-default-features

# Python deterministic tests (~4,490). Since #658 this is what bare `pytest` runs.
pytest
```

CI's own command is `pytest tests/ --ignore=tests/test_typing.py -m "not formal and
not hypothesis"`, so the two marker expressions are **not** identical — the local
default also carries `not slow`. Nothing in that tier executes under CI conditions
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

#### Drift gates

Four checks in Tier 1 guard something a normal test cannot: they compare a *generated or
published artifact* against the source of truth, so they fail when the two drift apart
rather than when behaviour is wrong. Each exists because the drift they catch happened.

| Gate | Guards | Fails when |
|---|---|---|
| `bindings/cabi/disarm.h` diff (`C ABI (safer-ffi)` job) | The committed C header | An exported signature changes without the header being regenerated (#580) |
| `tests/test_doc_table_counts.py` | 11 documented row counts across 5 files | A table is regenerated and prose still quotes the old figure (#591) |
| `build.rs` ASCII assertions | Generated table values | A generated value is non-ASCII, against #341's contract (#587) |
| `JvmSignatureTest` (`Java binding (JDK …)` job) | Published JVM signatures | A Kotlin default argument deletes an arity that shipped (#588) |

Two of them read a build product rather than source text, which is the point:
`JvmSignatureTest` reflects over the compiled facade, and the header gate diffs the
regenerated header. Source-level assertions would not have caught either defect.

**When you regenerate a table, read the data diff, not just the test output.** A change to
`gen_confusables.py` can silently *remove* rows, and a passing suite does not prove it
did not — that is how an over-broad filter deleted `Ç → C` during #593.

### Tier 2 — Hypothesis / property-based (opt-in)

Property-based / fuzz tests across the Unicode input space. **587 tests, ~67s on a
release build** — the figures here read "~440 / ~40s" until #658 measured them.

```bash
pytest -m hypothesis
```

Bare `pytest` used to include these, which meant a contributor paid the tier on
every local run while no CI job ran it. `nightly-hypothesis.yml` runs it at 03:17
UTC with `--hypothesis-seed=random` and a 10× oracle budget, which explores more
input space than one more fixed-seed pass ever did. Run it locally when you touch
the input-handling boundary; the nightly is the safety net.

### Tier 2b — Expensive, opt-in (`slow`)

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

### Running the suite in parallel

`pytest-xdist` is in the `test` extra:

```bash
pytest -n 2 --dist loadfile
```

**`--dist loadfile` is not optional.** `register_lang` mutates process-global state
that cannot be undone, so tests must stay grouped by file; per-file distribution
preserves that and nothing failed under it.

Measured after the #658 fixes, on a 10-core machine: serial 6.1s, `-n 2` 4.9s,
`-n 4` 5.0s, `-n auto` 5.4s. `auto` is *worse* than `-n 2` — once the suite is
short enough, worker startup dominates. CI keeps the serial command for the same
reason: the ~1s saved does not pay for installing the plugin.

### Tier 3 — Formal / pre-release (gated, opt-in)

Exhaustive enumeration — every Hangul syllable (11,172), the full BMP (63,488 code
points) both bare and crossed with composing marks, all CJK ideographs, 15 Indic blocks
— plus the seven formalized invariants (I1–I7). `.github/workflows/tier3.yml` runs the
same set.

Three of these now run in **PR CI** rather than only here (#658): the
transliterate, grapheme and width targets cost 0.62s against a profile the `test`
job has already built, so a regression in them surfaces on the pull request that
caused it. `width_conformance` was in no workflow and no documented gate before
that, so nothing had ever run it.

```bash
# Rust exhaustive domain tests (16 tests, marked #[ignore]) — also in PR CI
PYO3_PYTHON=$(which python3) cargo test --no-default-features \
  --test exhaustive_transliterate -- --ignored

# Grapheme-boundary integrity across the same domain (#174) — also in PR CI.
cargo test --no-default-features --test exhaustive_grapheme -- --ignored

# Width bounds over every Unicode scalar (#224) — also in PR CI.
cargo test --no-default-features --test width_conformance -- --ignored

# Confusables on the Layer-2 API: the BMP crossed with composing marks, checked for
# idempotence and for output that is still confusable (#586). Deliberately separate
# from the lib-level sweep below, which tests Layer 1 — testing the layer beneath the
# one the bindings call is how #586 survived a year. --release keeps it near 1s.
cargo test --no-default-features --release \
  --test exhaustive_confusables -- --ignored

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

## Linting and formatting

CI runs these as a gate; run them locally first.

```bash
# Rust
cargo fmt --all -- --check
cargo clippy --no-default-features -- -D warnings

# Python
ruff check .
ruff format --check .
mypy python/disarm --ignore-missing-imports
```

### Three gates CI runs that the block above does not

Each of these has sent an avoidable red build. They are listed here because running the
core-and-Python commands to the letter is *not* sufficient to predict CI.

**1. `cargo doc` is run by nobody.** No CI job invokes it, so a broken rustdoc link ships
to docs.rs unnoticed — six were live at once in August 2026. It is fast, and it is the
published API page:

```bash
cargo doc --no-deps      # must be warning-free
```

Note `crate::` paths in public docs must point at the **`crate::api::` re-export**, not at
the `pub(crate)` module the item really lives in; rustdoc rejects the latter as a private
link.

**2. Your clippy is not CI's clippy.** CI follows `dtolnay/rust-toolchain@… # stable` and
there is no `rust-toolchain.toml` pinning the repo, so a local toolchain drifts behind and
lints added in the gap cannot fire for you at all. `rustup update stable` before trusting
a `-D warnings` run.

**3. The binding gates are not in the block above.** RuboCop, Biome, the Ruby and Node
suites, the JVM tests and the C smoke test all run in CI and none is listed anywhere in
this file. Every binding builds against the **published** core, so an unreleased API needs
the `[patch.crates-io]` redirect CI injects — and its location differs per binding.
`bindings/ruby` is a cargo workspace, so a patch appended to `bindings/ruby/ext/disarm/`
is **ignored with only a warning** and the build then fails against the published core.

| binding | append the redirect to | path |
|---|---|---|
| cabi | `bindings/cabi/Cargo.toml` | `../..` |
| node | `bindings/node/Cargo.toml` | `../..` |
| ruby | `bindings/ruby/Cargo.toml` (**workspace root**) | `../..` |
| java | `bindings/java/rust/Cargo.toml` | `../../..` |

Run every line from the repo root. Each is a **subshell** so the `cd` does not leak into
the next one — chaining bare `cd`s here silently runs the second binding's commands inside
the first binding's directory.

```bash
# Allocation gate on the glue. BINDING is a PATH the script cd's into, not a short name.
BINDING=bindings/node       bash scripts/perf_lint.sh
BINDING=bindings/ruby/ext/disarm bash scripts/perf_lint.sh
BINDING=bindings/cabi       bash scripts/perf_lint.sh
BINDING=bindings/java/rust  bash scripts/perf_lint.sh

( cd bindings/ruby && bundle exec rubocop && bundle exec rake compile && bundle exec rspec )
( cd bindings/node && npx biome check . && npm run build:debug && npm test )
( cd bindings/java && ./gradlew test --offline )

# The C ABI: smoke.c is the ONLY behavioural coverage that crate has — CI never runs
# `cargo test` there, so a Rust #[test] in it would be compiled and never executed.
( cd bindings/cabi \
  && cargo build --release \
  && cc examples/smoke.c -I. -L target/release -ldisarm_ffi -o /tmp/disarm_smoke \
  && LD_LIBRARY_PATH="$PWD/target/release" /tmp/disarm_smoke )
```

**Restore every manifest afterwards** (`git checkout -- <manifest>`). A committed
relative-path redirect breaks release packaging.

Skip the binding block only when `git status` shows no `bindings/` file changed and no
public `src/api` signature moved.

## Building documentation

```bash
pip install --require-hashes -r requirements/docs.txt
mkdocs serve              # local preview at http://127.0.0.1:8000
mkdocs build              # build static site to site/
```

`requirements/docs.txt` is **generated** — the `[docs]` extra in `pyproject.toml` is the
single source of truth, and the lockfile is compiled from it (same pattern as
`requirements/bench.txt`). After changing the extra, regenerate:

```bash
uv pip compile pyproject.toml --extra docs --generate-hashes -o requirements/docs.txt
```

## Doc-test recipes

Cookbook examples are **executed in CI** against the shipped wheel — a wrong or
broken snippet turns the suite red (#154). This kills "recipe rot": output
claims that are wrong at authoring time, or that silently break when the API
moves. The harness is [Sybil](https://sybil.readthedocs.io/); it runs every
fenced `python` block in an allowlisted page and checks any `assert` it
contains.

Run the doc-tests locally (they need the `[test]` extra, which pulls in Sybil):

```bash
pip install -e ".[test]"
python scripts/run_doc_tests.py       # all pages, each in its own process
pytest docs/user-guide/filenames.md   # a single page
```

The runner executes each page in a **separate process**. Some documented APIs
mutate process-global state (`register_lang` is not reversible), so running every
page in one process would let one page's registration leak into another and break
exact-output examples. `pytest docs/` (one process) is therefore not the gate.

**Recipe template.** Assert outputs; never decorate them with `# =>`:

````markdown
```python
from disarm import sanitize_filename

assert sanitize_filename("café.txt") == "cafe.txt"
```
````

Rules:

- **Assert, don't comment.** `assert f(x) == "y"` is checked; `f(x)  # => "y"`
  is not. The `# =>` pattern is what we are removing (#156).
- **Public API only.** Reaching into internals (`disarm._...`) in a published
  example is itself a doc bug — the example must exercise what users can call.
- **One namespace per page.** Blocks share state top-to-bottom, so import once
  and reuse the binding in later blocks.
- **Hide setup** that would clutter the prose in an invisible block — it runs
  but does not render:

  ```markdown
  <!--- invisible-code-block: python
  tmp = make_fixture()
  -->
  ```

- **Skip** a block that is intentionally not runnable (e.g. pseudo-code or a
  shell transcript mislabelled `python`) with `<!--- skip: next -->`.

**Enabling a page.** A page is executed only once it is on the allowlist in
`docs/conftest.py` (the `EXECUTED_RECIPES` list). Convert its examples to
asserts, add the path, and confirm `pytest docs/` is green. This is a deliberate
ratchet: un-converted pages stay visibly unguarded until their claims are
asserted.

### `README.md` is the source; `docs/index.md` is generated (#656)

Do not edit `docs/index.md`. It is produced by `scripts/generate_docs_index.sh`
from `README.md` plus `docs/_index_nav.md`, which rewrites the `(docs/…)` link
prefixes and appends the site navigation. Edit one of the two sources and
regenerate:

```bash
bash scripts/generate_docs_index.sh           # write it
bash scripts/generate_docs_index.sh --check   # fail if it is out of date
```

The banner at the top of the file said this already, and it did not hold. Before
the `--check` gate existed the file had drifted **both ways at once**: two
*Features* bullets lived only in the generated file, where the next run would have
deleted them, and a Node.js nav entry, a whole-script-spoof example and a
coverage-residue note lived only in the sources and had never reached the site.
The second kind is the dangerous one — the change appears on GitHub, so it looks
applied.

**This is also what executes the README.** Every `python` block in `README.md`
lands in `docs/index.md`, which is first on `EXECUTED_RECIPES` and runs under
Sybil on every CI run. In sync, the README's examples are asserted; out of sync,
they are not. So a README example is written to the same standard as any other
recipe: assert outputs, never decorate them with `# =>`.

### Key-builder output is gated (#644)

`search_key`, `catalog_key` and `sort_key` produce values a consumer **stores**
and compares later, so a change to them is a reindex event on somebody's
production data. `docs/RUST_API.md` states the contract — *a patch release never
changes key-builder output; a minor release may* — and
`tests/test_key_stability.py` holds it.

If it fails, **read the diff before doing anything else.** It prints a
per-function count and a sample of what moved:

```
search_key: 267 of 22878 changed (1.17%)
    'подъезд'
      was 'podъezd'
      now 'podezd'
```

Then decide. If the movement is intended:

```bash
python scripts/gen_key_fixture.py     # rewrite the expected values
```

Commit the regenerated fixture **in the same change**, write it up in the
release's *Upgrade notes*, and cut that release as a **minor**. Regenerating to
make the test go green without reading the diff is the one use the script does
not have.

Review does not substitute for this. `0.14.0` moved `search_key` on 4.1% of a
5,030-input corpus, and the change responsible (#602) was a correctness fix whose
diff said nothing about keys.

The corpus is not reproducible and its licence is not MIT; both are recorded in
`tests/fixtures/key_stability/README.md`.

### Does the artifact work? (#667, #669)

Every step above tests your worktree. It contains untracked files, generated
artefacts, a populated `target/` and whatever `.gitignore` hides — so a file
present locally and absent from the commit is invisible to all of it. And
`maturin develop` produces no distributable artifact at all, so nothing before a
push touches installability.

Two checks close that, sharing one body (`scripts/smoke_installed.py`):

```bash
# The tracked tree — exactly what someone fetching this commit receives.
tmp=$(mktemp -d) && git archive HEAD | tar -x -C "$tmp"
python -m venv "$tmp/venv" && "$tmp/venv/bin/pip" install "$tmp"
(cd "$tmp" && "$tmp/venv/bin/python" "$OLDPWD/scripts/smoke_installed.py")

# The sdist — the artifact CI does not cover either, until #667's job runs.
maturin sdist --out "$tmp/dist"
python -m venv "$tmp/sv" && "$tmp/sv/bin/pip" install --no-binary disarm "$tmp"/dist/*.tar.gz
(cd "$tmp" && "$tmp/sv/bin/python" "$OLDPWD/scripts/smoke_installed.py")
```

Run them from **outside** the checkout, as above. A source tree on `sys.path`
shadows the installed package and the check passes without testing an install —
the failure it exists to find. The script says so if it happens.

These cost a full compile each, which is too slow per commit and about right per
push. `.github/workflows/smoke.yml` runs both in CI: the tracked-tree job on
every push to `main` with **no** paths filter, since the point is that it runs on
every commit that lands.

### The docs describe `main`; the reader executes a tag (#641)

Every gate above runs against the branch. The site deploys from `main` on each
push, but `pip install disarm` gives a reader the newest **tag**. At the worst
point those were 68 commits apart, and `docs/security/cve-validation.md` named
five entry points that raised `AttributeError` on the release it described.

Two things now cover that gap:

- A `mkdocs` hook stamps every page with the commit it was built from and the
  published version (`scripts/mkdocs_build_banner.py`). Nothing to do when
  writing docs; it is mentioned here so nobody deletes it as decoration.
- A weekly job resolves every `disarm` name the docs use against the newest
  published wheel. Run it yourself against any build:

  ```bash
  python scripts/check_docs_against_release.py
  ```

  A **red run means documented API has outrun the last release** — cut one, or
  correct the page. It is deliberately not a pull-request gate: documentation
  ships with the feature it documents, so during that window the gap is correct
  and a PR gate would block every feature branch.

  Names it cannot fix are listed in `_KNOWN_GAPS`, each against an open issue.
  An entry may only go in with an issue number, and the script fails if a listed
  name starts resolving — so the list shrinks rather than accumulating.

### Per-language usage tabs (Rust & Ruby)

User-guide pages show usage in `pymdownx.tabbed` tabs — `=== "Python"` /
`=== "Rust"` / `=== "Ruby"` — over shared, language-neutral concept prose (#50).
**Each binding's tab may only use functions that binding actually exposes** (Rust
≈ the full `disarm::api`; Ruby is a smaller surface — see
`bindings/ruby/lib/disarm.rb`). Do not invent a call; if a topic isn't in a
binding, omit that tab. Every tab is gated:

```bash
python scripts/check_doc_rust_examples.py   # compile + run every ```rust block
ruby scripts/check_doc_ruby_examples.rb      # eval every Ruby `# =>` line (needs the built gem)
```

- **Rust tabs** use `assert_eq!`. The gate extracts every ```rust block, wraps
  each in a `#[test]`, and compiles + runs it against the pure core with
  `#![deny(unused_must_use)]` — so an example that **discards** its result (a
  `Result`, `Vec`, or `Cow`) is a hard error. Assert the output; don't leave a
  bare call with a `// =>` comment. Mark a genuinely illustrative block (a trait
  sketch, a macro) with `<!--- rust-skip -->` (the Rust gate's own opt-out —
  distinct from Python's `<!--- skip: next -->`, which Sybil would choke on
  before a non-Python block).
- **Ruby tabs** document outputs with `# =>` and start with `require "disarm"`.
  The gate evals each `Disarm.* # => value` line against the freshly-compiled gem
  (it tolerates trailing prose after the literal). It runs in the Ruby workflow
  on `bindings/ruby/**` **and** `docs/**` changes.

## Sign your work — Developer Certificate of Origin

By submitting a contribution, you agree it is licensed under the project's
[MIT License](https://github.com/raeq/disarm/blob/main/LICENSE) (inbound =
outbound). disarm does **not** require a CLA.

We do use the [Developer Certificate of Origin](https://github.com/raeq/disarm/blob/main/DCO) (DCO 1.1): a per-commit
attestation that you wrote the code, or otherwise have the right to submit it
under the project's license. Certify it by adding a `Signed-off-by` trailer to
**every** commit:

```
Signed-off-by: Jane Developer <jane@example.com>
```

Git adds it for you with the `-s` flag:

```bash
git commit -s -m "Your message"
```

The name and email in the sign-off **must match the commit author**. To sign off
a series of existing commits, rebase with `--signoff`:

```bash
git rebase --signoff main
```

A **"DCO sign-off"** status check flags any PR whose commits are not signed off;
it is a required check on `main`.

> If an AI agent assisted the commit, it **also** needs an `Assisted-by:` trailer — see [Attribute the assistant](#attribute-the-assistant). The assistant is attributed there; the human still signs off here.

## Submitting changes

All changes go through pull requests; direct pushes to `main` are blocked by branch
protection.

1. Fork the repository and create a branch from `main`.
2. Make your change **with a test** — ideally one that fails before the change and
   passes after.
3. Run Tier 1 locally (tests + linters) and confirm it's green.
4. **Sign off** your commits (`git commit -s`) — see [Sign your work](#sign-your-work-developer-certificate-of-origin) above.
5. Open a pull request describing **what** changed and **why**. Link any related issue.
6. Wait for the required status checks — **"All checks passed"**, **"DCO sign-off"**
   and **"iai estimated-cycles gate"** — to go green. The first is a single roll-up:
   #583 collapsed the former per-language contexts into it, so one green tick now
   stands for the whole Rust, Python, binding and doc matrix.

A PR that arrives with a passing CI run and a focused test is the easiest kind to
review and merge. Thank you for contributing.
