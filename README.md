# translit

[![Documentation](https://readthedocs.org/projects/translit/badge/?version=latest)](https://translit.readthedocs.io/en/latest/) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/raeq/translit/blob/main/LICENSE)

Unicode canonicalization and TR39 confusable analysis for Python — building blocks for text-security pipelines (homoglyph/bidi/zalgo/invisible-character handling) plus standards-based transliteration. Rust-powered.

**[Documentation](docs/index.md)** | **[API Reference](docs/api/index.md)** | **[PyPI](https://pypi.org/project/translit-rs/)**

## Demo

**[Try translit in your browser](https://translit-web.pages.dev/)**

## Why translit

The text-cleaning libraries already in most pipelines — `ftfy`, `unidecode`, `anyascii` — were built for encoding repair and ASCII conversion. They map confusables *phonetically* (Cyrillic `р` → Latin `r`), which does not reverse a homoglyph substitution.

translit implements *visual* confusable mapping per [Unicode TR39](https://www.unicode.org/reports/tr39/) (Cyrillic `р` → Latin `p`). In a controlled benchmark (six attack types, three downstream tasks, two architectures; 435,864 observations), visual TR39 mapping reached **XMR = 1.000 on the tested TR39 homoglyph pairs** (17 Latin–Cyrillic, 19 Greek), where phonetic transliterators plateaued near half:

| Tool class | Mapping | Homoglyph XMR (tested TR39 pairs) |
|---|---|---|
| `unidecode`, `anyascii`, `cyrtranslit`, `uroman` | phonetic | ~0.49 |
| **translit** (`strip_obfuscation` / `normalize_confusables`) | **visual (TR39)** | **1.000** |

`ftfy` was statistically equivalent to no preprocessing; `unidecode` *degraded* accuracy on invisible-character attacks. Details: **[Adversarial-Text Defense](docs/security/adversarial-defense.md)** (paper *"Fire Extinguishers Full of Gasoline"*; XMR metric: [Zenodo 10.5281/zenodo.19323513](https://doi.org/10.5281/zenodo.19323513)).

> **Scope.** translit is a **defense-in-depth layer, not a complete control.** It canonicalizes the confusables it bundles (TR39) and strips the format characters it enumerates; it does not promise to stop any attack class, and the confusable space is far larger than any table. See the **[Threat Model](THREAT_MODEL.md)** for what is and isn't in scope.

```python
from translit import strip_obfuscation, normalize_confusables, is_safe_hostname

# Fold Cyrillic look-alikes to their Latin prototypes (TR39 visual mapping)
strip_obfuscation("рroduсt")        # → "product"  (р→p, с→c)
strip_obfuscation("pаypаl 🔥🔥")     # → "paypal fire fire"  (also strips zalgo/bidi/invisible/emoji)

normalize_confusables("раypal")      # → "paypal"   (mixed Cyrillic skeleton → Latin)

# IDN / hostname spoofing check
safe, details = is_safe_hostname("аpple.com")   # leading Cyrillic а
# safe is False; details.has_confusables and details.mixed_script flag why
```

## Installation

```bash
pip install translit-rs
```

The package installs as `translit-rs` on PyPI but imports as `translit`:

```python
import translit  # not translit_rs
```

Requires Python 3.9+. Wheels are available for Linux, macOS, and Windows.

## Features

- **[Confusable & homoglyph analysis (TR39)](docs/security/adversarial-defense.md)**: visual [confusable mapping](docs/user-guide/confusables.md), bidi-control / zalgo / zero-width / invisible-character stripping, and the `strip_obfuscation` pipeline (defense-in-depth — see the [Threat Model](THREAT_MODEL.md))
- **[Canonicalization pipelines](docs/api/pipelines.md)**: `security_clean`, `sanitize_user_input`, `catalog_key`, `search_key`, `sort_key`, `display_clean`, `ml_normalize` for common workflows
- **[Hostname / IDN analysis](docs/api/predicates.md#is_safe_hostname)**: mixed-script and confusable detection for domains
- **[Standards-based transliteration](docs/user-guide/transliteration.md)**: best-in-class Latin / Cyrillic / Greek with ISO 9:1995, GOST R 7.0.34, and BGN/PCGN, plus [reverse transliteration](docs/user-guide/language-support.md#reverse-transliteration) (Russian, Ukrainian, Greek)
- **[Text normalization](docs/user-guide/normalization.md)**: NFC/NFD/NFKC/NFKD, full Unicode case folding (1,557 CaseFolding.txt mappings via PHF), [whitespace collapse](docs/user-guide/text-cleaning.md)
- **[Slugification](docs/user-guide/slugification.md)** & **[filename sanitization](docs/user-guide/filenames.md)**: URL-safe slugs (python-slugify compatible) and cross-platform safe filenames with path-traversal handling
- **[Grapheme clusters](docs/user-guide/graphemes.md)**: correct user-perceived character counting, splitting, and truncation
- **[Encoding detection](docs/api/encoding.md)**: auto-detect and decode byte sequences to UTF-8 (chardetng)
- **Broad transliteration coverage** for CJK, Indic, and other scripts — a context-free [unidecode-compatible drop-in](#coverage-tiers) (best-effort; see caveats)

All text processing is implemented in Rust with O(1) PHF lookups and exposed to Python via PyO3.

## Quick start

### Defense & canonicalization

```python
from translit import (
    is_confusable, normalize_confusables, strip_obfuscation,
    security_clean, sanitize_user_input,
)

is_confusable("аpple")             # → True  (contains Cyrillic а)
normalize_confusables("раypal")  # → "paypal"

# Maximum deobfuscation: homoglyphs, zalgo, invisible chars, bidi, emoji → clean text
strip_obfuscation("рroduсt")  # → "product"   (does NOT transliterate; chain transliterate() if needed)

# Pipelines
security_clean("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥")            # → "Real text"   (NFKC → confusables → strip bidi → collapse ws)
sanitize_user_input("pаypal")      # → "paypal"      (NFKC → strip zalgo → confusables → strip bidi → collapse ws)
```

### Transliteration (standards-based core)

```python
from translit import transliterate, slugify

transliterate("café")                      # → "cafe"
transliterate("Москва")                    # → "Moskva"     (Cyrillic, BGN/PCGN)
transliterate("Αθήνα")                     # → "Athina"     (Greek, BGN/PCGN)

# Named standards (Latin / Cyrillic / Greek)
transliterate("Юрий", strict_iso9=True)    # → "Jurij"      (ISO 9:1995)
transliterate("Москва", gost7034=True)     # → "Moskva"     (GOST R 7.0.34)

# Language profiles (sparse overrides on top of the default table)
transliterate("Ärger", lang="de")          # → "Aerger"
transliterate("Київ", lang="uk")           # → "Kyiv"

# Auto-detect language from script
transliterate("Москва", lang="auto")       # → "Moskva"     (detects Cyrillic → Russian)

# Reverse transliteration (Latin → native script): Russian, Ukrainian, Greek
transliterate("Moskva", target="ru")       # → "Москва"
transliterate("Athina", target="el")       # → "Αθηνα"

# Slugs & filenames
slugify("café au lait")                    # → "cafe-au-lait"
```

### Compatibility coverage (CJK and other scripts)

```python
# Context-free, character-by-character — best-effort, unidecode-parity (see caveats below)
transliterate("北京市")                     # → "bei jing shi"   (Chinese, toneless pinyin)
transliterate("서울")                       # → "seo ul"         (Korean, Revised Romanization)
transliterate("ひらがな")                   # → "hiragana"       (Japanese, Hepburn)
```

## Coverage tiers

translit transliterates a very wide range of scripts, but the **quality guarantee differs by tier**. Lead with the core; treat the rest as compatibility coverage.

| Tier | Scripts | Policy | Standard |
|---|---|---|---|
| **Core** (best-in-class) | Latin, Cyrillic, Greek | Standards-based romanization + reverse | BGN/PCGN (default), ISO 9:1995 (`strict_iso9`), GOST R 7.0.34 (`gost7034`) |
| **Compatibility** (best-effort) | CJK (Chinese / Japanese / Korean), Arabic, Hebrew, Devanagari & 9 other Indic scripts, Thai, Lao | Context-free, character-by-character — same approach as Unidecode/AnyAscii | Unihan `kMandarin`, Revised Romanization, Hepburn, UNGEGN/IAST-derived, RTGS-derived |
| **Best-effort** | Georgian, Armenian, and a long tail of additional scripts | Context-free coverage so input is never silently dropped | see [Language support](docs/user-guide/language-support.md) |

**Compatibility-tier transliteration is context-free and character-by-character** — no linguistic analysis, polyphony handling, or phonological rules. For CJK/Arabic/Indic this is fundamentally lossy and no better than Unidecode; it exists so translit is a complete drop-in, not because it is best-in-class there. See [docs/limitations.md](docs/limitations.md) for trade-offs and the [full per-script policy table](docs/user-guide/language-support.md).

> **Context-aware abjad (Arabic, Persian, Hebrew):** an optional dictionary-backed mode (`transliterate(text, context=True)`) restores vowels for more readable output. It is a best-effort *readability aid*, not a romanization standard. See [Abjad scripts](docs/user-guide/abjad-transliteration.md).

## Precompiled pipelines

```python
from translit import security_clean, ml_normalize, catalog_key, sanitize_user_input, strip_obfuscation

# Security: NFKC → confusables → strip bidi → collapse whitespace
security_clean("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥")  # → "Real text"

# ML/NLP: NFKC → emoji→text → transliterate → strip accents → fold case
ml_normalize("Café ☕ Ünïcödé")  # → "cafe hot beverage unicode"

# Library catalog: NFKC → transliterate → confusables → strip accents → fold case
catalog_key("Москва", lang="ru")  # → "moskva"
catalog_key("ΩMEGA  café")        # → "omega cafe"

# Web input: NFKC → strip bidi → strip zero-width → strip zalgo → confusables → collapse
sanitize_user_input("pаypal")  # → "paypal" (Cyrillic а folded to Latin)

# Maximum deobfuscation: homoglyphs, zalgo, invisible chars → clean text
strip_obfuscation("рroduсt")       # → "product" (Cyrillic р→p, с→c via TR39)
strip_obfuscation("pаypаl 🔥🔥")  # → "paypal fire fire"
# Note: does NOT transliterate — chain with transliterate() if needed
```

## Text builder

```python
from translit import Text

result = (
    Text("Ünïcödé Café ☕")
    .normalize(form="NFKC")
    .demojize()
    .transliterate()
    .strip_accents()
    .fold_case()
    .value
)
# → "unicode cafe hot beverage"
```

## Package structure

The API is organized into domain-specific namespaces. All functions are also available at the top level for convenience.

| Namespace | Purpose | Key functions |
|---|---|---|
| `translit.security` | Defense & safety analysis | `normalize_confusables`, `is_confusable`, `is_mixed_script`, `is_safe_hostname`, `strip_bidi`, `security_clean` |
| `translit` | Core transforms | `transliterate`, `slugify`, `strip_obfuscation`, `Text`, `TextPipeline` |
| `translit.normalization` | Unicode normalization | `normalize`, `strip_accents`, `fold_case`, `collapse_whitespace` |
| `translit.files` | Filename handling | `sanitize_filename` |
| `translit.codec` | Byte decoding | `decode_to_utf8`, `detect_encoding` |

```python
# Namespace imports
from translit.security import is_confusable, security_clean
from translit.codec import decode_to_utf8
from translit.normalization import fold_case

# Top-level imports also work
from translit import is_confusable, security_clean, decode_to_utf8, fold_case
```

## Language profiles

Built-in language profiles span the core and compatibility tiers, with ISO 9:1995 scholarly Cyrillic support. Profiles apply **sparse overrides** on top of the default table (e.g. German maps `ü` → `ue` instead of the default `u`).

```python
from translit import list_langs, transliterate

print(list_langs())
# ['am', 'ar', 'as', 'bg', 'bn', 'bo', 'ca', 'cs', 'cy', 'da', 'de', 'dv', 'el',
#  'es', 'et', 'fa', 'fi', 'fr', 'ga', 'gu', 'he', 'hi', 'hr', 'hu', 'hy',
#  'is', 'it', 'ja', 'jv', 'ka', 'km', 'kn', 'ko', 'lo', 'lt', 'lv', 'ml', 'mn',
#  'mr', 'mt', 'my', 'ne', 'nl', 'no', 'or', 'pa', 'pl', 'pt', 'ro', 'ru', 'sa',
#  'si', 'sk', 'sl', 'sq', 'sr', 'sv', 'ta', 'te', 'th', 'tr', 'uk', 'vi', 'zh']
```

See [Language support](docs/user-guide/language-support.md) for the full registry, per-script policies, and tier classification.

## Performance

translit is compiled Rust with O(1) compile-time perfect hash tables — no regex, no per-character Python iteration, no runtime data loading. Speed is a supporting benefit, not the headline; correctness and defense come first.

| Operation | Throughput | vs. legacy |
|---|---|---|
| Transliterate (Latin) | 450M chars/sec | **38×** faster than Unidecode |
| Transliterate (Cyrillic) | 130M chars/sec | **18×** faster than Unidecode |
| Slugify | 849K slugs/sec | **10–24×** faster than python-slugify |
| Batch transliterate (100 strings) | 2.8× faster than loop | — |

See [docs/performance.md](docs/performance.md) for full benchmark methodology and results.

## Drop-in replacement

translit provides compatibility aliases for painless migration from existing libraries:

```python
from translit import unidecode, casefold, remove_accents

unidecode("café")        # → "cafe"       (alias for transliterate)
casefold("Straße")       # → "strasse"    (alias for fold_case)
remove_accents("café")   # → "cafe"       (alias for strip_accents)
```

`sanitize_filename()` also accepts `replacement_text` and `max_len` kwargs for pathvalidate compatibility, and `is_confusable()` accepts `greedy` for confusable_homoglyphs compatibility. See [migration guides](docs/migration/index.md) for details.

> **Security note:** the `unidecode` alias is for *coverage* compatibility only. For security/defense use it is the wrong tool (phonetic mapping does not reverse homoglyph attacks and can degrade downstream accuracy). Use `strip_obfuscation` / `normalize_confusables` instead — see [Migration from Unidecode](docs/migration/from-unidecode.md).

## Exhaustive testing

translit is exhaustively tested with three layers of machine-verifiable assurance beyond conventional unit and property-based tests:

- **Compile-time assertions**: `build.rs` asserts all transliteration table values are ASCII and entry counts match expectations — if any check fails, `cargo build` fails
- **Exhaustive domain coverage**: Every Hangul syllable (11,172), every BMP codepoint (63,488), every CJK ideograph (20,992), and every Indic script block are tested individually — zero sampling gaps
- **Stated invariants**: Seven stated properties (ASCII passthrough, idempotence, determinism, output bounds, etc.) verified by exhaustive enumeration and Hypothesis

See [docs/formal-verification.md](docs/formal-verification.md) for details.

## Architecture

Rust core with compile-time PHF (perfect hash function) tables for O(1) per-character lookup. Exposed to Python via PyO3 with the stable ABI (abi3-py39). The Chinese pinyin table contains 20,924 entries from the Unicode Unihan database; Korean romanization is purely algorithmic (jamo decomposition, ~100 lines of Rust).

## Links

| | |
|---|---|
| **Source code** | <https://github.com/raeq/translit> |
| **Releases** | <https://github.com/raeq/translit/releases> |
| **PyPI package** | <https://pypi.org/project/translit-rs/> |
| **Documentation** | <https://translit.readthedocs.io/> |
| **Issue tracker** | <https://github.com/raeq/translit/issues> |
| **Changelog** | <https://github.com/raeq/translit/blob/main/CHANGELOG.md> |

## License

MIT
