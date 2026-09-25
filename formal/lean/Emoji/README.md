# Formal model of the emoji scanners (Lean 4)

A Lean 4 model of `src/emoji.rs` and `src/py/emoji.rs` at `bec93cf`, validated
against the real library by differential testing, and a set of theorems about it.
Some are proved in general and some are checked exhaustively up to a length bound.
Every failed property was minimised and reproduced on the real library.

> **Status.** F1, F2, F3 and F5 are fixed in #1011, with regression tests in
> `tests/test_emoji_formal_findings.py`. Still open: F4, a design question (a combining
> mark on a removed emoji lands on the preceding letter), and F6 (standalone `demojize` is
> not idempotent on the 38 CLDR names that contain curly quotes). This README describes
> the code as it was at `bec93cf`; `Fixes.lean` is the fixes as proposed (F1-F3; F5 was
> fixed in the code only). Run in `--fixed` mode against the library after #1011, the
> differential test found one more defect, fixed in #1015: the F5 fix let a U+FE0F
> continue a sequence anywhere, so `demojize` named a regional indicator, U+FE0F and a
> second regional indicator as a flag. After #1015, `replace_emoji` agrees with the fixed
> model on all 219,724 inputs, and every `demojize` difference falls in one of four
> deliberate classes, listed in #1015. #1015 also asserts `MAX_WINDOW >= 4` (the latent
> item below) and corrects the `src/pipeline.rs` comment (the doc drift below).

The three entry points modelled:

| Python surface | Rust | Lean |
|---|---|---|
| `replace_emoji(text, replacement)` | `demojize_rust_replace_into` + `CharWindow` | `replaceEmoji` (= `replaceW 9`) and the unbounded `replaceU` |
| `TextPipeline(demojize=True)` | `demojize_rust_into`, `NamePolicy::PIPELINE_BASELINE` | `pipelineDemojize` |
| `demojize(text, errors=, replace_with=, provider=)` | `demojize_impl` | `demojizePy` |

`strip_modifiers` is not modelled, because it only trims the text of a name.
`NamePolicy::skip_tr39_claimed` is also left out: no pipeline sets it, only the
comparison presets do.

## Layout

| File | Contents |
|---|---|
| `scripts/gen_tables.py` | Generates `Emoji/Tables.lean` from `src/tables/data/*.tsv` |
| `Emoji/Tables.lean` | Generated: the alphabet and the real tables projected onto it |
| `Emoji/Model.lean` | The model. Each definition names its Rust function and line numbers |
| `Emoji/Props.lean` | The properties, as `Bool` predicates on one input, plus the enumerators |
| `Emoji/Fixes.lean` | The proposed fixes, applied to a copy of the model |
| `Emoji/Suite.lean` | The property list over the shipped model and over the fixed one |
| `Emoji/General.lean` | Theorems proved by induction over all inputs and all of `Char` |
| `Emoji/Checks.lean` | Bounded-exhaustive theorems and counterexample theorems (`native_decide`) |
| `Main.lean` | Differential-test driver (`lake exe emojimodel`) |
| `Cex.lean` | Counterexample search (`lake exe cex N [shipped\|fixed\|extra] [filter]`) |
| `scripts/difftest.py` | Runs the model against the real `disarm` |

## Abstraction

The characters are real `Char`s. The alphabet has one code point per class that the
Rust code branches on:

| Class | Code point | Why it is its own class |
|---|---|---|
| EP, named single, not a multi starter | U+1F600 😀 | `lookup_emoji_single` |
| EP, named, multi starter | U+1F468 👨 | skin-tone and ZWJ entries in the trie |
| EP, named, inside a named ZWJ sequence | U+1F525 🔥 | `❤‍🔥` |
| `Emoji=Yes`, text default, named, starter | U+2764 ❤ | named + opens with U+FE0F only |
| `Emoji=Yes`, text default, named single | U+2122 ™ | |
| `Emoji=Yes`, text default, **no** CLDR name | U+00A9 © | #1003's class (★ U+2605 behaves identically) |
| keycap base, alphanumeric | `1` | `needs_separator_after_a_name` differs from `*` |
| keycap base, not alphanumeric | `*` | |
| KEYCAP | U+20E3 | |
| VS15 / VS16 / ZWJ | U+FE0E / U+FE0F / U+200D | |
| skin tone | U+1F3FB | EP, named alone, a head modifier |
| TAG | U+E0041 | a lone tag is dropped by demojize (#914) |
| regional indicators | U+1F1E6, U+1F1E7 | BA and BB are named flags; AA and AB are not |
| combining mark | U+0301 | |
| letter | `x` | alphanumeric, and in no name, so it can be counted |
| space | ` ` | the only whitespace (`pad_emoji_replacement`) |
| euro | U+20AC | CLDR-named, no emoji property: the #757 row, folds to `e` |
| other | `.` | |

**Tables.** `gen_tables.py` evaluates every table predicate on the alphabet and on
all of ASCII, which is the character set of the names. It reads `Emoji_Presentation`,
`Emoji` alone (the VS16 arm, #992), `Emoji`/`Extended_Pictographic` (the #757 row set),
`emoji_single`, `emoji_starters`, `confusables_to_latin` and `General_Category=M`. On
this alphabet `isEmojiYes` and `isEmojiProperty` agree: every member with either
property is `Emoji=Yes`, so #992 moved the model's citation and not its behaviour. Outside that domain every predicate
is `false`/`none`, and no model input or output leaves the domain. The CLDR sequence
table is exact for this alphabet: `multiKeys` holds every `emoji_multi.tsv` key made
only of alphabet code points (8 keys: two keycaps, ❤‍🔥, two flags, 👨🏻, and 👨‍❤‍👨 with
and without skin tones). A trie walk over alphabet-only input can reach no other key.
The one abstraction is the choice of representatives. The model claims nothing
about code points outside the alphabet beyond what their class shares.

**Structural predicates**: regional indicator, tag, skin tone, keycap base, and the
four special code points. These are copied from Rust over all of `Char`.

**Loops.** Each `while` over a `CharWindow` becomes a recursion on a fuel argument of
at least the number of characters left. Every iteration consumes a character, so the
fuel never runs out. `CharWindow` is modelled literally with `buf`, `pushback` and
`rest`, and its size `W` is a parameter. `replaceEmoji` fixes `W = 9` (`MAX_WINDOW`).

## Validation (differential testing)

```bash
cd formal/lean/Emoji
lake build emojimodel
PATH=/path/to/venv-with-disarm/bin:$PATH python3 scripts/difftest.py 300000 7 40
```

Each run covers every string of length 3 or less over the 21-letter alphabet (9,724
strings). It then adds `N` weighted random strings and `N/20` long ZWJ chains built
to exercise the window's growth path. Ten outputs are compared per input: `replace_emoji`
with `""`, `" "` and `"#"`; the **unbounded** model against the real windowed
`replace_emoji`; `demojize` with `errors` set to `replace`, `ignore` and `preserve`;
`replace_with=""`; a registered provider; and `TextPipeline(demojize=True)`.

Results against `bec93cf`:

| Seed | Inputs | Max length | Disagreements, all 10 modes |
|---|---|---|---|
| 1 | 30,724 | 24 | 0 |
| 7 | 324,724 | 40 | 0 |
| 42 | 324,724 | 16 | 0 |

The harness can disagree. `--fixed` makes the executable run the fixed model instead,
and one run of 30,724 inputs then produces 37 to 2,724 disagreements per mode. All of
them fall in the finding classes below.

## Theorems

### Proved in general (`Emoji/General.lean`: induction, all inputs, all of `Char`)

None of these proofs unfolds a table predicate, so they hold for the full tables too.

* `headLen_none_stable`: `HEAD_LOOKAHEAD = 3` is enough. A `None` from `head_len_at`
  on at least three characters stays `None` whatever follows. This generalises the
  Rust test `head_lookahead_is_enough`, which covers 11 characters and 2 appended.
* `headLen_some_stable`, `headLen_pos`, `chainLoop_ge`, `chainLoop_stable`: lemmas.
* `presLen_prefix_stable`: **the window's fast path is sound** (emoji.rs:335). If
  `presentation_len_at` on a prefix returns `len` short of the prefix's end, and the
  character at `len` is not a joiner or is a joiner with at least 3 characters after
  it, then every extension of the prefix gives the same answer.
* `window_fastPath_sound`: the same statement about `Win.buf ++ pushback ++ rest`.
* `grow_stop_sound`: the growth loop's stop rule (emoji.rs:357-360) is sound whenever
  the scan it doubled held at least 4 characters. `CharWindow` always starts from 9.

### Bounded-exhaustive (`Emoji/Checks.lean`, `native_decide`)

`full` means all 4,288,306 strings of length ≤ 5 over the 21 classes. `grammar` means
all 21,435,888 strings of length ≤ 7 over the 11 classes the grammar branches on.

| Theorem | Statement | Bound |
|---|---|---|
| `replace_space_clean`, `replace_hash_clean` | `replace_emoji(s, " "/"#")` contains no presentation sequence | full ≤ 5 |
| `replace_space_idem`, `replace_hash_idem` | idempotent | full ≤ 5 |
| `replace_keeps_text` | `x . space U+0301 €` are never removed | full ≤ 5 |
| `replace_keeps_stray_keycap` | a keycap with nothing to bind to survives (`""`, `" "`) | full ≤ 5 |
| `replace_space_mark_stays_put` | with `" "`, a mark never moves onto an alphanumeric | full ≤ 5 |
| `window9_eq_unbounded` | shipped window = unbounded scanner | full ≤ 5 |
| `window4_eq_unbounded` (`_space`) | window 4 = unbounded, growth path exercised | grammar ≤ 7 (≤ 6) |
| `window3_is_not_enough` | window 3 ≠ unbounded on a 7-character input, so the `before ≥ 4` bound is tight | witness |
| `demojize_keeps_text` | `x . space © U+0301 1 *` survive `errors="ignore"` and the pipeline (plus `€` there) | full ≤ 5 |
| `demojize_keeps_stray_keycap` | ignore / replace / pipeline | full ≤ 5 |
| `demojize_replace_separates`, `demojize_preserve_separates` | #200 and #996 hold when a visible token is written | full ≤ 5 |
| `pipeline_eq_demojize_ignore` | pipeline = `demojize(errors="ignore")`, `€` excluded | 20 classes ≤ 5 |
| `provider_keycap_whole` | #1006: a provider claiming `1` still takes the keycap | full ≤ 5 |
| `fixed_model_holds` | the fixed model satisfies every property except F4's strong form and the `€` agreement | full ≤ 5 |

### Failed: findings

Each failure has a witness theorem (`F*_…`) and a minimality theorem (`F*_minimal`:
no shorter string fails).

* **F1** (`F1_replace_manufactures_keycap`): `replace_emoji("1️😀⃣", "")`
  is `"1️⃣"`, a keycap. The seam rule looks back one output character, and
  a keycap head is three characters long.
* **F2** (`F2_demojize_manufactures_keycap`): `demojize("1︎⃣")` is
  `"1⃣"`, a keycap, and a second pass names it `keycap: 1`. The loop-top skip of
  VS15/VS16/ZWJ is a removal that does not close its seam. This confirms the open
  item. `"1\u200d\u20e3"` behaves the same way.
* **F3** (`F3_name_glued`): `😀🇦x` gives `grinning facex` under `errors="ignore"`,
  `replace_with=""` and the pipeline, and `😀🇦́` gives `grinning facé`. A drop
  that writes nothing resets `last_was_emoji`.
* **F4** (`F4_mark_moves`), a design question: a combining mark on a removed emoji
  lands on the preceding letter. `replace_emoji("x😀́", "")` is `"x́"`.
* `euro_documented`: pipeline ≠ `demojize` on `€`. This is #757, intended.

### Found while building the table abstraction (outside the property suite)

* **F5.** Fully qualified ZWJ sequences with an interior U+FE0F are named piecewise.
  CLDR keys the multi table without selectors (`2764_200D_1F525`), and the #972 retry
  covers keycaps only. So `demojize("❤️‍🔥")` is `red heart fire` and
  `demojize("🏳️‍🌈")` is `white flag rainbow`. 306 of the 1,021 ZWJ keys whose
  fully qualified form carries a U+FE0F are affected. The model reproduces this with
  the real table: the key `2764_200D_1F525` does not match `❤ FE0F ZWJ 🔥`.
* **F6.** Standalone `demojize` is not idempotent on 38 names that contain `’ “ ”`.
  Those characters are CLDR-named rows (`woman’s hat` then becomes
  `woman right apostrophe s hat`). The pipeline skips them (#757) and is unaffected.
* **Latent.** `CharWindow` needs `MAX_WINDOW ≥ 4` (`grow_stop_sound`,
  `window3_is_not_enough`), and nothing asserts it. `MAX_WINDOW = 9` today.
* **Doc drift.** The comment at `src/pipeline.rs:520-525` says a hand-composed
  `TextPipeline` "names every row". Since #918 it uses `PIPELINE_BASELINE`, as the
  field doc at `pipeline.rs:209-232` says, and as the model and the library agree.

## The fixes (`Emoji/Fixes.lean`)

1. `drop_marks_the_seam_would_bind` also asks `head_len_at` of the last **two** output
   characters plus the mark. It drops the mark when that head reaches past the two
   characters (closes F1).
2. After the loop-top skip of VS15/VS16/ZWJ in both demojize scanners, run the same
   seam rule (closes F2). This drops the orphan keycap. The other option is to accept
   U+FE0E in the #972 keycap retry and name `1︎⃣` as `keycap: 1`, but that alone
   leaves `1 FE0E FE0F 20E3` and `1 ZWJ 20E3` open.
3. When the unnamed branch writes nothing (the pure scanner, `errors="ignore"`, or
   `replace_with=""`), leave `last_was_emoji` and `last_was_raw` as they were instead
   of resetting them (closes F3). This changes `ml_normalize` keys
   (`"I 😀🇦x ok"` → `i grinning facex ok` today), so `KEY_SCHEMA_VERSION` would move.

## Re-running

```bash
cd formal/lean/Emoji
lake build                 # builds everything, including Checks (a few minutes: native_decide)
lake exe cex 4 shipped     # shortest counterexample per property, shipped model
lake exe cex 5 fixed       # the same for the fixed model
lake exe cex 7 extra "window 4"
```

Trusted base: the Lean kernel for `General.lean`. For `Checks.lean` it also includes
the Lean compiler and runtime, because `native_decide` trusts compiled evaluation.
