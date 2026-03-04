# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `src/unicode_ranges.rs` — named constants for all Unicode codepoint ranges used
  by the library, eliminating magic numbers scattered across modules.
- `tests/test_concurrency.py` — concurrent access tests for `LANG_TABLES` and
  `HANGUL_CACHE`, plus malformed Unicode input tests.
- Code coverage reporting in CI (`pytest-cov`, XML report uploaded as artifact).
- `CLOCK$`, `KEYBD$`, `SCREEN$`, `COM0`, `LPT0` added to Windows reserved filename list.

### Changed
- `transliterate_impl` refactored: capacity estimation extracted to `estimate_capacity()`,
  character classification to `classify_char()`, and CJK spacing logic to
  `needs_cjk_space()`.
- All `RwLock` accesses now recover from lock poisoning using
  `.unwrap_or_else(|e| e.into_inner())` instead of silently falling through.
- Lambda closures in `_compat.py` replaced with named inner functions for clarity.
- `emoji.rs` `write!()` call no longer uses `.unwrap()` (infallible, documented with
  a `// SAFETY` comment).

### Deprecated
- `translit._compat` awesome-slugify compatibility layer (`Slugify`, `UniqueSlugify`,
  `slugify_*` instances) — planned removal in v1.0.

## [0.1.0] — 2024-01-01

### Added
- Initial release.
- Unicode transliteration for 37 language profiles.
- Slugification, normalization, confusable detection, filename sanitization.
- Emoji demojization with ZWJ sequence support.
- Backward-compatible layers for Unidecode and awesome-slugify.
