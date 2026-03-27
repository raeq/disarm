# Testing and Guarantees

How translit's test suite ensures correctness across 64 language profiles, full Unicode coverage, and security-critical operations.

---

## Test Suite Overview

| Category | Files | Tests | Coverage |
|----------|-------|-------|----------|
| Python (pytest) | 33 | 1,295+ | All public API functions |
| Rust (#[test]) | 19 modules | 383+ | Core algorithms, tables, edge cases |
| Property-based (Hypothesis) | 5 | Full Unicode input space | Invariants, idempotency, safety |
| CI matrix | — | — | 3 OS x 6 Python versions |

---

## Per-Language Reference Tests

Each of the 64 built-in language profiles has dedicated tests verifying:

- **Known transliteration pairs** — reference texts with expected output (e.g., "Москва" → "Moskva" for Russian, "Київ" → "Kyiv" for Ukrainian)
- **Language override behavior** — `lang="xx"` produces different output from the default table where expected
- **ISO 9 and GOST interaction** — scholarly modes override language-specific mappings correctly

Key test files:
- `tests/test_transliterate.py` — 18 languages with reference texts
- `tests/test_lang_overrides.py` — language override mechanics
- `tests/test_strict_iso9.py` — ISO 9:1995 scholarly standard
- `tests/test_cjk_transliteration.py` — Chinese pinyin, Korean romanization, Japanese Hepburn
- `tests/test_lang_expansion.py` — language table expansion and registration

---

## Property-Based Testing

translit uses [Hypothesis](https://hypothesis.readthedocs.io/) extensively to verify invariants across the full Unicode input space (BMP, SMP, combining marks, emoji sequences):

### Tested properties

| Property | What it guarantees |
|----------|-------------------|
| **ASCII output** | `transliterate(text).isascii()` — output is always valid ASCII |
| **Idempotency** | `normalize(normalize(x)) == normalize(x)` — normalizing twice is the same as once |
| **No panics** | No Rust panic on any valid UTF-8 input, including adversarial strings |
| **Batch consistency** | `transliterate_batch(xs) == [transliterate(x) for x in xs]` — batch API is semantically identical to looping |
| **Length bounds** | Output length is bounded relative to input for all transforms |

### Test files

- `tests/test_hypothesis.py` — core transform properties (2,060 lines, 500+ examples per property)
- `tests/test_batch_consistency.py` — batch API equivalence for all batch functions
- `tests/test_fuzz.py` — edge case fuzzing with adversarial inputs

### Rust property tests

The Rust side uses [proptest](https://proptest-rs.github.io/proptest/) for normalization invariants:

```rust
// Example from normalize.rs
proptest! {
    #[test]
    fn nfc_idempotent(s in "\\PC{0,200}") {
        let once = nfc(&s);
        let twice = nfc(&once);
        prop_assert_eq!(once, twice);
    }
}
```

---

## Security Invariant Guarantees

`tests/test_security_invariants.py` uses Hypothesis to verify that `security_clean()` enforces its security contracts on **any** input:

| Invariant | Guarantee |
|-----------|-----------|
| **Bidi stripping** | All 13 bidi override/isolate characters are removed |
| **Zero-width stripping** | All 9 zero-width characters (ZWSP, ZWJ, ZWNJ, etc.) are removed |
| **Confusable neutralization** | Output contains no cross-script confusable characters |
| **NFKC normalization** | Output is always in NFKC form |
| **Whitespace collapse** | No consecutive whitespace in output |
| **Idempotency** | `security_clean(security_clean(x)) == security_clean(x)` |
| **Combined vectors** | Mixed attack inputs (bidi + zalgo + confusables) are all neutralized |

---

## CI Matrix

Every push and pull request runs the full test suite across:

| Axis | Values |
|------|--------|
| **Operating system** | Ubuntu, macOS, Windows |
| **Python version** | 3.9, 3.10, 3.11, 3.12, 3.13, 3.14 |
| **Rust checks** | `cargo fmt --check`, `cargo clippy -D warnings`, `cargo test` |
| **Python checks** | pytest, ruff lint, mypy strict mode, doctest |

This ensures:
- **Platform compatibility** — no OS-specific Unicode handling bugs
- **Python version compatibility** — works across 6 Python versions
- **Type safety** — mypy strict mode validates all type stubs

---

## Unicode Table Update Process

When Unicode versions are updated (new characters, new emoji, updated segmentation rules):

1. **Dependency update** — bump `unicode-segmentation`, `unicode-normalization`, and confusable table crates
2. **Rebuild tables** — `build.rs` regenerates PHF lookup tables from TSV source data at compile time
3. **CI verification** — the full test suite catches any regressions from table changes
4. **Property tests** — Hypothesis tests verify invariants still hold across the new character space
5. **Reference text tests** — existing per-language tests confirm no behavioral changes for known inputs

---

## Benchmarks

Performance is tracked with [Criterion](https://bheisler.github.io/criterion.rs/) (Rust) benchmarks:

- **Core transforms** — transliterate, slugify, normalize across ASCII, Latin, Cyrillic, CJK, and mixed-script inputs
- **Regression detection** — CI runs benchmark smoke tests to catch performance degradation
- **No Python overhead** — benchmarks measure pure Rust performance, excluding PyO3 boundary crossing
