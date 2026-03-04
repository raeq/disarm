# API Reference

Complete reference for all public functions, classes, and types in translit.

## Modules

| Module | Description |
|---|---|
| [Core Transforms](transforms.md) | 8 functions for text transformation |
| [Predicates](predicates.md) | 5 functions for text inspection |
| [Classes](classes.md) | Slugifier, UniqueSlugifier, TextPipeline, + compat aliases |
| [Enums & Types](enums.md) | Script, NF, type aliases |
| [Language Profiles](language-profiles.md) | Language listing and registration |
| [Exceptions](exceptions.md) | TranslitError |

## Import convention

All public symbols are available from the top-level package:

```python
from translit import transliterate, slugify, Script, LANG_DE
```

## Compatibility aliases

translit provides drop-in aliases for several legacy libraries:

```python
# Unidecode / text-unidecode
from translit import unidecode

# awesome-slugify
from translit import Slugify, UniqueSlugify
from translit import slugify_url, slugify_filename, slugify_unicode
from translit import slugify_ru, slugify_de, slugify_el

# Elasticsearch/Solr
from translit import ascii_fold
```

See [Classes → Compatibility aliases](classes.md#compatibility-aliases-awesome-slugify) and the [migration guides](../migration/index.md) for details.

## Type annotations

translit is fully typed. A `py.typed` marker file and `.pyi` stub files are included for mypy and pyright support.

```python
# All functions have full type annotations
reveal_type(transliterate("test"))  # str
reveal_type(detect_scripts("test")) # list[Script]
reveal_type(is_ascii("test"))       # bool
```
