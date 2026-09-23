# Formal models

Machine-checked models of parts of disarm, written to find bugs rather than to
decorate the code. Each model was written against the source, then **validated
against the built library by differential testing** before any proof or
counterexample counted. Every property that failed was cut down to a minimal input
and reproduced on the library, and every finding became a fix with a regression test
in the ordinary suites: the fix is kept fixed by those tests, not by the model.

| Model | Tool | Subject | Findings, and where they were fixed |
|---|---|---|---|
| [`lean/Transliterate`](lean/Transliterate/README.md) | Lean 4 | the argument for invariants I1–I3 and I7 | `context=True` passed non-word spans through raw (#1008); canonical equivalents that disagreed (#1013); the claims `docs/formal-verification.md` corrected |
| [`lean/Deletions`](lean/Deletions/README.md) | Lean 4 | `resolve_deletions` | line breaks the detector knew and the resolver did not; a zero-width character taking a cell (#1010) |
| [`lean/Emoji`](lean/Emoji/README.md) | Lean 4 | `replace_emoji`, `demojize` and the pipeline step | fully qualified ZWJ sequences named piece by piece; a dropped emoji gluing two words together; removals that left a new keycap behind (#1011); a selector continuing a sequence where none belongs, which the model caught in #1011 itself (#1015) |
| [`tla/Concurrency`](tla/Concurrency/README.md) | TLA+ | locks and the GIL in the Python binding; registration in the Rust API | two deadlocks through `__del__` (#1009); a stale cached transliterator (#1012); a registration landing after the seal and past the cap, and a `UniqueSlugifier` that could not be shared (#1014) |

The READMEs describe the code at the commit each model was written against
(`bec93cf`), and name its line numbers. Where a model has a *fixed* variant (`Fixes.lean`,
`stepFixed`, the `*_fixed.cfg` configurations) that variant describes the fix as
proposed; the pull requests above say where the shipped fix differs.

## Running them

Lean: core Lean 4.34.0, no Mathlib (each project's `lean-toolchain` pins it).

```bash
cd formal/lean/Deletions && lake build        # about 4 minutes
cd formal/lean/Emoji && lake build            # about 9 minutes (bounded native_decide checks)
cd formal/lean/Transliterate && lake build    # seconds
```

TLA+: TLC 1.7.4 (`tla2tools.jar`), Java 11 or later.

```bash
TLA2TOOLS=/path/to/tla2tools.jar bash formal/tla/Concurrency/run_tlc.sh
```

`run_tlc.sh` compares every configuration's verdict with `expected.tsv` and exits
non-zero on a difference. The configurations that model the code *as it was* are
expected to fail, and stay in: a model change that made one pass would have lost its
bug.

The differential tests (`scripts/difftest.py`, `search/*.py`, `repro/*.py`) need an
importable `disarm` and are run by hand; each README says how.

## In CI

`.github/workflows/formal.yml` runs every `lake build` and every TLC configuration
when anything under `formal/` changes. It is path-filtered and outside the "All checks
passed" roll-up, since nothing outside `formal/` can change a model's verdict.

## Trust

Results proved by induction rest on the Lean kernel alone. The bounded-exhaustive
checks use `native_decide`, which also trusts Lean's compiler and runtime; each README
says which results are which. A TLC pass covers every interleaving of the configuration
it names (two or three threads), not every thread count.
