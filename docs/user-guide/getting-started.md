# Getting Started

## Installation

Install translit from PyPI:

```bash
pip install translit-rs
```

Pre-built wheels are available for:

- **Linux** (x86_64, aarch64) — manylinux
- **macOS** (x86_64, arm64) — universal2
- **Windows** (x86_64)
- **Python 3.9–3.14+** (abi3 stable ABI)

No Rust toolchain is needed for installation — the compiled extension is included in the wheel.

## Basic usage

```python
import translit

# Transliterate Unicode to ASCII
translit.transliterate("café")          # => "cafe"

# Generate URL slugs
translit.slugify("Hello, World!")       # => "hello-world"

# Normalize Unicode
translit.normalize("é", form="NFC")    # => "é" (single codepoint)

# Detect mixed scripts
translit.is_mixed_script("Неllo")      # => True

# Sanitize filenames
translit.sanitize_filename("my:file<2>.txt")  # => "my_file_2.txt"
```

## Core concepts

### Transforms

Transforms take a string and return a new string. They never mutate the input.

| Function | Purpose |
|---|---|
| `transliterate()` | Unicode → ASCII conversion |
| `slugify()` | URL-safe slug generation |
| `normalize()` | Unicode normalization (NFC/NFD/NFKC/NFKD) |
| `normalize_confusables()` | Replace homoglyphs with target-script equivalents |
| `sanitize_filename()` | OS-safe filename generation |
| `strip_accents()` | Remove diacritical marks |
| `fold_case()` | Unicode case folding |
| `collapse_whitespace()` | Normalize whitespace variants |

### Predicates

Predicates return `True` or `False` without transforming the input.

| Function | Purpose |
|---|---|
| `is_ascii()` | All characters in U+0000–U+007F? |
| `is_normalized()` | Already in specified normalization form? |
| `is_mixed_script()` | Contains multiple Unicode scripts? |
| `is_confusable()` | Contains confusable homoglyphs? |
| `detect_scripts()` | List scripts present in text |

### Stateful objects

| Class | Purpose |
|---|---|
| `Slugifier` | Reusable configured slugifier |
| `UniqueSlugifier` | Slugifier with deduplication |
| `TextPipeline` | Composable multi-step text processor |

## Language-aware processing

Many functions accept a `lang` parameter for language-specific behavior:

```python
from translit import transliterate, slugify

# German: ü → ue
transliterate("München", lang="de")   # => "Muenchen"

# Default: ü → u
transliterate("München")              # => "Munchen"

# Slugify with language rules
slugify("Ärger", lang="de")           # => "aerger"
```

See [Language Support](language-support.md) for the full list of 83 built-in profiles.

## Error handling

All translit functions raise `TranslitError` on invalid arguments:

```python
from translit import normalize, TranslitError

try:
    normalize("text", form="INVALID")
except TranslitError as e:
    print(e)  # => "Invalid normalization form: INVALID"
```

## Next steps

- [Transliteration](transliteration.md) — deep dive into Unicode → ASCII conversion
- [Slugification](slugification.md) — URL slug generation with full python-slugify compatibility
- [Text Pipeline](pipeline.md) — compose multi-step cleaning in a single call
