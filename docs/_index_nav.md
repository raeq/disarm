
---

## User Guide

Core concepts and usage for each feature area.

- **[Getting Started](user-guide/getting-started.md)** — Installation, first steps, and basic usage
- **[Adversarial-Text Defense](security/adversarial-defense.md)** — TR39 visual confusable mapping vs phonetic transliteration, the XMR benchmark, and why it matters
- **[Transliteration](user-guide/transliteration.md)** — Unicode → ASCII with language profiles, plus reverse (Latin → native script)
- **[Slugification](user-guide/slugification.md)** — URL-safe slug generation, drop-in python-slugify replacement
- **[Normalization](user-guide/normalization.md)** — NFC / NFD / NFKC / NFKD Unicode normalization
- **[Confusable Detection](user-guide/confusables.md)** — TR39 homoglyph detection and normalization
- **[Filename Sanitization](user-guide/filenames.md)** — Cross-platform safe filenames
- **[Text Cleaning](user-guide/text-cleaning.md)** — Accent stripping, case folding, whitespace collapse
- **[Grapheme Clusters](user-guide/graphemes.md)** — User-perceived character counting, splitting, and truncation
- **[Text Pipeline](user-guide/pipeline.md)** — Composable, pre-compiled multi-step processing
- **[Language Support](user-guide/language-support.md)** — Built-in profiles, auto-detection, custom profiles
- **[Abjad Scripts](user-guide/abjad-transliteration.md)** — Context-aware Arabic, Persian, and Hebrew with dictionary-based vowel restoration
- **[Language Detection](user-guide/language-detection.md)** — How `lang="auto"` works: script identification, character-level discrimination, fail-safe fallbacks

---

- **[Policy Templates](policy-templates.md)** — Named institutional presets for libraries, web apps, ML, and more
- **[CLI](cli.md)** — Command-line usage, piping, and shell integration

---

## API Reference

Complete function signatures, parameters, and return types.

- **[Overview](api/index.md)** — API reference index
- **[Core Transforms](api/transforms.md)** — `transliterate`, `slugify`, `normalize`, `sanitize_filename`, `strip_accents`, `strip_zalgo`, `fold_case`, `collapse_whitespace`, `demojize`, `strip_bidi` (all accept `str` or `list[str]`)
- **[Precompiled Pipelines](api/pipelines.md)** — `security_clean`, `ml_normalize`, `catalog_key`, `display_clean`, `search_key`, `sort_key`, `normalize_user_input`, `PRESETS`, `get_pipeline`, `list_profiles`
- **[Classes](api/classes.md)** — `Text`, `Slugifier`, `UniqueSlugifier`, `TextPipeline`, compatibility aliases
- **[Predicates](api/predicates.md)** — `detect_scripts`, `inspect_auto_lang`, `is_mixed_script`, `is_confusable`, `is_ascii`, `is_normalized`, `is_zalgo`, `is_suspicious_hostname`
- **[Grapheme Clusters](api/graphemes.md)** — `grapheme_len`, `grapheme_split`, `grapheme_truncate`
- **[Encoding Detection](api/encoding.md)** — `detect_encoding`, `decode_to_utf8`
- **[Language Profiles](api/language-profiles.md)** — `list_langs`, `register_lang`, `register_replacements`
- **[Enums & Types](api/enums.md)** — `Script`, `NF`, `EmojiProvider`, type aliases, language constants
- **[Exceptions](api/exceptions.md)** — `DisarmError`

---

## Reference

- **[Language Reference](reference.md)** — All languages: codes, names, reference texts, and per-language transliteration rule tables
- **[Provenance](provenance.md)** — Standards and sources behind every transliteration mapping

---

## Architecture

Internal design documentation for contributors and advanced users.

- **[Transliteration Engine](architecture/transliteration-engine.md)** — PHF lookup, language table chain, Indic virama handling
- **[Data Tables](architecture/data-tables.md)** — TSV format, build.rs code generation, compile-time PHF
- **[Pipeline](architecture/pipeline.md)** — TextPipeline internals, execution order, step bitflags
- **[Emoji Engine](architecture/emoji-engine.md)** — Emoji detection, provider system, pure-Rust path
- **[Emoji Plugins](architecture/emoji-plugins.md)** — EmojiProvider protocol, custom providers
- **[Security](architecture/security.md)** — Confusable detection, hostname validation, bidi stripping
- **[Performance](architecture/performance.md)** — Optimization strategies, PHF tables, batch amortization
- **[Testing & Guarantees](architecture/testing-guarantees.md)** — Test philosophy, property-based testing, security invariants, CI matrix
- **[Exhaustive Testing](formal-verification.md)** — Compile-time assertions, exhaustive domain coverage, stated invariants (I1–I7)
- **[Transliteration Comparison](architecture/transliteration-comparison.md)** — Character-level diff vs Unidecode and anyascii

---

## Benchmarks

- **[Performance Overview](performance.md)** — Benchmark methodology, results, and optimization details
- **[Benchmark Suite](benchmarks.md)** — How to run benchmarks, Criterion and timeit configurations

---

## Migration Guides

Parameter-compatible replacements for existing libraries.

- **[Migration Overview](migration/index.md)** — Feature comparison matrix
- **[From Unidecode / text-unidecode](migration/from-unidecode.md)** — Drop-in `unidecode()` alias
- **[From python-slugify / awesome-slugify](migration/from-python-slugify.md)** — Parameter-compatible `slugify()`
- **[From confusable_homoglyphs](migration/from-confusable-homoglyphs.md)** — Script detection and normalization
- **[From pathvalidate](migration/from-pathvalidate.md)** — Filename sanitization
- **[From anyascii](migration/from-anyascii.md)** — Language-aware transliteration

---

## Other

- **[Limitations](limitations.md)** — Known constraints, edge cases, and design trade-offs
