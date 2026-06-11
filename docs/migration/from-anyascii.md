# Migrating from anyascii

disarm's `transliterate()` replaces [anyascii](https://pypi.org/project/anyascii/) for Unicode-to-ASCII conversion.

## Quick migration

<!--- skip: next -->
```python
# Before
from anyascii import anyascii
result = anyascii("café")

# After
from disarm import transliterate
result = transliterate("café")
```

Or use the compatibility alias:

```python
from disarm import unidecode as anyascii
result = anyascii("café")
```

## API comparison

| anyascii | disarm | Notes |
|---|---|---|
| `anyascii(s)` | `transliterate(s)` | |
| — | `transliterate(s, lang="de")` | **New**: language profiles |
| — | `transliterate(s, errors="ignore")` | **New**: error modes |
| — | `transliterate(s, errors="preserve")` | **New**: preserve unmapped |

## Behavioral differences

### Transliteration approach

anyascii and disarm both provide Unicode → ASCII transliteration, but they use different lookup tables. The core Latin-script mappings are very similar, but edge cases may differ. A [detailed character-level comparison](../architecture/transliteration-comparison.md) across all 83 supported languages shows:

- **49,089 codepoints** across all Unicode blocks tested comprehensively (no sampling)
- **48,415** mapped by disarm vs **48,761** by anyascii — anyascii has broader coverage of some extended script blocks, while disarm provides language-aware romanization with 83 language profiles and 1,136 characters only disarm maps
- Most differences are systematic: CJK pinyin casing, Korean romanization, and language-specific national standards

```python
from disarm import transliterate

# Common cases — identical
assert anyascii("café") == 'cafe'
assert transliterate("café") == 'cafe'

# CJK — may differ in romanization style
anyascii("北京")       # romanization varies
assert transliterate("北京") == 'bei jing'
```

### Language awareness

anyascii has no language parameter. disarm provides 83 language-specific profiles:

```python
from disarm import transliterate

# anyascii can't do this
assert transliterate("München", lang="de") == 'Muenchen'
assert transliterate("Malmö", lang="sv") == 'Malmoe'
```

### Error handling

anyascii silently drops characters with no mapping. disarm gives you control:

```python
from disarm import transliterate

assert transliterate("♠", errors="replace", replace_with="?") == '?'
assert transliterate("♠", errors="ignore") == ''
assert transliterate("♠", errors="preserve") == '♠'
```

## New features in disarm

Beyond basic transliteration, disarm also provides:

- `slugify()` — URL slug generation
- `sanitize_filename()` — OS-safe filenames
- `normalize_confusables()` — homoglyph normalization
- `TextPipeline` — composable text processing
- `strip_accents()`, `fold_case()` — granular text cleaning

All in a single package with one consistent API.
