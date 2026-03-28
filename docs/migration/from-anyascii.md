# Migrating from anyascii

translit's `transliterate()` replaces [anyascii](https://pypi.org/project/anyascii/) for Unicode-to-ASCII conversion.

## Quick migration

```python
# Before
from anyascii import anyascii
result = anyascii("café")

# After
from translit import transliterate
result = transliterate("café")
```

Or use the compatibility alias:

```python
from translit import unidecode as anyascii
result = anyascii("café")
```

## API comparison

| anyascii | translit | Notes |
|---|---|---|
| `anyascii(s)` | `transliterate(s)` | |
| — | `transliterate(s, lang="de")` | **New**: language profiles |
| — | `transliterate(s, errors="ignore")` | **New**: error modes |
| — | `transliterate(s, errors="preserve")` | **New**: preserve unmapped |

## Behavioral differences

### Transliteration approach

anyascii and translit both provide Unicode → ASCII transliteration, but they use different lookup tables. The core Latin-script mappings are very similar, but edge cases may differ. A [detailed character-level comparison](../architecture/transliteration-comparison.md) across all 65 supported languages shows:

- **49,089 codepoints** across all Unicode blocks tested comprehensively (no sampling)
- **48,297** mapped by translit vs **48,761** by anyascii — anyascii has broader coverage of some extended script blocks, while translit provides language-aware romanization with 65 language profiles and 1,046 characters only translit maps
- Most differences are systematic: CJK pinyin casing, Korean romanization, and language-specific national standards

```python
# Common cases — identical
anyascii("café")    # => "cafe"
transliterate("café")  # => "cafe"

# CJK — may differ in romanization style
anyascii("北京")       # romanization varies
transliterate("北京")  # => "bei jing"
```

### Language awareness

anyascii has no language parameter. translit provides 65 language-specific profiles:

```python
from translit import transliterate

# anyascii can't do this
transliterate("München", lang="de")  # => "Muenchen"
transliterate("Malmö", lang="sv")    # => "Malmoe"
```

### Error handling

anyascii silently drops characters with no mapping. translit gives you control:

```python
from translit import transliterate

transliterate("♠", errors="replace", replace_with="?")  # => "?"
transliterate("♠", errors="ignore")                      # => ""
transliterate("♠", errors="preserve")                    # => "♠"
```

## New features in translit

Beyond basic transliteration, translit also provides:

- `slugify()` — URL slug generation
- `sanitize_filename()` — OS-safe filenames
- `normalize_confusables()` — homoglyph normalization
- `TextPipeline` — composable text processing
- `strip_accents()`, `fold_case()` — granular text cleaning

All in a single package with one consistent API.
