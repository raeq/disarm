# Testing and Guarantees

## Testing methodology

Most Unicode text libraries rely on *example-based testing*: a developer writes a handful of input/output pairs, runs them in CI, and calls it done. Example-based tests verify the *specific cases the developer thought of*. They say nothing about the rest.

disarm combines three techniques that are uncommon in this space: compile-time data integrity assertions, exhaustive domain coverage, and stated invariant specifications. We are not aware of another transliteration or slugification library that publishes all three, though we haven't audited every library in every language.

---

## What "exhaustively tested" means

Testing rigor is a spectrum between conventional tests and full formal verification (mathematical proofs of correctness). disarm operates at the strongest level achievable without nightly-only tools:

| Level | What it proves | Who does this |
|-------|---------------|---------------|
| **Example-based tests** | Specific inputs produce expected outputs | Everyone |
| **Property-based tests** | Random inputs satisfy stated properties (statistical confidence) | ~5% of open-source projects |
| **Exhaustive domain tests** | *Every* element in a bounded domain satisfies stated properties (certainty) | disarm |
| **Compile-time assertions** | Data integrity invariants that fail the build if violated (zero runtime cost) | disarm |
| **Stated invariant specs** | Properties stated as specifications with verification method documented | disarm |
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
| **disarm** | **Rust + Python** | **2,900+ tests** | **Compile-time assertions, exhaustive domain, stated invariants** |

These libraries are mature and widely used. The test counts above are approximate (based on public repos at time of writing) and may not reflect internal or downstream test suites. The point is not that they are poorly tested — example-based testing is the norm — but that disarm's approach is different in kind.

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
| I2 | ASCII Output | ∀s: f(s, errors='ignore').is_ascii() | Structural argument, checked in Lean (`formal/lean/Transliterate`) + exhaustive BMP per code point (Rust) + Hypothesis 1,000 incl. SMP |
| I3 | Idempotence | ∀s: f(f(s)) = f(s) | Follows from I1 and I2 (Lean) + exhaustive BMP per code point (Rust) + Hypothesis 500 |
| I4 | No Exceptions | ∀s ∈ UTF-8, \|s\| ≤ 10 MiB: f(s) does not throw | Hypothesis 1,000 + explicit edge cases |
| I5 | Deterministic | ∀s, n>0: f(s) called n times → same result | 100× repeat on 10 mixed-script inputs |
| I6 | No Input Size Cap | ∀s: f(s) accepts s whatever its length | Boundary test: 12 MiB accepted (#80 removed the cap) |
| I7 | Output Length Bounded | ∀s: \|f(s)\| ≤ \|s\|\_bytes × 5 + \|s\|\_chars | Exhaustive per code point (worst case U+337F, ratio 5) + Hypothesis 1,000 |

I1–I3 are stated for `tones=False` and no runtime registrations; the scope and the argument behind I2 are in [Exhaustive Testing](../formal-verification.md#stated-invariants-i1i7-the-lossy-normalizer-specification). Each invariant is a test class with a docstring stating the property. The verification method combines exhaustive enumeration (where the domain is bounded) with Hypothesis property-based testing (where it is not).

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
| Absence of panics | Requires Kani bounded model checking (nightly-only) | Property tests with 1,000+ random inputs; no panics in 2,900+ tests; cargo-fuzz over arbitrary bytes and text (below) |

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

`tests/test_security_invariants.py` uses Hypothesis to verify that `canonicalize()` enforces its security contracts on any input:

| Invariant | Guarantee |
|-----------|-----------|
| Bidi stripping | All 13 bidi override/isolate characters removed |
| Zero-width stripping | All 9 zero-width characters removed |
| Confusable neutralization | No cross-script confusables in output |
| NFKC normalization | Output always in NFKC form |
| Whitespace collapse | No consecutive whitespace in output |
| Idempotency | `canonicalize(canonicalize(x)) == canonicalize(x)` |

---

## Fuzzing, coverage and mutation testing

Three measurements of the suites above, all report-only: none is part of the required
*All checks passed* status. How to run each is in `docs/contributing/testing.md` under
*Fuzzing, coverage and mutation testing*.

| Tool | What it adds | CI |
|------|--------------|----|
| cargo-fuzz (`fuzz/`) | Arbitrary bytes through `decode_to_utf8`, and arbitrary text through ten surfaces, each checked against its documented properties | `fuzz.yml`: 60 s per target on pull requests touching the core, 15 min nightly |
| cargo-llvm-cov | Which lines and branches of the core the Rust suite executes | `coverage.yml`: job summary and lcov artifact |
| cargo-mutants | Whether the Rust suite notices when a line of a security-critical module changes | `mutants.yml`: weekly, six modules |

### Baselines

Measured on 2026-09-23 on four cores, at the commit that added the tools. Re-measure
rather than trust these once the code moves.

**Fuzzing.** Every target ran for at least 180 s from the committed seeds in the default
build, which keeps debug assertions and overflow checks on, and seven of them also for
180 s optimized (`nightly-2026-09-01`, cargo-fuzz 0.13.2, AddressSanitizer). No run found
a panic, an overflow, a sanitizer report or a timeout: every failure was a property.
Throughput follows the work per input: `presets` runs every builder at least twice and
managed about 360 inputs a second, `decode_bytes` calls the decoder thirteen times per
input at about 720, and `slugify` about 4,000.

The runs found documented properties that did not hold: six in the first runs, and two
more on 2026-09-24. Each is reproduced through the public API in `tests/fuzz_findings.rs`
(and `tests/test_fuzz_findings.py` where the binding reaches it), and each target asserts
the full property once its finding is resolved:

| Surface | Documented | Reproduction | Resolution |
|---|---|---|---|
| `slugify` | numeric entities are decoded; `allow_unicode` gives one slug for both spellings (#477) | A numeric entity that fails to decode is skipped together with up to 14 bytes of the ASCII after it: `"Q&#A session"` gives `q`, `"Tom &#and Jerry"` gives `tom`, and `"issue &#12 fixed"` (a control character, refused) gives `issue`. The skip stops at the first non-ASCII byte, so `"&#a\u0301"` gives `""` while its NFC gives `\u00e1`. | Fixed: `&#` with no digit after it is text, as in HTML, and an entity that names no allowed character is dropped without the text after it. A hex letter carrying a combining mark is not a digit, so both normal forms decode alike. `"Q&#A session"` gives `q-a-session`. |
| `find_unmapped_confusables`, `find_confusables`, `find_untranslatable` | "its byte offset in the input string"; `find_confusables`: "the character as it appeared in the input" | `find_unmapped_confusables("\u04aa\u0327", Latin)` reports U+0327 at offset 0, where U+04AA is; `find_untranslatable("x\ufe0f")` reports U+FE0F at offset 0, where `x` is; `find_confusables("\u0456\u0308", Latin)` reports U+0457, which the input does not contain. The locators walk composed clusters and report every character of one at the cluster's start. | Fixed: each character is located at the input character it came from, and the one reported is the input's there: a mark that composes with nothing at its own offset, a decomposed homoglyph as its base with the composed character's fold as `target`. |
| `find_untranslatable` | "exactly the set `run` would replace/ignore/preserve" | `transliterate("\U0001f240")` is `[?]ben[?]` and `find_untranslatable` reports nothing: the NFKC brackets around the ideograph have no romanization. | Fixed: a character counts as recovered only when its whole NFKC form transliterates, so U+1F240 is reported, and `errors="strict"` raises on it. |
| `sanitize_filename` | "The result is a fixed point" | With `preserve_extension=False`, `"a" + ".*" * 9` gives `a._`, which sanitizes to `a`. Each pass strips one trailing `._`, and the pass loop stops at eight (`MAX_PASSES`), which `src/filename.rs` admits can cost idempotence. | Fixed: a pass repeats its trailing-separator and dot strips until neither removes anything, so the input settles in one call, and a debug build asserts the pass bound is not reached. |
| `slugify` with `allow_unicode` and `separator=""` | a valid slug is unchanged | `"\u1100 \u1161"` gives the two conjoining jamo, whose slug is U+AC00; `"\U00016d67,\U00016d67"` does the same with Kirat Rai. Joining the words puts two characters that compose side by side after composition has run. | Fixed: with an empty separator the joined slug is composed again, so the first call returns U+AC00. |
| `transliterate`, invariant I7 | output bytes at most five per input byte plus one per input character | With `tones=True`, U+337F gives `zhu sh\u00ec hu\u00ec sh\u00e8`: 18 bytes for 3. I1-I3 are scoped to `tones=False`; I7 is not. | Open |
| `slugify` with `allow_unicode` | none of the circled and squared Latin symbols in the slug (#1028) | Found on 2026-09-24: a slug kept U+24B6 under a separator of NULs, `/`, U+24B6 and `d`. The U+24B6 was the separator's, inserted as given between two words. | Not a library defect: the target checked the whole slug where the property is about the words. It now checks the words, and `SlugConfig::separator` says a separator is inserted as given. |

**Coverage.** Rust, `cargo +nightly-2026-09-01 llvm-cov --no-default-features --branch`
over the Tier-1 Rust suite (1,237 tests; doctests are not instrumented): **92.4% of lines
(14,281 of 15,458), 85.1% of branches, 92.1% of functions** under `src/`. The lowest
modules, generated tables aside, are the Layer-2 wrappers that the Python suite
exercises through the binding and the Rust suite mostly does not:

| Module | Lines | Branches |
|---|---:|---:|
| `src/api/presets.rs` | 56.0% | - |
| `src/api/safety.rs` | 66.7% | - |
| `src/lib.rs` | 71.0% | - |
| `src/normalize.rs` | 77.8% | 66.7% |
| `src/whitespace.rs` | 79.9% | 77.8% |
| `src/api/mod.rs` | 84.1% | 45.0% |
| `src/api/transliterate.rs` | 85.3% | - |
| `src/api/text.rs` | 85.6% | - |

Python, `pytest --cov=disarm` over the Tier-1 Python suite: **96% of the 1,289 statements** of the `disarm` package, lowest `_compat.py` (88%) and `_api.py` (95%). That measures the Python wrappers only; the Rust they call is the table above.

**Mutation.** cargo-mutants 27.1.0 over two of the six modules, against the Rust suite:

| Module | Mutants | Caught | Missed | Timeout | Unviable |
|---|---:|---:|---:|---:|---:|
| `src/invisibles.rs` | 69 | 63 | 5 | 1 | 0 |
| `src/hostname.rs` | 52 | 30 | 20 | 0 | 2 |

121 mutants took 44 minutes with two jobs. The timeout is `subdivision_flag_len`
returning `Some(0)`, which never advances the scan: a hang the timeout catches, as it
should. The misses are the useful part. Nothing in the Rust suite fails when
`is_invisible_in_hostname` always returns `false`, when `strip_invisibles` does nothing,
or when `has_compat_form` always returns `false`: the hostname screen's invisible and
compatibility-form checks (#605, #709, #1019) are asserted only by the Python suite
(`tests/test_hn_compat_and_mapping.py`), which cargo-mutants does not run. The same
holds for `strip_variation_selectors`, which can return `"xyzzy"` unnoticed, for
`is_default_ignorable_format`, and for the IPv6-literal parser. Every other binding calls
this code through the Rust core, so each miss is a Rust test worth writing.

---

## CI matrix

Every push and pull request runs the full test suite across:

| Axis | Values |
|------|--------|
| **OS** | Ubuntu, macOS, Windows |
| **Python** | 3.10, 3.11, 3.12, 3.13, 3.14 |
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
