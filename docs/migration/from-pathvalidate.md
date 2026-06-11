# Migrating from pathvalidate

disarm's `sanitize_filename()` replaces [pathvalidate](https://pypi.org/project/pathvalidate/) for filename sanitization use cases.

## Quick migration

<!--- skip: next -->
```python
# Before
from pathvalidate import sanitize_filename

# After
from disarm import sanitize_filename
```

## API comparison

| pathvalidate | disarm | Notes |
|---|---|---|
| `sanitize_filename(s)` | `sanitize_filename(s)` | Same function name |
| `sanitize_filepath(s)` | Not available | disarm handles filenames only |
| `validate_filename(s)` | Not available | disarm sanitizes rather than validates |
| `validate_filepath(s)` | Not available | |
| `is_valid_filename(s)` | Not available | |

## Parameter mapping

```python
from disarm import sanitize_filename

# pathvalidate — these work directly in disarm (compatibility aliases)
assert sanitize_filename("my<file>.txt", replacement_text="_") == 'my_file.txt'
assert sanitize_filename("my<file>.txt", max_len=100) == 'my_file.txt'

# disarm native names
assert sanitize_filename("my<file>.txt", separator="_") == 'my_file.txt'
assert sanitize_filename("my<file>.txt", max_length=100) == 'my_file.txt'

# platform values are lowercase in disarm
assert sanitize_filename("my<file>.txt", platform="windows") == 'my_file.txt'
```

| pathvalidate parameter | disarm parameter | Notes |
|---|---|---|
| `replacement_text` | `separator` | Both accepted — `replacement_text` maps to `separator` |
| `platform` | `platform` | Values are lowercase in disarm |
| `max_len` | `max_length` | Both accepted — `max_len` maps to `max_length` |
| — | `lang` | **New**: language-aware transliteration |
| — | `preserve_extension` | **New**: protect file extension during truncation |

## New features in disarm

### Unicode transliteration

pathvalidate strips or replaces non-ASCII characters. disarm transliterates them:

<!--- skip: next -->
```python
# pathvalidate
from pathvalidate import sanitize_filename
sanitize_filename("café résumé.pdf")  # "caf rsm.pdf" (stripped)

# disarm
from disarm import sanitize_filename
sanitize_filename("café résumé.pdf")  # "cafe_resume.pdf" (transliterated)
```

### Language-aware filenames

```python
from disarm import sanitize_filename

assert sanitize_filename("Ärger.txt", lang="de") == 'Aerger.txt'
assert sanitize_filename("Ärger.txt") == 'Arger.txt'
```

### Extension preservation

```python
from disarm import sanitize_filename

assert sanitize_filename("very_long_name.pdf", max_length=15, preserve_extension=True) == 'very_long_n.pdf'
```

## What's not covered

disarm focuses on filename sanitization. pathvalidate also provides:

- **File path sanitization** (`sanitize_filepath`) — disarm handles filenames only, not full paths
- **Validation** (`validate_filename`, `is_valid_filename`) — disarm sanitizes rather than validates

If you need path sanitization or validation, you may need to keep pathvalidate for those specific functions.
