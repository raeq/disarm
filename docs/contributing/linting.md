# Linting and formatting

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

**Run CI's ruff, not whichever one is on your PATH.** The pre-commit hooks are
`language: system`, so they use the `ruff` your shell finds, and it is easy for that to
be older than the pin. It matters more than a version number usually does: **0.16
formats Python inside Markdown fenced blocks and 0.15 does not**, and this repository's
docs are full of executable Python in fences. A stale ruff passes `ruff format --check .`
locally and fails the *Lint & format* job with no hint that a version is involved.

```bash
uv pip install "ruff==$(python3 -c "
import re,pathlib
print(re.search(r'ruff==([0-9.]+)', pathlib.Path('pyproject.toml').read_text()).group(1))")"
```

The pin is written once, in the `dev` extra; CI's *Lint & format* job reads it from
there. `tests/test_toolchain_pins.py` asserts that CI keeps no copy of its own and that
the ruff you are running matches the pin, so this is caught by `pytest` rather than by a
pull request.

## Three gates CI runs that the block above does not

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
