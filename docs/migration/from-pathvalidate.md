# Migrating from pathvalidate

translit's `sanitize_filename()` replaces [pathvalidate](https://pypi.org/project/pathvalidate/) for filename sanitization use cases.

## Quick migration

```python
# Before
from pathvalidate import sanitize_filename

# After
from translit import sanitize_filename
```

## API comparison

| pathvalidate | translit | Notes |
|---|---|---|
| `sanitize_filename(s)` | `sanitize_filename(s)` | Same function name |
| `sanitize_filepath(s)` | Not available | translit handles filenames only |
| `validate_filename(s)` | Not available | translit sanitizes rather than validates |
| `validate_filepath(s)` | Not available | |
| `is_valid_filename(s)` | Not available | |

## Parameter mapping

```python
# pathvalidate
sanitize_filename("my<file>.txt", replacement_text="_")
sanitize_filename("my<file>.txt", platform="Windows")

# translit
sanitize_filename("my<file>.txt", separator="_")
sanitize_filename("my<file>.txt", platform="windows")  # lowercase
```

| pathvalidate parameter | translit parameter | Notes |
|---|---|---|
| `replacement_text` | `separator` | Different name |
| `platform` | `platform` | Values are lowercase in translit |
| `max_len` | `max_length` | Different name |
| — | `lang` | **New**: language-aware transliteration |
| — | `preserve_extension` | **New**: protect file extension during truncation |

## New features in translit

### Unicode transliteration

pathvalidate strips or replaces non-ASCII characters. translit transliterates them:

```python
# pathvalidate
from pathvalidate import sanitize_filename
sanitize_filename("café résumé.pdf")  # => "caf rsm.pdf" (stripped)

# translit
from translit import sanitize_filename
sanitize_filename("café résumé.pdf")  # => "cafe_resume.pdf" (transliterated)
```

### Language-aware filenames

```python
from translit import sanitize_filename

sanitize_filename("Ärger.txt", lang="de")  # => "Aerger.txt"
sanitize_filename("Ärger.txt")             # => "Arger.txt"
```

### Extension preservation

```python
from translit import sanitize_filename

sanitize_filename("very_long_name.pdf", max_length=15, preserve_extension=True)
# => "very_long_.pdf"  (extension preserved)
```

## What's not covered

translit focuses on filename sanitization. pathvalidate also provides:

- **File path sanitization** (`sanitize_filepath`) — translit handles filenames only, not full paths
- **Validation** (`validate_filename`, `is_valid_filename`) — translit sanitizes rather than validates

If you need path sanitization or validation, you may need to keep pathvalidate for those specific functions.
