# Migrating from Unidecode

translit provides a drop-in replacement for both [Unidecode](https://pypi.org/project/Unidecode/) and [text-unidecode](https://pypi.org/project/text-unidecode/).

## Quick migration

### Option 1: Drop-in alias

```python
# Before
from unidecode import unidecode

# After — one-line change
from translit import unidecode
```

The `translit.unidecode()` function is a direct alias for `transliterate()` with default settings. It accepts a single string argument and returns ASCII text.

### Option 2: Use transliterate directly

```python
# Before
from unidecode import unidecode
result = unidecode("café")

# After
from translit import transliterate
result = transliterate("café")
```

`transliterate()` provides additional features not available in Unidecode:

```python
# Language-specific transliteration
transliterate("München", lang="de")          # => "Muenchen"

# Error handling modes
transliterate("♠", errors="ignore")          # => ""
transliterate("♠", errors="preserve")        # => "♠"
transliterate("♠", errors="replace",
              replace_with="?")              # => "?"
```

## API comparison

| Unidecode | translit | Notes |
|---|---|---|
| `unidecode(s)` | `unidecode(s)` | Direct alias |
| `unidecode(s)` | `transliterate(s)` | Full-featured alternative |
| `unidecode_expect_ascii(s)` | `transliterate(s, errors="replace")` | Default behavior |
| `unidecode_expect_nonascii(s)` | `transliterate(s, errors="preserve")` | Keep unmapped chars |

## Behavioral differences

### Transliteration tables

translit uses its own hand-curated transliteration tables. Most common mappings are identical to Unidecode, but some edge cases may differ:

```python
# Identical in both
unidecode("café")       # => "cafe"
unidecode("北京")       # => "bei jing"

# May differ for obscure characters
# translit aims for more linguistically accurate results
```

### License

| | Unidecode | text-unidecode | translit |
|---|---|---|---|
| License | GPL-2.0 | Artistic-1.0 | MIT |

If your project requires MIT licensing, translit is a safe replacement.

## text-unidecode migration

text-unidecode has the same API as Unidecode. The migration is identical:

```python
# Before
from text_unidecode import unidecode

# After
from translit import unidecode
```
