# Formal Verification & Exhaustive Testing

translit goes beyond conventional unit and property-based testing with three layers of machine-verifiable assurance: **compile-time proofs**, **exhaustive domain coverage**, and **formalized invariant specifications**.

---

## Overview

"Formally tested" for translit means:

1. **Compile-time guarantees** — Data integrity assertions that fail the build if violated
2. **Exhaustive domain testing** — Every element in bounded Unicode domains is tested (not sampled)
3. **Formalized invariants** — Seven properties stated as formal specifications and verified by exhaustive enumeration or property-based testing

This is stronger than property-based testing alone because exhaustive tests leave *zero untested inputs* within their domain.

---

## Compile-Time Guarantees (build.rs)

The build script verifies data integrity before compilation succeeds:

| Assertion | Scope | What it proves |
|-----------|-------|---------------|
| All default BMP table values are ASCII | 5,000+ mappings | No transliteration introduces non-ASCII output |
| All SMP table values are ASCII | All SMP mappings | Same guarantee for characters above U+FFFF |
| All language override values are ASCII | 22 language tables | Language-specific overrides are pure ASCII |
| All Hanzi pinyin values are ASCII | 20,924 entries | Chinese romanization is pure ASCII |
| Confusables table count ≥ 1,000 | TR39 table | Confusables data not truncated |
| Default BMP table count ≥ 5,000 | BMP translations | Default table not truncated |
| Hanzi pinyin count ≥ 20,000 | CJK mappings | Pinyin table not truncated |

Additionally, `src/tables/hangul.rs` contains const assertions:
- `JUNGSEONG_COUNT == 21`, `JONGSEONG_COUNT == 28` (Unicode spec constants)
- Total Hangul syllable count = `19 × 21 × 28 = 11,172`
- Compatibility jamo range = 51 entries

**If any assertion fails, `cargo build` fails.** No runtime overhead.

---

## Exhaustive Domain Coverage

### Hangul Syllables (11,172 characters)

Every precomposed Hangul syllable (U+AC00–U+D7A3) is tested:
- `romanize_hangul()` returns `Some` (no unmapped syllables)
- Output is pure ASCII and non-empty
- Decomposition indices are in bounds: `cho < 19`, `jung < 21`, `jong < 28`
- Round-trip: `cho * 21 * 28 + jung * 28 + jong == syllable_index`

### Compatibility Jamo (51 characters)

Every standalone jamo (U+3131–U+3163):
- `lookup_compat_jamo()` returns `Some`
- Output is pure ASCII

### Full BMP — ASCII Output (63,488 characters)

Every non-surrogate codepoint U+0080–U+FFFF with `ErrorMode::Ignore`:
- Output is pure ASCII (proves invariant I2 exhaustively for the BMP)

### Full BMP — Idempotence (63,488 characters)

Every non-surrogate codepoint U+0080–U+FFFF:
- `transliterate(transliterate(ch)) == transliterate(ch)` (proves I3 exhaustively)

### CJK Unified Ideographs (20,992 characters)

Every character U+4E00–U+9FFF:
- Output is ASCII and non-empty (every ideograph has a pinyin mapping)

### Indic Block Structure (9 core + 4 extended scripts)

For each Brahmic script block, structural properties are verified exhaustively:
- Virama at expected offset classified as `IndicRole::Virama`
- Full consonant range returns `IndicRole::Consonant`
- Full dependent vowel range returns `IndicRole::DependentVowel`

Scripts covered: Devanagari, Bengali, Gurmukhi, Gujarati, Oriya, Tamil, Telugu, Kannada, Malayalam, Sinhala, Tibetan, Myanmar, Khmer, Balinese, Javanese.

---

## Formalized Invariants (I1–I7)

| ID | Invariant | Statement | Verification |
|----|-----------|-----------|-------------|
| I1 | ASCII Passthrough | `∀s: s.is_ascii() → transliterate(s) = s` | Exhaustive (all 128 ASCII) + Hypothesis |
| I2 | ASCII Output | `∀s: transliterate(s, errors='ignore').is_ascii()` | Exhaustive BMP (Rust) + Hypothesis 1000 (Python, incl. SMP) |
| I3 | Idempotence | `∀s: f(f(s)) = f(s)` where `f = transliterate(·, errors='ignore')` | Exhaustive BMP (Rust) + Hypothesis 500 (Python) |
| I4 | No Exceptions | `∀s ∈ UTF-8, |s| ≤ 10MiB: transliterate(s) does not throw` | Hypothesis 1000 + edge cases |
| I5 | Deterministic | `∀s, n>0: transliterate(s) called n times → same result` | 100× repeat on 10 mixed-script inputs |
| I6 | Input Size Bounded | `∀s: |s| > 10MiB → TranslitError` | Boundary test at 10 MiB / 10 MiB + 1 |
| I7 | Output Length Bounded | `∀s: |f(s)| ≤ |s|_bytes × 4 + |s|_chars` | Hypothesis 1000 |

---

## Property-Based Testing Coverage

In addition to formal/exhaustive tests, translit uses:

- **proptest** (Rust): Property tests in `tests/integration_transliterate.rs`
- **Hypothesis** (Python): 79KB of property tests in `tests/test_hypothesis.py` covering transliteration, slugification, normalization, confusables, and more
- **Fuzz testing**: `tests/test_fuzz.py` with random Unicode generation

Total test count: 2,256+ tests across Rust and Python.

---

## What Is NOT Verified

| Area | Why not verified | Mitigation |
|------|-----------------|------------|
| PHF hash correctness | Trusted from `phf_codegen` crate (widely used, well-tested) | Functional tests exercise every lookup path |
| Linguistic accuracy | Transliteration correctness is empirical, not formally provable | Extensive test corpus from native speakers; regression tests |
| Unicode version drift | New Unicode versions may add codepoints | CI tracks Unicode version; new chars fall through to ErrorMode |
| Memory safety (UB) | Requires Miri (nightly only) | `unsafe_code = "forbid"` in Cargo.toml; no unsafe anywhere |

---

## Future: Nightly CI Extensions

When nightly Rust is available in CI:

- **Kani** bounded model checking: Prove absence of panics, overflow, and out-of-bounds for `indic_char_role`, `romanize_hangul`, and decomposition arithmetic
- **Miri** UB detection: Run the full test suite under Miri to detect undefined behavior, use-after-free, and data races
