# Packaging decisions

Why `pyproject.toml` is set the way it is, one section per setting. The prose here used
to sit in comments beside each setting and was moved without rewording; `pyproject.toml`
now keeps a one- or two-line comment that points at the section. Nothing on this page
changes a setting.

## Optional dependencies

### test: pytest-xdist

Not optional, and on by default in `addopts`. `--dist loadfile` is not
optional either: `register_lang` mutates process-global state that cannot be
undone, so tests have to stay grouped by file, which per-file distribution
preserves.

The #658 note here said serial 6.1s / -n 2 4.9s / -n auto 5.4s and concluded
`auto` over-provisions and CI should stay serial. That was true of a 6-second
suite and stopped being true as it grew; re-measured on four cores, without
coverage: serial 93.4s, -n 2 65.2s, -n auto 35.1s. `--dist loadgroup` with
only the process-global-state modules pinned was tried and is worse on both
counts — 45.0s, and it breaks `test_docs_index_drift`, which depends on its
file's tests sharing a worker.

### test: pyyaml

The workflow gates (#830, #832) read `.github/workflows/*.yml`, and pattern-
matching them is what produced the bug review caught: an `on: push` written
inline read as "not a push workflow" and was silently exempted. Parsing needs
a YAML reader, and `on` being a YAML 1.1 boolean is not a thing to hand-roll.

### test: towncrier

Assembles changelog.d/ into CHANGELOG.md at release time (#993). In `test`, not
`dev`: CI's test job installs `.[test]`, and with towncrier only in `dev` the
assembly tests in tests/test_changelog_fragments.py skipped on every pull request
(#994 review). `dev` still gets it through `disarm[test]`. Pinned here and read
from here by CI's changelog job, for the reason #985 recorded: a second copy of a
pin inside a workflow's `run:` line is invisible to Dependabot and turns every
bump red until someone copies the number across.

### bench: exact pins

Exact-pinned so cross-run comparator ratios are reproducible (#234 gate V8).
No `>=` permitted here: a floating comparator silently shifts every ratio's
denominator. The hash-locked lockfile (gate V7) pins transitive deps + wheels;
these `==` lines pin the declared intent. Versions are PyPI-current stable.

On `uroman`: (marker no longer needed: requires-python is >=3.10 since #277 lever 1)

### No context-mode extras

NOTE: context-aware transliteration (transliterate(context=True), ar/fa/he) is
NOT pip-installable. The dictionaries are large (~37 MB) and are not shipped in
the wheel. There used to be empty `arabic`/`hebrew`/`context` extras here; they
did nothing (installing them added no dictionaries), so they were removed (#56).
To enable context mode: build the dictionaries from a source checkout with

```bash
bash scripts/bootstrap_dicts.sh
```

and point the DISARM_DICT_DIR environment variable at the output directory.
(Tracked for a proper packaged distribution — see issues #56/#60.)

## `[tool.maturin]`

### Dictionary data files

Context dictionary data files (data/*.bin) are NOT shipped in the wheel. They
are built from source via `bash scripts/bootstrap_dicts.sh` and located at
runtime via the DISARM_DICT_DIR environment variable (see src/context.rs).
For a self-contained build, compile with the `embed-dicts` Cargo feature.

## `[tool.pytest.ini_options]`

### testpaths

Cookbook doc-tests live under docs/ and run as a separate invocation
(`python scripts/run_doc_tests.py`, see [Doc-test recipes](documentation.md#doc-test-recipes) — `pytest docs/` in one
process is NOT the gate, because `register_lang` is irreversible and one page's
registration leaks into another). They are deliberately NOT in testpaths:
docs/conftest.py would otherwise shadow tests/conftest.py, which the suite
imports shared fixtures from via `from conftest import ...`.

### pythonpath

Put the repo root on sys.path so tests can import the out-of-CI `benchmarks`
package (e.g. tests/test_adversarial_eval.py). Needed when disarm is
installed from a wheel rather than editable — as in CI — where the repo root
is not otherwise importable.

### addopts

Bare `pytest` runs CI's selection minus the opt-in `slow` tier (#658). CI uses
`-m "not formal and not hypothesis and not serial"`, so the two expressions differ by
`not slow` — but nothing in that tier executes under CI conditions anyway:
`test_cabi_header_drift` skips when $CI is set, and the ratio floors need the
`bench` extra, which CI does not install. Measured with CI=1 and no bench
extra: 5 selected, 5 skipped. The *executed* set matches; the *expression*
does not.

The Hypothesis tier was in the local default and in no CI job at all, so a
contributor paid ~67s on every run for a tier `nightly-hypothesis.yml` already
runs at 03:17 UTC with a freshly generated seed and a 10x oracle budget — a better
exercise of it than one more fixed-seed pass. `pytest -m hypothesis` on demand.
`-n auto --dist loadfile` is the default because the suite is no longer short enough
for worker startup to matter: 93s serial against 35s on four cores. Startup is not
free, though: re-measured on four cores, one small file costs ~0.6s more under
`-n auto` than under `-n 0` (test_slugify.py 1.1s against 0.5s), so pass `-n 0` for a
single-file inner loop, and for a debugger. `--dist loadfile` is not optional — see
the `test` extra.

`not serial` (#997 review): tests that measure wall-clock parallelism cannot be
measured with a worker already on every core, so the parallel run deselects them and
CI runs them in a step of their own with `pytest -m serial -n 0`. CI's `-m` replaces
this one, so its expression has to say `not serial` too; tests/test_serial_tier.py
holds the three together.

### markers

Opt-in since #658: the marker described itself as deselectable and nothing
deselected it, so it had no effect. Both things it covers are gated
elsewhere — `test_cabi_header_drift` mirrors the `cabi` CI job and costs a
cold cargo build (~25s) on the first run after a Rust change, and
`test_performance_claims`' ratio floors need the pinned comparators from
the `bench` extra and skip without them. Run with `pytest -m slow`.

## `[tool.towncrier]`

### Why fragments

Entries live one-per-change in `changelog.d/` and are assembled into
CHANGELOG.md at release. Editing CHANGELOG.md directly is what made every pair
of concurrent PRs conflict: entries were prepended to the same anchor line, so
the collision was a function of concurrency rather than of content.

### Wrapping

Entries here are essays with code blocks, tables and measured numbers. Re-wrapping
them would destroy that, and the bullet is already part of the fragment: they are
written exactly as they will appear, so `towncrier build` concatenates rather than
reformats.

### Fragment names

A fragment is named for the PULL REQUEST, not the issue. Several PRs per issue
is the norm here — #972 alone produced #973, #975, #976 and #989 — so keying on
the issue would put four fragments at one filename and rebuild the conflict this
is removing.

### Type order

The order below is the order the headings are written in, and it is the order the
releases already use: 0.16.0, 0.15.0 and 0.14.0 all open on *Upgrade notes*, the
part a reader has to act on. tests/test_changelog_fragments.py pins it to the
latest release's order.
