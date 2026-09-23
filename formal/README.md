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
| [`lean/Confusables`](lean/Confusables/README.md) | Lean 4 | the confusable fold, compose-at-lookup and `skeleton_key` | `skeleton_key` not a fixed point; Kirat Rai folds that break idempotence; six documentation claims (#1024) |
| [`lean/Detection`](lean/Detection/README.md) | Lean 4 | `has_anomalies`, `decode_smuggled` and `is_mixed_script`, with sweeps over the detector/cleaner pairs and the hostname screen | detectors silent on text their cleaners change, and split verdicts on canonically equivalent spellings (#1025); script-table gaps and a smuggled-payload decoder miss (#1023); Default_Ignorable characters the hostname screen let through (#1019) |
| [`lean/Presets`](lean/Presets/README.md) | Lean 4 | every preset step list, the fast-path guard, `STEP_ORDER` and the pipeline profiles | `search_key`/`sort_key` not fixed points under `tr39` and `preserve`; profiles that orphan a negation overlay; a removed character separating two that compose; the `PRESETS` mirror and output ceiling; documentation claims (open) |
| [`lean/Sanitizers`](lean/Sanitizers/README.md) | Lean 4 | `sanitize_filename`, `slugify`, `UniqueSlugifier`, `strip_log_injection`, `escape_html`, `percent_encode`, `edit_distance` | a sanitized filename that is a Windows device name, an unvalidated separator, and `decode_to_utf8` letting a BOM override an explicit encoding (#1026); slug truncation and suffix defects (open); the hostname screen (#1019) |
| [`lean/Text`](lean/Text/README.md) | Lean 4 | case folding, whitespace and control strips, zalgo, display width, invisible strips, punctuation, contractions, edit distance | a spacing mark resetting the zalgo count; a Prepend character zeroing `terminal_width` (open) |
| [`bindings`](bindings/README.md), [`tla/CABI`](tla/CABI/README.md) | differential harness, TLA+ | every scalar and a 40,000-string corpus through the core and the Python, Node, Ruby, Java and C bindings; the C ABI's ownership and input protocol | invalid UTF-8 undefined behaviour at the C boundary (#1020); Java lone surrogates, Ruby ignoring the string encoding, binding defaults and argument checks that differ from Python (open) |
| [`tla/WatchPR`](tla/WatchPR/README.md) | TLA+ | the merge protocol of `scripts/watch_pr.py` against a pull request that changes while it is read | a failed thread read taken for "no threads", a merge of a head never evaluated, a refused merge retried blind, a superseded cancelled run stopping a green PR, and `--await-review` merging over a change request (this model's pull request) |

The READMEs describe the code at the commit each model was written against
(`bec93cf` for the first five, `595fbda` for the rest), and name its line numbers.
A model of the code as it was keeps agreeing with that commit, not with `main`: once a
finding is fixed, its reproduction stops reproducing and the differential test reports
the fixed behaviour as a disagreement. Where a model has a *fixed* variant (`Fixes.lean`,
`stepFixed`, the `*_fixed.cfg` configurations) that variant describes the fix as
proposed; the pull requests above say where the shipped fix differs.

## Running them

Lean: core Lean 4.34.0, no Mathlib (each project's `lean-toolchain` pins it).

```bash
cd formal/lean/Confusables && lake build      # about 2 minutes
cd formal/lean/Deletions && lake build        # about 4 minutes
cd formal/lean/Detection && lake build        # about 1 minute
cd formal/lean/Emoji && lake build            # about 9 minutes (bounded native_decide checks)
cd formal/lean/Presets && lake build          # about 2 minutes
cd formal/lean/Sanitizers && lake build       # about 2 minutes
cd formal/lean/Text && lake build             # about 2 minutes
cd formal/lean/Transliterate && lake build    # seconds
```

TLA+: TLC 1.7.4 (`tla2tools.jar`), Java 11 or later.

```bash
TLA2TOOLS=/path/to/tla2tools.jar bash formal/tla/Concurrency/run_tlc.sh
TLA2TOOLS=/path/to/tla2tools.jar bash formal/tla/CABI/run_tlc.sh
```

`run_tlc.sh` compares every configuration's verdict with `expected.tsv` and exits
non-zero on a difference. WatchPR runs from `formal/tla/WatchPR/run_tlc.py` instead: its
largest configurations explore tens of millions of states, so it is run by hand, and its
counterexamples live on as `tests/test_watch_pr_protocol.py` in the ordinary suite. The configurations that model the code *as it was* are
expected to fail, and stay in: a model change that made one pass would have lost its
bug.

The differential tests (`scripts/difftest.py`, `search/*.py`, `repro/*.py`) need an
importable `disarm` and are run by hand; each README says how. `bindings/` needs every
binding built against the in-repo core (`bindings/build.sh`), so it too is run by hand.

## In CI

`.github/workflows/formal.yml` runs every `lake build` and every `run_tlc.sh` when
anything under `formal/` changes. It is path-filtered and outside the "All checks
passed" roll-up, since nothing outside `formal/` can change a model's verdict.

## Trust

Results proved by induction rest on the Lean kernel alone. The bounded-exhaustive
checks use `native_decide`, which also trusts Lean's compiler and runtime; each README
says which results are which. A TLC pass covers every interleaving of the configuration
it names (two or three threads), not every thread count.
