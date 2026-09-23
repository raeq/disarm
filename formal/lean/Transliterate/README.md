# Formal audit: the per-character → string lift for `transliterate` (I1–I3, I7)

Method: model the argument, make its premises explicit, then check the premises
against the real code. Every premise that fails is a bug in the claim or in the code.

> **Status.** F1 is fixed in #1008 and F5 in #1013, each with a regression test. F2, F3,
> F4, F6, F7 and F8 were claims in the documentation, corrected in
> `docs/formal-verification.md` and `docs/architecture/testing-guarantees.md` together
> with this model; the I7 test now uses the corrected bound and pins U+337F. The Greek
> spacing accents U+1FCD-U+1FCF and U+1FDE noted under F5 are consistent with their
> decompositions and were left as they are.

**Target.** `docs/formal-verification.md` and `docs/architecture/testing-guarantees.md`
say I1 (ASCII passthrough), I2 (ASCII output with `errors='ignore'`) and I3
(idempotence) are *proven* "over their finite domains (exhaustion, with a structural
lift for I2)" (`formal-verification.md` lines 119–130). The exhaustion is
`tests/exhaustive_transliterate.rs` (`exhaustive_bmp_ignore_produces_ascii`,
`exhaustive_bmp_idempotence`): one BMP code point at a time, **default options
only** (`lang=None`, default scheme, `tones=false`). The lift is defined at lines
28–30 and 35–36: "the output of a character-wise map that emits ASCII for every
character is ASCII for every string".

## Summary

1. **The lift's premise is false for the real code.** The lift needs `f` to be a
   monoid homomorphism (`f(a+b) = f(a)+f(b)`, premise **H**). `transliterate` is not
   one: 1,755,178 counterexamples in 13,256,192 checked pairs and triples, from
   five mechanisms, all of them intended behaviour. So the per-code-point exhaustion
   proves nothing about strings, and "(b) structural (concatenation of ASCII is
   ASCII)" does not apply as written.
2. **I2 and I3 still hold at string level under the default profile**, for a
   different reason. The engine *emits* pieces, and when every piece it can emit
   is ASCII (premise **E**) the output is ASCII. That holds for any context-sensitive
   plan (`Engine.lean`: `translit_I2`). I1 is the ASCII fast path, and I3 follows
   from I1 and I2 without H (`I3_of_I1_I2`). Premise E is discharged by the
   `build.rs` assertions over *table values* and by reading the four
   `push_str` sites, not by the per-code-point exhaustion.
3. **Premise E fails under three options**, and the docs do not restrict I2/I3 to
   exclude them:
   * `context=True`: non-word spans are appended verbatim. This is a **real bug**:
     the output is non-ASCII, bidi controls survive, and `errors=` is ignored for
     those spans.
   * `tones=True`: toned pinyin is non-ASCII by design, which breaks both I2 and I3.
     The docs overclaim here.
   * `register_lang` / `register_replacements`: user-supplied values break I1, I2
     and I3. The docs overclaim here too.
4. **I7 is false.** The stated bound fails on the single code point U+337F `㍿`.
5. Side findings: normal-form invariance (the #477 claim) fails for U+1FEE, U+1FFD,
   and 156 CJK compatibility ideographs under `tones=True`. The I6 statement
   contradicts the code and its own test. I3 fails under
   `errors='preserve', lang='auto'`.

## The Lean development

`lake build` (Lean 4.34.0 core, no Mathlib) checks everything. `Transliterate.lean`
prints the axioms of each headline result. None uses `sorryAx`, and none uses
`native_decide` (`Lean.ofReduceBool`).

| File | Result | Premises |
|---|---|---|
| `Lift.lean` | `IsHom.nil`, `IsHom.eq_charwise`: H ⇔ "`f` is a character-wise map" | — |
| | `lift_I1`: per-char I1 ⇒ string I1 | **H** |
| | `lift_I2`: per-char ASCII ⇒ string ASCII (the doc's lift) | **H** |
| | `lift_I3_hom`: per-char idempotence ⇒ string idempotence | **H** |
| | `lift_I3_via_I1_I2`: per-char I1 + per-char I2 ⇒ string I3 | **H** |
| | `I3_of_I1_I2`: string I1 + string I2 ⇒ string I3 | none (no H) |
| `Counterexamples.lean` | `dropXY`: per-char I1 and I3 hold for **every** `Char`; string I3 and I1 fail (`"xxy"`, `"xy"`); `dropXY_not_hom` | shows H is necessary for I1/I3 |
| | `sepJoin '·'`: per-char I2 holds for every `Char`, `sepJoin '·' "北京"` is not ASCII — the separator is never seen by a per-character test | shows H is necessary for I2 |
| | `sepJoin ' '`: ASCII for every string (`sepJoin_space_ascii`) yet not a homomorphism | the real engine's shape |
| `Engine.lean` | `engine_I2`, `translit_I2`: output ASCII for every string, any recursion depth | **E** (every emitted piece ASCII); plan arbitrary and context-sensitive |
| | `translit_I1`: string I1 (fast path) | none |
| | `translit_I3`: string I3 | **E** |
| | `not_I2_of_emit`: one non-ASCII emitted piece breaks I2 | shows E is necessary |
| | `ctxShipped_not_I2`: the shipped `context=True` shape breaks I2 whenever a non-word token is non-ASCII | — |
| | `ctxFixed_I2/I1/I3`: routing non-word tokens through `f` restores all three | `f` satisfies I1 and I2; tokenisation is a partition; ASCII has no word tokens |

The engine model (`Act.emit` / `Act.recover` / `Act.pop`, `run` with recursion fuel)
matches `transliterate_run` and `handle_unmapped` in `src/transliterate.rs`. It
appends pieces (lines 689, 792, 909, 926, plus the `' '` pushes at 685/787 and the
`Preserve` push at 931), and its only deletion is `result.pop()` (737, the Indic
inherent-`a` rule). Which pieces it appends can depend on the whole input
(composition, `lang="auto"`, neighbours). The model allows that because `plan` is an
arbitrary function.

### Premise E, discharged piece by piece against the code

| Emitted piece (src/transliterate.rs) | ASCII? | Discharged by |
|---|---|---|
| ASCII run, l.689 | yes | selected by `bytes[i] < 0x80` |
| default / SMP / lang / iso9 / gost7034 table value, l.792 | yes | `build.rs` asserts every value |
| toned-pinyin value (`tones=True`), l.792 | **no** | not asserted; `běi` by design |
| `register_lang` value, l.792 | **no** | `register_lang` does not validate |
| separator `' '`, l.685/787 | yes | literal |
| NFKC recovery `sub`, l.909 | yes | induction (`engine_I2`) |
| unmapped, `errors='ignore'` | yes | emits nothing |
| unmapped, `errors='replace'`, l.926 | iff `replace_with` is ASCII | caller |
| unmapped, `errors='preserve'`, l.931 | **no** | by design (I2 is stated for `ignore`) |
| `result.pop()`, l.737 | preserves ASCII | `AllA.dropLast` |
| `context=True`: non-word token, `src/context.rs:498` | **no** | **bug** (F1) |

## Premise checks against the real library

All searches drive the installed `disarm` 0.16.0 built from `main` (`bec93cf`). Numbers
are from the full (non-`--quick`) runs.

### Premise H (homomorphism): `search/homomorphism.py` — FAILS

13,256,192 checks: exhaustive pairs in 20 domains, one exhaustive triple domain,
and 800,000 random BMP pairs, under 1–7 `lang`/scheme profiles × 3 `errors`
modes (plus `tones`). Hangul L×V×T triples are exhaustive at 10,773 × 6 profiles.
The script checks string-level I2 and I3 on every input as well.

| Mechanism (classification) | Counterexamples | Minimal example (default options unless noted) |
|---|---|---|
| CJK word spacing (`needs_cjk_space`) | 1,730,912 | `北京` → `bei jing`; `北`+`京` → `beijing` |
| Indic inherent-`a` deletion (virama / mātrā) | 18,596 | `का` → `ka`; `क`+`ा` → `kaa` |
| canonical reordering at the compose boundary | 2,601 | Hebrew `\u05b2\u05b0` (ccc 12, 10) → `ea`; concat `ae` |
| `lang="auto"` whole-string detection | 1,681 | `ЂЇ` → `DjYi`; `Ђ`+`Ї` → `DjI` |
| composition (NFC, decomposing marks, singletons) | 1,177 | `Е`+`\u0308` → `Yo`; concat `E` |
| composition via the #477 widening map | 197 | `क`+`़` → `qa` (U+0958); `א`+`ַ` → `a`, concat `'a` |
| other (`lang="auto"` + kana spacing) | 14 | `\u3324\u3058` → `dasu ji`; concat `da-suji` |
| **total** | **1,755,178** | |

Digits (every `Nd` in the BMP, 2,874,900 pair checks over 21 profiles), Greek (with
`lang="el"`), Thai/Lao, and mark×mark are homomorphic on the domains searched.
Greek final sigma and Japanese sokuon are not context rules in this engine:
`きって` → `kitsute`, which is the documented behaviour.
`transliterate` has no digit-policy argument (that is a confusables option), so
the digit-policy axis does not apply.

All of these are intended behaviour. The finding is not that the code is wrong; it
is that the lift the docs describe needs H, and H does not hold.

### String-level I1 / I2 / I3 / I7: `search/invariants.py`

The script checks:

* every Unicode scalar (1,112,064) under 18 core profiles: `lang` ∈ {None, auto} ×
  scheme ∈ {default, strict_iso9, gost7034} × `tones` × `errors` ∈ {ignore, replace, preserve}
* every BMP scalar under each of the 83 `lang=` codes × `tones` (166 profiles)
* 20,000 random 2–12-character mixed-script strings (marks, jamo, Indic and CJK
  over-represented) under all 202 profiles

| Invariant | Checks | Failures | Where |
|---|---|---|---|
| I1 | 32,118 (+57,456 with `context=True`) | 0 | every profile; fails only with `register_replacements` (below) |
| I2 (`ignore`) | 27,443,776 | 415,799 | **all** with `tones=True`; 0 otherwise |
| I3 | 54,613,312 | 473,342 | all but 2 with `tones=True`; 2 with `errors='preserve', lang='auto'` |
| I7 (`ignore`) | 27,443,776 | 178 | U+337F, under every `ignore` profile (89 × 2) |
| normal-form invariance | 2,791,834 | 41,518 | U+1FEE/U+1FFD (all profiles); CJK compat ideographs (`tones=True`) |

With `tones=False`, `context=False` and no registrations, I2 and I3 hold on every
string checked, as `translit_I2`/`translit_I3` predict.

### `context=True`: `search/context_dict.py`

Context dictionaries are not committed. The script writes a minimal valid `TRLD` v1
dictionary per language to a temp dir and sets `DISARM_DICT_DIR`. The findings do
not depend on its content. It checks {ar, fa, he} × 3 `errors` × 3 schemes, over
every BMP scalar alone, after a word, and before a word.

| Invariant | Checks | Failures |
|---|---|---|
| I1 | 57,456 | 0 |
| I2 | 1,710,720 | **1,673,055** |
| I3 | 5,132,160 | 0 (verbatim spans are idempotent) |
| I7 | 1,710,720 | 0 |
| H | 1,710,720 | 37,530 (dictionary lookup is per word, which is intended) |

### Registrations: `search/registration.py`

`register_lang('xx', {'é': 'éé'})` is accepted, and then I2 and I3 fail.
`register_replacements({'a': 'b'})` breaks I1; this is documented, since the pre-pass
runs before the fast path. `register_replacements({'x': 'yx'})` breaks I3:
`x → yx → yyx`.

## Findings

Class **(a)** means a bug in `transliterate`. Class **(b)** means the behaviour is
correct but the docs claim a proof they do not have.

**F1 (a), high within scope: `context=True` passes non-Arabic/Hebrew text through
raw.** `src/context.rs:498` `result.push_str(&token.text)` for every non-word token.
Tokens outside U+0590–05FF, U+0600–06FF, U+0750–077F, U+08A0–08FF, U+FB1D–FDFF and
U+FE70–FEFF are non-word tokens. They are not transliterated, and `errors=` does not
apply to them. Affected inputs include Persian ZWNJ (common in ordinary Persian),
bidi marks, NBSP, and any Latin, Cyrillic or CJK text.

```python
# needs a dictionary: DISARM_DICT_DIR=<dir with *_dict.bin> (search/context_dict.py builds one)
fa = "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645"  # Persian word with a ZWNJ
disarm.transliterate(fa, lang="fa", context=True, errors="ignore")  # 'my\u200ckhvahm'
disarm.transliterate(fa, lang="fa", errors="ignore")  # 'mykhvahm' (context-free)
he = "\u200f\u05e9\u05dc\u05d5\u05dd\u200f"  # RLM + shalom + RLM
disarm.transliterate(he, lang="he", context=True)  # '\u200fshalom\u200f'
disarm.transliterate("\u00e9", lang="ar", context=True, errors="ignore")  # '\xe9'
disarm.transliterate("\u5317\u4eac", lang="ar", context=True, errors="replace")  # '\u5317\u4eac'
```

The expected behaviour is ASCII. The docstring says "Returns: ASCII transliteration
of the input". `docs/user-guide/abjad-transliteration.md:138` lists the
context-aware output charset as ASCII. I2 is stated for all `s`. The context-free
call returns `'mykhvahm'`. The existing `tests/test_context_*.py` never mix in a
non-abjad non-ASCII character, and they are skipped in CI where no dictionary is
present. **Fix:** route non-word tokens through the same function:
`result.push_str(&transliterate_fn(&token.text, lang))`. ASCII tokens still take the
borrowed fast path. `ctxFixed_I1/I2/I3` prove this restores I1–I3 given the
context-free engine's I1 and I2. Add a regression test that feeds a non-abjad
non-ASCII character to each context language.

**F2 (b), low: I2 and I3 are false with `tones=True`.**
`disarm.transliterate("北", tones=True, errors="ignore")` returns `'běi'`, which is
not ASCII. Applying it again returns `'bei'`, so I3 fails too. 2,375 single scalars
are affected, plus every string that contains one. This is the documented
behaviour of `tones` (`docs/limitations.md:157`). The overclaim is that I2/I3 in
`formal-verification.md:120–121` and `testing-guarantees.md:92–93` quantify over
all `s` with no option scope. The build-time table "All … values are ASCII"
(`formal-verification.md:47–52`) also omits the toned table, which is not asserted.
**Fix (doc):** scope I1–I3 to `tones=False, context=False` with no runtime
registrations, and say so next to the statements.

**F3 (b), low: I7 is false.** `disarm.transliterate("\u337f", errors="ignore")` returns
`'zhu shi hui she'`, 15 characters. The bound is 3 bytes × 4 + 1 = 13
(`formal-verification.md:125`, `testing-guarantees.md:97`,
`tests/test_formal_invariants.py::TestI7OutputLengthBound`). Its rationale,
"CJK pinyin is longest", misses NFKC-recovered CJK compatibility squares. The
worst per-scalar ratio over all 1,112,064 scalars is exactly 5.0, at U+337F. It
is the only violating scalar. A 500-example Hypothesis run will essentially never
draw it. **Fix:** either state the bound as `5·bytes + chars` and pin U+337F as a
regression, or drop the constant from the spec.

**F4 (b): the claimed proof of I2 and I3 is not a proof.** H fails (table above),
so "exhaustion over the BMP + (b) structural (concatenation of ASCII is ASCII)"
proves I2 only for single code points under the default profile, not for strings.
The same applies to I3. The strong statements are true under the default profile
and provable (`translit_I2`, `translit_I3`), but the justification is premise E
plus the fast path, not the exhaustion. **Fix (doc):** replace the lift sentence
with the emitter argument: every appended piece is ASCII, which is asserted per
table by `build.rs` and holds for `' '`, ASCII runs and recursion; `pop` preserves
ASCII; I1 is the fast path; I3 follows from I1 + I2. I2 and I3 can then be tagged
(b) for the default profile. Note that the BMP exhaustion covers default options
only.

**F5 (a), low: normal-form invariance (#477) fails on three sets.**
* `transliterate("\u1fee")` returns `'x'`, but its canonical equivalent
  `transliterate("\u0385")` returns `'"'`.
* `transliterate("\u1ffd")` returns `'x'`, but `transliterate("\u00b4")` returns `' '`.
  Both come from table rows `translit_default.tsv:6572,6583`. The Greek spacing
  accents U+1FCE/1FDE (`x`) and U+1FCD/1FCF (`ps`) look like the same data defect.
* With `tones=True`, 156 CJK compatibility ideographs get toneless pinyin:
  `transliterate("\ufa34", tones=True)` returns `'qin'`, while their NFC form
  `transliterate("\u52e4", tones=True)` returns `'q\xedn'` (`qín`).

The comment at `src/transliterate.rs:389` says the transform "is invariant to the
input's normal form". I1–I3 are not affected. **Fix:** map the Greek spacing
accents to their canonical equivalents' values, and in `default_lookup(ch, true)`
retry the canonical singleton before falling back to the toneless table.

**F6 (b), low: I3 fails under `errors='preserve', lang='auto'`.**
`transliterate("\u5317\ua69d", lang="auto", errors="preserve")` returns `'bei\ua69d'`. Applying it
again detects Cyrillic and returns `"bei'"`. This is outside the stated I3, which
is for `ignore`. Mention it if I3 is ever widened.

**F7 (b), low: registrations are outside the invariants.** See `registration.py`.
`register_lang` accepts non-ASCII values: its docstring says "ASCII (best-effort)",
but nothing validates them. **Fix:** validate ASCII in `register_lang`, or scope
I1–I3 to no registrations (F2's doc fix).

**F8 (b), low: I6 contradicts the code.** `formal-verification.md:124` and
`testing-guarantees.md:96` say "`|s| > 10 MiB → DisarmError`". `#80` removed the
cap, and `tests/test_formal_invariants.py::TestI6NoInputSizeCap` asserts that a
12 MiB input is *accepted*. `transliterate("é" * 6*2**20)` returns normally. The
only 10 MiB limit left is `MAX_REPLACEMENT_OUTPUT_BYTES`.

## Re-running

```bash
# Lean (Lean 4.34.0 toolchain on PATH; no Mathlib)
cd formal/lean/Transliterate && lake build

# Searches (need the built `disarm` package importable)
cd formal/lean/Transliterate/search
python3 homomorphism.py [--quick] [--json out.json]   # ~3 min full, 30 s quick
python3 invariants.py   [--quick] [--json out.json]   # ~5 min full (all 1.1M scalars)
python3 context_dict.py [--json out.json]             # ~2 min; builds a temp TRLD dict
python3 registration.py                               # mutates global state: own process
```

The searches only call the public `disarm.transliterate` / `register_*` API, so they
can be re-run against any build. `--quick` limits the scalar sweep to the BMP and
shrinks the random samples.
