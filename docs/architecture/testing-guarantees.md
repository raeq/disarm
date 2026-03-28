# Testing and Guarantees

## Testing methodology

Most Unicode text libraries rely on *example-based testing*: a developer writes a handful of input/output pairs, runs them in CI, and calls it done. Example-based tests verify the *specific cases the developer thought of*. They say nothing about the rest.

translit combines three techniques that are uncommon in this space: compile-time data integrity assertions, exhaustive domain coverage, and stated invariant specifications. We are not aware of another transliteration or slugification library that publishes all three, though we haven't audited every library in every language.

---

## What "exhaustively tested" means

Testing rigor is a spectrum between conventional tests and full formal verification (mathematical proofs of correctness). translit operates at the strongest level achievable without nightly-only tools:

| Level | What it proves | Who does this |
|-------|---------------|---------------|
| **Example-based tests** | Specific inputs produce expected outputs | Everyone |
| **Property-based tests** | Random inputs satisfy stated properties (statistical confidence) | ~5% of open-source projects |
| **Exhaustive domain tests** | *Every* element in a bounded domain satisfies stated properties (certainty) | translit |
| **Compile-time assertions** | Data integrity invariants that fail the build if violated (zero runtime cost) | translit |
| **Stated invariant specs** | Properties stated as specifications with verification method documented | translit |
| **Bounded model checking** | Machine-checked proofs of absence of panics, overflow, UB | Future (requires nightly Rust) |

The gap between property-based testing and exhaustive testing is the difference between "we checked 1,000 random Hangul syllables" and "we checked all 11,172 Hangul syllables." The former gives statistical confidence. The latter gives certainty.

---

## How the alternatives compare

| Library | Language | Tests | Exhaustive testing |
|---------|----------|-------|----------------|
| [Unidecode](https://pypi.org/project/Unidecode/) | Python | ~200 example tests | None |
| [text-unidecode](https://pypi.org/project/text-unidecode/) | Python | ~50 example tests | None |
| [anyascii](https://github.com/anyascii/anyascii) | Multi | Basic round-trip + snapshot | None |
| [python-slugify](https://pypi.org/project/python-slugify/) | Python | ~80 example tests | None |
| [awesome-slugify](https://pypi.org/project/awesome-slugify/) | Python | ~30 example tests | None |
| [confusable_homoglyphs](https://pypi.org/project/confusable-homoglyphs/) | Python | ~20 example tests | None |
| [pathvalidate](https://pypi.org/project/pathvalidate/) | Python | Example + parametrize | None |
| [unidecode (Rust)](https://crates.io/crates/unidecode) | Rust | ~10 example tests | None |
| **translit** | **Rust + Python** | **2,900+ tests** | **Compile-time assertions, exhaustive domain, stated invariants** |

These libraries are mature and widely used. The test counts above are approximate (based on public repos at time of writing) and may not reflect internal or downstream test suites. The point is not that they are poorly tested — example-based testing is the norm — but that translit's approach is different in kind.

---

## The three layers of assurance

### Layer 1: Compile-time data integrity assertions (build.rs)

Every time `cargo build` runs, the build script reads all transliteration TSV data files and asserts:

| Assertion | Scope | Consequence if violated |
|-----------|-------|----------------------|
| All default BMP table values are pure ASCII | 5,000+ mappings | **Build fails** |
| All SMP table values are pure ASCII | All supplementary mappings | **Build fails** |
| All 22 language override tables contain only ASCII values | de, ru, ja, fa, ... | **Build fails** |
| All 20,924 Hanzi pinyin values are pure ASCII | Full CJK block | **Build fails** |
| Default BMP table has ≥ 5,000 entries | Truncation detection | **Build fails** |
| Hanzi pinyin table has ≥ 20,000 entries | Truncation detection | **Build fails** |
| Confusables table has ≥ 1,000 entries | Truncation detection | **Build fails** |

Additionally, `hangul.rs` contains const assertions verifying that the Hangul decomposition algorithm constants match the Unicode specification:
- `JUNGSEONG_COUNT == 21`, `JONGSEONG_COUNT == 28`
- Total syllable count = 19 × 21 × 28 = 11,172
- Compatibility jamo range = 51 entries exactly

These assertions execute at compile time, not in CI. A release artifact cannot exist if any assertion fails.

### Layer 2: Exhaustive domain tests

These tests iterate over every element in a bounded Unicode domain. Unlike property-based tests (which sample randomly), exhaustive tests leave zero untested inputs within their domain.

| Domain | Size | What is verified |
|--------|------|-----------------|
| All Hangul syllables (U+AC00–U+D7A3) | 11,172 | `romanize_hangul()` returns Some, output is ASCII, non-empty, decomposition indices in bounds, round-trip formula correct |
| All compatibility jamo (U+3131–U+3163) | 51 | `lookup_compat_jamo()` returns Some, output is ASCII |
| Full BMP, ErrorMode::Ignore (U+0080–U+FFFF) | 63,488 | `transliterate_impl()` produces ASCII-only output for every codepoint |
| Full BMP idempotence | 63,488 | `f(f(ch)) == f(ch)` for every codepoint |
| All CJK Unified Ideographs (U+4E00–U+9FFF) | 20,992 | Output is ASCII, unmapped count < 200 |
| 15 Indic script blocks | ~2,000 codepoints | Every consonant/vowel/virama in the block is correctly classified |
| Determinism | 10 × 100 runs | Same mixed-script input produces identical output 100 times |

**Total exhaustive coverage: ~159,000+ individually verified codepoints.**

### Layer 3: Stated invariant specifications

Seven properties are stated as specifications, each with a documented verification method:

| ID | Invariant | Statement | Verification |
|----|-----------|-----------------|--------------|
| I1 | ASCII Passthrough | ∀s: s.is_ascii() → f(s) = s | Exhaustive (all 128 ASCII) + Hypothesis 500 |
| I2 | ASCII Output | ∀s: f(s, errors='ignore').is_ascii() | Exhaustive BMP (Rust) + Hypothesis 1,000 incl. SMP |
| I3 | Idempotence | ∀s: f(f(s)) = f(s) | Exhaustive BMP (Rust) + Hypothesis 500 |
| I4 | No Exceptions | ∀s ∈ UTF-8, \|s\| ≤ 10 MiB: f(s) does not throw | Hypothesis 1,000 + explicit edge cases |
| I5 | Deterministic | ∀s, n>0: f(s) called n times → same result | 100× repeat on 10 mixed-script inputs |
| I6 | Input Size Bounded | ∀s: \|s\| > 10 MiB → TranslitError | Boundary test at limit |
| I7 | Output Length Bounded | ∀s: \|f(s)\| ≤ \|s\|\_bytes × 4 + \|s\|\_chars | Hypothesis 1,000 |

Each invariant is a test class with a docstring stating the property. The verification method combines exhaustive enumeration (where the domain is bounded) with Hypothesis property-based testing (where it is not).

See [formal-verification.md](../formal-verification.md) for the full specification document.

---

## What exhaustive testing does NOT cover

Exhaustive testing is not formal verification. We are precise about the boundary:

| Area | Why not verified | Mitigation |
|------|--------------------------|------------|
| PHF hash correctness | Trusted from `phf_codegen` crate | Functional tests exercise every lookup path |
| Linguistic accuracy | Transliteration correctness is empirical, not provable by testing alone | Extensive corpus from native speakers; 83 language reference tests |
| Unicode version drift | New Unicode versions add codepoints | CI tracks Unicode version; unknown chars handled by ErrorMode |
| Memory safety / UB | Requires Miri (nightly-only) | `unsafe_code = "forbid"` in Cargo.toml — zero unsafe anywhere |
| Absence of panics | Requires Kani bounded model checking (nightly-only) | Property tests with 1,000+ random inputs; no panics in 2,900+ tests |

**Future**: When nightly Rust is available in CI, we plan to add Kani bounded model checking — a form of formal verification that would prove absence of panics and overflow in `romanize_hangul`, `indic_char_role`, and decomposition arithmetic — and Miri UB detection.

---

## Conventional testing (still comprehensive)

The exhaustive testing layers sit on top of a conventional test suite that is itself unusually thorough:

### Test suite overview

| Category | Tests | Coverage |
|----------|-------|----------|
| Python (pytest) | 2,268 | All public API functions |
| Rust (#[test]) | 635 | Core algorithms, tables, edge cases |
| Exhaustive domain (Rust) | 16 | Full BMP, Hangul, CJK, Indic |
| Stated invariants (Python) | 12 | I1–I7 specifications |
| Property-based (Hypothesis) | 500+ examples/property | Full Unicode input space |
| Property-based (proptest) | Rust-side invariants | Normalization, roundtrips |
| **Total** | **2,900+** | |

### Per-language reference tests

Each of the 83 built-in language profiles has dedicated tests verifying:

- **Known transliteration pairs** — reference texts with expected output (e.g., "Москва" → "Moskva" for Russian, "Київ" → "Kyiv" for Ukrainian)
- **Language override behavior** — `lang="xx"` produces different output from the default table where expected
- **ISO 9 and GOST interaction** — scholarly modes override language-specific mappings correctly

### Security invariant tests

`tests/test_security_invariants.py` uses Hypothesis to verify that `security_clean()` enforces its security contracts on any input:

| Invariant | Guarantee |
|-----------|-----------|
| Bidi stripping | All 13 bidi override/isolate characters removed |
| Zero-width stripping | All 9 zero-width characters removed |
| Confusable neutralization | No cross-script confusables in output |
| NFKC normalization | Output always in NFKC form |
| Whitespace collapse | No consecutive whitespace in output |
| Idempotency | `security_clean(security_clean(x)) == security_clean(x)` |

---

## CI matrix

Every push and pull request runs the full test suite across:

| Axis | Values |
|------|--------|
| **OS** | Ubuntu, macOS, Windows |
| **Python** | 3.9, 3.10, 3.11, 3.12, 3.13, 3.14 |
| **Rust checks** | `cargo fmt --check`, `cargo clippy -D warnings`, `cargo test` |
| **Python checks** | pytest, ruff lint, mypy strict mode, doctest |

---

## Unicode table update process

When Unicode versions are updated:

1. **Dependency update** — bump `unicode-segmentation`, `unicode-normalization`, and confusable table crates
2. **Rebuild tables** — `build.rs` regenerates PHF lookup tables from TSV source data at compile time. **Compile-time assertions verify the new data is well-formed.**
3. **Exhaustive tests** — the full BMP and CJK domain tests verify invariants hold across any new characters
4. **Property tests** — Hypothesis tests verify invariants still hold across the new character space
5. **Reference text tests** — existing per-language tests confirm no behavioral changes for known inputs
