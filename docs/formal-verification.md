# Exhaustive Testing & Compile-Time Assurance

disarm's assurance is described using the methodology of the technical note
*Provably Lossless Reversible Transliteration: A Formal Specification and an
Exhaustive-Verification Methodology* ([DOI 10.5281/zenodo.20613272](https://doi.org/10.5281/zenodo.20613272)).
Its central idea is to **separate what is proven from what is only tested**, and
to tag every guarantee with the *strength* of assurance behind it.

!!! warning "Scope: the shipping transforms are lossy, not reversible"
    The paper specifies a *reversible mode* (its requirements R1–R7). disarm
    does **not** ship that mode — its transforms are **lossy by design**: ASCII
    output (I2) and idempotence (I3) are canonicalization properties that
    *preclude* reversibility. This page adopts the paper's verified-vs-tested
    language to describe the **existing** testing; it makes **no** claim that
    `transliterate` (or any shipping transform) is reversible.

---

## Three strengths of assurance

Every guarantee below is tagged with one of these:

- **(a) Proof by exhaustion.** Enumerate *every* element of a finite domain and
  check a decidable predicate. This is a constructive proof over that domain, not
  a sample — it leaves zero untested inputs (e.g. all 11,172 Hangul syllables,
  the full BMP, all CJK ideographs).
- **(b) Structural proof.** An argument over the *structure* of the computation
  that reaches properties quantifying over unbounded strings (e.g. "an engine that
  only ever appends ASCII pieces produces ASCII for every string"). Exhaustion
  cannot reach these because the input set is infinite.
- **(c) Property-based testing.** Randomized/fuzz testing (Hypothesis, proptest)
  of unbounded-input properties not reduced to (a) or (b). It is sound but
  **incomplete** evidence — label it **"tested, not proven."**

The shipping library rests on **(a)** and **(c)**, with **(b)** for I1–I3. This page
used to justify I2 by lifting the per-character exhaustion to strings, and that lift
does not hold: it needs `transliterate` to be a character-wise map, `f(a+b) = f(a) +
f(b)`, and it is not one. CJK word spacing, the Indic inherent vowel, canonical
composition and `lang="auto"` all look past one character, and a Lean audit
(`formal/lean/Transliterate`) counted 1,755,178 pairs where the equation fails. The
argument that does hold is about what the engine *appends*, and is given under I2
below.
The paper's structural proofs of *reversibility / unique decodability* describe
its reversible mode and are **out of scope** here.

---

## Compile-Time Guarantees (build.rs) — (a) exhaustion at build time

The build script enumerates the generated tables and fails the build if a
decidable predicate does not hold for every entry:

| Assertion | Scope | What it proves |
|-----------|-------|---------------|
| All default BMP table values are ASCII | 5,000+ mappings | No transliteration introduces non-ASCII output |
| All SMP table values are ASCII | All SMP mappings | Same guarantee for characters above U+FFFF |
| All language override values are ASCII | 22 language tables | Language-specific overrides are pure ASCII |
| All Hanzi pinyin values are ASCII | 20,924 entries | Chinese romanization is pure ASCII |
| *(not asserted)* toned pinyin values | the `tones=True` table | Toned pinyin carries diacritics by design (`běi`), which is why I2 excludes `tones=True` |
| Confusables table count ≥ 1,000 | TR39 table | Confusables data not truncated |
| Default BMP table count ≥ 5,000 | BMP translations | Default table not truncated |
| Hanzi pinyin count ≥ 20,000 | CJK mappings | Pinyin table not truncated |

`src/tables/hangul.rs` adds const assertions: `JUNGSEONG_COUNT == 21`,
`JONGSEONG_COUNT == 28`, total Hangul = `19 × 21 × 28 = 11,172`, compatibility
jamo = 51. **If any assertion fails, `cargo build` fails.** No runtime overhead.

---

## Exhaustive Domain Coverage — (a) proof by exhaustion

Each property below is checked for **every** element of a finite domain, so it is
proven over that domain.

### Hangul Syllables (11,172 characters)

Every precomposed syllable (U+AC00–U+D7A3): `romanize_hangul()` returns `Some`,
output is pure ASCII and non-empty, decomposition indices are in bounds
(`cho < 19`, `jung < 21`, `jong < 28`), and the index identity
`cho·21·28 + jung·28 + jong == syllable_index` holds. (This identity is the
Hangul *decomposition arithmetic* — it is **not** a transliteration-reversibility
claim.)

### Compatibility Jamo (51 characters)

Every standalone jamo (U+3131–U+3163): `lookup_compat_jamo()` returns `Some` and
output is pure ASCII.

### Full BMP — ASCII Output (63,488 characters)

Every non-surrogate codepoint U+0080–U+FFFF with `ErrorMode::Ignore` yields pure
ASCII — proves **I2** for each BMP code point on its own, under the default options.
It says nothing about strings by itself: see I2 below for what does.

### Full BMP — Idempotence (63,488 characters)

Every non-surrogate codepoint U+0080–U+FFFF: `transliterate(transliterate(ch)) ==
transliterate(ch)` — proves **I3** for each BMP code point on its own, under the
default options.

### CJK Unified Ideographs (20,992 characters)

Every character U+4E00–U+9FFF maps to non-empty ASCII (every ideograph has a
pinyin mapping).

### Indic Block Structure (15 scripts)

For each Brahmic block, structural roles are checked exhaustively over the block:
virama at the expected offset is `IndicRole::Virama`, the full consonant range is
`Consonant`, the full dependent-vowel range is `DependentVowel`. Scripts:
Devanagari, Bengali, Gurmukhi, Gujarati, Oriya, Tamil, Telugu, Kannada,
Malayalam, Sinhala, Tibetan, Myanmar, Khmer, Balinese, Javanese.

---

## Stated Invariants (I1–I7) — the lossy-normalizer specification

I1–I7 are the invariants of disarm's **lossy normalizer**. Two of them — **I2
(ASCII output)** and **I3 (idempotence)** — are *canonicalization* properties:
they say the transform collapses input toward a canonical ASCII form, which is
precisely why the transform is **not** reversible. None of I1–I7 asserts
reversibility.

Each invariant is tagged with the strongest assurance that discharges it:

| ID | Invariant | Statement | Assurance |
|----|-----------|-----------|-----------|
| I1 | ASCII Passthrough | `∀s: s.is_ascii() → transliterate(s) = s` | **(a)** exhaustion over the 128 ASCII chars + **(c)** property-tested at string level |
| I2 | ASCII Output | `∀s: transliterate(s, errors='ignore').is_ascii()` | **(b)** every piece the engine appends is ASCII, and its one deletion keeps ASCII ASCII (below); checked in Lean (`translit_I2`) and on 27 million inputs; **(a)** exhaustion per BMP code point |
| I3 | Idempotence | `∀s: f(f(s)) = f(s)`, `f = transliterate(·, errors='ignore')` | **(b)** follows from I1 and I2 (`I3_of_I1_I2` in Lean): the output is ASCII, and ASCII is its own image; **(a)** exhaustion per BMP code point + **(c)** property-tested |
| I4 | No Exceptions | `∀s ∈ UTF-8, |s| ≤ 10 MiB: transliterate(s) does not throw` | **(c)** property-tested (Hypothesis + edge cases) |
| I5 | Deterministic | `∀s, n>0: n calls of transliterate(s) → identical result` | **(c)** property-tested (100× over mixed-script inputs) |
| I6 | No Input Size Cap | `∀s: transliterate(s)` accepts `s` whatever its length | **(c)** boundary test: a 12 MiB input is accepted. #80 removed the 10 MiB cap; the one 10 MiB limit left bounds the *output* of registered replacements |
| I7 | Output Length Bounded | `∀s: |f(s)| ≤ |s|_bytes × 5 + |s|_chars` | **(a)** exhaustion per code point over every Unicode scalar: the worst ratio is exactly 5, at U+337F SQUARE CORPORATION (`zhu shi hui she`) + **(c)** property-tested for strings |

**Why I2 holds for every string.** `transliterate` builds its output by appending
pieces, and each piece is ASCII: table values (the `build.rs` assertions above), runs
of ASCII input, the `' '` it inserts between CJK words, and the NFKC-recovery path,
which appends pieces of the same kinds. With `errors='ignore'` an unmapped character
appends nothing. Its only deletion is one `pop` (the Indic inherent vowel), and
removing a character from ASCII leaves ASCII. Which pieces are appended may depend on
the whole input, so the argument survives every context rule the engine has. It is
modelled and checked in `formal/lean/Transliterate` (`translit_I2`), with each kind
of piece discharged against the code.

**Scope.** I1–I3 are stated for `tones=False` and no runtime registrations, and hold
for every `lang`, scheme and `context` setting within that. Outside it:

- `tones=True` emits pinyin with diacritics by design (`北` → `běi`), so it is outside
  I2, and outside I3 too, since a second pass strips the tone.
- Values given to `register_lang` and `register_replacements` are the caller's and
  are not checked: a non-ASCII value breaks I2 and I3, and `register_replacements`
  also breaks I1, because it runs before the ASCII fast path.
- I3 is stated for `errors='ignore'`. Under `errors='preserve'` with `lang='auto'` it
  can fail, because a preserved character changes what the second pass detects.
- `context=True` kept none of I1–I3 for text outside Arabic and Hebrew words until
  #1008, which found it this way.

**Proven vs tested at a glance.** I1–I3 are *proven* for every string within that
scope, by the argument above; the BMP exhaustion checks their per-character
premises. I7 is exhaustive per code point and *tested, not proven* for strings. I4
and I5 are *tested, not proven*; I6 is a boundary test.

---

## Reversibility is out of scope

disarm deliberately ships a **lossy** transform. The paper's reversible mode
(R1–R7) — and the *structural* proofs of round-trip identity and unique
decodability it carries — apply to a **specified reversible encoding**, which
disarm does not implement. The exhaustive and structural results above are
about canonicalization (I1–I7); none of them imply that `transliterate` can be
inverted. Do not read "exhaustively verified" as "reversible."

---

## Machine-checked models (`formal/`)

Eleven models, each written against the code and **validated against the built library
by differential testing before any proof or counterexample was trusted**. Every
property that failed was cut down to a minimal input and reproduced on the library,
and each of those became a fix with a regression test in the ordinary suites, which
is what keeps it fixed. `.github/workflows/formal.yml` re-checks the models whenever
they change.

| Model | Tool | What it establishes | Found |
|---|---|---|---|
| `formal/lean/Transliterate` | Lean 4 | I1–I3 for every string from the emitter argument; that the per-character lift needs a premise the code does not meet | #1008 (`context=True` passed non-word spans through raw), #1013 (canonical equivalents that disagreed), and the corrections on this page |
| `formal/lean/Deletions` | Lean 4 | `resolve_deletions` never panics, never invents text and is idempotent; bounded-exhaustive checks up to length 7 | #1010 (line breaks the detector knew and the resolver did not; a zero-width character taking a cell) |
| `formal/lean/Emoji` | Lean 4 | properties of `replace_emoji`, `demojize` and the pipeline step, in general by induction and exhaustively up to a length bound | #1011 (fully qualified ZWJ sequences named piece by piece, a dropped emoji gluing two words together, removals that left a new keycap behind), and #1015, a defect in #1011 that the model caught when run against it |
| `formal/tla/Concurrency` | TLA+ / TLC | lock and GIL interleavings of the Python binding, and the registration paths of the Rust API | #1009 (two deadlocks through `__del__`), #1012 (a stale cached transliterator), #1014 (a registration landing after the seal and past the cap) |
| `formal/lean/Confusables` | Lean 4 | the confusable fold, compose-at-lookup and `skeleton_key`, in general by induction and exhaustively up to a length bound | #1024 (`skeleton_key` not a fixed point; Kirat Rai left uncomposed; documentation claims) |
| `formal/lean/Detection` | Lean 4 | `has_anomalies`, `decode_smuggled` and `is_mixed_script`; sweeps of every scalar through each detector and the cleaner beside it | #1025 (detectors silent on text their cleaners change; split verdicts on canonically equivalent spellings), #1023 (script-table gaps; a smuggled-payload decoder miss), #1019 (Default_Ignorable characters the hostname screen let through) |
| `formal/lean/Presets` | Lean 4 | every preset step list, the fast-path guard and the pipeline profiles: which are fixed points, and which step breaks the ones that are not | #1024 (`skeleton_key` not a fixed point); #1029 (`search_key`/`sort_key` under a digit policy and three profiles not fixed points; a removed character separating two that compose; the `PRESETS` mirror; the output ceiling; documentation claims) |
| `formal/lean/Sanitizers` | Lean 4 | `sanitize_filename` never returns an empty, dot or illegal name and respects `max_length`; `UniqueSlugifier` slugs are distinct; the escapers round-trip | #1026 (a sanitized filename that is a Windows device name; an unvalidated separator; a BOM overriding an explicit encoding), #1019 (the hostname screen), #1028 (slug truncation, stopword, symbol and suffix defects) |
| `formal/lean/Text` | Lean 4 | case folding, the whitespace, control and invisible strips, zalgo, display width, punctuation, contractions and edit distance | #1034 (a class-0 mark resetting the zalgo count; `strip_zalgo` output that was still zalgo; a Prepend character zeroing `terminal_width`; a stray VS16 widening a letter; `fold_punctuation` gaps; documentation claims) |
| `formal/bindings`, `formal/tla/CABI` | differential harness, TLA+ / TLC | every scalar and a 40,000-string corpus through the core and all five bindings, byte for byte; the C ABI's ownership and input protocol | #1020 (invalid UTF-8 undefined behaviour at the C boundary); #PR (Java lone surrogates, Ruby string encodings, the `strip_zalgo` default, unknown `lang` codes, `strip_accents` on singleton decompositions, `demojize` of an unnamed emoji, `register_replacements` in the Rust API, error kinds and classes, Node size checks, the `arabic` and `hebrew` targets in Java) |
| `formal/tla/WatchPR` | TLA+ / TLC | the merge protocol of the repository's own `scripts/watch_pr.py`, against a pull request that GitHub changes between reads | a failed review-thread read taken for "no threads", a merge of a head never evaluated, a refused merge retried blind, and `--await-review` merging over a change request |

The Lean results use the kernel alone where they are proved by induction. The
bounded-exhaustive ones use `native_decide`, which also trusts Lean's compiler; each
model's README lists which is which. TLC explores every interleaving of a small
configuration (two or three threads), so its passes are proofs about that
configuration, not about every thread count. The configurations that model the code
*as it was* are kept, and CI requires them to keep failing: a model change that made
one pass would have lost its bug.

---

## Property-Based Testing — (c) tested, not proven

- **proptest** (Rust): property tests in `tests/integration_transliterate.rs`.
- **Hypothesis** (Python): property tests in `tests/test_hypothesis.py` across
  transliteration, slugification, normalization, and confusables.
- **Fuzz testing**: random Unicode generation across the input space.

These run across the three test tiers (deterministic CI, Hypothesis, and the
formal/exhaustive pre-release tier) — thousands of tests across Rust and Python.
They are sound but incomplete: evidence, not proof.

---

## What Is NOT Verified

| Area | Why not verified | Mitigation |
|------|-----------------|------------|
| PHF hash correctness | Trusted from `phf_codegen` (widely used) | Functional tests exercise every lookup path |
| Linguistic accuracy | Correctness is empirical, not provable by testing | Native-speaker corpus; regression tests; see [#173] quality benchmark |
| Unicode version drift | New Unicode versions add codepoints | CI tracks the Unicode version; new chars fall through to `ErrorMode` |
| Memory safety (UB) | Requires Miri (nightly only) | `unsafe_code = "forbid"`; no unsafe anywhere |

[#173]: https://github.com/raeq/disarm/issues/173

---

## Future: Nightly CI Extensions

- **Kani** bounded model checking — would add machine-checked *structural* proofs
  (absence of panics, overflow, out-of-bounds) for `indic_char_role`,
  `romanize_hangul`, and the decomposition arithmetic.
- **Miri** UB detection — run the suite under Miri to detect undefined behavior.

---

## Reference

- *Provably Lossless Reversible Transliteration: A Formal Specification and an
  Exhaustive-Verification Methodology.* [DOI 10.5281/zenodo.20613272](https://doi.org/10.5281/zenodo.20613272).
  This page adopts its verified-vs-tested methodology to describe disarm's
  existing, **lossy** testing — not its reversible-mode requirements.
