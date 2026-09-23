# Contributing to disarm

Thank you for your interest in contributing! disarm is maintained by a small
team, and thoughtful contributions are genuinely welcome. This guide explains what
we're looking for, how the project is built and tested, and how to get a change
merged.

disarm is a Unicode canonicalization and UTS-39 confusable-analysis library: one
pure-Rust core (`src/`) with a thin binding per language over it. Behaviour lives
in the core, so a change to it updates every binding in the same pull request.

## Contents

Everything longer than this page lives under `docs/contributing/`, also the
*Contributing* section of the [docs site](https://docs.disarm.dev/):

| page | read it when |
|---|---|
| [What we're looking for][what-we-want] | choosing what to work on, or filing a bug |
| [Test architecture][testing] | tiers beyond Tier 1, drift gates, parallel runs |
| [Linting and formatting][linting] | green locally, red in CI; binding gates |
| [Documentation][documentation] | you touched `docs/`, a docstring or `README.md` |
| [Keys, artifacts and releases][gates] | `test_key_stability` failed, or an install could break |
| [Conventions][conventions] | naming a public function, logging, cleaning up nearby |
| [AI-assisted contributions][ai-assistance] | an AI agent helped with the change |
| [Pull requests][pull-requests] | why fragments exist; `scripts/watch_pr.py` |
| [Packaging decisions][packaging] | a `pyproject.toml` setting looks wrong |

Also at the top level: [BINDINGS.md](BINDINGS.md) before starting a new language
binding, [RELEASING.md](RELEASING.md) for cutting a release, and
[SECURITY.md](SECURITY.md) for reporting a vulnerability, which never goes in a public
issue.

## Prerequisites

- Rust stable toolchain (>= 1.88, the MSRV in `Cargo.toml`): `rustup update stable`
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

## Everyday build and test

Tier 1, what every pull request must pass. The default build is the pure Rust core;
the Python extension is built by `maturin`, never by `cargo build`.

```bash
PYO3_PYTHON=$(which python3) cargo test --no-default-features   # Rust core
maturin develop && pytest                                       # Python, in parallel
pytest -m serial -n 0                                           # the serial tier
```

The Hypothesis, `slow` and formal tiers are opt-in; they and the drift gates are in
[Test architecture][testing].

## Before you push

CI runs these as a gate; run them locally first.

```bash
# Rust
cargo fmt --all -- --check
cargo clippy --all-targets -- -D warnings                              # pure core
cargo clippy --all-targets --features extension-module -- -D warnings  # bindings
bash scripts/perf_lint.sh                                              # allocation lints

# Python
ruff check .
ruff format --check .
mypy python/disarm --ignore-missing-imports
```

That is not all of CI: `cargo doc`, a current clippy, the ruff version CI pins and
every binding's suite are in [Linting and formatting][linting]. If you touched `docs/`,
also run the [doc-tests][doc-tests] and `mkdocs build --strict`.

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

> If an AI agent assisted the commit, it **also** needs an `Assisted-by:` trailer — see [Attribute the assistant][attribution]. The assistant is attributed there; the human still signs off here.

## Submitting changes

All changes go through pull requests; direct pushes to `main` are blocked by branch
protection.

1. Fork the repository and create a branch from `main`.
2. Make your change **with a test** — ideally one that fails before the change and
   passes after.
3. Run Tier 1 locally (tests + linters) and confirm it's green.
4. **Sign off** your commits (`git commit -s`) — see [Sign your work](#sign-your-work-developer-certificate-of-origin) above.
5. Open a pull request describing **what** changed and **why**. Link any related issue.
6. **Add a changelog fragment** named for that pull request — see
   [Changelog fragments](#changelog-fragments-993) below. CI gates it.
7. Wait for the required status checks — **"All checks passed"**, **"DCO sign-off"**
   and **"iai estimated-cycles gate"** — to go green. The first is a single roll-up:
   #583 collapsed the former per-language contexts into it, so one green tick now
   stands for the whole Rust, Python, binding and doc matrix.

A PR that arrives with a passing CI run and a focused test is the easiest kind to
review and merge. Thank you for contributing.

### Changelog fragments (#993)

**Do not edit `CHANGELOG.md`.** It is assembled at release time from one file per change
in `changelog.d/`, and there is no `## [Unreleased]` section to add to. The rules below
are the short version; `changelog.d/README.md` in the repository is the full one.

```bash
# Named for the PULL REQUEST, not the issue: several PRs per issue is normal here,
# and an issue-numbered fragment would rebuild the conflict on day one.
cat > changelog.d/991.fixed.md <<'EOF'
- **`demojize` destroyed 777 non-emoji characters (#990).** `demojize("rated 3 ★ of 5")`
  returned `rated 3 [?] of 5` — the star is `U+2605`, which the UCD gives no emoji
  presentation. Both scanners now ask the UCD rather than a block range.
EOF
```

Write the fragment **exactly as it should appear** in the changelog: leading `- `, bold
lead-in naming the defect or capability with its numbers inline, two-space continuation
indent. Assembly concatenates and never re-wraps, so what a reviewer reads in your pull
request is what ships. The type suffix picks the heading (`fixed`, `added`, `changed`,
`breaking`, `docs`, `internal`, `performance`, `security`, `upgrade`).

```bash
towncrier build --draft --version NEXT       # the unreleased section, rendered
towncrier check --compare-with origin/main   # exactly what CI's gate runs
```

CI fails a pull request that edits `CHANGELOG.md` by hand. The escape hatch for a
change with nothing to say is the `no changelog` label; why fragments exist, and
exactly what CI checks, are in [Pull requests][pull-requests].

[what-we-want]: https://github.com/raeq/disarm/blob/main/docs/contributing/what-we-want.md
[testing]: https://github.com/raeq/disarm/blob/main/docs/contributing/testing.md
[linting]: https://github.com/raeq/disarm/blob/main/docs/contributing/linting.md
[documentation]: https://github.com/raeq/disarm/blob/main/docs/contributing/documentation.md
[gates]: https://github.com/raeq/disarm/blob/main/docs/contributing/gates.md
[conventions]: https://github.com/raeq/disarm/blob/main/docs/contributing/conventions.md
[ai-assistance]: https://github.com/raeq/disarm/blob/main/docs/contributing/ai-assistance.md
[pull-requests]: https://github.com/raeq/disarm/blob/main/docs/contributing/pull-requests.md
[doc-tests]: https://github.com/raeq/disarm/blob/main/docs/contributing/documentation.md#doc-test-recipes
[attribution]: https://github.com/raeq/disarm/blob/main/docs/contributing/ai-assistance.md#attribute-the-assistant
[packaging]: https://github.com/raeq/disarm/blob/main/docs/contributing/packaging.md
