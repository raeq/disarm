# Formal model of the confusable fold (Lean 4)

A Lean 4 model of the confusable surface at `595fbda`: the fold in `src/confusables.rs`,
compose-at-lookup in `src/compose.rs`, and `skeleton_key` in `src/presets.rs`, with the
Unicode normalization it runs on. It was validated against the real library by
differential testing before any proof or counterexample was trusted. Some properties are
proved for every input, some are checked exhaustively up to a length bound, and every
property that failed was cut down to a minimal input and reproduced on the library. A
Rust probe (`probe/`) and a Python sweep (`search/`) then ran the same properties
directly against the library over all of Unicode.

> **Status.** All fixed in #1024: F1, F3 and F4 in the code, F2 and F5-F10 in the
> documentation. What follows describes the code at `595fbda`, before the fix. `repro/fix.patch` is a proposed fix for F1, F3 and F4. It was applied to a
> scratch copy of the crate, where the probe finds no failure left and
> `cargo test --no-default-features` passes (1,163 tests). The model of the fix
> (`Fixes.lean`) agrees with that build on 504,205 inputs.

| Python surface | Rust | Lean |
|---|---|---|
| `normalize_confusables(text, digit_policy=)` | `normalize_confusables_fixed_cow` | `fixedFold` (`fixedFoldB` also returns whether the loop converged) |
| `is_confusable(text)` | `is_confusable` | `isConfusable` |
| `find_confusables(text)` | `find_confusables` | `findConfusables` (offsets dropped) |
| `find_unmapped_confusables(text)` | `find_unmapped_confusables` | `findUnmapped` (offsets dropped) |
| `skeleton_key(text, digit_policy=)` | `presets::skeleton_key` via `run_static` | `skeletonKey` (guard + `skeletonSteps`) |
| `normalize(text, form=)` | `unicode-normalization` 0.1.25 | `nfc`, `nfd`, `nfkc` |
| `fold_case(text)` | `fold_case_into` | `foldCase` |
| `find_key_collisions(values, key=)` | `collisions::find_key_collisions` | `findKeyCollisions` (checked in Python, see below) |

The model covers the Latin target only. The other three targets use the same code with
a different table, and the probe covers them.

## Layout

| File | Contents |
|---|---|
| `scripts/gen_tables.py` | Generates `Confusables/Tables.lean` from `src/tables/data/*.tsv` and the built library |
| `Confusables/Tables.lean` | Generated: the alphabet, its closed domain, and the real tables projected onto it |
| `Confusables/Model.lean` | The model. Each definition names its Rust item and line numbers |
| `Confusables/Fixes.lean` | The proposed fixes, applied to a copy of the model, plus each half of F1's fix alone |
| `Confusables/Props.lean` | The properties as `Bool` predicates on one input, the claim each encodes, and the enumerators |
| `Confusables/General.lean` | Theorems proved by the kernel for every input |
| `Confusables/Checks.lean` | Bounded-exhaustive theorems, and the witness and minimality theorems of the findings (`native_decide`) |
| `Main.lean` | Differential-test driver (`lake exe confmodel [fixed]`) |
| `Cex.lean` | Counterexample search (`lake exe cex N [filter...]`) |
| `scripts/difftest.py` | The model against the installed `disarm` |
| `scripts/difftest_fix.py` | The model of the fix against a build of the fix (two executables, no Python `disarm`) |
| `probe/` | A Rust crate on the in-repo core (`disarm::api`, the layer every binding calls) that sweeps the properties over all of Unicode |
| `search/sweep_codepoints.py` | The same properties, every code point, through the Python binding |
| `repro/*.py`, `repro/fix.patch` | One script per finding, run against the installed library, and the proposed patch |

## What is modelled

| Rust (at `595fbda`) | Lean |
|---|---|
| `confusables.rs:33-35` `skipped_by_detection` | `asciiGraphic` |
| `confusables.rs:129-145` `lookup_with_policy`, `:216-219` the two flags | `lookup` |
| `confusables.rs:203-257` `normalize_confusables_cow` (the compose-gated branch and the borrow-on-no-op branch) | `foldPass` (`none` = `Cow::Borrowed`) |
| `confusables.rs:281-305` `normalize_confusables_fixed_cow`, `:60` `MAX_CONFUSABLE_PASSES` | `fixedFoldB`, `fixedLoop`, `maxPasses` |
| `confusables.rs:309-342` `normalize_confusables_into` (no composition) | `foldInto` |
| `confusables.rs:374-394`, `:413-435`, `:480-497` | `findUnmapped`, `findConfusables`, `isConfusable` |
| `confusables.rs:922-943` `prototype_fold_into` | `prototypeFold` |
| `compose.rs:71-93` `needs_composition`, `could_compose` | `needsComposition`, `couldCompose` |
| `compose.rs:155-209` `Composed::next` | `composed` |
| `compose.rs:229-268` `recompose_excluded`, `excluded_prefix` | `recomposeExcluded`, `recomposeGreedy`, `excludedPrefix` |
| `presets.rs:2061-2122` `skeleton_key`'s step list | `skeletonSteps` |
| `presets.rs:443-462` `Step::FixedPoint`, `:28` `CONFUSABLE_FIXED_POINT_ITERS` | `fixedPoint`, `fpIters` |
| `presets.rs:950-980` `run_static`, `:829-891` `classify`, `:732-783` `acts_on_nonascii` | `skeletonKey`, `classify`, `Tables.guardNonAscii` |
| `case_fold.rs:75-100`, `whitespace.rs:33-58`, `whitespace.rs:117-126` | `foldCase`, `collapseWs`, `stripControl` |
| `unicode-normalization` 0.1.25 `recompose.rs:67-156` and canonical ordering | `recompose`, `reorder` |
| `collisions.rs:71-125` | `findKeyCollisions` |

**Not modelled, and why that is sound for the domain.** Conjoining Hangul jamo
(`compose.rs:127-149`): no jamo is in the domain, and the generator asserts it. In
`skeleton_key`, `ResolveDeletions`, `StripBidi`, `StripInvisible` and `StripZeroWidth`
are each the identity on a string with no BS/DEL, bidi control, invisible or zero-width
character, and the domain has none. Byte offsets: the model returns characters, and
`difftest.py` checks the library's offsets separately (each one starts a character of the
input, and they come in order).

## Abstraction

The characters are real `Char`s. The input alphabet has one code point for each class
the Rust code branches on:

| Code point | Why it is its own class |
|---|---|
| `a` | a plain letter, the target of U+0430 |
| `C` | an uppercase ASCII letter (`fold_case`, the guard), the target of U+04AA |
| `y` | composes with U+0300 to U+1EF3, which is a fold source |
| `I` | the prototype fold's letter half (`I` becomes `l`) |
| `1` | the prototype fold's digit half under `tr39` |
| `\|` | an ASCII fold source that detection skips (#957) |
| space | `collapse_whitespace`, and the guard's `WhitespaceOnly` verdict |
| U+0001 | a control that `StripControl` removes |
| U+0430 | CYRILLIC SMALL A: the basic homoglyph |
| U+00A5 | YEN SIGN: folds to `Y`, which then composes with a following mark (#522) |
| U+04AA | CYRILLIC CAPITAL ES WITH DESCENDER: folds to `C`, and with U+0327 composes to a source (#522) |
| U+0300, U+0301, U+0308, U+0327 | combining marks (ccc 230, 230, 230, 202) |
| U+0390 | GREEK SMALL IOTA WITH DIALYTIKA AND TONOS: case-folds to a decomposed triple |
| U+1EF3 | folds to a non-ASCII value, U+00FD |
| U+0101 | folds to a non-ASCII value, U+00E3 |
| U+0966 | DEVANAGARI DIGIT ZERO: a digit row (`0` numeric, `o` tr39, kept by preserve) |
| U+16D67 | KIRAT RAI VOWEL SIGN E: a starter that composes with the starter before it (Unicode 16) |
| U+2126 | OHM SIGN: an NFC singleton, which folds only after NFKC and a case fold |

**Tables.** `gen_tables.py` closes the alphabet under everything the model does:
canonical and compatibility decomposition, primary composition of two domain characters,
NFC of one code point, `fold_case`, the Latin map and the tr39 overrides (every value
character), and the #481 widening map. The result is a domain of 94 code points, with 62
primary composites and 1 widening-map entry over it. Each table is then evaluated on the
whole domain, so it is exact on every string over the domain, and no model run can leave
the domain. Decompositions, NFC and case folds come from the library itself
(`disarm.normalize`, `disarm.fold_case`), which uses Unicode 17. Combining classes and
the composition pairs come from Python's `unicodedata`. The five Kirat Rai code points
are newer than that database, so they are stated in the script, and the script checks
every composition pair against the library's NFC. The one real abstraction is the choice
of representatives: the model claims nothing about a code point outside the domain
beyond what its class shares.

**Loops.** The fold's loop is `fixedLoop` on a pass budget of 8, and `skeleton_key`'s is
`fixedPoint` on a budget of 8, as in the code. `composed` recurses on length:
`dropWhile_length_le` gives the termination measure.

## Validation (differential testing)

```bash
cd formal/lean/Confusables
lake build confmodel
PATH=/path/to/venv-with-disarm/bin:$PATH python3 scripts/difftest.py 200000 7 12 4
```

Each run feeds every string up to length `EXHAUSTIVE` over the 21-letter alphabet, plus
`N` weighted random strings, to the model and to the library, and compares 13 outputs
per input: `normalize_confusables` under all three policies, `is_confusable`,
`find_confusables` (source and target), `find_unmapped_confusables`, `skeleton_key`
under all three policies, NFC, NFD, NFKC and `fold_case`. It also checks the offsets
that the library reports.

Results against `595fbda` (the installed library was built from it):

| Seed | Inputs | Exhaustive to | Random, max length | Disagreements, all 13 modes |
|---|---|---|---|---|
| 7 | 404,205 | length 4 (204,205) | 200,000, 12 | 0 |
| 42 | 209,724 | length 3 (9,724) | 200,000, 6 | 0 |

The harness can disagree. With `--fixed`, the executable runs the fixed `skeleton_key`,
and on 29,724 inputs the three `skeleton_key` modes then disagree on 7,301, 8,305 and
7,289 inputs. The other ten modes still agree.

`difftest_fix.py` runs the fixed model against a build of the crate with
`repro/fix.patch` applied. On 504,205 inputs (exhaustive to length 4, plus 300,000
random strings up to length 12), the three `skeleton_key` modes agree with 0
disagreements. Against the shipped build, the same script reports about 9,000-10,000
disagreements per mode on 29,724 inputs.

## Library sweeps (no model involved)

`probe/` runs on `disarm::api`, the Rust layer that the Node, Ruby, Java, Kotlin and C
bindings call. `search/sweep_codepoints.py` runs through the Python binding.

| Sweep | Cases | Result |
|---|---|---|
| `search/sweep_codepoints.py`: every scalar value x 4 targets x 3 policies: fold idempotence, completeness, NFC/NFD invariance of the fold and of `is_confusable`, `is_confusable` against `find_confusables`, `unmapped_confusables` against `find_unmapped_confusables`, tr39 scoping, and `skeleton_key` idempotence, lowercase output and NFD invariance | 1,112,064 code points | idempotence, completeness (numeric and tr39), detection, unmapped consistency, tr39 scoping and lowercase output hold everywhere. Failures: F1 (8 code points), F2 (161 Latin, 66 Cyrillic, 23 Arabic, 25 Hebrew), F3/F4 (U+16D68-U+16D6A) |
| `probe pairs`: every table source, value character and decomposition head, crossed with every one of the 2,543 combining marks, for 4 targets x 3 policies | 35,299,383 | fold idempotence, NFC/NFD invariance of the fold and of detection, and detection against `find_confusables`: **0** failures anywhere. Completeness: 0 under numeric and tr39; under preserve, F2 (411,719 Latin cases) |
| `probe triples`: every Latin source, value character and decomposition head x composing mark x composing mark (124 x 124), numeric | 37,855,712 | idempotence, completeness, NFC/NFD invariance of fold and detection, detection = find: **0** failures |
| `probe skeleton`: every scalar value, and 17,452 bases x 124 composing marks, directly and with U+0001 between them, x 3 policies | 1,112,064 + 4,328,096 | F1: 8 + 36,649 non-idempotent (numeric), 2,788 keys that `is_confusable` flags. F3: 3 |
| `probe starters` | all of Unicode 17 | the only compositions whose last element is not a combining mark or a jamo are U+16D68-U+16D6A (Kirat Rai). No character with a non-zero combining class is outside `General_Category=M` |
| `search/sweep_codepoints.py`: `find_key_collisions(key="normalize_confusables")` against a reference grouping, and the #763 formula | 3,000 random batches | agree |
| `probe pairs` and `probe skeleton` on the patched build (`repro/fix.patch`) | as above | **0** failures, except F2, which the patch does not touch |

The existing exhaustive tests cover the Latin and Cyrillic targets only: the
`#[ignore]` test in `confusables.rs` under numeric, and `tests/exhaustive_confusables.rs`
under numeric and tr39. Nothing swept the Arabic and Hebrew targets (#792), the preserve
policy, or `skeleton_key` (whose idempotence test, `tests/test_skeleton_key.py:122`,
checks ten hand-picked probes) until the runs above. The `pairs` run found nothing new in the
fold; `skeleton_key` is where the failures are.

## Theorems

### Proved in general (`Confusables/General.lean`: kernel, every input)

Only `isMark_ascii` unfolds a table, and it states a table fact. None of the other
proofs unfolds a table, so they hold for the full tables and not only for the projection.

* `fixedFold_idem`: **idempotence follows from convergence**. If the loop leaves
  through a stability exit, `f(f(x)) = f(x)`, for every input and all three policies.
  The lemmas are `fixedLoop_stable`, `fixedFoldB_stable` and `fixedFold_of_stable`.
  Only convergence depends on the tables. `Checks.lean` bounds it, and no swept input
  reached the cap.
* `isConfusable_eq_find`: `is_confusable(s)` is true exactly when `find_confusables(s)`
  is non-empty.
* `foldPass_tr39_eq_numeric`, `foldPass_preserve_eq_numeric`: on a string with no
  override source (or no digit-row source), one tr39 (or preserve) pass is exactly one
  numeric pass. The lemmas are `lookup_tr39_of_no_override`, `lookup_numeric` and
  `lookup_preserve`.
* `borrowed_not_confusable`: under numeric or tr39, a string that the pass leaves
  borrowed is not confusable. This is completeness for every fold that ends on a
  borrowing pass. The other exit, an owned pass equal to its input, can only happen on
  input with a combining mark, and it depends on the tables. Under preserve it is false
  (F2). The lemma `composed_no_mark` says that `composed` is the identity without marks.

### Bounded-exhaustive (`Confusables/Checks.lean`, `native_decide`)

Length <= 5 means all 4,288,306 strings over the alphabet. Length <= 4 means 204,205.

| Theorem | Statement | Bound |
|---|---|---|
| `fold_idem_*` | the fold is idempotent (all 3 policies) | <= 5 |
| `fold_converges_*` | the loop never reaches the 8-pass cap (all 3) | <= 5 |
| `fold_complete_numeric`, `_tr39` | `is_confusable` is false on the output | <= 5 |
| `detect_nf` | `is_confusable(NFC s) = is_confusable(NFD s)` | <= 5 |
| `detect_changes` | a detection implies the fold changes the string | <= 5 |
| `tr39_scope`, `preserve_scope` | a policy differs from numeric only where its rows occur | <= 5 |
| `unmapped_sound` | `find_unmapped` reports only unmapped characters | <= 5 |
| `sk_lower_*`, `sk_nf_tr39`, `sk_nf_preserve` | `skeleton_key` is case-folded, and form-invariant off the guard | <= 4 |
| `fixed_sk_*` | the fixed `skeleton_key` is idempotent (3 policies), form-invariant, not flagged by `is_confusable`, case-folded, and the guard is an optimisation | <= 4 |

### Failed: the witnesses

Each finding below has a witness theorem and a minimality theorem (`..._minimal`: no
shorter string fails). `lake exe cex N` prints the shortest failure of every property.

## Findings

Severity is for a caller relying on the documented contract. Line numbers are at
`595fbda`. Each reproduction is a script in `repro/`, and the output quoted is from the
library as installed.

### F1 (a) code bug, **medium**: `skeleton_key` is not idempotent, and confusable inputs miss each other

The claim is at `presets.rs:2085-2098` and in the `skeleton_key` docstring
(`python/disarm/_presets.py`): *"a key that is not a fixed point is not a key"*. The
minimal witness is one code point (`F1a_casefold_decomposes`, `F1a_minimal`).

```python
>>> sk = disarm.skeleton_key
>>> sk("\u0390"), sk(sk("\u0390"))                  # (a)
('i\u0308\u0301', '\u1e2f')
>>> sk("\u00a5\u0300"), sk(sk("\u00a5\u0300"))      # (b)
('y\u0300', '\xfd')
>>> disarm.is_confusable(sk("\u00a5\u0300"))        # the key is itself flagged
True
>>> sk("a\x01\u0300"), sk(sk("a\x01\u0300"))        # (c)
('a\u0300', '\xe0')
>>> sk("\u04aa\u0327"), sk("\u00e7")                # the #522 pair: no collision
('c\u0327', 'c')
>>> sk("cafe\x01\u0301"), sk("caf\u00e9")           # a control changes the key
('cafe\u0301', 'caf\xe9')
```

Across all of Unicode, 8 single code points fail. So do 36,649 of the 4,328,096
base-plus-mark probes (38,041 under tr39), and 2,788 keys are flagged by `is_confusable`.

**Root cause.** The step list at `presets.rs:2066-2107` normalizes once, at the top, and
then runs steps that can each leave the string denormalized, with nothing after them to
recompose it:
(a) `FoldCase` is full case folding and emits decomposed sequences (U+0390 becomes
U+03B9 U+0308 U+0301). (b) `ConfusablesCtx` is `normalize_confusables_into`
(`confusables.rs:309-342`), which deliberately does not compose, so a folded base is
left beside a mark it composes with. This is the interaction #522 fixed for
`normalize_confusables`, and it is still present here. (c) `StripControl` (step 6) runs
after the last fold, so removing a control joins a base to its mark.

**Proposed fix** (`repro/fix.patch`, `Fixes.lean` `skeletonStepsFixed`). Add
`Step::Nfkc` to the fixed point, making it `[FoldCase, ConfusablesCtx("latin"), Nfkc]`,
and move `StripControl` and `StripZeroWidth` up beside `StripInvisible`, ahead of the
first fold. Both halves are needed: with only the first, `[a, U+0001, U+0300]` still
fails (`F1_half_fix_nfkc`), and with only the second, `[U+0390]` still fails
(`F1_half_fix_strip`). After the patch the probe finds 0 failures, and `fixed_sk_*`
hold to length 4. The patch changes keys, so under #644/#733 it belongs in a minor
release with an upgrade note.

### F2 (b) doc overclaim, **low**: under `digit_policy="preserve"` the fold's output is confusable

The claims are the guide's *"its output is never itself confusable"*
(`docs/user-guide/confusables.md:268-270`) and the completeness sentence at
`api/safety.rs:112-113` and `confusables.rs:269-271`. `normalize_confusables` accepts
`preserve`, and preserve keeps the digit rows by design (#648). `is_confusable` takes
no policy, so it still flags them.

```python
>>> out = disarm.normalize_confusables("\u0966", digit_policy="preserve"); out
'\u0966'
>>> disarm.is_confusable(out)
True
```

161 Latin code points behave this way (66 Cyrillic, 23 Arabic, 25 Hebrew), and so do
411,719 base-plus-mark probes. The witnesses are `F2_preserve_incomplete` and
`F2_minimal`. **Fix:** qualify the completeness claim as holding under `numeric` and
`tr39`, which is what `borrowed_not_confusable` and the sweeps establish. The
alternative is to give `is_confusable` the policy.

### F3 (a) code bug, **low**: the #458 fast-path guard skips a composition that NFKC performs

`skeleton_key`, `canonicalize` and `canonicalize_strict` return the input unnormalized
for Kirat Rai text in NFD under the default policy. Any other `digit_policy` bypasses
the guard (`presets.rs:962`), so it normalizes the same text, although no digit is
involved.

```python
>>> d = "\U00016d67\U00016d67"               # NFD of U+16D68
>>> disarm.canonicalize(d), disarm.canonicalize(d, digit_policy="tr39")
('\U00016d67\U00016d67', '\U00016d68')
>>> disarm.skeleton_key(d), disarm.skeleton_key("\U00016d68")
('\U00016d67\U00016d67', '\U00016d68')
```

**Root cause.** `acts_on_nonascii` (`presets.rs:780`) tests NFKC one character at a time
and exempts only conjoining jamo (`is_conjoining_jamo`, `presets.rs:792-794`). Unicode 16
added a second class of starter that composes with the starter before it: Kirat Rai
U+16D63 or U+16D67 followed by U+16D67. The probe's `starters` subcommand shows that
this is the only such class in Unicode 17. The witnesses are `F3_guard`, `F3_nf` and
`F3_policy`. **Fix:** add `0x16D63 | 0x16D67` to `is_conjoining_jamo`, and rename it.
Better still, derive the set at build time as every non-mark starter that appears
second in a primary composition, so that the next Unicode version cannot reopen this.

### F4 (a) code bug, **low**: the fold is not invariant to the input's normal form

The claim is at `api/safety.rs:106-110`: *"the fold is invariant to the input's normal
form"*. It fails on the same Kirat Rai class, for the same reason, in
`compose::Composed` (`compose.rs:179`, where a cluster is anchored only by a following
combining mark).

```python
>>> c = "\U00016d68"; d = disarm.normalize(c, form="NFD")
>>> disarm.normalize_confusables(c), disarm.normalize_confusables(d)
('\U00016d68', '\U00016d67\U00016d67')
```

No Kirat Rai character is a confusable source, so detection is unaffected. The same
gate feeds transliteration's compose-at-lookup. The witnesses are `F4_fold_nf` and
`F4_minimal`. **Fix:** treat U+16D67 as a cluster follower in `could_compose` and
`Composed::next` (the second hunk of `repro/fix.patch`), or derive the set at build
time as in F3.

### F5 (b) doc overclaim, **low**: "45 rows" is 47

The claim is *"disarm and upstream TR39 disagree on 45 rows"* / *"The two differ on 45
rows and agree on everything else"*. It appears at `api/safety.rs:128`,
`confusables.rs:68`, `docs/user-guide/confusables.md:319,325`,
`python/disarm/_api.py:879,885` and `python/disarm/_text.py:125`.
`confusables_digit_tr39.tsv` has 47 rows, and the sweep finds exactly 47 code points on
which tr39 and numeric differ. The half about agreeing everywhere else holds: it is
`tr39_scope`, `foldPass_tr39_eq_numeric`, and the sweep. **Fix:** say 47. Better, add the
count to `tests/test_doc_table_counts.py`, which does not cover it.

### F6 (b) doc overclaim, **low**: the `normalize_confusables` docstring says 68 and 8

The docstring (`python/disarm/_api.py:833-849`) and `src/pipeline.rs:154-156` say that
*"68 code points get a different answer (8 for the Cyrillic target)"*, split 44/15/9.
The measured counts are **65 and 5**, which are what the guide, the limitations page and
`tests/test_fold_order_divergence.py` pin, split 43/15/7. #833 fixed the pages and not
these two places. **Fix:** update both, and extend the pinning test to the docstring.

### F7 (b) doc overclaim, **low**: `is_confusable` says only `"latin"` is accepted

The `is_confusable` docstring (`python/disarm/_api.py:2366-2367`) says: *'Currently only
"latin" is supported; any other value raises DisarmError'*. The library accepts all four
targets:

```python
>>> disarm.is_confusable("\u0430", target_script="cyrillic")
False
```

The same staleness is in the Layer-1 rustdoc, which says *"`"latin"` or `"cyrillic"`.
Any other value returns an error"* (`confusables.rs:185-186, 356-357, 372-373,
411-412, 478-479`). #888 fixed the error message and not these.

### F8 (b) doc overclaim, **low**: "the presets have no such switch"

The guide says, at `docs/user-guide/confusables.md:348-350`: *"The presets
(`canonicalize`, `catalog_key`, `search_key`, ...) have no such switch and always fold
numerically"*. Since #896 they take `digit_policy`:

```python
>>> disarm.canonicalize("\u0966", digit_policy="tr39"), disarm.search_key("\u0966", digit_policy="tr39")
('o', 'o')
```

### F9 (c) inconsistency, **low**: the `Text.normalize_confusables` stub has no `digit_policy`

`python/disarm/_text.pyi:27` declares
`def normalize_confusables(self, *, target_script: str = "latin") -> Text`, but the
implementation (`python/disarm/_text.py:118-120`) takes `digit_policy`. A type-checked
caller cannot pass it. **Fix:** add the parameter to the stub, and let
`target_script` accept `Script` as the implementation does.

### F10 (b) doc overclaim, **low**: the borrow contract, and an idempotence argument

`api/safety.rs:118-120` says: *"Returns `Cow::Borrowed` when the input is already NFC
and nothing folds, `Cow::Owned` otherwise"*. Both directions fail (`probe cow`):
`"x\u{0301}"` is NFC and nothing folds, yet it comes back `Owned`. `"\u{2126}"` is not
NFC, yet it comes back `Borrowed`. What actually decides it is "no combining mark or L
jamo, and nothing folds". Separately, the proptest at `confusables.rs:849-852` says
idempotence *"must hold because every confusable maps to an ASCII target"*. 35 Latin
rows do not map to ASCII (`normalize_confusables("\u0101")` is `'\xe3'`). Idempotence
holds for another reason, the loop (`fixedFold_idem`).

## Checked and holding (not findings)

* The fold (`normalize_confusables`) is idempotent, complete under numeric and tr39,
  and form-invariant everywhere except F4. This holds for every target and every
  policy, over 35.3 M probes and all of Unicode.
* Detection is form-invariant, and `is_confusable` equals `bool(find_confusables)`
  (kernel proof, plus sweeps).
* tr39 is a no-op for the Cyrillic, Arabic and Hebrew targets. tr39 and preserve change
  nothing outside their rows.
* `find_key_collisions(key="normalize_confusables")` equals a reference grouping, and
  the #763 reduced-count formula holds, on 3,000 random batches.
* No function raises on lone surrogates, NUL, U+FFFD or U+10FFFF.
* The documented counts that are right: 2,356 / 1,352 / 373 / 261 mappings, 6,565
  upstream sources, 4,330 Latin-unmapped, and the five ASCII characters `% 0 1 I m`.

## Not confirmed

* **The NFC wording.** *"The input is canonically recomposed (NFC) before folding"*
  (`api/safety.rs:106`) is literally false for singletons with no following mark:
  `normalize_confusables("\u2126")` stays U+2126 instead of becoming U+03A9. Over every
  non-NFC code point, though, the fold of `c` and the fold of `NFC(c)` agree up to NFC,
  and detection differs only for U+037E, U+1FEF and U+212A. Each of those has a
  printable-ASCII NFC image that detection skips, which is intended (#957). There is no
  observable defect beyond the wording.
* **Convergence in general.** Idempotence is proved from convergence, and convergence
  is only bounded (length <= 5 in the model, and every probe in the sweeps). The bound
  was the gap: `C` + U+0327 composes to `Ç`, which folds back to `C`, so each pass takes
  one cedilla, and a stack needs one pass per mark. The nightly fuzz run found U+04AA +
  eight U+0327, which used up the 8-pass cap. A wrong result needs U+04AA + nine or
  `C` + ten, 10 or 11 characters, twice the bound. Every symbol of it is in the
  alphabet: no bound of 5 could reach it, however long the check ran. Since then the
  Rust no longer stops at the cap: past it, `converge_slow` folds span by span and skips
  a cycle's repeats. `fixedLoop` and `maxPasses` model the loop as it was, and still
  hold on every string of length <= 5.

## Re-running

```bash
cd formal/lean/Confusables
lake build                       # all proofs and bounded checks: 2.5 to 4.5 minutes
lake exe cex 4                   # shortest failure of every property (seconds)

# regenerate the tables (needs an importable disarm)
python3 scripts/gen_tables.py

# the differential test
PATH=/path/to/venv/bin:$PATH python3 scripts/difftest.py 200000 7 12 4
PATH=/path/to/venv/bin:$PATH python3 scripts/difftest.py 20000 1 8 3 --fixed   # must disagree

# library sweeps (Rust, on the in-repo core)
cd probe && cargo run --release -- pairs      # about 3 minutes on 4 cores
cargo run --release -- triples     # about 9 minutes
cargo run --release -- skeleton; cargo run --release -- starters; cargo run --release -- cow
cd .. && python3 search/sweep_codepoints.py                           # about 5 minutes

# the reproductions (each exits 0 while its finding is present)
for f in repro/*.py; do python3 "$f"; done

# the fix: apply to a scratch copy of the crate, never the checkout under test
root=$(git rev-parse --show-toplevel); mkdir -p /tmp/patched
git -C "$root" archive HEAD | tar -x -C /tmp/patched
(cd /tmp/patched && patch -p1 < "$root/formal/lean/Confusables/repro/fix.patch")
(cd /tmp/patched/formal/lean/Confusables/probe && cargo build --release && ./target/release/confusables-probe skeleton)
python3 scripts/difftest_fix.py /tmp/patched/formal/lean/Confusables/probe/target/release/confusables-probe 300000 1 12 4
```
