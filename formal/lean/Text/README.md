# Formal model of the text primitives (Lean 4)

A Lean 4 model of disarm's text primitives: `fold_case` and `is_case_fold_stable`
(`src/case_fold.rs`), `collapse_whitespace`, `strip_control_chars` and
`strip_zero_width_chars` (`src/whitespace.rs`), `is_zalgo` and `strip_zalgo`
(`src/zalgo.rs`), `grapheme_width` and `terminal_width` (`src/width.rs`), the invisible
strips under both policies (`src/invisibles.rs`) with `strip_bidi` and the `strip_format`
composition, `fold_punctuation` (`src/punctuation.rs`), `contract` (`src/contraction.rs`)
and `edit_distance` (`src/utils.rs`). The grapheme functions (`src/grapheme.rs`) and
`strip_accents` are checked by exhaustive sweeps against independent oracles rather than
modelled: they delegate to `unicode-segmentation` and `unicode-normalization`.

The model was validated against the built library by differential testing before any proof
or counterexample counted. Every failed property was cut down to a minimal input and
reproduced on the library (`scripts/repro.py`).

Written against `main` at `595fbda`. Line numbers (`L75`) refer to the file named in each
section at that commit. The toolchain is core Lean 4.34.0 only, with no Mathlib. All test
data in this directory is written as escapes; no file here contains a literal invisible
character.

## Findings at a glance

| # | Class | Severity | One line |
|---|---|---|---|
| Z1 | (a) code bug | **medium** | Almost any class-0 mark (1,493 of 1,496, including the invisible `U+034F`, `U+180B`-`U+180F`, `U+17B4`/`U+17B5`) between two runs of one mark resets the count in `is_zalgo`, `strip_zalgo`, the key builders' repeat-dropper and the `duplicate_mark` detector, so a base can carry any number of stacked marks. `canonicalize` keeps 20 acutes on one letter. |
| Z2 | (c) inconsistency | low | `strip_zalgo` exempts one negation overlay from the cap and `is_zalgo` counts it, so `strip_zalgo`'s output is still zalgo at the same threshold. |
| Z3 | (b) doc overclaim | low | The docstrings cap marks "per base character"; the code caps marks per combining class (by design since #842), so `a` + 9 marks is ordinary. |
| W1 | (a) code bug | medium-low | A grapheme cluster that opens with a zero-width `Prepend` (`U+0600`-`U+0605`, `U+06DD`, `U+070F`, `U+0890`, `U+0891`, `U+08E2`, `U+110BD`, `U+110CD`) measures 0 whatever follows: `terminal_width(("\u0600" + "A") * 100) == 0`. `docs/limitations.md` also claims the separator always starts a fresh cluster, which a `Prepend` refutes. |
| W2 | (c) inconsistency | low | A stray `U+FE0F` after a non-emoji base makes it 2 columns; a stray `U+FE0E` is ignored. |
| C1 | (b) doc overclaim | low | Python docs say `is_case_fold_stable(t)` answers `fold_case(t) == t.lower()`, and that `fold_case` is `str.casefold()`; the lowercase compared is the Rust toolchain's, so the first fails for 28 scalars on every current Python and 55 on Python 3.13 and older. |
| C2 | (b) doc overclaim | low | `docs/provenance.md` and the `is_case_fold_stable` rustdoc call the toolchain dependence (#718) "latent rather than live". It is live: this build's `to_lowercase` is Unicode 17, so 28 Unicode 17 letters read unstable here and stable on a rustc 1.88 build. |
| D1 | (b) doc overclaim | low | `strip_zero_width_chars`' docstring gives "exactly" 10 code points; it removes 22. |
| D2 | (b) doc overclaim | low | `docs/limitations.md` says `canonicalize` keeps 18 Default_Ignorable code points, listing ones #813 removes; it keeps 6. |
| D3 | (b) doc overclaim | low | `fold_punctuation` says it folds "the non-standard spaces", "the curly quotes" and "the primes"; it leaves `U+1680`, `U+201B`, `U+201F` and `U+2034`-`U+2037`. |

None of the proofs needed the findings to be absent: everything else claimed about these
functions holds, generally or up to the stated bound (see *What is proved*).

## Layout

| File | Contents |
|---|---|
| `Text/Enum.lean` | The bounded enumerator `allUpTo`, and its soundness theorem. |
| `Text/Hom.lean` | Per-scalar maps: homomorphism, idempotence, length, filter lemmas; the chunk lemma behind `stable_correct`. |
| `Text/CaseFold.lean` | `is_case_fold_stable` as an algorithm over abstract data, and `stable_correct`. |
| `Text/Whitespace.lean` | `collapse_whitespace` exactly as written, a second formulation, their equality, and the proofs. |
| `Text/Zalgo.lean` | NFD as canonical reordering, `is_zalgo`, `strip_zalgo`, the position count `worstPosition`, and the fixed model. |
| `Text/ZalgoProofs.lean` | General theorems about `strip_zalgo`. |
| `Text/Width.lean`, `Text/WidthProofs.lean` | `grapheme_width`, `terminal_width` over given clusters, the fixed model, general theorems. |
| `Text/Invisibles.lean` | `strip_tags`, `strip_invisible_classes` (both policies), the filters, `strip_format`. |
| `Text/Punct.lean` | `fold_punctuation` and its theorems. |
| `Text/Utils.lean` | `edit_distance` (the two-row programme as written, and the textbook recursion) and leftmost-longest `contract`. |
| `Text/Findings.lean` | The failed properties as minimal counterexamples, checked by the kernel (`decide`). |
| `Text/Bounded*.lean` | Bounded exhaustive checks (`native_decide`). |
| `Text/Axioms.lean` | `#print axioms` for the headline theorems (not in the default build). |
| `Main.lean`, `scripts/difftest.py` | The differential test. |
| `scripts/premises/` | A Rust program that checks the case-folding premises on every scalar, against the library's own table and the `to_lowercase` compiled into the same build. |
| `scripts/sweep.py` | Every Unicode scalar, and targeted pairs, against each claimed property. |
| `scripts/repro.py` | The findings, reproduced on the installed library. |

## Step 1: what is claimed

The properties the code, its docstrings, `docs/` and the tests claim or imply, and the
verdict. "Proved" means for every input; "bounded" means exhaustively up to the stated size;
"swept" means over every Unicode scalar (and the stated pairs) on the real library.

| Function | Property (source) | Verdict |
|---|---|---|
| `fold_case` | per-scalar; idempotent; never drops a scalar; no ASCII uppercase left; ASCII in, ASCII out (`case_fold.rs` L446-485, proptests) | proved from per-scalar premises (`Hom.lean`), premises checked on all 1,112,064 scalars |
| `fold_case` | CaseFolding.txt status C+F, Unicode 16.0 (`_api.py` L1074) | swept: equals Python 3.14's `str.casefold` (UCD 16.0) on every assigned scalar |
| `fold_case` | "Equivalent to `str.casefold()`" (`_api.py` L1084, `_text.py` L176) | **C1**: only when the host Python is on UCD 16 |
| `is_case_fold_stable` | computes `fold_case(t) == t.to_lowercase()` with a per-scalar scan (L102-157) | **proved** (`stable_correct`) under premises checked on every scalar; 2,000,000 random strings agree |
| `is_case_fold_stable` | Python: "Answers `fold_case(text) == text.lower()`" (L1125) | **C1** |
| `collapse_whitespace` | folds exactly White_Space + `U+001C`-`U+001F` + blank-render (L60-101) | swept |
| `collapse_whitespace` | idempotent; no leading, trailing or double space; only ASCII space left; deletes nothing else (L6-24, proptests, tier-3 test) | **proved** (`collapse_idem`, `collapse_nf`, `collapse_keeps_non_ws`) |
| `strip_control_chars` | removes Cc minus the fold set (L103-126) | proved (a filter) + swept |
| `strip_zero_width_chars` | "The set is exactly" 10 code points (`_api.py` L1233-1248) | **D1** (22) |
| `strip_bidi` | removes UAX #9 controls + soft hyphen + `U+206A`-`U+206F` + `U+FFF9`-`U+FFFB` (`presets.rs` L1006-1059) | swept; `Bidi_Control` is a subset |
| `strip_tags` etc. | exact ranges; keep exactly the three RGI subdivision flags (`invisibles.rs`) | swept + bounded (no stray tag, idempotent) |
| `strip_format` / comparison policy | idempotent; leaves no control, zero-width, bidi, stray tag, orphaned selector; collapses (`presets.rs` L1739-1766, `invisibles.rs` L205-217) | bounded |
| `is_zalgo` / `strip_zalgo` | "True if any base character has more than threshold consecutive combining marks in NFD" / "caps ... per base character" (`_presets.py` L1001-1052, `api/text.rs` L129-142) | **Z3** |
| `is_zalgo` / `strip_zalgo` | per class at one position, "an attacker cannot break up a run by interleaving classes" (`tests/test_zalgo_combining_class.py` L17-21, `zalgo.rs` L66-68, `anomalies.rs` L841-843) | **Z1** |
| `strip_zalgo` | never removes a mark from text `is_zalgo` calls ordinary (#788, `test_zalgo_cap.py`) | proved |
| `strip_zalgo` | its output is not zalgo at the same threshold (implied by the #788 pairing) | **Z2** |
| `strip_zalgo` | NFC output; idempotent; subsequence of NFD(input); keeps every base and (cap > 0) every class-0 mark (L178-279, #842) | proved / bounded / swept |
| `strip_zalgo(max_marks=0)` | "strips all combining marks (equivalent to `strip_accents`)" | proved up to the #749 negation overlay; the equivalence swept |
| `strip_accents` | removes every mark except a negation overlay on a symbol; idempotent (`transliterate.rs` L1578-1629) | swept |
| `terminal_width` | sum over UAX #29 clusters of `grapheme_width`; at most `2 * grapheme_len` (I_w2); ASCII printable = 1 (I_w1) | proved / differential |
| `terminal_width` | "combining marks, controls, and zero-width characters are 0" and other characters are not (`_api.py` L1533-1545) | **W1** |
| `grapheme_width` | "VS15 forces text presentation; a stray VS15 on a non-emoji base is ignored" (`width.rs` L104-106) | **W2** (VS16 is not ignored) |
| `grapheme_split` / `grapheme_len` / `grapheme_truncate` | UAX #29; lossless; truncation is the first `n` clusters and never splits one | swept against `regex`'s `\X` |
| `terminal_width` additivity | "the separator always starts a fresh cluster regardless of what `a` ends with" (`limitations.md` L879) | **W1** |
| `fold_punctuation` | per-scalar; idempotent; identity on ASCII (`punctuation.rs`, `_presets.py` L748-772) | **proved** |
| `fold_punctuation` | folds "the non-standard spaces", "the curly and low-9 quotes and the primes" | **D3** |
| `contract` | idempotent; leftmost-longest (`contraction.rs` L19-29) | bounded; the build-time precondition is sufficient because targets are single characters |
| `edit_distance` | Levenshtein in scalars (`utils.rs` L18-34, `_api.py` L3756) | bounded (equals the recursive definition; metric) |
| `canonicalize` (composition) | keeps 18 of 405 Default_Ignorable code points (`limitations.md` L317-330) | **D2** (keeps 6) |

## The model

### Zalgo (`Zalgo.lean`)

| Token | `Ch` | Class | Character |
|---|---|---|---|
| `a`, `b` | `base false i` | letter | `a`, `b` |
| `e` | `base true 0` | a base `is_negation_of` accepts | `=` |
| `A`, `G` | `mark 230 false i` | above | `U+0301`, `U+0300` |
| `U` | `mark 220 false 0` | below | `U+0316` |
| `O` | `mark 1 false 0` | overlay | `U+0334` |
| `N`, `R` | `mark 1 true i` | negation overlay | `U+0338`, `U+20D2` |
| `T`, `C` | `mark 0 false i` | class-0 mark | `U+0E31`, `U+034F` |

| Rust (`src/zalgo.rs`) | Lean |
|---|---|
| `text.nfd()` | `canon`: stable sort of each run of non-zero-class marks (these characters do not decompose) |
| L53-91 `exceeds_combining_run`, L102-108 `is_zalgo` | `exceedsGo`, `isZalgo` |
| L227-241 negation branch | first branch of `stripStep` |
| L252-255 class-0 branch | second branch |
| L257-266 per-class count | third branch |
| L268-273 base | last branch |
| L208-211 fast path | `strip` |

The library returns NFC. The differential test maps it back through NFD (the host's
`unicodedata`; these characters are old enough for any version) and compares with the
model, whose outputs are canonically ordered and decomposed.

`worstPosition k s` is the specification of the documented cap: for each base, the number
of marks of each non-zero class (every class when `k = 0`), exempting the first negation
overlay on a `sym` base. `isZalgoFixed`/`stripFixed` are the proposed fix: they count with
that table and do not reset at a class-0 mark.

### Width (`Width.lean`)

`grapheme_width_opts` (L64-121) reads six attributes of a scalar, and the model's `Sc` is
exactly those: `ascii`, the `width_class` (0/1/2/3), `emo` (Emoji_Presentation or a regional
indicator), `sel` (VS15, VS16, the keycap), `kb` (a keycap base) and `prep` (GCB=Prepend,
which only the fix reads). The model does not re-implement UAX #29: the differential test
feeds it the clusters the library's own `grapheme_split` returns, and the segmentation facts
the findings rely on are checked against the `regex` module's `\X` separately.

| Token | Character | `cls` | other |
|---|---|---|---|
| `a`, `1`, `x` | `a`, `1`, `U+0001` | 1, 1, 0 | ASCII; `1` is a keycap base |
| `m`, `j` | `U+0301`, `U+200D` | 0 | |
| `p` | `U+0600` | 0 | Prepend |
| `r` | `U+0D4E` | 1 | Prepend |
| `c`, `q` | `U+4E00`, `U+00A1` | 2, 3 | |
| `E`, `F`, `I` | `U+1F600`, `U+1F3FB`, `U+1F1E6` | 2, 0, 1 | emoji |
| `h` | `U+263A` | 1 | emoji, text default |
| `s`, `S`, `k` | `U+FE0E`, `U+FE0F`, `U+20E3` | 0 | selectors |

### Whitespace (`Whitespace.lean`)

`ws i` (a fold-whitespace or blank-render character; `ws 0` is the ASCII space `collapse`
writes), `ctl i` (a control that is not fold whitespace), `zw i` (`is_zero_width`), `ch i`
(anything else). Concrete: space, TAB, NBSP, `U+001C`, `U+2800`, `U+3164`, `U+2028`, NEL;
NUL, DEL, `U+009B`; `U+200B`, `U+FEFF`, `U+1D173`; `a`, `b`, `U+00E9`. `loop` is the loop of
`collapse_whitespace_into` (L40-51) and `collapse` adds the truncate (L55-57).

### Invisibles and `strip_format` (`Invisibles.lean`)

One token per predicate the scanners branch on: the flag base, tag letters (carrying the
letter), the cancel tag, other tags, CGJ, a noncharacter, a PUA code point, a variation
selector, VS15, VS16, a #813 format character, a zero-width character, whitespace, the
Braille blank, a control, and a bidi control. The table is in the module header. The
functions take the subdivision-flag allowlist as a parameter; the differential test uses
the real one (`gbeng`, `gbsct`, `gbwls`), and the bounded checks use `gb` so that a valid
flag fits in four scalars. `stripCompare` is `strip_format` with the comparison policy: the
part of `canonicalize` this alphabet reaches, which the differential test compares with
`canonicalize` itself.

### Case folding (`CaseFold.lean`)

Abstract: any alphabet, with `fold`, `low`, an ASCII test, a distinguished `sigma`, and
`lowerCtx`, the per-position chunks of `str::to_lowercase`. The theorem is proved for all of
them; `scripts/premises` checks that disarm's table and Rust's `to_lowercase` satisfy the
premises.

## Validation: differential testing

```bash
lake build textmodel                              # this directory
python3 scripts/difftest.py                       # needs an importable `disarm`
```

| Model | Library surface | Inputs | Agree |
|---|---|---|---|
| zalgo | `is_zalgo`, `strip_zalgo` (NFD of the output), `max_marks` 0-3 | every word of length <= 7 over `a e A U O N T` (960,800) + 300,000 random words of length <= 16 over all 11 tokens, x 4 thresholds | **5,043,200 / 5,043,200** for each of the two functions |
| width | `grapheme_width` on any argument, both policies | every word of length <= 3 over the 16 tokens (4,369), x 2 | **8,738 / 8,738** |
| width | `terminal_width`, the model summed over `grapheme_split` | 200,000 random words of length <= 10, x 2 | **400,000 / 400,000** |
| whitespace | `collapse_whitespace`, `strip_control_chars`, `strip_zero_width_chars` | every word of length <= 7 over `_ t B 0 z a b` (960,800) + 300,000 random over all 17 tokens | **1,260,800 / 1,260,800** each |
| invisibles | `strip_tags`, `strip_format`, `canonicalize` | every word of length <= 6 over 8 tokens (299,593) + 300,000 random words mixing valid, broken and smuggling flag sequences | **599,593 / 599,593** each |
| punctuation | `fold_punctuation` | every token alone (138) + 100,000 random words | **100,138 / 100,138** |
| utils | `edit_distance` | every pair of words of length <= 5 over `a b` (3,969) + 100,000 random pairs including non-ASCII | **103,969 / 103,969** |
| utils | `is_suspicious_hostname(w + ".com", contractions=True).canonical` | every non-empty word of length <= 6 over `r n v c l m x` (137,256) | **137,256 / 137,256** |

**Result: 16,417,680 of 16,417,680 comparisons agree.** The fixed zalgo model agrees with
the library on every input that has neither a class-0 mark nor a negation overlay
(584,808 of 584,808), and differs only on the shapes of Z1 and Z2.

The zalgo exhaustive part runs over exactly the words `BoundedZalgo.lean` quantifies over,
so each bounded result about the *current* zalgo model is also a result about the built
library up to that bound. `canonicalize`'s steps other than the five `stripCompare` models
are the identity on the invisibles alphabet; the agreement with `canonicalize` confirms that
rather than assuming it.

### The Rust suite

`cargo test --release --no-default-features --lib -- --include-ignored` filtered to the nine
modules: 138 tests pass, including the tier-3 `exhaustive_fold_case_invariants`,
`exhaustive_agrees_with_the_definition`, `only_sigma_has_a_context_sensitive_lowercase` and
`exhaustive_collapse_whitespace`. The last two are premises of `stable_correct` and a
bounded check of what `collapse_idem` proves in general.

### Premises: `scripts/premises` (Rust)

```bash
cd scripts/premises && CARGO_TARGET_DIR=../../.lake/cargo cargo run --release
```

On all 1,112,064 scalars, against the library's table and the `to_lowercase` compiled into
the same build: the fold is never empty, is idempotent, leaves no ASCII uppercase, keeps
ASCII ASCII; only `U+03A3` lowercases differently in context (alone, medial, final, initial,
after a sigma); the lowercase is never longer than the fold; ASCII folds as it lowercases;
`U+03A3` folds to `U+03C3`. Then 2,000,000 random strings drawn from the 1,671 scalars
whose fold or lowercase moves, plus sigma and ASCII: `is_case_fold_stable(s) ==
(fold_case(s) == s.to_lowercase())` and `fold_case` is per-scalar on every one. **0
failures.**

### Sweeps: `scripts/sweep.py`

Every scalar, on the library (host UCD 14.0.0; the `regex` module and `unicodedata2==15.1.0`
as oracles):

* `fold_case`: per-scalar premises hold everywhere; equal to `str.casefold()` on every
  scalar the host knows. Run separately under Python 3.14 (UCD 16.0, the table's version):
  equal on every assigned scalar, and `is_case_fold_stable(c) == (fold_case(c) == c.lower())`
  on every assigned scalar.
* `collapse_whitespace` folds exactly White_Space + `U+001C`-`U+001F` + the five
  blank-render code points; the run-context invariants hold for every scalar.
  `strip_control_chars` removes exactly Cc minus that set.
* `strip_bidi`, `strip_tags`, `strip_variation_selectors`, `strip_noncharacters`,
  `strip_pua` remove exactly their documented sets; `Bidi_Control` is contained in
  `strip_bidi`'s.
* `strip_accents` equals `strip_zalgo(max_marks=0)`, is idempotent and leaves no mark but a
  negation overlay; `strip_zalgo` is idempotent with NFC output (each scalar alone, after
  `=`, before `U+0338`, before one and five `U+0301`).
* `grapheme_split` equals `regex`'s `\X` on `a+c+b`, `c+c`, `U+0600+c` and `c+ZWJ+emoji` for
  every scalar (4,448,256 strings), concatenates back, and agrees with `grapheme_len`;
  `grapheme_truncate` is the first `n` clusters on 200,000 random strings.
* `grapheme_width` of every scalar the UCD 15.1 oracle knows equals UAX #11 plus the
  documented zero-width rule, except 26 spacing marks (`U+0CC0`, `U+1715`, `U+1B44`, ...)
  that Unicode 16 made `Grapheme_Extend`: the oracle's property data is newer than the
  table. Not a finding (see *Not confirmed*).
* Z1: 1,493 of the 1,496 class-0 marks hide six `U+0301` on one base from `is_zalgo`, and
  `U+034F` hides a six-stack of 911 of the 912 non-zero-class marks. W1: 13 of the 27
  `Prepend` scalars make `Prepend + '7'` measure 0.

## What is proved

### In general, by induction (no `native_decide`)

`Axioms.lean` shows only `propext`, `Quot.sound` and `Classical.choice`.

| Theorem | Statement |
|---|---|
| `allUpTo_sound` | The bounded enumerator covers every word up to its bound. |
| `pmap_append`, `pmap_idem`, `pmap_length_ge`, `pmap_all`, `pmap_id_on` | A per-scalar map commutes with concatenation; idempotence, "never drops a scalar", "no ASCII uppercase left" and "identity on a class" lift from scalars to all strings. This is the argument the Rust comment on `exhaustive_fold_case_invariants` makes, made explicit; `scripts/premises` discharges the per-scalar side. |
| `chunks_eq_of_flatten_eq` | Equal concatenations of equally many chunks, each right chunk no longer than its partner, are equal chunk by chunk. |
| `stable_correct` | **`is_case_fold_stable`'s per-scalar scan decides `fold_case(s) == s.to_lowercase()` for every string**, given the premises. Without `dom` it would not: two scalars that each disagree can agree once concatenated. |
| `collapse_eq_cs` | The loop as written, with its trailing truncate, equals a lazy formulation (a space is owed and paid only before a non-space). |
| `collapse_nf` | The output is in normal form: no leading, trailing or doubled space, and ASCII space is the only whitespace left. |
| `collapse_idem` | **Idempotence**, the #433 acceptance criterion. |
| `collapse_keeps_non_ws`, `collapse_id_of_no_ws` | Folds whitespace only: every other character survives, in order; whitespace-free input is returned unchanged. |
| `stripControl_idem`, `stripZeroWidth_idem`, `strips_commute` | The two strips are idempotent and commute. |
| `strip_sublist` | `strip_zalgo`'s output is a subsequence of NFD(input). |
| `strip_keeps_protected`, `strip_keeps_bases` | Every non-mark survives in order, and for `max_marks > 0` every class-0 mark too (#842). |
| `strip_id_of_not_zalgo` | When `is_zalgo` is false the result is NFD(input): the #788 invariant. |
| `strip_zero_only_negation` | With `max_marks = 0`, every mark left is a negation overlay. |
| `gw_le_two`, `tw_le` | Every argument measures at most 2, so `terminal_width <= 2 * grapheme_len` (I_w2). |
| `gw_ascii_single`, `gw_amb_mono` | I_w1 for a lone ASCII scalar; the ambiguous-wide policy never narrows anything. |
| `gwFixed_spacing`, `gwFixed_eq` | Under the W1 fix, a zero-width `Prepend` prefix never hides the scalar it attaches to, and nothing else changes. |
| `foldPunct_idem`, `foldPunct_ascii`, `fold_image_ascii` | `fold_punctuation` is idempotent, the identity on ASCII, and writes only ASCII for what it folds. |

### Bounded exhaustively (`native_decide`)

| Theorem | Domain | Result |
|---|---|---|
| `slow_eq_fast` | zalgo, 960,800 words x `k` in 0..3 | the fast path is only an optimization |
| `strip_idem` | same | `strip_zalgo` is idempotent |
| `cap_holds_elsewhere`, `pred_is_position_count_elsewhere` | same | without a class-0 mark or negation overlay, the cap holds, the output is not zalgo, and `is_zalgo` is exactly "some position carries more than `k`" |
| `fixed_cap`, `fixed_pairing`, `fixed_idem` | same | the fix caps every position, pairs the two functions both ways, and is idempotent |
| `fixed_agrees_elsewhere`, `fixed_only_adds_detections` | same | the fix moves nothing outside the Z1/Z2 shapes, and only ever adds detections |
| `tags_props`, `inv_props` | 1,111,111 words over 10 tokens | `strip_tags` and both policies are idempotent and leave no tag outside a valid flag; comparison leaves no selector, PUA or CGJ; rendering keeps a selector only after a presentation base |
| `format_props`, `compare_idem` | 1,948,717 words over 11 tokens | `strip_format` is idempotent, collapses, and leaves no control, format, bidi, blank, stray tag or orphaned selector; the comparison composition is idempotent and selector-free |
| `ed_eq_lev`, `ed_metric` | 14,641 pairs; 29,791 triples | `edit_distance` computes Levenshtein distance and is a metric |
| `contract_idem` | 960,800 words | contraction is idempotent and leaves no rule source behind |

`Findings.lean` checks each counterexample below with `decide` (kernel only).

## Findings

### Z1: a class-0 mark between two runs of one mark resets the count (code bug, medium)

`is_zalgo` counts, per combining class, the marks *consecutive in NFD*, and resets on a
class-0 mark (`src/zalgo.rs` L75-79). `strip_zalgo` does the same (L252-255). The #842
argument for counting per class is that canonical ordering sorts a base's marks by class,
so "an attacker cannot break up a run by interleaving classes"
(`tests/test_zalgo_combining_class.py` L17-21; the same reasoning at `zalgo.rs` L66-68 and
`anomalies.rs` L841-843). But canonical ordering only sorts *between starters*, and a
class-0 mark is a starter. 1,493 of the 1,496 class-0 marks split a run into runs of at
most `k` (swept), and the base then carries as many marks as the attacker writes. Among the separators
are `U+034F` (the combining grapheme joiner, whose purpose is to block canonical
reordering), the Mongolian free variation selectors `U+180B`-`U+180D`, `U+180F` and the
Khmer inherent vowels `U+17B4`/`U+17B5`, all of which render as nothing, and the last six
of which `canonicalize` keeps. The same reset is in `drop_repeated_marks_into` (L145-152)
and `anomalies::duplicate_stacking_mark`, so neither the key builders' repeat-dropper nor
the `duplicate_mark` finding sees the repeat either.

```bash
python3 -c 'import disarm,unicodedata as u; s="a"+"\u0301"*3+"\u034f"+"\u0301"*3; t="a"+("\u0301"+"\u180b")*20; print(disarm.is_zalgo(s), u.normalize("NFD",disarm.strip_zalgo(s)).count("\u0301"), u.normalize("NFD",disarm.canonicalize(t)).count("\u0301"), disarm.inspect_anomalies(t).kinds)'
# False 6 20 ['mixed_script']
```

Expected: `True 3 3` and a `zalgo` finding; `is_zalgo("a" + "\u0301" * 6)` is `True`. A
visible separator works too: `"a" + ("\u0301" * 3 + "\u0e31") * 10` gives
`is_zalgo` `False` and 30 acutes after `strip_zalgo`. Minimal counterexample (kernel,
`z1_minimal`): `a U+0301 U+0E31 U+0301` at `max_marks = 1`.

**Severity: medium.** It defeats the one control disarm has for mark stacking, in every
surface that runs it, with invisible characters, and `canonicalize`'s output keeps the
stack. It needs crafted input.

**Minimal fix:** count per base and per class, and let a class-0 mark neither count nor
reset (for `threshold > 0`): a `[u16; 256]` table (or a small list of the classes touched)
cleared at each non-mark, in `exceeds_combining_run`, `strip_zalgo_into`,
`has_repeated_mark`/`drop_repeated_marks_into` (reset `previous` only at a non-mark) and
`duplicate_stacking_mark`. Checked on the model (`isZalgoFixed`, `stripFixed`):
`fixed_cap`, `fixed_pairing`, `fixed_idem`, and `fixed_agrees_elsewhere`, which shows the
fix changes nothing on input without a class-0 mark or a negation overlay.
**Stored keys move** for inputs that stack more than three same-class marks on one base
across a class-0 mark. Measured on `"a" + ("\u0301" * 3 + sep) * 6`, which should reduce like
`"a" + "\u0301" * 8` (one acute): `canonicalize` keeps 6 acutes for every separator tried
(`U+180B`, `U+1CE1`, `U+20DD`, `U+1CF00`, `U+0E31`), `canonicalize_strict` 6 for the
`Inherited` ones (`U+1CE1`, `U+20DD`, `U+1CF00`), `sort_key` 6 for all but `U+180B`;
`search_key`, `catalog_key` and `strip_obfuscation` remove every mark and are unaffected. A
`KEY_SCHEMA_VERSION` question (`src/api/metadata.rs` L149 records the last bump for this
cap).

### Z2: `strip_zalgo`'s output is still zalgo (inconsistency, low)

`strip_zalgo` keeps the first negation overlay (`U+0338`, `U+20D2`) on a symbol without
counting it (L227-241, #749), then `max_marks` more; `is_zalgo` counts all of them
(L53-91). So the transform's output is flagged by the predicate at the same threshold, and
at `max_marks = 0`, documented as "strips all combining marks", `U+2260` keeps its stroke.

```bash
python3 -c 'import disarm; o=disarm.strip_zalgo("="+"\u0338"*4); print(ascii(o), disarm.is_zalgo(o), ascii(disarm.strip_zalgo("\u2260", max_marks=0)), disarm.is_zalgo("\u2260", threshold=0))'
# '\u2260\u0338\u0338\u0338' True '\u2260' True
```

Expected: the output of `strip_zalgo(s, k)` is never `is_zalgo(., k)` (`fixed_pairing`
holds on the fixed model). **Minimal fix:** exempt the same first overlay in
`exceeds_combining_run` (`is_negation_of(ch, base)`, tracking `base` as the stripper does);
and say "every combining mark except one negation overlay on a symbol (#749)" where the docs
say "all". No key moves (the predicate is not in a key).

### Z3: "per base character" (doc overclaim, low)

`_presets.py` L1001-1052 and `api/text.rs` L129-142: `is_zalgo` is "True if any base
character has more than threshold consecutive combining marks", `strip_zalgo` "caps the
number of combining marks per base character". Since #842 the cap is per combining class
("at one position", `test_zalgo_cap.py`), so a base can carry `k` marks of every class:

```bash
python3 -c 'import disarm,unicodedata as u; s="a"+"\u0301"*3+"\u0316"*3+"\u0334"*3; print(disarm.is_zalgo(s), sum(1 for c in u.normalize("NFD",disarm.strip_zalgo(s)) if u.combining(c)))'
# False 9
```

**Fix:** the docstrings should say "more than *threshold* marks of one combining class on
one base". No code change; no key moves.

### W1: a cluster that opens with a zero-width `Prepend` measures 0 (code bug, medium-low)

`grapheme_width_opts` takes the first scalar of a cluster as its base and returns 0 when
that base is zero-width (`src/width.rs` L65-87). By UAX #29 GB9b a `Prepend` attaches to
the *following* character, so `U+0600 ARABIC NUMBER SIGN` + `1` is one cluster whose first
scalar is a `Cf` of width class 0, and the digit's cell disappears. Thirteen `Prepend`
scalars do this (`U+0600`-`U+0605`, `U+06DD`, `U+070F`, `U+0890`, `U+0891`, `U+08E2`,
`U+110BD`, `U+110CD`); the width is under-reported by one column per occurrence, without
bound.

```bash
python3 -c 'import disarm; print(disarm.terminal_width("\u0600"+"1"), disarm.terminal_width("\u0600"+"123"), disarm.terminal_width(("\u0600"+"A")*100), disarm.terminal_width("\u0600 ok"))'
# 0 2 0 2
```

Expected `1 3 100 3` (the number sign is `Cf`, 0 columns; the characters after it are not).
The docstring says zero columns are for "combining marks, controls, and zero-width
characters". `docs/limitations.md` L879 also says "the left operand `a` is unaffected: the
separator always starts a fresh cluster regardless of what `a` ends with"; with `a` ending
in any of the 27 `Prepend` scalars it does not (`grapheme_len("\u0600" + " " + "ok")` is 3,
not 4). Kernel counterexample: `w1`.

**Severity: medium-low.** A caller using `terminal_width` to bound a column (log
alignment, truncation to a terminal width) can be handed arbitrarily long visible text that
measures 0.

**Minimal fix:** skip leading scalars that are `Grapheme_Cluster_Break=Prepend` with width
class 0 before choosing the base (`gwFixed`; `gwFixed_spacing` proves the fixed width is at
least 1 whenever the scalar after the prefix takes a cell, `gwFixed_eq` that nothing else
changes). The 13 scalars can be a generated range table beside `WIDTH_RANGES`. Correct the
`limitations.md` sentence to exclude a left operand ending in a `Prepend`. No key moves.

### W2: a stray VS16 widens a non-emoji base (inconsistency, low)

`width.rs` L104-116 ignores a VS15 that follows a non-emoji base but not a VS16:
`has_vs16` alone returns 2. UTS #51 defines emoji presentation only for the bases listed in
`emoji-variation-sequences.txt`; `a` + `U+FE0F` renders as `a`.

```bash
python3 -c 'import disarm; print(disarm.grapheme_width("a\ufe0f"), disarm.grapheme_width("a\ufe0e"), disarm.terminal_width("a\ufe0fb\ufe0fc\ufe0f"))'
# 2 1 6
```

Expected `1 1 3`. **Fix:** honour VS16 only on a base with the `Emoji` property (the
`emoji_property.tsv` that build.rs already reads), symmetric with VS15. Kernel: `w2`. No key
moves.

### C1: `is_case_fold_stable` and `fold_case` against the host's `str` (doc overclaim, low)

`_api.py` L1125: `is_case_fold_stable` "Answers `fold_case(text) == text.lower()`", and
L1084 / `_text.py` L176: `fold_case` is "Equivalent to `str.casefold()`". Both actually
compare with what is compiled into disarm: the Unicode 16.0 fold table, and the
`to_lowercase` of the Rust toolchain that built the wheel (Unicode 17.0 for this one). The
predicate therefore disagrees with `fold_case(t) == t.lower()` on

* the 27 cased letters Unicode 16 added (`U+1C89`, `U+A7CB`, `U+A7CC`, Garay, ...), on any
  Python before 3.14, and
* the 28 cased letters Unicode 17 added (`U+A7CE`, `U+A7D2`, `U+A7D4`, `U+16EA0`-`U+16EB8`),
  on every current Python, 3.14 included (swept under both 3.11 and 3.14).

```bash
python3 -c 'import disarm; c="\u1c89"; print(disarm.is_case_fold_stable(c), disarm.fold_case(c)==c.lower(), ascii(disarm.fold_case(c)), ascii(c.casefold()))'
# True False '\u1c8a' '\u1c89'     (Python 3.11, UCD 14.0)
python3.14 -c 'import disarm; c="\ua7ce"; print(disarm.is_case_fold_stable(c), disarm.fold_case(c)==c.lower())'
# False True                        (Python 3.14, UCD 16.0)
```

The docstring warns about one direction only (characters the host knows and the table does
not). **Fix:** say that the comparison is with the lowercase compiled into disarm, not the
host's; the Rust doc (`api/text.rs` L156-191) is already precise about that. No key moves.

### C2: the toolchain dependence of `is_case_fold_stable` is live, not latent (doc overclaim, low)

`docs/provenance.md` L50-56 and `api/text.rs` L175-185: "two builds of the same disarm version
can disagree here (#718) ... That divergence is currently latent rather than live ... every
rustc from 1.88 carries Unicode 16 or newer ... no toolchain that can compile disarm
currently exercises it." The argument checks the oldest toolchain only. The fold table is
pinned at Unicode 16.0, and any toolchain on a *newer* Unicode than the table lowercases
letters the table does not fold. `scripts/premises` prints the toolchain's version: this
build's `to_lowercase` is Unicode 17.0.0, and the 28 Unicode 17 letters above read unstable
(`fold_case` leaves them, `to_lowercase` moves them). On rustc 1.88 (Unicode 16) neither
side knows them and they read stable.

```bash
python3 -c 'import disarm; print([disarm.is_case_fold_stable(c) for c in "\ua7ce\ua7d2\U00016ea0"], ascii(disarm.fold_case("\ua7ce")))'
# [False, False, False] '\ua7ce'
```

Reproduced: the value on this build, and that the three are unassigned in UCD 16.0 (Python
3.14's `unicodedata`), so a Unicode 16 `to_lowercase` cannot move them. Not reproduced: the
`True` on a rustc 1.88 build (only a current stable toolchain is installed here).
**Fix:** state the dependence as live for toolchains newer than the table, or pin the
comparison to a lowercase table generated from the same UCD as `case_folding.tsv`, which
removes the dependence. No key moves.

### D1: `strip_zero_width_chars` "the set is exactly" 10 code points (doc overclaim, low)

`_api.py` L1233-1248 lists `U+200B`-`U+200D`, `U+2060`-`U+2064`, `U+FEFF`, `U+180E` as
"exactly" the set. Since #813 `whitespace::is_zero_width` (L153-178) also removes
`U+1BCA0`-`U+1BCA3` and `U+1D173`-`U+1D17A`: 22 code points (swept).

```bash
python3 -c 'import disarm; print(ascii(disarm.strip_zero_width_chars("a\U0001d173b")))'
# 'ab'
```

**Fix:** add the two #813 ranges to the list. No key moves.

### D2: the Default_Ignorable code points `canonicalize` keeps (doc overclaim, low)

`docs/limitations.md` L317-330 says `canonicalize` removes 387 of the 405 assigned
Default_Ignorable code points and lists what it keeps, including `U+1BCA0`-`U+1BCA3` and
`U+1D173`-`U+1D17A`. Since #813 it removes those; measured over the 405 (UCD 18 via the
`regex` oracle, the same 405), it keeps 6: `U+17B4`, `U+17B5`, `U+180B`, `U+180C`,
`U+180D`, `U+180F`. (The list also has 19 entries under a heading of 18.)

```bash
python3 -c 'import disarm; print(ascii(disarm.canonicalize("a\U0001d173b")), ascii(disarm.canonicalize("a\U0001bca0b")), ascii(disarm.canonicalize("a\u180bb")))'
# 'ab' 'ab' 'a\u180bb'
```

**Fix:** 399 removed, 6 kept, and the table cut to the Khmer and Mongolian rows. Worth
noting there too: the six kept are exactly the invisible Z1 separators `canonicalize` lets
through.

### D3: `fold_punctuation`'s classes are not complete (doc overclaim, low)

`punctuation.rs` L30-44 against the docstring (`_presets.py` L748-772, `api/text.rs`
L65-67): "the non-standard spaces become a space" leaves `U+1680 OGHAM SPACE MARK`, the
only other `Zs` (which `collapse_whitespace` does fold); "the curly and low-9 quotes" leaves
the reversed curly quotes `U+201B`, `U+201F`; "the primes" leaves `U+2034`-`U+2037`.

```bash
python3 -c 'import disarm; print(ascii(disarm.fold_punctuation("a\u1680b\u201bc\u201fd\u2034e")))'
# 'a\u1680b\u201bc\u201fd\u2034e'
```

**Fix:** add them to `ascii_for` (`U+1680` to a space, `U+201B` to `'`, `U+201F` to `"`,
the reversed primes `U+2035`/`U+2036` like `U+2032`/`U+2033`, the triple primes to three
apostrophes), or narrow the docstring to the characters folded. `fold_punctuation` is not
in any preset, so no key moves.

## Checked, and holds (or matches documented intent)

* **`is_case_fold_stable`'s early return is sound** (`stable_correct`). The per-scalar scan
  could in principle miss cancelling disagreements; the premise that makes it impossible
  (no scalar lowercases to something longer than its fold) holds on every scalar.
* **`collapse_whitespace` ordering (review D-8).** A strip run *after* the collapse can
  leave two spaces (`d8_order_matters`); the presets always collapse last, as documented.
* **Contraction idempotence.** `build.rs` asserts only that no target occurs inside a
  source. That is not sufficient in general (with a two-character target `ab -> pq`,
  `qz -> y`, the input `abz` gives `pqz`, then `py`), but build.rs also asserts every target
  is one character, and with that the argument holds: `contract_idem` confirms it on 960,800
  words.
* **Negation overlays in `strip_accents`/`strip_zalgo(0)`** are the documented #749
  exception, and the two functions agree on every scalar.
* **`strip_bidi`** removes more than its Python docstring lists (`U+206A`-`U+206F`,
  `U+FFF9`-`U+FFFB`, as the Rust doc says): an under-claim, not a defect.
* **`grapheme_split`'s Python cap** is 10 x 2^20 *characters*, raising
  `ResourceLimitError` (a `DisarmError` subclass); `docs/user-guide/graphemes.md` says
  "10 MB". A unit slip only.

## Not confirmed

* **Width table and segmenter versions.** The width table is UCD 15.1; `unicode-segmentation`
  is 17.0. 26 spacing marks that the newer UCD makes `Grapheme_Extend` (`U+0CC0`, `U+1715`,
  `U+1B44`, `U+A953`, `U+111C0`, ...) measure 1 when they start a cluster (for instance at
  the start of the text), where a table from the segmenter's UCD would give 0. Inside a
  cluster they are not counted, so this only shows for a leading mark; it is version skew,
  not a logic error, and not counted as a finding.
* **`closest_match`** (`utils.rs` L40-66) says the edits "must be a minority of the longer
  string"; the guard `d * 2 < max_len + 1` admits exactly half. Only used for "did you
  mean" hints; not reproduced as a user-visible defect.

## Re-running

```bash
export PATH=/path/to/lean-4.34.0/bin:$PATH
cd formal/lean/Text
lake build                                   # every proof; about 3 minutes
lake env lean Text/Axioms.lean               # the axiom audit
python3 scripts/difftest.py                  # needs an importable `disarm`
python3 scripts/repro.py                     # the findings, on the installed library
TEXT_ORACLE_PATH=... python3 scripts/sweep.py
(cd scripts/premises && CARGO_TARGET_DIR=../../.lake/cargo cargo run --release)
```
