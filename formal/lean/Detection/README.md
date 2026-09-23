# Formal model of detection and safety analysis (Lean 4)

Lean 4 models of three detectors: `has_anomalies` (`src/anomalies.rs`), the
smuggled-payload decoder `decode_smuggled` (`src/smuggled.rs`) and `is_mixed_script`
(`src/scripts.rs`). Each model was validated against the built library by differential
testing before any proof or counterexample counted. The properties are the ones the code
and the documentation claim, or that a detector owes the cleaners it sits beside. Every
property that failed was cut down to a minimal input and reproduced on the library. Four
sweeps over every Unicode scalar check the detector/cleaner pairs directly. They also cover
the hostname screen in `src/api/safety.rs`, which has no model.

Written against `main` at `595fbda`. Line numbers (`L1247`) refer to that commit. The
library under test is the `0.16.0` wheel built from the same commit. The toolchain is core
Lean 4.34.0, with no Mathlib.

Non-ASCII characters appear in this directory only as escapes (`\u200f`) or as `U+200F`.

## Layout

| File | Contents |
|---|---|
| `Detection/Anomaly.lean` | The `has_anomalies` model, the cleaner classes, and the three proposed fixes (`hasAnomaliesFixed`). |
| `Detection/Props.lean` | General theorems about it: locality, canonical equivalence, the fixed number-run rule. |
| `Detection/Smuggled.lean` | The decoder model (`step`, `decodeF`) and the three documented encoders. |
| `Detection/SmuggledProps.lean` | General theorems: the fuel bound, the cut lemma, and the three round trips. |
| `Detection/Scripts.lean` | `AugmentedState` as code (`isMixed`) and UTS #39 section 5.1 as a specification (`spec`, `specScx`). |
| `Detection/Findings.lean` | The failed properties as minimal counterexamples, checked by `decide`. |
| `Detection/Bounded.lean` | Bounded exhaustive checks (`native_decide`). |
| `Detection/Axioms.lean` | `#print axioms` for the headline theorems. Not in the default build. |
| `Main.lean`, `scripts/difftest.py` | The differential test. |
| `scripts/sweep_*.py`, `scripts/fuzz.py` | The all-scalar sweeps, and a random fuzz of every detector. |
| `repro/r*.py` | One reproduction per finding. |

## The models

### `has_anomalies`

The alphabet is split by the branches `classify` (L1125-1504) takes. Each class is one
concrete code point.

| Class | Concrete | Branch it exercises |
|---|---|---|
| `a`, `p`, `m` | `e`, `U+00E9`, `U+0301` | ASCII letter; precomposed letter (alphabetic, not ASCII, NFD `a m`); stacking mark |
| `h`, `d` | `U+05D0`, `1` | strong-R letter; ASCII digit |
| `sp`, `cr`, `lf` | space, CR, LF | token boundaries; line breaks (`overwriting_cr`, L665-680) |
| `zw`, `nj` | `U+200B`, `U+200C` | neighbour rule (L1186-1215), non-joiner and joiner |
| `shy`, `vs`, `tag`, `pua` | `U+00AD`, `U+FE01`, `U+E0061`, `U+E000` | the four carrier runs, floors 8, 2, 1, 4 (`carrier_run`, L1091-1123) |
| `rlo`, `rli`, `rlm`, `lrm` | `U+202E`, `U+2067`, `U+200F`, `U+200E` | the bidi rules (L1225-1253) |
| `fmt` | `U+206A` | a deprecated format control: no detector predicate |
| `bel` | `U+0007` | the `control` rule (L1154-1156) |

The lexicon is empty (`lexicon=None`), so `leet` and `segmentation` cannot fire. On this
alphabet `mixed_numbers`, `enclosing_mark`, `compat_fold` and `confusable` never fire
either. The differential test establishes that, rather than an argument. The
`decoded_payloads` disjunct is left out, because every decoding run here is also a carrier
run over its floor. The differential test confirms that too.

### `decode_smuggled`

`step` is one iteration of `decode` (L117-156): the subdivision-flag skip, then the tag,
selector and zero-width scanners in that order. `decodeF` is the loop, with fuel so the
kernel can evaluate it. The classes are `z0 z1 zs` (`U+200B U+200C U+200D`), `vsb n`, `tagb n`,
`cancel` (`U+E007F`), `flag` (`U+1F3F4`) and `x` (anything else). The percent scheme is
not modelled, and nothing in the alphabet is a `%`.

### `is_mixed_script`

`isMixed` is `AugmentedState::accept` (L82-102) with the early exit of `all`. `spec` is
UTS #39 section 5.1 read literally: intersect the augmented script sets of every
character, where Common and Inherited are every set. Characters are abstracted to the
script `detect_char_script` gives them.

## Validation: differential testing

```bash
lake build difftest
python3 scripts/difftest.py --exhaustive-anomaly 5 --exhaustive-smuggled 4 \
    --exhaustive-scripts 5 --random 300000 --seed 1017
```

| Model | Inputs | Agree |
|---|---|---|
| `has_anomalies` | every word of length 5 or less over the 20 classes (3,368,421), plus 300,000 random words up to length 16 | **3,668,421 of 3,668,421** |
| `decode_smuggled` | every word of length 4 or less over 30 symbols (837,931), plus 300,000 random compositions of encoder output, flags and noise | **1,137,931 of 1,137,931** |
| `is_mixed_script` | every word of length 5 or less over 12 script classes (271,453), plus 300,000 random words | **571,453 of 571,453** |

The decoder comparison covers the scheme, the byte span, `units` and the bytes of every
payload, plus `text` on ASCII payloads. The defaults (`--exhaustive-anomaly 4
--exhaustive-smuggled 3 --exhaustive-scripts 4 --random 100000`) take about ten seconds.

One class could not be tested. `U+3105` (`bopo`) was meant to be Bopomofo, but no code
point resolves to Bopomofo in the library (Finding 5). It is left out of the differential
test and kept in the model, where it exercises a code branch the library cannot reach.

## What is proved

### In general, by induction (`Props.lean`, `SmuggledProps.lean`)

No `sorry` and no `native_decide`. `Axioms.lean` shows only `propext`, `Quot.sound` and
`Classical.choice`.

| Theorem | Statement |
|---|---|
| `hasAnomalies_append_lf` | **A line feed is a hard cut.** `has_anomalies(u + "\n" + v) == has_anomalies(u) or has_anomalies(v)` for every `u` and `v`, `CR` included. |
| `hasAnomalies_append_sp` | A space is a cut when neither side holds a `CR`. With one it is not, and should not be: `a \rX` overwrites the `a `, which neither half sees. The example after the theorem shows this. |
| `nfd_nfc`, `nfd_nfd` | The model's `nfc` and `nfd` fall in the same canonical-equivalence class. |
| `hasAnomaliesNfd_canonical`, `hasAnomaliesFixed_canonical` | **The proposed fix for Finding 3 is invariant under canonical equivalence**: inputs with equal NFD get one verdict. |
| `hasAnomaliesNfd_eq_of_no_p` | That fix changes nothing on input with no precomposed letter. |
| `anyRlmBeforeDigit_iff` | The fixed number-run rule is exactly the documented one: some `RLM` immediately before a digit. |
| `decodeF_fuel` | `l.length` fuel is enough, so `decodeAt` is the loop. |
| `decodeAt_cut` | **An ordinary character is a cut point.** Decoding `u + "x" + v` is decoding `u` and `v` separately, with the offsets shifted. |
| `roundtrip_tag`, `roundtrip_vs`, `roundtrip_zw` | **Each documented encoder round-trips.** Its output, set between two ordinary characters anywhere in any text, decodes to exactly the encoded bytes and span. Nothing else in the text changes. Printable ASCII is needed for `tag_ascii`, two bytes or more for `variation_bytes`, and one byte or more for `zero_width_binary`. |

### Bounded exhaustively (`Bounded.lean`, `native_decide`, about 40 seconds)

| Theorem | Words | Result |
|---|---|---|
| `isMixed_eq_spec` | every word of length 6 or less over 13 script classes (5,229,043) | holds: **the `AugmentedState` walk is UTS #39 section 5.1 over `Script`** |
| `isMixed_infix` | every infix of every word of length 5 or less | holds: `per_word=True` is never looser than the string-level answer |
| `fixed_agrees_elsewhere` | every word of length 5 or less (3,368,421) | holds: the three fixes move nothing except the three findings' inputs |
| `fixed_rlm_rule` | tokens of length 6 or less over 8 classes | holds for the fixed rule. It fails on the current one (Finding 2). |
| `fixed_cleaner_sound`, `current_cleaner_sound_but_fmt` | `u + [a, c, a] + v` with `u` and `v` of length 2 or less over all 20 classes | Deleting a zero-width, joiner, tag, override or control from inside a word is always reported. The current code fails only on `fmt` (Finding 1). |

## Sweeps over every Unicode scalar

```bash
python3 scripts/sweep_cleaners.py     # about 1 minute
python3 scripts/sweep_nf.py           # about 3 minutes
python3 scripts/sweep_scripts.py --fonttools DIR   # DIR: an unpacked fonttools 4.65.0 wheel
python3 scripts/sweep_hostname.py
python3 scripts/fuzz.py 11 1000000     # about 2 minutes
```

The sweeps cover 1,112,064 scalars. The first three contexts are `c`, `pay<c>pal` and
`1<c>2`.

| Pair | Result |
|---|---|
| `has_anomalies` against `inspect_anomalies(...).anomalous` | agree everywhere. They also agree on 1,000,000 random strings over a 61-character alphabet, where no detector function panicked either. |
| `is_canonical` against `canonicalize(s) == s` | agree everywhere |
| `has_anomalies(c)` implies `canonicalize(c) != c`, the one-way claim of `docs/api/predicates.md` | holds: 0 flagged-and-canonical code points |
| `strip_zero_width_chars`, `strip_tags`, `strip_control_chars` delete `c` from a word, so `has_anomalies` fires | holds for all three |
| `canonicalize` deletes `c` from a word, so `has_anomalies` fires | fails on 335 non-PUA code points. `U+00AD`, `U+034F`, `U+200E`, `U+200F` and lone selectors are documented spares. `U+206A`-`U+206F` and `U+FFF9`-`U+FFFB` are not (Finding 1), and neither are the 66 noncharacters. |
| `has_bidi_control` (the census) against `strip_bidi` changing the text | differ only on `U+00AD`, `U+206A`-`U+206F` and `U+FFF9`-`U+FFFB`, the extras `strip_bidi` documents |
| `has_anomalies` on NFC against NFD | 2,328,179 split verdicts across 7 contexts (Finding 3) |
| `detect_scripts` against UCD 17 `Script` | 70 code points get a script where the UCD says Common or Inherited, and 0 get a different script (Finding 5) |
| `is_mixed_script` against UTS #39 over `Script_Extensions` | 1,493 pairs over 82 code points are mixed to the library and single to UTS #39. None go the other way (Finding 5). |
| `is_suspicious_hostname` against the UTS #46 mapping it runs | 28 code points deleted silently (Finding 8) |

## Findings

Each finding was reproduced on the library. The output shown is the actual output of the
`repro/` script.

### Finding 1: `canonicalize` deletes a deprecated format control from inside a word, and the detector says nothing

**Class (a), code bug. Severity: medium.** This is the shape #813 fixed for `U+1D173`, and
#700 fixed for `U+2064` and `U+180E`. A guardrail that screens with `has_anomalies` passes
text that the comparison presets treat as something other than text.

```bash
python3 repro/r1_deprecated_format.py
# 'pay\u200bpal' True 'paypal' 'pay\u200bpal'
# 'pay\U0001d173pal' True 'paypal' 'pay\U0001d173pal'
# 'pay\u206apal' False 'paypal' 'paypal'
# 'pay\u206fpal' False 'paypal' 'paypal'
# 'pay\ufff9pal' False 'paypal' 'paypal'
# 'pay\ufffbpal' False 'paypal' 'paypal'
# 'pay\ufdd0pal' False 'paypal' 'pay\ufdd0pal'
```

The library's own comment at `src/presets.rs` L1053-1058 calls `U+206A`-`U+206F` and
`U+FFF9`-`U+FFFB` "invisible/format characters", and `strip_bidi`, `strip_format` and
`canonicalize` delete them. `U+206A`-`U+206F` are `Default_Ignorable_Code_Point`.

**Root cause:** `is_invisible_in_word` (`src/anomalies.rs` L47-55) ORs three predicates
from `crate::invisibles`. The set is in `presets::is_bidi_or_format` (`src/presets.rs`
L1038-1058) and in none of those three. The comment on
`invisibles::is_default_ignorable_format` (`src/invisibles.rs` L41-57) says it covers the
`Default_Ignorable` `Cf` code points "that no other predicate here covers". These six are
covered by a predicate in `presets`, which the detector never reads.

**Minimal fix:** move `matches!(ch, '\u{206A}'..='\u{206F}' | '\u{FFF9}'..='\u{FFFB}')`
into `invisibles` as one named predicate. `is_bidi_or_format` calls it, and
`is_invisible_in_word` ORs it in. Checked on the model: `f1_fixed` and
`fixed_cleaner_sound`. `f1_only_fmt` shows `fmt` is the only undocumented class the
current code misses.

**Secondary, class (c), low:** `canonicalize` also deletes the 66 noncharacters
(`U+FDD0`-`U+FDEF`, and `U+nFFFE` and `U+nFFFF`) from a word without a report. A
noncharacter usually renders as a replacement glyph, so this is an inconsistency rather
than a hidden-character attack.

### Finding 2: a second RTL mark defeats the number-run rule

**Class (a), code bug. Severity: medium.** It is a one-character evasion of a rule
written for exactly this construction (#741), and what the reader sees does not change.

```bash
python3 repro/r2_double_rlm.py
# 'Transfer \u200f100 200 300 to Bob' ['bidi']
# 'Transfer \u200f\u200f100 200 300 to Bob' []
# 'acct \u061c4321-9876' ['bidi']
# 'acct \u061c\u061c4321-9876' []
# 'acct a\u200f,\u200f4321-9876' []
```

An independent UBA implementation (python-bidi 0.4.2) renders both `Transfer` lines as
`Transfer 300 200 100 to Bob`. The second mark is another strong R beside the first and
changes no resolved level.

**Root cause:** `src/anomalies.rs` L1247 uses `chars.iter().position(...)`. That finds the
**first** mark in the token, and only that one is tested for a following digit.

**Minimal fix:** test every mark:
`chars.windows(2).find(|w| BIDI_RTL_MARKS.contains(&w[0]) && w[1].is_ascii_digit())`.
Checked on the model: `anyRlmBeforeDigit_iff` (the fixed rule is the documented one) and
`fixed_rlm_rule`. `f2_counterexample` is the minimal failure `[rlm, rlm, d]`, and
`f2_minimal` shows nothing shorter fails.

### Finding 3: canonically equivalent inputs get different verdicts

**Class (c), inconsistency. Severity: low to medium.** For `bidi` and `invisible`, the
**NFC** spelling is the unreported one, and NFC is the form nearly all text arrives in.
The library already treats form invariance as a requirement for the fold
(`fold_and_detect_are_form_invariant`, `src/confusables.rs` L706, #475, #477).

```bash
python3 repro/r3_canonical_equivalence.py
# '\xe9t\xe9\u2067' [] | 'e\u0301te\u0301\u2067' ['bidi']
# '\xe9\u200d\xe9' [] | 'e\u0301\u200de\u0301' ['invisible']
# '\xe0\xe9\u200f1' [] | 'a\u0300e\u0301\u200f1' ['bidi']
# 'Fran\xe7ais' ['confusable'] | 'Franc\u0327ais' []
# 'ch\u1ec9' ['confusable'] | 'chi\u0309' []
```

Minimal model counterexample: `[p, rli]`, which is `\u00e9\u2067` (`f3_isolate`).
`f3_minimal` shows no single character separates the forms. The sweep finds 2,328,179
split verdicts in 7 contexts.

**Root cause:** four tests read the token's code points as spelled, where they should read
its letters.

- `is_majority_latin` (L711-724) counts `is_ascii()`, so `\u00e9t\u00e9` is not
  "majority Latin" and its isolate is spared as right-to-left text.
- The joiner rule (L1193-1197) wants `is_ascii_alphabetic` on both sides.
- The `compat_fold` gate (L1375) and the `confusable` gate (L1484) want an ASCII letter.
- `folded_confusable` (L879) looks up precomposed `U+00E7` but never the NFD pair.

Four code points (`U+0385`, `U+1FC1`, `U+1FED`, `U+1FEE`) split the other way, through
Finding 5's table.

**Minimal fix:** run those four tests over `tok.nfd()`, as `duplicate_stacking_mark`
already does, and look confusables up composed, as `confusables.rs` does. Checked on the
model: classifying the NFD (`hasAnomaliesNfd`) is proved invariant for every input, and
proved identical to the current code on input without a precomposed letter.

### Finding 4: `confusable` fires on ordinary Latin orthography that the guide says is spared

**Class (b), doc overclaim, with a false positive. Severity: low.**
`docs/user-guide/anomaly-detection.md` L46 lists "accented Latin, which the fold leaves
alone (`caf\u00e9`, `na\u00efve`, `stra\u00dfe`)" as spared. In fact 264 Latin letters (`Ll`, `Lu`, `Lt`)
fire inside an ASCII word. Five of them decompose (`U+00C7`, `U+00E7`, `U+01FE`, `U+1EC9`,
`U+212A`), and 186 have no decomposition (`U+00F8`, `U+0111`, `U+0142`, `U+00FE`,
`U+00D0`, `U+0127`, ...).

```bash
python3 repro/r4_accented_latin.py
# 'Fran\xe7ais' ['confusable'] ['\\xe7 (U+00E7) folds to c'] 'Francais'
# 'gar\xe7on' ['confusable'] ['\\xe7 (U+00E7) folds to c'] 'garcon'
# 'T\xfcrk\xe7e' ['confusable'] ['\\xe7 (U+00E7) folds to c'] 'T\xfcrkce'
# 'a\xe7\xe3o' ['confusable'] ['\\xe7 (U+00E7) folds to c'] 'ac\xe3o'
# 'K\xf8benhavn' ['confusable'] ['\\xf8 (U+00F8) folds to o'] 'Kobenhavn'
# '\u0141\xf3d\u017a' ['confusable'] ['\\u0141 (U+0141) folds to L'] 'L\xf3d\u017a'
# '\u0111\u01b0\u1eddng' ['confusable'] ['\\u0111 (U+0111) folds to d'] 'd\u01b0\u1eddng'
# 'ch\u1ec9' ['confusable'] ['\\u1ec9 (U+1EC9) folds to i'] 'chi'
# 'caf\xe9' [] [] 'caf\xe9'
# 'na\xefve' [] [] 'na\xefve'
# 'stra\xdfe' [] [] 'stra\xdfe'
```

The folds themselves are deliberate: `tests/integration_unmapped_confusables.rs` L310-345
pins `U+00C7`, `U+00E7` and `U+01FE`, and the guide's own positive example is `U+0131`.
The spared-list sentence is what is wrong. French, Portuguese, Turkish, Danish, Polish and
Vietnamese words report as disguises.

**Minimal fix:** correct the sentence to say which Latin letters the fold reaches. To keep
the detector quiet on orthography, skip a source whose NFD begins with its own fold target
(`U+00E7` is `c` plus a cedilla). That also removes the NFC/NFD split for `U+00E7`,
`U+00C7` and `U+1EC9` in Finding 3.

### Finding 5: `Script` from a block table, where UTS #39 reads `Script_Extensions`

**Class (a), code bug. Severity: low (false positives).**

```bash
python3 repro/r5_script_table.py
# [Script.ARABIC] True          <- BOM: detect_scripts('\ufeff'), is_mixed_script('\ufeffhello')
# True                          <- Bengali word + U+0964 DEVANAGARI DANDA
# False                         <- Hindi word + danda
# True                          <- Thaana word + U+060C ARABIC COMMA
# ['mixed_script']              <- inspect_anomalies('\u03b1\u00d7\u03b2'): Greek, multiplication sign
# [] False                      <- detect_scripts('\u3105'): Bopomofo resolves to nothing
```

- **70 code points get a script where UCD 17 says Common or Inherited**
  (`scripts/sweep_scripts.py`). Examples are `U+FEFF`, `U+0964`-`U+0965`, `U+060C`,
  `U+061B`, `U+061F`, `U+0640`, the harakat `U+064B`-`U+0655`, `U+00D7`, `U+00F7`,
  `U+0385`, `U+0387`, `U+30FB`-`U+30FC` and `U+0E3F`. This contradicts `is_mixed_script`'s
  "(Common/Inherited excluded)" and #819's rule that a block table must not contradict the
  standard. A BOM-prefixed English file is "mixed script".
- **`Script`, not `Script_Extensions`.** The docstring says the function "resolves the UTS
  #39 section 5.1 augmented script sets", and section 5.1 resolves through
  `Script_Extensions`. The sweep finds 1,493 pairs over 82 code points that the library
  calls mixed and UTS #39 calls single-script. Bengali, Gujarati and Tamil with a danda,
  Thaana and Syriac with Arabic punctuation, and Myanmar digits are among them. No pair
  goes the other way, so this only over-reports.
- **Bopomofo is never detected.** `SCRIPT_RANGES` has no Bopomofo range. `augmented_set`'s
  `"Bopomofo" => HANB` arm (L52) and the docstring's "Han + Bopomofo: Chinese" row are
  unreachable, and `a\u3105` is not mixed.

**Root cause:** `SCRIPT_RANGES` (`src/scripts.rs` L181-420) is keyed by block, for
example L185, L190, L204, L218 and L397. `AugmentedState::accept` (L82) takes one script
per character.

**Minimal fix:** generate the carve-outs for the 70 code points from `data/Scripts.txt`,
which the repository already ships. Add `U+3100`-`U+312F` and `U+31A0`-`U+31BF` as
Bopomofo. Then let `accept` intersect a character's `Script_Extensions` set. Checked on
the model: `isMixed_eq_spec` shows the walk is section 5.1 over `Script`. `f5_danda` is
the kernel-checked case where `Script` and `Script_Extensions` disagree.

### Finding 6: the decoder does not round-trip next to a carrier of its own scheme, and can report text nobody encoded

**Class (a), code bug. Severity: low.** `invisible` still fires on every case, so
detection is not lost. What is lost is `smuggled`, the "no threshold, no policy" evidence
of #701. In the zero-width case it is replaced by a wrong decode, which is what the `text` field
(`src/smuggled.rs` L73-80) says it must never report: "reporting a garbage decode would undo the reason a
decode is trustworthy".

```bash
python3 repro/r6_smuggled_context.py
# [('variation_bytes', b'hi', 'hi')] ['smuggled', 'invisible']
# [('variation_bytes', b'\x0fhi', None)] ['invisible']              <- after U+2764 U+FE0F
# [('zero_width_binary', b'hi', 'hi')] ['smuggled', 'invisible']
# [('zero_width_binary', b'44', '44')] ['smuggled', 'invisible']    <- after one stray U+200B
# [('zero_width_binary', b'\xb44', None)] ['invisible']             <- after one stray U+200C
```

The emoji case is the ordinary one. A fully qualified emoji (`U+2764 U+FE0F`) already ends
in `VS16`, and emoji smuggling hangs its payload after an emoji.

**What holds:** `roundtrip_tag`, `roundtrip_vs` and `roundtrip_zw` prove every documented
encoder round-trips between two ordinary characters, in any text. `f6_vs`, `f6_zw` and
`f6_zw_nj` are the kernel-checked failures when that guard is dropped.

**Root cause:** `scan_variation` (`src/smuggled.rs` L257-281) folds a presentation
selector already attached to an emoji into the payload as byte `0x0F`. `scan_zero_width`
(L333-377) frames bytes from the first bit, so one stray leading bit shifts every byte.

**Minimal fix:** in `scan_variation`, when the run starts with `U+FE0E` or `U+FE0F` right
after a non-selector and the rest decodes as printable, drop that one selector. In
`scan_zero_width`, when the bit count is not a multiple of 8, the frame is ambiguous.
Decode both the head-aligned and the tail-aligned frame, and set `text` only when exactly
one of them is printable. Otherwise report bytes with `text=None`.

### Finding 7: documentation the code contradicts

**Class (b), doc overclaim. Severity: informational.**

```bash
python3 repro/r7_doc_claims.py
# 'a\u03bb' True ['mixed_script']
# 'a\u05d0' True ['bidi_mixed']
# 'x\u0301' 'x\u0301'
```

- `docs/api/predicates.md` L375 says "the detector never fires on text the canonicalizer
  would leave alone". The measurement behind it was single code points, where it holds
  (0 of 1,112,064). It does not hold for strings: `a\u03bb` is canonical and
  `mixed_script`, and `a\u05d0` is canonical and `bidi_mixed`.
- `AnomalyKind::DuplicateMark` (`src/anomalies.rs` L409-413) says "a duplicate survives
  canonicalization whatever the cap is set to: a base with two acutes does not
  canonicalize to the same string as the same base with one". `canonicalize` now drops a
  repeated mark (`drop_repeated_marks_into`, `src/zalgo.rs` L136): `x\u0301\u0301` and
  `x\u0301` both give `x\u0301`.
- `docs/user-guide/anomaly-detection.md` L18 says "Eight branches fire. Six need no
  lexicon", and L162 says "none of the six branches". There are fifteen kinds.
- `src/anomalies.rs` L929-935 says taking the base's script from `detect_char_script`
  fixed the `\u1c80\u0488` false positive. It did not: `U+1C80` resolves to no script.
  `tests/test_marks_and_bidi_marks.py` L174-189 already pins this as a known limitation,
  so only the comment is wrong.

### Finding 8: the hostname screen reports a zero-width space and misses 28 invisibles that UTS #46 deletes the same way

**Class (c), inconsistency. Severity: medium.** This is the blocklist bypass that
`compat_fold` (#709) and `has_invisible` (#605, #610) were added to close. The raw name is
not in the blocked set, it screens clean, and it resolves to the blocked name.

```bash
python3 repro/r8_hostname_invisible.py
# 'ev\u200bil.com' True True evil.com
# 'ev\xadil.com' False False evil.com
# 'ev\u034fil.com' False False evil.com
# 'ev\u206ail.com' False False evil.com
# 'ev\u180bil.com' False False evil.com
# 'ev\U0001d173il.com' False False evil.com
# 'ev\u115fil.com' False False evil.com
```

`scripts/sweep_hostname.py` lists all 28: `U+00AD`, `U+034F`, `U+115F`-`U+1160`,
`U+17B4`-`U+17B5`, `U+180B`-`U+180D`, `U+180F`, `U+206A`-`U+206F`, `U+1BCA0`-`U+1BCA3`
and `U+1D173`-`U+1D17A`. Each is `Default_Ignorable_Code_Point`, which UTS #46 maps to
nothing. `has_anomalies` fires on `ev<c>il` for 20 of them: `invisible` for the fillers and
the default-ignorable `Cf`, and `mixed_script` for the Khmer and Mongolian ones.

**Root cause:** `is_invisible_in_hostname` (`src/hostname.rs` L23-29) is the #605/#610
list. The strip that runs before the mapping (L345-352) sees only that list, and the
mapping deletes the rest silently, which is the failure L345-349 describes for the listed
set.

**Minimal fix:** make `is_invisible_in_hostname` the whole `Default_Ignorable_Code_Point`
property, minus the bidi controls that `bidi_control` already reports. As a narrower
alternative, add the soft hyphen, `U+034F`, the Mongolian free variation selectors,
`U+17B4`-`U+17B5`, the fillers, `is_default_ignorable_format` and Finding 1's predicate.

## Checked and not a bug

- `has_anomalies` and `inspect_anomalies` agree on every scalar in three contexts and on
  1,000,000 random strings. No detector function panicked on those strings.
- Locality across a line feed is proved. Locality across a space without `CR` is proved.
  Both agree with the library, lexicon included, on 892,424 random `CR`-free pairs
  (`scripts/fuzz.py 11 1000000`).
- `strip_zero_width_chars`, `strip_tags` and `strip_control_chars`: every deletion from a
  word is reported.
- A lone `U+00AD`, `U+034F`, `U+200E`, variation selector or PUA code point deleted from a
  word goes unreported. The guide documents all five as spares.
- The `AugmentedState` walk is UTS #39 section 5.1 over `Script` (`isMixed_eq_spec`, every
  word up to length 6). What Finding 5 changes is the input, not the algorithm.
- UTS #39 section 5.2 restriction levels: no function in the library computes one, so
  there is nothing to check.

## Not confirmed

- Whether `U+FFF9`-`U+FFFB` render invisibly depends on the renderer. The Finding 1 severity
  rests on `U+206A`-`U+206F`, which are `Default_Ignorable`.
- The `percent_escape` scheme and `percent_encode` were not modelled or swept.
- The hostname sweep inserts one character into one label. Whole-script confusables,
  cross-label scripts and contractions were not examined.

## Re-running

```bash
export PATH=/path/to/lean-4.34.0/bin:$PATH
cd formal/lean/Detection
lake build                               # every proof; about 1.5 minutes clean, Bounded.lean ~40 s
lake env lean Detection/Axioms.lean      # the axiom audit
python3 scripts/difftest.py              # needs an importable `disarm`
python3 repro/r1_deprecated_format.py    # ... and the other repro scripts
```
