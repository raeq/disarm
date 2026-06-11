<!-- AUTO-GENERATED from README.md + docs/_index_nav.md -->
<!-- Do not edit directly. Run: bash scripts/generate_docs_index.sh -->

# disarm

[![Documentation](https://readthedocs.org/projects/disarm/badge/?version=latest)](https://docs.disarm.dev/en/latest/) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/raeq/disarm/blob/main/LICENSE)

Unicode canonicalization and TR39 confusable analysis for Python — building blocks for text-security pipelines (homoglyph/bidi/zalgo/invisible-character handling) plus standards-based transliteration. Rust-powered.

**[Documentation](index.md)** | **[API Reference](api/index.md)** | **[PyPI](https://pypi.org/project/disarm/)**

## Demo

**[Try disarm in your browser](https://disarm-web.pages.dev/)**

## Why disarm

The text-cleaning libraries already in most pipelines — `ftfy`, `unidecode`, `anyascii` — were built for encoding repair and ASCII conversion. They map confusables *phonetically* (Cyrillic `р` → Latin `r`), which does not reverse a homoglyph substitution.

disarm implements *visual* confusable mapping per [Unicode TR39](https://www.unicode.org/reports/tr39/) (Cyrillic `р` → Latin `p`). In a controlled benchmark (six attack types, three downstream tasks, two architectures; 435,864 observations), visual TR39 mapping reached **XMR = 1.000 on the tested TR39 homoglyph pairs** (17 Latin–Cyrillic, 19 Greek), where phonetic transliterators plateaued near half:

| Tool class | Mapping | Homoglyph XMR (tested TR39 pairs) |
|---|---|---|
| `unidecode`, `anyascii`, `cyrtranslit`, `uroman` | phonetic | ~0.49 |
| **disarm** (`strip_obfuscation` / `normalize_confusables`) | **visual (TR39)** | **1.000** |

`ftfy` was statistically equivalent to no preprocessing; `unidecode` *degraded* accuracy on invisible-character attacks. Details: **[Adversarial-Text Defense](security/adversarial-defense.md)** (paper *"Fire Extinguishers Full of Gasoline"*; XMR metric: [Zenodo 10.5281/zenodo.19323513](https://doi.org/10.5281/zenodo.19323513)).

> **Scope.** disarm is a **defense-in-depth layer, not a complete control.** It canonicalizes the confusables it bundles (TR39) and strips the format characters it enumerates; it does not promise to stop any attack class, and the confusable space is far larger than any table. See the **[Threat Model](THREAT_MODEL.md)** for what is and isn't in scope.

```python
from disarm import strip_obfuscation, normalize_confusables, is_safe_hostname

# Fold Cyrillic look-alikes to their Latin prototypes (TR39 visual mapping)
assert strip_obfuscation("рroduсt") == 'product'
assert strip_obfuscation("pаypаl 🔥🔥") == 'paypal fire fire'

assert normalize_confusables("раypal") == 'paypal'

# IDN / hostname spoofing check
safe, details = is_safe_hostname("аpple.com")   # leading Cyrillic а
# safe is False; details.has_confusables and details.mixed_script flag why
```

## Installation

```bash
pip install disarm
```

Install and import use the same name, `disarm`:

```python
import disarm
```

Requires Python 3.10+. Wheels are available for Linux, macOS, and Windows.

## Features

- **[Confusable & homoglyph analysis (TR39)](security/adversarial-defense.md)**: visual [confusable mapping](user-guide/confusables.md), bidi-control / zalgo / zero-width / invisible-character stripping, and the `strip_obfuscation` pipeline (defense-in-depth — see the [Threat Model](THREAT_MODEL.md))
- **[Canonicalization pipelines](api/pipelines.md)**: `security_clean`, `sanitize_user_input`, `catalog_key`, `search_key`, `sort_key`, `display_clean`, `ml_normalize` for common workflows
- **[Hostname / IDN analysis](api/predicates.md#is_safe_hostname)**: mixed-script and confusable detection for domains
- **[Standards-based transliteration](user-guide/transliteration.md)**: best-in-class Latin / Cyrillic / Greek with ISO 9-style ASCII (`strict_iso9`), GOST R 7.0.34, and BGN/PCGN, plus [reverse transliteration](user-guide/language-support.md#reverse-transliteration) (Russian, Ukrainian, Greek)
- **[Text normalization](user-guide/normalization.md)**: NFC/NFD/NFKC/NFKD, full Unicode case folding (1,557 CaseFolding.txt mappings via PHF), [whitespace collapse](user-guide/text-cleaning.md)
- **[Slugification](user-guide/slugification.md)** & **[filename sanitization](user-guide/filenames.md)**: URL-safe slugs (python-slugify compatible) and cross-platform safe filenames with path-traversal handling
- **[Grapheme clusters](user-guide/graphemes.md)**: correct user-perceived character counting, splitting, and truncation
- **[Encoding detection](api/encoding.md)**: auto-detect and decode byte sequences to UTF-8 (chardetng)
- **Broad transliteration coverage** for CJK, Indic, and other scripts — a context-free [unidecode-compatible drop-in](#coverage-tiers) (best-effort; see caveats)

All text processing is implemented in Rust with O(1) PHF lookups and exposed to Python via PyO3.

## Quick start

### Defense & canonicalization

```python
from disarm import (
    is_confusable, normalize_confusables, strip_obfuscation,
    security_clean, sanitize_user_input,
)

assert is_confusable("аpple") == True
assert normalize_confusables("раypal") == 'paypal'

# Maximum deobfuscation: homoglyphs, zalgo, invisible chars, bidi, emoji → clean text
assert strip_obfuscation("рroduсt") == 'product'

# Pipelines
assert security_clean("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥") == 'Real text'
assert sanitize_user_input("pаypal") == 'paypal'
```

### Transliteration (standards-based core)

```python
from disarm import transliterate, slugify

assert transliterate("café") == 'cafe'
assert transliterate("Москва") == 'Moskva'
assert transliterate("Αθήνα") == 'Athina'

# Named standards (Latin / Cyrillic / Greek)
assert transliterate("Юрий", strict_iso9=True) == 'Jurij'
assert transliterate("Москва", gost7034=True) == 'Moskva'

# Language profiles (sparse overrides on top of the default table)
assert transliterate("Ärger", lang="de") == 'Aerger'
assert transliterate("Київ", lang="uk") == 'Kyiv'

# Auto-detect language from script
assert transliterate("Москва", lang="auto") == 'Moskva'

# Reverse transliteration (Latin → native script): Russian, Ukrainian, Greek
assert transliterate("Moskva", target="ru") == 'Москва'
assert transliterate("Athina", target="el") == 'Αθηνα'

# Slugs & filenames
assert slugify("café au lait") == 'cafe-au-lait'
```

### Compatibility coverage (CJK and other scripts)

```python
# Context-free, character-by-character — best-effort, unidecode-parity (see caveats below)
assert transliterate("北京市") == 'bei jing shi'
assert transliterate("서울") == 'seo ul'
assert transliterate("ひらがな") == 'hiragana'
```

## Coverage tiers

disarm transliterates a very wide range of scripts, but the **quality guarantee differs by tier**. Lead with the core; treat the rest as compatibility coverage.

| Tier | Scripts | Policy | Standard |
|---|---|---|---|
| **Core** (best-in-class) | Latin, Cyrillic, Greek | Standards-based romanization + reverse | BGN/PCGN (default), ISO 9-style ASCII (`strict_iso9`), GOST R 7.0.34 (`gost7034`) |
| **Compatibility** (best-effort) | CJK (Chinese / Japanese / Korean), Arabic, Hebrew, Devanagari & 9 other Indic scripts, Thai, Lao | Context-free, character-by-character — same approach as Unidecode/AnyAscii | Unihan `kMandarin`, Revised Romanization, Hepburn, UNGEGN/IAST-derived, RTGS-derived |
| **Best-effort** | Georgian, Armenian, and a long tail of additional scripts | Context-free coverage so input is never silently dropped | see [Language support](user-guide/language-support.md) |

**Compatibility-tier transliteration is context-free and character-by-character** — no linguistic analysis, polyphony handling, or phonological rules. For CJK/Arabic/Indic this is fundamentally lossy and no better than Unidecode; it exists so disarm is a complete drop-in, not because it is best-in-class there. See [limitations.md](limitations.md) for trade-offs and the [full per-script policy table](user-guide/language-support.md).

> **Context-aware abjad (Arabic, Persian, Hebrew):** an optional dictionary-backed mode (`transliterate(text, context=True)`) restores vowels for more readable output. It is a best-effort *readability aid*, not a romanization standard. See [Abjad scripts](user-guide/abjad-transliteration.md).

## Precompiled pipelines

```python
from disarm import security_clean, ml_normalize, catalog_key, sanitize_user_input, strip_obfuscation

# Security: NFKC → confusables → strip bidi → collapse whitespace
assert security_clean("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥") == 'Real text'

# ML/NLP: NFKC → emoji→text → transliterate → strip accents → fold case
assert ml_normalize("Café ☕ Ünïcödé") == 'cafe hot beverage unicode'

# Library catalog: NFKC → transliterate → confusables → strip accents → fold case
assert catalog_key("Москва", lang="ru") == 'moskva'
assert catalog_key("ΩMEGA  café") == 'omega cafe'

# Web input: NFKC → strip bidi → strip zero-width → strip zalgo → confusables → collapse
assert sanitize_user_input("pаypal") == 'paypal'

# Maximum deobfuscation: homoglyphs, zalgo, invisible chars → clean text
assert strip_obfuscation("рroduсt") == 'product'
assert strip_obfuscation("pаypаl 🔥🔥") == 'paypal fire fire'
# Note: does NOT transliterate — chain with transliterate() if needed
```

## Text builder

```python
from disarm import Text

result = (
    Text("Ünïcödé Café ☕")
    .normalize(form="NFKC")
    .demojize()
    .transliterate()
    .strip_accents()
    .fold_case()
    .value
)
assert result == 'unicode cafe hot beverage'
```

## Package structure

The API is organized into domain-specific namespaces. All functions are also available at the top level for convenience.

| Namespace | Purpose | Key functions |
|---|---|---|
| `disarm.security` | Defense & safety analysis | `normalize_confusables`, `is_confusable`, `is_mixed_script`, `is_safe_hostname`, `strip_bidi`, `security_clean` |
| `disarm` | Core transforms | `transliterate`, `slugify`, `strip_obfuscation`, `Text`, `TextPipeline` |
| `disarm.normalization` | Unicode normalization | `normalize`, `strip_accents`, `fold_case`, `collapse_whitespace` |
| `disarm.files` | Filename handling | `sanitize_filename` |
| `disarm.codec` | Byte decoding | `decode_to_utf8`, `detect_encoding` |

```python
# Namespace imports
from disarm.security import is_confusable, security_clean
from disarm.codec import decode_to_utf8
from disarm.normalization import fold_case

# Top-level imports also work
from disarm import is_confusable, security_clean, decode_to_utf8, fold_case
```

## Language profiles

Built-in language profiles span the core and compatibility tiers, with scholarly ASCII Cyrillic support (`strict_iso9`; ISO 9-style digraphs, not the diacritic standard). Profiles apply **sparse overrides** on top of the default table (e.g. German maps `ü` → `ue` instead of the default `u`).

```python
from disarm import list_langs, transliterate

print(list_langs())
# ['am', 'ar', 'as', 'bg', 'bn', 'bo', 'ca', 'cs', 'cy', 'da', 'de', 'dv', 'el',
#  'es', 'et', 'fa', 'fi', 'fr', 'ga', 'gu', 'he', 'hi', 'hr', 'hu', 'hy',
#  'is', 'it', 'ja', 'jv', 'ka', 'km', 'kn', 'ko', 'lo', 'lt', 'lv', 'ml', 'mn',
#  'mr', 'mt', 'my', 'ne', 'nl', 'no', 'or', 'pa', 'pl', 'pt', 'ro', 'ru', 'sa',
#  'si', 'sk', 'sl', 'sq', 'sr', 'sv', 'ta', 'te', 'th', 'tr', 'uk', 'vi', 'zh']
```

See [Language support](user-guide/language-support.md) for the full registry, per-script policies, and tier classification.

## Performance

disarm is compiled Rust with O(1) compile-time perfect hash tables — no regex, no per-character Python iteration, no runtime data loading. Speed is a supporting benefit, not the headline; correctness and defense come first.

| Operation | Throughput | vs. legacy |
|---|---|---|
| Transliterate (Latin) | 450M chars/sec | **38×** faster than Unidecode |
| Transliterate (Cyrillic) | 130M chars/sec | **18×** faster than Unidecode |
| Slugify | 849K slugs/sec | **10–24×** faster than python-slugify |
| Batch transliterate (100 strings) | 2.8× faster than loop | — |

See [performance.md](performance.md) for full benchmark methodology and results.

## Drop-in replacement

disarm provides compatibility aliases for painless migration from existing libraries:

```python
from disarm import unidecode, casefold, remove_accents

assert unidecode("café") == 'cafe'
assert casefold("Straße") == 'strasse'
assert remove_accents("café") == 'cafe'
```

`sanitize_filename()` also accepts `replacement_text` and `max_len` kwargs for pathvalidate compatibility, and `is_confusable()` accepts `greedy` for confusable_homoglyphs compatibility. See [migration guides](migration/index.md) for details.

> **Security note:** the `unidecode` alias is for *coverage* compatibility only. For security/defense use it is the wrong tool (phonetic mapping does not reverse homoglyph attacks and can degrade downstream accuracy). Use `strip_obfuscation` / `normalize_confusables` instead — see [Migration from Unidecode](migration/from-unidecode.md).

## Exhaustive testing

disarm is exhaustively tested with three layers of machine-verifiable assurance beyond conventional unit and property-based tests:

- **Compile-time assertions**: `build.rs` asserts all transliteration table values are ASCII and entry counts match expectations — if any check fails, `cargo build` fails
- **Exhaustive domain coverage**: Every Hangul syllable (11,172), every BMP codepoint (63,488), every CJK ideograph (20,992), and every Indic script block are tested individually — zero sampling gaps
- **Stated invariants**: Seven stated properties (ASCII passthrough, idempotence, determinism, output bounds, etc.) verified by exhaustive enumeration and Hypothesis

See [formal-verification.md](formal-verification.md) for details.


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
- **[Precompiled Pipelines](api/pipelines.md)** — `security_clean`, `ml_normalize`, `catalog_key`, `display_clean`, `search_key`, `sort_key`, `sanitize_user_input`, `PRESETS`, `get_pipeline`, `list_profiles`
- **[Classes](api/classes.md)** — `Text`, `Slugifier`, `UniqueSlugifier`, `TextPipeline`, compatibility aliases
- **[Predicates](api/predicates.md)** — `detect_scripts`, `inspect_auto_lang`, `is_mixed_script`, `is_confusable`, `is_ascii`, `is_normalized`, `is_zalgo`, `is_safe_hostname`
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
