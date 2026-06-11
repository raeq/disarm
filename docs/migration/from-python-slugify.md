# Migrating from python-slugify

disarm's `slugify()` is parameter-compatible with [python-slugify](https://pypi.org/project/python-slugify/). In most cases, migration requires only changing the import.

## Quick migration

<!--- skip: next -->
```python
# Before
from slugify import slugify

# After
from disarm import slugify
```

All parameters are supported with identical names and defaults:

```python
from disarm import slugify

# These work identically in both libraries
assert slugify("Hello, World!") == 'hello-world'
assert slugify("My Post", separator="_") == 'my_post'
assert slugify("Long Title", max_length=10, word_boundary=True) == 'long-title'
assert slugify("the big fox", stopwords=["the"]) == 'big-fox'
assert slugify("C++ Code", replacements=[("C++", "cpp")]) == 'cpp-code'
```

## Parameter compatibility

| Parameter | python-slugify | disarm | Notes |
|---|---|---|---|
| `text` | ✓ | ✓ | |
| `separator` | `"-"` | `"-"` | |
| `lowercase` | `True` | `True` | |
| `max_length` | `0` | `0` | |
| `word_boundary` | `False` | `False` | |
| `save_order` | `False` | `False` | |
| `stopwords` | `()` | `()` | |
| `regex_pattern` | `None` | `None` | |
| `replacements` | `()` | `()` | |
| `allow_unicode` | `False` | `False` | |
| `entities` | `True` | `True` | |
| `decimal` | `True` | `True` | |
| `hexadecimal` | `True` | `True` | |
| `lang` | ✗ | ✓ | **New** in disarm |

## New features in disarm

### Language-aware slugification

```python
from disarm import slugify

# python-slugify can't do this
assert slugify("Ärger im Büro", lang="de") == 'aerger-im-buero'
```

### Reusable slugifiers

```python
from disarm import Slugifier, UniqueSlugifier

# Pre-configured slugifier
slug = Slugifier(lang="de", separator="_")

# Unique slug generation
unique = UniqueSlugifier()
assert unique("My Post") == 'my-post'
assert unique("My Post") == 'my-post-1'
```

## awesome-slugify migration

[awesome-slugify](https://pypi.org/project/awesome-slugify/) users can migrate with zero code changes — disarm provides drop-in `Slugify` and `UniqueSlugify` classes that accept awesome-slugify's parameter names.

### Drop-in replacement (no code changes needed)

<!--- skip: next -->
```python
# Before
from slugify import slugify, Slugify, UniqueSlugify

# After — same class names, same parameter names
from disarm import Slugify, UniqueSlugify

custom = Slugify(to_lower=True)
custom("Hello World")  # "hello-world"

unique = UniqueSlugify()
unique("My Post")   # "My-Post"
unique("My Post")   # "My-Post-1"
```

### awesome-slugify parameter compatibility

| awesome-slugify | disarm `Slugify` | Notes |
|---|---|---|
| `to_lower` | ✓ (maps to `lowercase`) | Both names accepted |
| `separator` | ✓ | Identical |
| `max_length` | ✓ | Identical |
| `stop_words` | ✓ (maps to `stopwords`) | Both names accepted |
| `safe_chars` | ✓ (best-effort) | Approximated via post-processing |
| `capitalize` | ✓ | Uppercases first letter of result |
| `pretranslate` | ✓ (dict only) | Maps to `replacements`; callable form not supported |
| `translate` | ⚠ ignored | disarm uses built-in engine; use `lang` instead |
| `fold_abbrs` | ⚠ ignored | Deprecated warning issued |

### awesome-slugify attribute-style configuration

awesome-slugify allows setting properties after construction. disarm supports this:

```python
from disarm import Slugify

my_slugify = Slugify()
my_slugify.to_lower = True
my_slugify.stop_words = ("a", "an", "the")
my_slugify.max_length = 200
my_slugify.separator = "_"
my_slugify.pretranslate = {"©": "c", "®": "r"}

assert my_slugify("Hello © World") == 'hello_c_world'
```

### Preconfigured instances

awesome-slugify ships preconfigured instances. disarm provides equivalent drop-in replacements:

<!--- skip: next -->
```python
# awesome-slugify                    # disarm equivalent
from slugify import slugify_url      from disarm import slugify_url
from slugify import slugify_filename from disarm import slugify_filename
from slugify import slugify_unicode  from disarm import slugify_unicode
from slugify import slugify_ru       from disarm import slugify_ru
from slugify import slugify_de       from disarm import slugify_de
from slugify import slugify_el       from disarm import slugify_el
```

| Instance | Configuration |
|---|---|
| `slugify_url` | `to_lower=True`, `stop_words=("a", "an", "the")`, `max_length=200` |
| `slugify_filename` | `separator="_"`, `safe_chars="-."`, `max_length=255` |
| `slugify_unicode` | `allow_unicode=True` |
| `slugify_ru` | Russian transliteration via `lang="ru"` |
| `slugify_de` | German transliteration via `lang="de"` (ä→ae, ö→oe, ü→ue) |
| `slugify_el` | Greek transliteration via `lang="el"` |

### Native disarm classes

If you prefer disarm's native API (which offers more features), use `Slugifier` and `UniqueSlugifier`:

```python
from disarm import Slugifier, UniqueSlugifier

custom = Slugifier(lowercase=True, lang="de")
assert custom("Ärger im Büro") == 'aerger-im-buero'

unique = UniqueSlugifier()
assert unique("My Post") == 'my-post'
assert unique("My Post") == 'my-post-1'
```

### What's different

- **`translate` parameter**: awesome-slugify lets you swap in a custom transliteration function. disarm always uses its built-in Rust transliteration engine, which is faster and covers more scripts. Use the `lang` parameter for language-specific rules.
- **`pretranslate` callables**: awesome-slugify accepts both dicts and callables for `pretranslate`. disarm only accepts dicts (mapped to `replacements`). Callable pretranslate triggers a deprecation warning.
- **`safe_chars`**: awesome-slugify preserves these characters through the pipeline. disarm approximates this with best-effort post-processing. For precise control, use `regex_pattern` instead.
- **Default `to_lower`**: awesome-slugify defaults to `to_lower=False`; the disarm `Slugify` class matches this for compatibility. Note that disarm's native `slugify()` function and `Slugifier` class default to `lowercase=True` (matching python-slugify).
