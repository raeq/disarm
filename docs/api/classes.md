# Classes

Stateful objects and builders for repeated or specialized text processing.

## Text

::: translit.Text

### Usage

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
# => "unicode cafe hot beverage"
```

Each transform method returns a **new** `Text` instance (immutable semantics, matching Python `str`). Predicates return their native type (`bool`, `list`) and do not chain.

### Chainable transforms

All core transforms are available as methods:

| Method | Returns | Description |
|---|---|---|
| `.normalize(form=)` | `Text` | Unicode normalization |
| `.normalize_confusables()` | `Text` | Replace confusable homoglyphs |
| `.strip_accents()` | `Text` | Remove diacritical marks |
| `.transliterate(lang=, ...)` | `Text` | Unicode → ASCII |
| `.fold_case()` | `Text` | Full Unicode case folding |
| `.collapse_whitespace()` | `Text` | Normalize whitespace |
| `.slugify(...)` | `Text` | Generate URL-safe slug |
| `.sanitize_filename(...)` | `Text` | Safe filename |
| `.demojize(...)` | `Text` | Emoji → text descriptions |
| `.strip_bidi()` | `Text` | Strip bidi overrides |
| `.security_clean()` | `Text` | Security pipeline |
| `.ml_normalize(...)` | `Text` | ML/NLP pipeline |
| `.display_clean()` | `Text` | Display cleanup pipeline |
| `.catalog_key(...)` | `Text` | Catalog key pipeline |
| `.grapheme_truncate(n)` | `Text` | Truncate to n graphemes |

### Non-chaining predicates

| Method | Returns | Description |
|---|---|---|
| `.is_ascii()` | `bool` | All characters are ASCII |
| `.is_normalized(form=)` | `bool` | Already in normalization form |
| `.is_confusable()` | `bool` | Contains confusable homoglyphs |
| `.is_mixed_script()` | `bool` | Multiple Unicode scripts |
| `.detect_scripts()` | `list[Script]` | Scripts present |
| `.grapheme_len()` | `int` | User-perceived character count |
| `.grapheme_split()` | `list[str]` | Split into grapheme clusters |

### Result extraction

Use `.value` or `str()` to extract the underlying string:

```python
text = Text("café").strip_accents()
text.value   # => "cafe"
str(text)    # => "cafe"
```

`Text` supports `==`, `hash()`, `len()`, and `bool()` — comparing against the underlying string value.

---

## Slugifier

::: translit.Slugifier

### Usage

```python
from translit import Slugifier

slug = Slugifier(separator="_", lang="de", max_length=50)
slug("Ärger im Büro")     # => "aerger_im_buero"
slug("Über den Wolken")   # => "ueber_den_wolken"

# Auto-detect language from script
auto_slug = Slugifier(lang="auto")
auto_slug("Москва")       # => "moskva" (detects Cyrillic → Russian)
```

Accepts all the same parameters as `slugify()`. Construct once, call many times.

---

## UniqueSlugifier

::: translit.UniqueSlugifier

### Usage

```python
from translit import UniqueSlugifier

unique = UniqueSlugifier()
unique("My Post")   # => "my-post"
unique("My Post")   # => "my-post-1"
unique("My Post")   # => "my-post-2"

unique.reset()      # clear seen slugs
unique("My Post")   # => "my-post"
```

### External uniqueness check

```python
def exists_in_db(slug: str) -> bool:
    return db.slugs.filter(slug=slug).exists()

unique = UniqueSlugifier(check=exists_in_db)
```

The `check` callback is called for each candidate slug. If it returns `True`, the slugifier increments the suffix and tries again.

---

## TextPipeline

::: translit.TextPipeline

### Usage

```python
from translit import TextPipeline

pipe = TextPipeline(
    normalize="NFC",
    confusables=True,
    strip_accents=True,
    fold_case=True,
    collapse_whitespace=True,
)

pipe("  Héllo Wörld  ")  # => "hello world"
```

### Execution order

Operations execute in this fixed order regardless of construction order:

1. Normalize → 2. Confusables → 3. Demojize → 4. Strip accents → 5. Transliterate → 6. Fold case → 7. Collapse whitespace

### Performance

The pipeline is pre-compiled at construction. Enabled steps are stored as a bitflag set — only enabled steps execute at call time.

---

## Compatibility aliases (awesome-slugify)

These classes provide drop-in replacements for awesome-slugify's `Slugify` and `UniqueSlugify`. They accept awesome-slugify's parameter names and map them to native translit parameters.

See the [migration guide](../migration/from-python-slugify.md#awesome-slugify-migration) for full details.

### Slugify

::: translit.Slugify

```python
from translit import Slugify

# Same API as awesome-slugify
custom = Slugify(to_lower=True)
custom("Hello World")  # => "hello-world"

# Attribute-style configuration (awesome-slugify pattern)
s = Slugify()
s.to_lower = True
s.stop_words = ("the", "a")
s.max_length = 200
s("The Big Fox")  # => "big-fox"
```

Accepts both awesome-slugify parameter names (`to_lower`, `stop_words`, `safe_chars`, `capitalize`, `pretranslate`) and native translit names (`lowercase`, `stopwords`, `replacements`).

Defaults to `to_lower=False` (matching awesome-slugify). For python-slugify compatibility (which defaults to `lowercase=True`), use the native `Slugifier` class or the `slugify()` function.

---

### UniqueSlugify

::: translit.UniqueSlugify

```python
from translit import UniqueSlugify

unique = UniqueSlugify(to_lower=True)
unique("My Post")   # => "my-post"
unique("My Post")   # => "my-post-1"

unique.reset()
unique("My Post")   # => "my-post"
```

Extends `Slugify` with uniqueness tracking. Accepts `uids` and `unique_check` parameters from awesome-slugify.

---

### Preconfigured instances

Drop-in replacements for awesome-slugify's preconfigured slugifiers:

```python
from translit import (
    slugify_url,       # lowercase, strips articles, max 200 chars
    slugify_filename,  # underscore separator, preserves -., max 255 chars
    slugify_unicode,   # keeps non-ASCII letters
    slugify_ru,        # Russian transliteration
    slugify_de,        # German transliteration (ä→ae, ö→oe, ü→ue)
    slugify_el,        # Greek transliteration
)

slugify_url("The Big Fox")        # => "big-fox"
slugify_de("Ärger im Büro")       # => "Aerger-im-Buero"
slugify_filename("My Report.pdf") # => "My_Report.pdf"
```
