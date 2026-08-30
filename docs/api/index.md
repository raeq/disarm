# API Reference

Complete reference for all public functions, classes, and types in disarm.

## Modules

| Module | Description |
|---|---|
| [Core Transforms](transforms.md) | Text transformation functions |
| [Precompiled Pipelines](pipelines.md) | Ready-to-use multi-step pipelines |
| [Predicates](predicates.md) | Text inspection functions |
| [Grapheme Clusters](graphemes.md) | User-perceived character operations |
| [Encoding](encoding.md) | Byte sequence detection and decoding |
| [Classes](classes.md) | Text, Slugifier, UniqueSlugifier, TextPipeline |
| [Enums & Types](enums.md) | Script, NF, EmojiProvider, type aliases |
| [Language Profiles](language-profiles.md) | Language listing and registration |
| [Exceptions](exceptions.md) | DisarmError |

## Module constants

```python
import disarm

# The installed distribution's version.
assert isinstance(disarm.__version__, str)

# The Unicode `confusables.txt` release the bundled confusable tables were folded
# from. This is the *data* vintage and moves independently of the release number —
# a confusable fold is only as current as its table.
assert disarm.CONFUSABLES_VERSION.count(".") >= 1
assert all(part.isdigit() for part in disarm.CONFUSABLES_VERSION.split("."))
```

Deliberately not named `UNICODE_VERSION`: disarm's bundled tables do not all track one
Unicode release (case folding is 16.0, East Asian width 15.1.0), so a library-wide name
would be wrong for most of them. See [Provenance](../provenance.md) for the full table
and the accessor in every binding.

## Import convention

All public symbols are available from the top-level package:

```python
from disarm import transliterate, slugify, Script, LANG_DE
```

Domain-specific namespaces are also available:

```python
from disarm.security import is_confusable, canonicalize
from disarm.normalization import fold_case, strip_accents
from disarm.codec import decode_to_utf8, detect_encoding
from disarm.files import sanitize_filename
```

## Compatibility aliases

disarm provides drop-in aliases for several legacy libraries:

```python
# Unidecode / text-unidecode
from disarm import unidecode

# str.casefold() / sklearn
from disarm import casefold, remove_accents

# awesome-slugify
from disarm import Slugify, UniqueSlugify
from disarm import slugify_url, slugify_filename, slugify_unicode
from disarm import slugify_ru, slugify_de, slugify_el

# Elasticsearch/Solr
from disarm import ascii_fold
```

See [Classes → Compatibility aliases](classes.md#compatibility-aliases-awesome-slugify) and the [migration guides](../migration/index.md) for details.

## Type annotations

disarm is fully typed. A `py.typed` marker file and `.pyi` stub files are included for mypy and pyright support.

<!--- skip: next -->
```python
# All functions have full type annotations
reveal_type(transliterate("test"))  # str
reveal_type(detect_scripts("test"))  # list[Script]
reveal_type(is_ascii("test"))  # bool
```
