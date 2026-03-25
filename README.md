# translit

Unicode text infrastructure for Python: transliteration, normalization, and safety analysis, powered by Rust.

## Features

- **Transliteration**: Unicode → ASCII for Latin, Cyrillic, Greek, CJK (Chinese pinyin, Korean romanization, Japanese kana), and 37 language-specific profiles
- **Slugification**: URL-safe slugs with python-slugify parameter compatibility
- **Filename sanitization**: Cross-platform safe filenames with NFC normalization, path traversal protection, and Windows reserved name handling
- **Text normalization**: NFC/NFD/NFKC/NFKD, confusable homoglyph detection (TR39), full Unicode case folding (1,557 CaseFolding.txt mappings via PHF), whitespace collapse
- **Precompiled pipelines**: `security_clean`, `ml_normalize`, `catalog_key`, `display_clean` for common workflows
- **Grapheme clusters**: Correct user-perceived character counting, splitting, and truncation
- **Hostname safety**: Mixed-script and homoglyph attack detection
- **Encoding detection**: Auto-detect and decode byte sequences to UTF-8 (chardetng)

All text processing is implemented in Rust with O(1) PHF lookups and exposed to Python via PyO3.

## Installation

```bash
pip install translit
```

Requires Python 3.9+ and a Rust toolchain for building from source.

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
from translit import security_clean, ml_normalize, catalog_key

# Security: NFKC → confusables → collapse whitespace → strip bidi
security_clean("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥")  # → "Real text"

# ML/NLP: NFKC → emoji→text → transliterate → strip accents → fold case
ml_normalize("Café ☕ Ünïcödé")  # → "cafe hot beverage unicode"

# Library catalog: NFKC → confusables → transliterate → strip accents → fold case
catalog_key("Москва", lang="ru")  # → "moskva"
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
| Cyrillic | Phonetic romanization | ISO 9:1995 (scholarly, via `strict_iso9=True`) or GOST-based (default) | `Москва` → `Moskva` |
| Greek | Transliteration | BGN/PCGN romanization | `Αθήνα` → `Athena` |
| Chinese (Hanzi) | Romanization | Unihan `kMandarin` (toneless pinyin) | `北京` → `bei jing` |
| Korean (Hangul) | Romanization | Revised Romanization of Korean | `서울` → `seo ul` |
| Japanese (Kana) | Romanization | Modified Hepburn | `ひらがな` → `hiragana` |
| Japanese (Kanji) | Romanization | Falls back to Chinese pinyin readings | `東京` → `dong jing` |
| Arabic | Transliteration | Buckwalter-derived | `مرحبا` → `mrhba` |
| Devanagari | Transliteration | IAST-derived | `नमस्ते` → `namaste` |
| Georgian | Transliteration | National romanization | `თბილისი` → `tbilisi` |
| Armenian | Transliteration | BGN/PCGN | `Երևան` → `Erevan` |

All transliteration is **context-free and character-by-character**, the same approach as AnyAscii/Unidecode. No linguistic analysis, polyphony handling, or phonological rules. See [docs/limitations.md](docs/limitations.md) for trade-offs.

Language-specific profiles (e.g., `lang="de"`) apply **sparse overrides** on top of the default table. For example, German maps `ü` → `ue` instead of the default `u`.

## Language profiles

37 built-in language profiles with ISO 9:1995 scholarly Cyrillic support:

```python
from translit import list_langs, transliterate

print(list_langs())
# ['ar', 'bg', 'ca', 'cs', 'cy', 'da', 'de', 'el', 'es', 'et',
#  'fi', 'fr', 'ga', 'hr', 'hu', 'is', 'it', 'ja', 'ko', 'lt',
#  'lv', 'mt', 'nl', 'no', 'pl', 'pt', 'ro', 'ru', 'sk', 'sl',
#  'sq', 'sr', 'sv', 'tr', 'uk', 'vi', 'zh']

# ISO 9:1995 scholarly transliteration
transliterate("Юрий", strict_iso9=True)  # → "Jurij"
```

## Drop-in replacement

`unidecode()` is a direct alias for `transliterate()` with default settings:

```python
from translit import unidecode

unidecode("café")  # → "cafe"
```

## Documentation

- [User Guide](docs/user-guide/)
- [API Reference](docs/api/)
- [Data Engineering Guide](docs/data-engineer-guide.md)
- [ML / LLM Pipeline Guide](docs/ml-pipeline-guide.md)
- [Security Guide](docs/security-guide.md)
- [Limitations](docs/limitations.md)
- [Migration from python-slugify / anyascii / Unidecode](docs/migration/)

## Architecture

Rust core with compile-time PHF (perfect hash function) tables for O(1) per-character lookup. Exposed to Python via PyO3 with the stable ABI (abi3-py39). The Chinese pinyin table contains 20,924 entries from the Unicode Unihan database; Korean romanization is purely algorithmic (jamo decomposition, ~100 lines of Rust).

## License

MIT
