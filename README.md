# translit

[![Documentation](https://readthedocs.org/projects/translit/badge/?version=latest)](https://translit.readthedocs.io/en/latest/) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/raeq/translit/blob/main/LICENSE)

Unicode text infrastructure for Python: transliteration, normalization, and safety analysis, powered by Rust.

**[Documentation](docs/index.md)** | **[API Reference](docs/api/index.md)** | **[PyPI](https://pypi.org/project/translit-rs/)**

## Demo

**[Try translit in your browser](https://translit-web.pages.dev/)**

## Features

- **[Transliteration](docs/user-guide/transliteration.md)**: Unicode → ASCII for Latin, Cyrillic, Greek, CJK (Chinese pinyin, Korean romanization, Japanese kana), and [65 language-specific profiles](docs/user-guide/language-support.md)
- **[Slugification](docs/user-guide/slugification.md)**: URL-safe slugs with [python-slugify parameter compatibility](docs/migration/from-python-slugify.md)
- **[Filename sanitization](docs/user-guide/filenames.md)**: Cross-platform safe filenames with NFC normalization, path traversal protection, and Windows reserved name handling
- **[Text normalization](docs/user-guide/normalization.md)**: NFC/NFD/NFKC/NFKD, [confusable homoglyph detection](docs/user-guide/confusables.md) (TR39), full Unicode case folding (1,557 CaseFolding.txt mappings via PHF), [whitespace collapse](docs/user-guide/text-cleaning.md)
- **[Precompiled pipelines](docs/api/pipelines.md)**: `security_clean`, `ml_normalize`, `catalog_key`, `display_clean`, `search_key`, `sort_key`, `sanitize_user_input` for common workflows
- **[Grapheme clusters](docs/user-guide/graphemes.md)**: Correct user-perceived character counting, splitting, and truncation
- **[Hostname safety](docs/api/predicates.md#is_safe_hostname)**: Mixed-script and homoglyph attack detection
- **[Encoding detection](docs/api/encoding.md)**: Auto-detect and decode byte sequences to UTF-8 (chardetng)
- **[Reverse transliteration](docs/user-guide/language-support.md#reverse-transliteration)**: Latin → native script for Russian, Ukrainian, Greek via `target` parameter

All text processing is implemented in Rust with O(1) PHF lookups and exposed to Python via PyO3.

## Installation

```bash
pip install translit-rs
```

The package installs as `translit-rs` on PyPI but imports as `translit`:

```python
import translit  # not translit_rs
```

Requires Python 3.9+. Wheels are available for Linux, macOS, and Windows.

## Quick start

```python
from translit import transliterate, slugify, sanitize_filename

# Latin/Cyrillic/Greek
transliterate("café")          # → "cafe"
transliterate("Москва")        # → "Moskva"
transliterate("Ünïcödé")       # → "Unicode"

# Chinese (Hanzi → Pinyin)
transliterate("北京市")         # → "bei jing shi"
slugify("北京烤鸭")            # → "bei-jing-kao-ya"

# Korean (Hangul → Revised Romanization)
transliterate("서울")           # → "seo ul"
slugify("대한민국")            # → "dae-han-min-gug"

# Japanese (Hiragana/Katakana → Hepburn)
transliterate("ひらがな")       # → "hiragana"
transliterate("カタカナ")       # → "katakana"

# Language-specific transliteration
transliterate("Ärger", lang="de")  # → "Aerger"
transliterate("Київ", lang="uk")   # → "Kyiv"

# Auto-detect language from script
transliterate("Москва", lang="auto")  # → "Moskva" (detects Cyrillic → Russian)
transliterate("ภาษาไทย", lang="auto")  # → Thai transliteration (detects Thai)

# Reverse transliteration (Latin → native script)
transliterate("Moskva", target="ru")   # → "Москва"
transliterate("Athina", target="el")   # → "Αθηνα"

# Slugification
slugify("Hello World!")            # → "hello-world"
slugify("café au lait")           # → "cafe-au-lait"

# Filename sanitization
sanitize_filename("my file<>.txt")         # → "my_file.txt"
sanitize_filename("CON.txt")               # → "_CON.txt"
sanitize_filename("../../etc/passwd")      # → ".etc_passwd"
```

## CJK transliteration

Chinese characters are mapped to toneless pinyin from the Unicode Unihan `kMandarin` field, covering the full CJK Unified Ideographs block (U+4E00–U+9FFF, 20,924 characters). Korean Hangul syllables are algorithmically decomposed into jamo and romanized using the Revised Romanization standard (all 11,172 precomposed syllables). Japanese hiragana and katakana use Modified Hepburn; kanji fall back to Chinese pinyin readings.

This is context-free, character-by-character transliteration, the same approach as Unidecode. See [docs/limitations.md](docs/limitations.md) for details on polyphony, phonological rules, and other trade-offs.

## Precompiled pipelines

```python
from translit import security_clean, ml_normalize, catalog_key, sanitize_user_input

# Security: NFKC → confusables → strip bidi → collapse whitespace
security_clean("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥")  # → "Real text"

# ML/NLP: NFKC → emoji→text → transliterate → strip accents → fold case
ml_normalize("Café ☕ Ünïcödé")  # → "cafe hot beverage unicode"

# Library catalog: NFKC → transliterate → confusables → strip accents → fold case
catalog_key("Москва", lang="ru")  # → "moskva"
catalog_key("ΩMEGA  café")        # → "omega cafe"

# Web input: NFKC → strip zalgo → confusables → strip bidi → collapse whitespace
sanitize_user_input("p\u0430ypal")  # → "paypal" (homoglyph neutralized)
```

## Text builder

```python
from translit import Text

result = (
    Text("Ünïcödé Café ☕")
    .normalize("NFKC")
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
| `translit` | Core transforms | `transliterate`, `slugify`, `Text`, `TextPipeline` |
| `translit.normalization` | Unicode normalization | `normalize`, `strip_accents`, `fold_case`, `collapse_whitespace` |
| `translit.security` | Safety analysis | `is_confusable`, `is_mixed_script`, `is_safe_hostname`, `security_clean` |
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

## Script policies

Transliteration applies different policies depending on the script. This table documents what each script does and which standard it follows.

| Script | Policy | Standard / Source | Example |
|---|---|---|---|
| Latin (accented) | Accent stripping | Unicode NFKD decomposition | `é` → `e` |
| Cyrillic | Phonetic romanization | BGN/PCGN (default), ISO 9:1995 (`strict_iso9=True`), GOST R 7.0.34 (`gost7034=True`) | `Москва` → `Moskva` |
| Greek | Transliteration | BGN/PCGN romanization | `Αθήνα` → `Athena` |
| Chinese (Hanzi) | Romanization | Unihan `kMandarin` (toneless pinyin) | `北京` → `bei jing` |
| Korean (Hangul) | Romanization | Revised Romanization of Korean | `서울` → `seo ul` |
| Japanese (Kana) | Romanization | Modified Hepburn | `ひらがな` → `hiragana` |
| Japanese (Kanji) | Romanization | Falls back to Chinese pinyin readings | `東京` → `dong jing` |
| Arabic | Transliteration | Buckwalter-derived | `مرحبا` → `mrhba` |
| Hebrew | Transliteration | Common Israeli | `שלום` → `shlvm` |
| Devanagari | Transliteration | UNGEGN/IAST-derived | `नमस्ते` → `namaste` |
| Bengali | Transliteration | UNGEGN-derived | `কলকাতা` → `kalakata` |
| Tamil | Transliteration | UNGEGN-derived | `தமிழ்` → `tamizh` |
| Telugu | Transliteration | UNGEGN-derived | `తెలుగు` → `telugu` |
| Gujarati | Transliteration | UNGEGN-derived | `ગુજરાતી` → `gujarati` |
| Kannada | Transliteration | UNGEGN-derived | `ಕನ್ನಡ` → `kannada` |
| Malayalam | Transliteration | UNGEGN-derived | `മലയാളം` → `malayalam` |
| Odia | Transliteration | UNGEGN-derived | `ଓଡିଆ` → `odia` |
| Sinhala | Transliteration | UNGEGN-derived | `සිංහල` → `simhala` |
| Gurmukhi | Transliteration | UNGEGN-derived | `ਪੰਜਾਬੀ` → `panjabi` |
| Thai | Transliteration | RTGS-derived | `สวัสดี` → `sawatdi` |
| Lao | Transliteration | BGN/PCGN-derived | `ລາວ` → `lao` |
| Georgian | Transliteration | National romanization | `თბილისი` → `tbilisi` |
| Armenian | Transliteration | BGN/PCGN | `Երևան` → `Eryevan` |

All transliteration is **context-free and character-by-character**, the same approach as AnyAscii/Unidecode. No linguistic analysis, polyphony handling, or phonological rules. See [docs/limitations.md](docs/limitations.md) for trade-offs.

Language-specific profiles (e.g., `lang="de"`) apply **sparse overrides** on top of the default table. For example, German maps `ü` → `ue` instead of the default `u`.

## Language profiles

[65 built-in language profiles](docs/user-guide/language-support.md) with ISO 9:1995 scholarly Cyrillic support and 10 Indic scripts:

```python
from translit import list_langs, transliterate

print(list_langs())
# ['am', 'ar', 'as', 'bg', 'bn', 'bo', 'ca', 'cs', 'cy', 'da', 'de', 'dv', 'el',
#  'es', 'et', 'fa', 'fi', 'fr', 'ga', 'gu', 'he', 'hi', 'hr', 'hu', 'hy',
#  'is', 'it', 'ja', 'jv', 'ka', 'km', 'kn', 'ko', 'lo', 'lt', 'lv', 'ml', 'mn',
#  'mr', 'mt', 'my', 'ne', 'nl', 'no', 'or', 'pa', 'pl', 'pt', 'ro', 'ru', 'sa',
#  'si', 'sk', 'sl', 'sq', 'sr', 'sv', 'ta', 'te', 'th', 'tr', 'uk', 'vi', 'zh']

# ISO 9:1995 scholarly transliteration
transliterate("Юрий", strict_iso9=True)  # → "Jurij"
```

## Performance

translit is compiled Rust with O(1) compile-time perfect hash tables — no regex, no per-character Python iteration, no runtime data loading.

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

`sanitize_filename()` also accepts `replacement_text` and `max_len` kwargs for pathvalidate compatibility, and `is_confusable()` accepts `greedy` for confusable_homoglyphs compatibility. See [migration guides](docs/migration/) for details.

## Documentation

- [User Guide](docs/user-guide/)
- [API Reference](docs/api/)
- [CLI](docs/cli.md) — command-line usage, piping, and shell integration
- [Docker](docs/docker.md) — run translit from a container, no Python install needed
- [Limitations](docs/limitations.md)
- [Migration from python-slugify / anyascii / Unidecode](docs/migration/)

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
