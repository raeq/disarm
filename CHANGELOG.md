# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-03-27

### Added
- **Formal testing framework** — three layers of machine-verifiable assurance:
  - **Compile-time proofs** (`build.rs`): all transliteration table values asserted
    ASCII-only, entry count sanity checks (Hanzi ≥20k, BMP ≥5k, confusables ≥1k).
    Build fails if any assertion is violated.
  - **Exhaustive domain tests** (Rust): 16 tests covering all 11,172 Hangul syllables,
    full BMP (63,488 codepoints) for ASCII output and idempotence, all 20,992 CJK
    ideographs, all 51 compatibility jamo, and structural verification of 15 Indic
    script blocks. Zero sampling gaps.
  - **Formalized invariant specifications** (Python): 7 formally-stated invariants
    (I1–I7) verified via exhaustive enumeration and Hypothesis — ASCII passthrough,
    ASCII output, idempotence, no exceptions, determinism, input size bound, output
    length bound.
- **Two-tier test architecture**: formal tests gated behind `#[ignore]` (Rust) and
  `@pytest.mark.formal` (Python) so they don't slow everyday development. Run before
  release with `cargo test -- --ignored` and `pytest -m formal`.
- **CLAUDE.md**: project-level development guide for automated agents — documents
  build commands, test tiers, and code conventions.
- `list_scripts()` function for programmatic script discovery.
- `docs/formal-verification.md`: specification document for formal testing methodology.
- Comprehensive overhaul of `docs/architecture/testing-guarantees.md` with formal
  testing differentiator analysis and alternative library comparison.

### Changed
- `IndicRole` enum and `indic_char_role()` / script-specific char_role functions
  changed from private to `pub` for integration test access (parent modules remain
  `#[doc(hidden)]`).
- `tables::hangul` module changed from `mod` to `pub mod` for integration test access.
- Hangul const assertions added: `JUNGSEONG_COUNT`, `JONGSEONG_COUNT`, total syllable
  count, and compatibility jamo range verified at compile time.
- Total test count: 2,900+ (up from 1,678 in 0.1.5).

## [0.1.5] — 2026-03-27

### Added
- **Reverse transliteration**: `transliterate(text, target="ru")` converts Latin → native
  script for Russian, Ukrainian, and Greek. PHF tables generated at build time from
  inverted language TSV data.
- **Toned pinyin**: `transliterate("北京", tones=True)` returns `"běi jīng"` with tone
  marks. Toned readings sourced from Unihan `kMandarin` field for all 20,924 CJK
  Unified Ideographs.
- **ISO 9:1995 scholarly Cyrillic**: `transliterate(text, strict_iso9=True)` for
  scholarly romanization. GOST R 7.0.34 variant via `gost7034=True`.
- **Japanese Kunrei-shiki** (`lang="ja-kunrei"`): alternative romanization profile,
  bringing total language count to 65.
- **Ancient scripts**: Coptic, Gothic, Old Italic, Runic, Ogham transliteration tables.
- **CLI short aliases**: `t` (transliterate), `s` (slugify), `n` (normalize),
  `p` (pipeline), `d` (demojize) — e.g. `translit t "café"`.
- **CLI `--target` flag**: `translit t --target ru "Moskva"` for reverse transliteration.
- **CLI `--tones`, `--strict-iso9`, `--gost7034` flags** for transliterate subcommand.
- **CLI `--lang` flag** for slugify subcommand.
- `console_scripts` entry point: `translit` command available after `pip install translit-rs`.
- `docs/cli.md`: comprehensive CLI documentation with piping, exit codes, examples.
- Links section in README.md and docs/index.md for RTD ↔ GitHub cross-references.

### Changed
- `transliterate()` API unified: `reverse_transliterate()` merged into `transliterate()`
  via `target` parameter. Old function removed.
- `transliterate_impl` Rust signature now takes 7 arguments (added `tones: bool`).
- Updated benchmark numbers after `tones` parameter addition (15–46% regression in
  transliteration hot path due to additional branch; throughput now 450M chars/sec
  Latin, 130M chars/sec Cyrillic).
- Performance documentation updated across 4 files to reflect current benchmark results.

### Fixed
- clippy `format_push_string` lint in `build.rs` — replaced `push_str(&format!())`
  with `write!()`.
- clippy `unreadable_literal` in PHF-generated `reverse_translit_phf.rs` — suppressed
  via inner attribute in `src/reverse.rs`.
- All 219 integration test call sites updated for 7-argument `transliterate_impl`.

## [0.1.4] — 2026-03-25

### Added
- **`lang="auto"` script-based language detection**: When `lang="auto"` is passed
  to `transliterate()`, `slugify()`, `TextPipeline`, `Slugifier`, or any other
  call site, the library detects the dominant non-Latin script in the input and
  maps it to a default language code automatically. Maps 28 scripts to language
  codes (e.g. Cyrillic→`ru`, Han→`zh`, Hiragana/Katakana→`ja`, Thai→`th`).
  Zero overhead for `lang=None` or explicit lang codes.
- `LANG_AUTO` constant (`"auto"`) in `translit._enums`.
- **Georgian transliteration** (`lang="ka"`): 114 TSV entries covering Mkhedruli,
  Mtavruli, and supplement ranges. BGN/PCGN national romanization.
- **Armenian transliteration** (`lang="hy"`): 86 TSV entries covering uppercase,
  lowercase, and 5 ligatures (U+FB13–FB17). BGN/PCGN romanization.
- **Sinhala transliteration** (`lang="si"`): 90 TSV entries. Extended Indic
  Brahmic engine range from `0x0900..=0x0D7F` to `0x0900..=0x0DFF` with
  dedicated `sinhala_char_role()` function for Sinhala-specific offsets.
- **Thai transliteration** (`lang="th"`): 87 TSV entries using RTGS romanization.
  New `ScriptClass::Tai` with tone-mark stripping and cancellation handling.
- **Lao transliteration** (`lang="lo"`): 67 TSV entries using BGN/PCGN
  romanization. Shares Tai engine with Thai via offset masking.
- **Ethiopic transliteration** (`lang="am"`): 307 TSV entries for Ge'ez
  alphasyllabary (34 consonant bases × 7 vowel orders + labialized forms +
  digits). Pure data addition — no engine changes needed.
- **Myanmar transliteration** (`lang="my"`): 89 TSV entries. New
  `myanmar_char_role()` for Brahmic engine with virama (U+1039) and asat
  (U+103A) support. Medials (U+103B–103E) classified as dependent vowels.
- **Khmer transliteration** (`lang="km"`): 110 TSV entries. New
  `khmer_char_role()` for Brahmic engine with coeng (U+17D2) as virama. All
  consonants normalized to inherent 'a' regardless of series.
- **Tibetan transliteration** (`lang="bo"`): 147 TSV entries. New
  `tibetan_char_role()` for Brahmic engine with halanta (U+0F84) and subjoined
  consonants (U+0F90–0FBC).
- Unicode range constants: `TIBETAN` (0x0F00–0x0FFF), `MYANMAR` (0x1000–0x109F),
  `KHMER` (0x1780–0x17FF) in `src/unicode_ranges.rs`.
- Comprehensive test coverage: example-based tests for all 9 new scripts,
  property-based tests (hypothesis + proptest), multi-script mixture tests.
- Built-in language count: 51 → 60.

### Changed
- `is_indic()` extended to include Tibetan, Myanmar, and Khmer ranges for
  Brahmic abugida processing.
- `indic_char_role()` dispatches to script-specific functions for Sinhala,
  Tibetan, Myanmar, and Khmer codepoint ranges.

## [0.1.3] — 2026-03-25

### Added
- `strip_control` and `strip_zero_width` now work as independent pipeline steps
  without requiring `collapse_whitespace=True`. Previously they were silently
  ignored when `collapse_whitespace` was disabled.
- `strip_control_chars()` and `strip_zero_width_chars()` standalone Rust
  functions for filtering without whitespace collapsing.
- `decimal` and `hexadecimal` flags in `SlugConfig` are now functional. Setting
  `decimal=False` preserves `&#NNN;` entities; `hexadecimal=False` preserves
  `&#xHHH;` entities. Previously these flags were accepted but silently ignored.
- Rust integration tests: `tests/integration_emoji.rs` (10 tests),
  `tests/integration_slugify.rs` (20 tests),
  `tests/integration_transliterate.rs` (21 tests),
  `tests/integration_whitespace.rs` (12 tests).

### Changed
- `TextPipeline` parameters `strip_control` and `strip_zero_width` changed from
  `bool` (default `True`) to `bool | None` (default `None`). When `None`, they
  inherit from `collapse_whitespace` — `True` if `collapse_whitespace=True`,
  `False` otherwise. Set explicitly to `True` for standalone use without
  `collapse_whitespace`. This is backward compatible: existing code that passes
  `collapse_whitespace=True` gets the same behavior as before.
- `steps()` now reports `strip_control` and `strip_zero_width` as separate
  entries when active, giving full visibility into pipeline behavior.
- Pipeline step order updated: `normalize → confusables → demojize →
  strip_accents → transliterate → fold_case → strip_control →
  strip_zero_width → collapse_whitespace`.
- Migrated from `once_cell` to `std::sync::LazyLock` / `OnceLock`; MSRV bumped
  to 1.80. Removed `once_cell` dependency.
- `needs_cjk_space()` match arm tightened from wildcard `_` to explicit
  `Ideograph | Hangul | Kana` to match the call-site `is_cjk` guard.

### Fixed
- `decode_entities()` corrupting multi-byte UTF-8 characters (BUG-1). The
  function used `bytes[i] as char` which treated each continuation byte as a
  separate Latin-1 codepoint (e.g. `café` → `cafÃ©`). Now advances by full
  UTF-8 characters.
- `decode_numeric_entity_skip()` panicking on malformed `&#` followed by
  multi-byte UTF-8 (BUG-2). The skip function walked through continuation
  bytes looking for `;`, landing inside a multi-byte character. Now stops at
  the first non-ASCII byte.

### Performance
- ASCII fast-path in `demojize_impl` and `demojize_rust`: pure-ASCII text
  returns immediately without `Vec<char>` allocation or emoji scanning.
- `filter_stopwords` replaced intermediate `Vec<_>` + `.join()` with a
  pre-allocated `String` fold, removing one allocation per slugify call.

## [0.1.2] — 2026-03-25

### Added
- Python 3.14 support (classifier and CI test matrix).
- `ruff check --fix` pre-commit hook for automatic lint fixing.
- CI publish workflow using `pypa/gh-action-pypi-publish` with OIDC trusted publishers.
- Multi-platform wheel builds: Linux (x86_64, aarch64), macOS (Intel, ARM64), Windows.
- `steps()` method on `_TextPipeline` type stub.

### Changed
- Resolved all clippy pedantic warnings instead of suppressing them — reduced
  lint suppressions from 48 to 22 (remaining are genuine PyO3 constraints).
  Fixes include: combined identical match arms, replaced manual counters with
  `.enumerate()`, moved item declarations before statements, used `clone_into()`,
  merged identical branches, fixed doc comment formatting.
- Widened `stopwords` and `replacements` type stubs from strict `tuple`/`list`
  to `Sequence` for better mypy compatibility.
- Applied `ruff format` to all Python source and test files.
- Switched docs publish from deprecated `maturin upload` to
  `pypa/gh-action-pypi-publish`.
- macOS Intel wheels now cross-compiled on ARM64 runner (macos-14) instead of
  deprecated macos-13.
- CI doctests now run against installed package (not source tree) with explicit
  `shell: bash` for Windows compatibility.

### Fixed
- `TextPipeline.explain()` doctest: output format is `normalize (NFC)` not
  `normalize (form=NFC)`.
- `from __future__ import annotations` placement in test files (must follow
  module docstring, not precede it).
- Malformed HTML entity test expectation: `decode_entities("&#xyz;")` correctly
  returns `""`, not `"yz;"`.
- Rust benchmark CI: target `bench_core` binary explicitly to avoid passing
  Criterion flags to the test harness.
- Ruff lint fixes: unsorted imports in `test_encoding.py`, unused import
  `is_mixed_script` in `test_security_invariants.py`.
- Read the Docs trigger workflow: simplified curl status handling, graceful
  warning when `RTD_TOKEN` is missing.
- Removed incorrect PyPy classifier (abi3 is CPython-only).

## [0.1.1] — 2026-03-25

### Added
- `src/unicode_ranges.rs` — named constants for all Unicode codepoint ranges used
  by the library, eliminating magic numbers scattered across modules.
- `tests/test_concurrency.py` — concurrent access tests for `LANG_TABLES` and
  `HANGUL_CACHE`, plus malformed Unicode input tests.
- Code coverage reporting in CI (`pytest-cov`, XML report uploaded as artifact).
- `CLOCK$`, `KEYBD$`, `SCREEN$`, `COM0`, `LPT0` added to Windows reserved filename list.
- `casefold()` alias for `fold_case()` — matches `str.casefold()` naming.
- `remove_accents()` alias for `strip_accents()` — matches sklearn/ML ecosystem naming.
- Compatibility parameter aliases: `replacement_text`/`max_len` on `sanitize_filename()`
  (pathvalidate), `greedy`/`preferred_aliases` on `is_confusable()` (confusable_homoglyphs),
  `delimiters` on `demojize()` (emoji library).
- Data Engineer persona guide (`docs/data-engineer-guide.md`) — ETL normalization,
  deduplication, batch processing, pandas/PySpark/Airflow integration patterns.
- Complete API documentation for 19 previously undocumented exported functions:
  precompiled pipelines, grapheme clusters, encoding detection, `Text` builder,
  `is_safe_hostname`, `demojize`, `strip_bidi`, `EmojiProvider` protocol.
- Three new API reference pages: Precompiled Pipelines, Grapheme Clusters, Encoding.
- "Guides by role" section in `docs/index.md` and `README.md`.
- Performance section in `README.md` with benchmark numbers.
- `Script` enum documentation expanded from 28 to all 41 members.

### Changed
- `transliterate_impl` refactored: capacity estimation extracted to `estimate_capacity()`,
  character classification to `classify_char()`, and CJK spacing logic to
  `needs_cjk_space()`.
- All `RwLock` accesses now recover from lock poisoning using
  `.unwrap_or_else(|e| e.into_inner())` instead of silently falling through.
- Lambda closures in `_compat.py` replaced with named inner functions for clarity.
- `emoji.rs` `write!()` call no longer uses `.unwrap()` (infallible, documented with
  a `// SAFETY` comment).
- MkDocs theme switched from `material` to `readthedocs`.
- All documentation references updated from "unirust" to "translit".
- Development status promoted from Alpha to Beta.
- Package renamed from `translit` to `translit-rs` on PyPI (interim until PEP 541
  grants the `translit` name). Python import remains `import translit`.

### Fixed
- Type stub `_text.pyi` imported from wrong module name (`unirust` → `translit`).
- Type stub `_translit.pyi` missing `min_confidence` parameter on `_decode_to_utf8`.
- Type stub `_text.pyi` missing `grapheme_split`, `grapheme_truncate`, `catalog_key` methods.
- `security_clean()` pipeline step order corrected in 5+ locations: strip_bidi runs
  before collapse_whitespace (matching Rust implementation).
- `catalog_key()` step order corrected: transliterate before strip_accents.
- Stale PyO3 boundary overhead corrected from ~4µs to ~240ns in docs and code comments.

### Deprecated
- `translit._compat` awesome-slugify compatibility layer (`Slugify`, `UniqueSlugify`,
  `slugify_*` instances) — planned removal in v1.0.

## [0.1.0] — 2026-01-01

### Added
- Initial release.
- Unicode transliteration for 60 language profiles.
- Slugification, normalization, confusable detection, filename sanitization.
- Emoji demojization with ZWJ sequence support.
- Backward-compatible layers for Unidecode and awesome-slugify.
