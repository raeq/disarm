# Contributing to translit

Thank you for your interest in contributing! translit is maintained by a small
team, and thoughtful contributions are genuinely welcome. This guide explains what
we're looking for, how the project is built and tested, and how to get a change
merged.

## What we're looking for

We'd love your help, especially with:

- **Domain-specific extensions and new use cases.** translit is a kit of canonicalization
  and transliteration building blocks. If you work in a domain we haven't designed
  for — a library catalog, a moderation pipeline, an IDN registrar check, a search
  index, a data-cleaning ETL step, a linguistics workflow — and translit *almost* does
  what you need, tell us. The most valuable feature requests come from real workflows
  we hadn't pictured. Use the **💡 Extension idea / new use case** issue form.
- **Language profiles.** Profiles apply sparse overrides on top of the default table
  (e.g. German `ü` → `ue`). Adding or refining a profile for a language you know well
  is a high-value, self-contained contribution. See
  [Language support](https://translit.readthedocs.io/user-guide/language-support.html).
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

## Reporting bugs and requesting features

Please use the [issue forms](https://github.com/raeq/translit/issues/new/choose) — they
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

## Prerequisites

- Rust stable toolchain (>= 1.70): `rustup update stable`
- Python 3.9+
- `maturin` for building the Python extension: `pip install maturin[patchelf]`

## Development setup

```bash
git clone https://github.com/raeq/translit.git
cd translit
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
# Rust unit + integration (~630 tests).
# --no-default-features disables the Python-linking extension-module feature.
PYO3_PYTHON=$(which python3) cargo test --no-default-features

# Python deterministic tests (~2,200), excluding the slow/non-deterministic tiers.
pytest -m "not formal and not hypothesis"
```

`build.rs` compile-time assertions are always on at zero runtime cost: they assert that
every transliteration table value is ASCII and that entry counts match expectations. If
one fails, `cargo build` fails.

### Tier 2 — Hypothesis / property-based (developer worktree)

Property-based / fuzz tests (~440) across the Unicode input space. Excluded from CI
because they are slow (~40s), non-deterministic, and costly.

```bash
pytest -m hypothesis      # (plain `pytest` includes these by default)
```

### Tier 3 — Formal / pre-release (gated, opt-in)

Exhaustive enumeration — every Hangul syllable (11,172), the full BMP (63,488 code
points), all CJK ideographs, 15 Indic blocks — plus the seven formalized invariants
(I1–I7).

```bash
# Rust exhaustive domain tests (16 tests, marked #[ignore])
PYO3_PYTHON=$(which python3) cargo test --no-default-features \
  --test exhaustive_transliterate -- --ignored

# Python formal invariant tests (12 tests)
pytest -m formal
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
mypy python/translit --ignore-missing-imports
```

## Building documentation

```bash
pip install -e ".[docs]"
mkdocs serve              # local preview at http://127.0.0.1:8000
mkdocs build              # build static site to site/
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
from translit import sanitize_filename

assert sanitize_filename("café.txt") == "cafe.txt"
```
````

Rules:

- **Assert, don't comment.** `assert f(x) == "y"` is checked; `f(x)  # => "y"`
  is not. The `# =>` pattern is what we are removing (#156).
- **Public API only.** Reaching into internals (`translit._...`) in a published
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

## Sign your work — Developer Certificate of Origin

By submitting a contribution, you agree it is licensed under the project's
[MIT License](https://github.com/raeq/translit/blob/main/LICENSE) (inbound =
outbound). translit does **not** require a CLA.

We do use the [Developer Certificate of Origin](https://github.com/raeq/translit/blob/main/DCO) (DCO 1.1): a per-commit
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

## Submitting changes

All changes go through pull requests; direct pushes to `main` are blocked by branch
protection.

1. Fork the repository and create a branch from `main`.
2. Make your change **with a test** — ideally one that fails before the change and
   passes after.
3. Run Tier 1 locally (tests + linters) and confirm it's green.
4. **Sign off** your commits (`git commit -s`) — see [Sign your work](#sign-your-work--developer-certificate-of-origin) above.
5. Open a pull request describing **what** changed and **why**. Link any related issue.
6. Wait for the required status checks — **"Rust checks passed"**, **"Python checks
   passed"**, and **"DCO sign-off"** — to go green.

A PR that arrives with a passing CI run and a focused test is the easiest kind to
review and merge. Thank you for contributing.
