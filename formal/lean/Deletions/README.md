# Formal model of `resolve_deletions_into` (Lean 4)

A Lean 4 model of `resolve_deletions_into` in `src/deletions.rs`, which is what
`TextPipeline(resolve_deletions=True)` and `TextPipeline(resolve_deletions=True,
resolve_cr=True)` run. The model is validated against the real library by differential
testing. Properties the code and docs claim are then proved about it. Each failed proof was
cut down to a minimal counterexample, then reproduced on the built library.

> **Status.** Both findings are fixed in #1010, which also adds their regression tests
> (`tests/test_window_and_erase_boundaries.py`). This README describes the code as it was
> at `bec93cf`; `stepFixed` is the fix as proposed. Run against the library after #1010,
> `scripts/difftest.py` finds `stepFixed` identical to the shipped fix on all 999,186
> cases, and the unfixed model identical on the 680,732 the fix did not change.

Written against `main` at `bec93cf`. Line numbers (`L114`) refer to `src/deletions.rs` at
that commit. The toolchain is core Lean 4.34.0 only, with no Mathlib.

## Layout

| File | Contents |
|---|---|
| `Deletions/Model.lean` | The model. `step` mirrors the loop body branch by branch, and `run`, `finish`, `needsScan`, `resolveInto` and `resolve` cover the rest. `stepFixed`/`resolveFixed` model the proposed fix. `simple` is the reference stack algorithm. |
| `Deletions/Lists.lean` | List lemmas: `set`, `modify`, `getD`, counting. |
| `Deletions/Invariants.lean` | The loop invariant `WF`: no panic, no underflow, dead code. |
| `Deletions/Output.lean` | General theorems about the output. |
| `Deletions/Simple.lean` | A simulation relation between the loop and the stack algorithm. |
| `Deletions/Spec.lean` | Vocabulary: the detector's `CR` rule, what is on screen, and word enumeration. |
| `Deletions/Vectors.lean` | Every `resolve` assertion from the Rust unit tests and the Python boundary test, replayed on the model. |
| `Deletions/Bounded.lean` | Bounded exhaustive checks (`native_decide`, N = 7). |
| `Deletions/Findings.lean` | The failed properties, as minimal counterexamples checked by the kernel. |
| `Deletions/Axioms.lean` | `#print axioms` for the headline theorems (not in the default build). |
| `Main.lean`, `scripts/difftest.py` | The differential test. |

## The model

The alphabet is split by the branch each character takes. Every non-control class carries
an identity (`Nat`), so outputs can be compared character by character.

| Class | Rust | Concrete characters used in the differential test |
|---|---|---|
| `bs`, `del`, `cr`, `lf` | `BS`, `DEL`, `CR`, `LF` (L49-52) | `\b`, `\x7f`, `\r`, `\n` |
| `v i` | `occupies_cell` is true | `a`-`z`, `U+0605`, `TAB`, `NUL`, `中`, `U+00AD` |
| `z i` | `occupies_cell` is false (L41-46) | `U+200B`, `U+0301`, `U+200D`, `U+FE0F`, `U+2060`, `U+202E`, `U+E0041`, `U+034F` (one per predicate) |
| `brk i` | `VT`, `FF`, `NEL`, `LS`, `PS`. `occupies_cell` is true, so the current code treats these exactly like `v`. | `\x0b`, `\x0c`, `\x85`, `U+2028`, `U+2029` |

The state `St` has the fields `out`, `line : List Cell`, `col`, `lead` and `occ`, which
match `out`, `line`, `col`, `lead` and `occupied`. A `Cell` is a `List C`, and `[]` is a
blank cell.

| Rust | Lean (`Model.lean`) |
|---|---|
| L68-70 early return | `needsScan`, `resolveInto` |
| L88, L101-113 erase: blank `line[col-1]`, decrement `occupied` if it was non-blank | `step`, first branch (`List.set`) |
| L114-122 line ending: `LF`, or `CR` when `!cr` or `peek` is none or `LF` | `endsLine`, second branch |
| L123-125 lone `CR` under the flag: `col = 0` | third branch |
| L126-130 no-cell character at `col > 0` joins `line[col-1]` | fourth branch (`List.modify`) |
| L131-143 no-cell character with `occupied > 0` goes to `lead` | fifth branch |
| L144-149 overwrite `line[col]` | sixth branch |
| L150-154 push a new cell | last branch |
| L156-159 flush `lead`, then the cells | `finish` |
| L165 `out != text` | `resolveInto` |
| `chars.peek()` | `rest.head?` in `run` |

`resolve` is what a caller sees. On `false` the caller keeps its input, as `pipeline.rs`
L619-624 and the `resolve` test helper (L172-179) do.

The model covers the control flow and the data. It does not cover UTF-8 byte handling,
allocation, or the cost claims ("O(1)", "not quadratic"). Nor does it model how
`occupies_cell` classifies individual code points: that rests on the differential test and
on the concrete characters above.

## Validation: differential testing

```bash
lake build difftest                                  # this directory
python3 scripts/difftest.py --exhaustive 7 --random 300000 --seed 1005
```

`difftest.py` covers two sets of inputs:

* every word of length 7 or less over `BS DEL CR LF v0 v1 z0 n0` (2,396,745 words, the
  same alphabet and bound as `Bounded.lean`);
* 300,000 random words of length 18 or less over the full concrete alphabet.

Each input runs under both flags, through `disarm.TextPipeline`. The model's output is
mapped to concrete characters by an injective table and compared as strings.

**Result: 5,393,490 of 5,393,490 comparisons agree.** That is 2,696,745 inputs under 2
flags. The defaults (`--exhaustive 6 --random 200000 --seed 937`) give 999,186 of 999,186.

The exhaustive part runs over exactly the words `Bounded.lean` quantifies over, and the
model agrees with the library on every one of them. So each bounded result about the
*current* model is also a result about the built library up to length 7, not only about
the model.

## What is proved

### In general, for every input, by induction (`Invariants.lean`, `Output.lean`, `Simple.lean`)

None of these use `sorry` or `native_decide`. `Axioms.lean` shows only `propext`,
`Quot.sound` and `Classical.choice`.

| Theorem | Statement |
|---|---|
| `wf_step`, `wf_run` | Loop invariant: `col ≤ line.len()`; every cell left of the cursor is non-blank; `occupied` = number of non-blank cells (L80); cells and `lead` hold no control. |
| `no_panic` | Every `line[col-1]` and `line[col]` index is in bounds, and `occupied ≥ 1` whenever L110 decrements it. No panic, no `usize` underflow. |
| `l128_dead` | At L127 the cell left of the cursor is never blank. **`occupied += 1` on L128 is dead code.** |
| `resolve_eq_finish` | The L68 pre-check and the L165 changed-flag are transparent. The caller always sees the loop's output. |
| `resolve_clean`, `resolve_no_erase` | The output holds no `BS`/`DEL`. Under `cr`, every `CR` in it is followed by `LF` or ends the text. |
| `finish_run_clean` | On text that is already clean, the loop rebuilds its input exactly. |
| `resolve_idem` | **Idempotence**: `resolve cr (resolve cr t) = resolve cr t`, for both flags. |
| `resolve_count_le` | **No invention or duplication**: `count x (resolve cr t) ≤ count x t` for every character `x`. |
| `resolve_lf` | The output's `LF`s, in order, are exactly the input's, under both flags. |
| `resolve_crlf_nocr` | Under `cr = false`, the `CR`s and `LF`s, in order, are exactly the input's. |
| `resolve_false_eq_simple` | Under `cr = false`, the resolver **is** the stack algorithm: an erase pops a cell, a no-cell character joins the top cell or starts one, anything else pushes. |
| `resolve_true_noCR_eq_simple`, `resolve_flag_irrelevant_noCR` | On input with no `CR`, `cr = true` gives the same stack algorithm, so the flag makes no difference. |
| `noCR_right_of_cursor_blank` | **L80-83**: without a `CR`, every cell at or right of the cursor is blank and `lead` stays empty. |
| `resolve_false_sublist`, `resolve_true_noCR_sublist` | With no overwriting `CR` possible, the output is a **subsequence** of the input: nothing is reordered. |
| `fixed_z_keeps_cursor` (`Findings.lean`) | In the fixed model, a no-cell character never moves the cursor, from any state. |

Order *does* change under `cr = true` when a `CR` overwrites. That happens in two ways,
and both are documented:

* The overwrite itself: `abc\rX` gives `Xbc`.
* The `lead` buffer, which puts a no-cell character met at column 0 after a `CR` ahead of
  the line (L136-137, the #1005 changelog entry). It is idempotent (`resolve_idem`), and
  by `noCR_right_of_cursor_blank` it cannot happen without a `CR`.

### Bounded exhaustively, N = 7: 2,396,745 words (`Bounded.lean`, `native_decide`, about 4 minutes)

| Theorem | Model | Result |
|---|---|---|
| `erase_costs_one_cell` | current, both flags | holds. This is the Rust test `an_erase_costs_at_most_one_cell` checked exhaustively instead of fuzzed. |
| `seen_ignores_z_nocr` | current, `cr = false` | holds. Removing every no-cell character leaves the visible output unchanged. |
| the same property under `cr = true` | current | **fails**: Finding 1 |
| `fixed_idem`, `fixed_clean`, `fixed_lf`, `fixed_no_invention`, `fixed_erase_costs_one_cell` | fixed, both flags | hold |
| `fixed_seen_ignores_z` | fixed, both flags | holds |
| `fixed_detector_agrees` | fixed, `cr = true` | holds. A `CR` the `deletion` detector does not report never changes what is on screen. |
| `fixed_breaks_survive` | fixed, both flags | holds. Every `VT`/`FF`/`NEL`/`LS`/`PS` survives. |
| `fixed_agrees_elsewhere` | fixed vs current | identical on every input without a no-cell character or a `brk`. The fix moves nothing else. |

`Vectors.lean` replays every `resolve` and `resolve_deletions_into` assertion from the
`src/deletions.rs` tests and from `TestEraseAfterCarriageReturn` in
`tests/test_window_and_erase_boundaries.py` on the model: 39 `example`s, some quantified
over both flags. All of them pass.

## Findings

### Finding 1: a no-cell character at the start of a line takes a cell, so `resolve_cr` misplaces the overwrite

L131 sends a no-cell character at column 0 to `lead` only when `occupied > 0`. On an
empty or all-blank line, the character falls through to L144/L150 instead. It takes a
cell and moves the cursor (`z_moves_cursor`). L136 says the opposite: "A character that
takes no cell does not move the cursor either". So does the #1005 changelog entry: "It
now takes no cell and moves nothing".

Under `resolve_cr`, every later overwrite then lands one column right of where a terminal
puts it. The visible result depends on an invisible character (`seen_depends_on_z`), and
one leading `U+200B` defeats the resolution `resolve_cr` exists for.

```bash
python3 -c 'import disarm; p=disarm.TextPipeline(resolve_deletions=True, resolve_cr=True); print(repr(p("ZZZZZZ\rpaypal")), repr(p("\u200bZZZZZZ\rpaypal")), repr(p("\u0301ZZZZZZ\rpaypal")), repr(p("\u200ba\ra")), repr(p("\u200b\ra")))'
# 'paypal' 'paypalZ' 'paypalZ' 'aa' 'a'
```

Expected: `'paypal' 'paypal' '\u0301paypal' '\u200ba' '\u200ba'`, which is what a
terminal shows, with the invisible character kept as L136-137 promise. The last case also
loses the `U+200B` it was given (`z_overwritten`), and L137 says removing it is
`strip_zero_width`'s job. The detector still reports these inputs
(`has_anomalies` → `True`).

**Severity: low to medium.** It needs the opt-in `resolve_cr`, and no preset, profile or
key builder sets that. Under `cr = False` the visible output is provably unaffected
(`seen_ignores_z_nocr`).

**Minimal fix:** at L131, replace `!occupies_cell(ch) && occupied > 0` with
`!occupies_cell(ch)`. The branch is already reached only at `col == 0`. After the change
`occupied` is never read, so the counter and L127-129 can go. Three results that are
asserted today then change:

* `"ab\b\b\u200b\b"` and `"\u200b\b"` give `"\u200b"` instead of `""`. They still
  agree with each other, which was Copilot's point on #1005.
* `"\u200b\ba"` gives `"\u200ba"` instead of `"a"`.

A `BS` at column 0 erases nothing, which is #937's own model. The assertions at
`src/deletions.rs` L191-192 and in `test_blank_cells_to_the_right_are_not_a_line_to_keep`
move with the fix. Checked on the model: `fixed_*` in `Bounded.lean`.

### Finding 2: the detector treats `VT`, `FF`, `NEL`, `LS` and `PS` as line breaks; the resolver does not

L61-63 say the resolver uses "the same guard `anomalies::overwriting_cr` applies, so the
detector and the resolver cannot disagree about what a line ending is". But
`overwriting_cr` starts a line after every UAX #14 mandatory break
(`anomalies::is_line_break`), while the resolver ends a line only at `LF` or a passing
`CR`, and `occupies_cell` gives the other five a cell. There are two consequences.

**(a) With `resolve_cr`:** a `CR` right after one of these five is at the start of its
line, so the detector stays silent. The resolver still overwrites text on the *previous*
line, including the break itself (`detector_silent`, `resolver_eats_break`,
`resolver_eats_previous_line`).

```bash
python3 -c 'import disarm; p=disarm.TextPipeline(resolve_deletions=True, resolve_cr=True); print([(repr(p(s)), disarm.has_anomalies(s)) for s in ["abc\u2028\rX", "abc\x85\rX", "abc\x0b\rX", "\u2028\rX", "abc\n\rX"]])'
# [("'Xbc\\u2028'", False), ("'Xbc\\x85'", False), ("'Xbc\\x0b'", False), ("'X'", False), ("'abc\\nX'", False)]
```

Expected: `'abc\u2028X'` and so on, as the `LF` case already gives. The reader sees
`abc` on one line and `X` on the next. The detector calls the input clean, yet the
resolver loses the `a`. That is "losing text the reader can see", the risk #934 declined
and the risk L99-100 cite. **Severity: medium**, behind the opt-in flag.

**(b) Without the flag:** a `BS` erases the break and joins two lines. It can never do
that to an `LF` (`bs_erases_break`). The default presets resolve deletions, so stored keys
move:

```bash
python3 -c 'import disarm; print([disarm.canonicalize(s) for s in ["pay\n\bpal", "pay\x85\bpal", "pay\u2028\bpal"]])'
# ['pay pal', 'paypal', 'paypal']
```

Expected: `'pay pal'` for all three, matching `LF`. A `BS` at the start of a line has no
cell before it. **Severity: low.** It needs crafted input, and the error goes in the
direction of a false match rather than a missed one.

**Minimal fix:** at L114, end the line at every mandatory break, reusing the detector's
predicate so the two cannot drift:
`(ch != CR && anomalies::is_line_break(ch)) || (ch == CR && (!cr || …))`. This means
making `is_line_break` `pub(crate)`. Checked on the model: `fixed_detector_agrees`,
`fixed_breaks_survive`. Part (b) changes key-builder output for input with a `BS` right
after one of the five, which is a `KEY_SCHEMA_VERSION` question.

### Checked and not a bug (matches documented intent)

* **`lead` reordering**: `abc\r\u200bY` gives `\u200bYbc`. It is documented at L136-137
  and in the #1005 changelog, and it is idempotent.
* **A `CR` at the start of a line under `resolve_cr` is dropped.** `\n\rX` gives `\nX`,
  and `\r\r\n` gives `\r\n`. Nothing visible changes, and the detector does not report it
  either.
* **`\u200b\ba` gives `a` under `cr = False`.** This is intended and asserted. It is only
  inconsistent with the column-0 rule in combination with `CR`, which is Finding 1. The
  visible output is unaffected.
* **"Blank, not remove"**: `set` keeps the line length. With `resolve_false_eq_simple` and
  the `Vectors.lean` shift cases (`aa\ra\ba` gives `aa`), the claimed semantics hold.

An aside outside this component, not investigated: `disarm.search_key("pay\u2028pal")`
returns `'paypal'`, while `canonicalize` gives `'pay pal'` and `search_key("pay\npal")`
gives `'pay pal'`.

## Re-running

```bash
export PATH=/path/to/lean-4.34.0/bin:$PATH
cd formal/lean/Deletions
lake build                                   # every proof; Bounded.lean takes ~4 min
lake env lean Deletions/Axioms.lean          # the axiom audit
python3 scripts/difftest.py                  # needs an importable `disarm`
```
