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
  that reaches properties quantifying over unbounded strings (e.g. "the output of
  a character-wise map that emits ASCII for every character is ASCII for every
  string"). Exhaustion cannot reach these because the input set is infinite.
- **(c) Property-based testing.** Randomized/fuzz testing (Hypothesis, proptest)
  of unbounded-input properties not reduced to (a) or (b). It is sound but
  **incomplete** evidence — label it **"tested, not proven."**

The shipping library rests on **(a)** and **(c)**, with **(b)** used only where a
finite per-character result lifts structurally to all strings (I2's ASCII output).
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
ASCII — proves **I2** over the BMP by exhaustion.

### Full BMP — Idempotence (63,488 characters)

Every non-surrogate codepoint U+0080–U+FFFF: `transliterate(transliterate(ch)) ==
transliterate(ch)` — proves **I3** over the BMP by exhaustion.

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
| I2 | ASCII Output | `∀s: transliterate(s, errors='ignore').is_ascii()` | **(a)** exhaustion over the BMP + **(b)** structural (concatenation of ASCII is ASCII); **(c)** tested for SMP |
| I3 | Idempotence | `∀s: f(f(s)) = f(s)`, `f = transliterate(·, errors='ignore')` | **(a)** exhaustion over the BMP + **(c)** property-tested (Python) |
| I4 | No Exceptions | `∀s ∈ UTF-8, |s| ≤ 10 MiB: transliterate(s) does not throw` | **(c)** property-tested (Hypothesis + edge cases) |
| I5 | Deterministic | `∀s, n>0: n calls of transliterate(s) → identical result` | **(c)** property-tested (100× over mixed-script inputs) |
| I6 | Input Size Bounded | `∀s: |s| > 10 MiB → DisarmError` | **(b)** structural guard (explicit length check), confirmed by a boundary test |
| I7 | Output Length Bounded | `∀s: |f(s)| ≤ |s|_bytes × 4 + |s|_chars` | **(c)** property-tested (Hypothesis) |

**Proven vs tested at a glance.** I1–I3 are *proven* over their finite domains
(exhaustion, with a structural lift for I2); I2 above the BMP and I4, I5, I7 are
*tested, not proven* (unbounded inputs); I6 is a structural guard confirmed by a
boundary test.

---

## Reversibility is out of scope

disarm deliberately ships a **lossy** transform. The paper's reversible mode
(R1–R7) — and the *structural* proofs of round-trip identity and unique
decodability it carries — apply to a **specified reversible encoding**, which
disarm does not implement. The exhaustive and structural results above are
about canonicalization (I1–I7); none of them imply that `transliterate` can be
inverted. Do not read "exhaustively verified" as "reversible."

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
