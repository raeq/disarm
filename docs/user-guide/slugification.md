# Slugification

disarm generates URL-safe slugs from Unicode text. The `slugify` operation is parameter-compatible with [python-slugify](https://pypi.org/project/python-slugify/), so migration requires only changing the import.

## Basic usage

=== "Python"

    ```python
    from disarm import slugify

    assert slugify("Hello, World!") == 'hello-world'
    assert slugify("My Blog Post — Draft #3") == 'my-blog-post-draft-3'
    assert slugify("Ünïcödé Téxt") == 'unicode-text'
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, SlugConfig};

    let cfg = SlugConfig::default();
    assert_eq!(api::slugify("Hello, World!", &cfg), "hello-world");
    assert_eq!(api::slugify("My Blog Post — Draft #3", &cfg), "my-blog-post-draft-3");
    assert_eq!(api::slugify("Ünïcödé Téxt", &cfg), "unicode-text");
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    Disarm.slugify("Hello, World!")           # => "hello-world"
    Disarm.slugify("My Blog Post — Draft #3")  # => "my-blog-post-draft-3"
    Disarm.slugify("Ünïcödé Téxt")             # => "unicode-text"
    ```

## Parameters

### separator

The character used between words (default: `"-"`):

=== "Python"

    ```python
    assert slugify("hello world", separator="_") == 'hello_world'
    assert slugify("hello world", separator=".") == 'hello.world'
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    Disarm.slugify("hello world", separator: "_")  # => "hello_world"
    Disarm.slugify("hello world", separator: ".")  # => "hello.world"
    ```

### lowercase

Whether to lowercase the output (default: `True`):

```python
assert slugify("Hello World", lowercase=False) == 'Hello-World'
```

### max_length

Truncate the slug to a maximum length (default: `0` = unlimited):

```python
assert slugify("a very long title here", max_length=10) == 'a-very-lon'
```

### word_boundary

When combined with `max_length`, truncate at word boundaries:

```python
assert slugify("a very long title here", max_length=10, word_boundary=True) == 'a-very'
```

### stopwords

Words to remove from the slug:

```python
assert slugify("the quick brown fox", stopwords=["the", "brown"]) == 'quick-fox'
```

### regex_pattern

Custom regex pattern for allowed characters:

```python
assert slugify("hello 123 world", regex_pattern=r"[^a-z]+") == 'helloworld'
```

### replacements

Pre-transliteration string replacements:

```python
assert slugify("C++ Programming", replacements=[("C++", "cpp")]) == 'cpp-programming'
```

### allow_unicode

Keep non-ASCII characters in the slug:

```python
assert slugify("日本語テスト", allow_unicode=True) == '日本語テスト'
```

### lang

Language profile for transliteration:

=== "Python"

    ```python
    assert slugify("Ärger im Büro", lang="de") == 'aerger-im-buero'
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, SlugConfig};

    assert_eq!(api::slugify("Ärger im Büro", &SlugConfig::new().with_lang("de")), "aerger-im-buero");
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    Disarm.slugify("Ärger im Büro", lang: :de)  # => "aerger-im-buero"
    ```

Use `lang="auto"` to auto-detect the language from the script. For ambiguous
Cyrillic, auto-detection defaults to Russian:

```python
assert slugify("Москва", lang="auto") == 'moskva'
assert slugify("ภาษาไทย", lang="auto") == 'phasaaithy'
```

### entities, decimal, hexadecimal

Decode HTML entities and numeric character references:

```python
assert slugify("&amp; test &#38;") == 'test'
```

### default

Fallback returned when the input has no sluggable characters (emoji,
punctuation, or zero-width only) and would otherwise slug to the empty string —
avoiding the routing hazard of multiple distinct inputs collapsing onto one
empty-slug URL:

```python
assert slugify("\U0001f525\U0001f525\U0001f525") == ''
assert slugify("\U0001f525\U0001f525\U0001f525", default="n-a") == 'n-a'
```

The fallback is **sanitized through the same slug pipeline** before being
returned, so a caller-derived default (a username, a filename) cannot inject
path-traversal or URL metacharacters into output that is assumed URL-safe. It is
also subject to the same `max_length`:

```python
assert slugify("\U0001f525", default="../../etc/passwd") == 'etc-passwd'
assert slugify("\U0001f525", default="a/b?c#d") == 'a-b-c-d'
assert slugify("\U0001f525", default="this-is-long", max_length=5) == 'this'
```

A `default` that is itself unsluggable sanitizes to `""`.

`default` is available on every entry point — `slugify()`, `Slugifier`,
`UniqueSlugifier`, and `Text.slugify`. On `UniqueSlugifier` the fallback is made
unique like any other slug:

```python
from disarm import UniqueSlugifier

u = UniqueSlugifier(default="n-a")
assert u("\U0001f525") == 'n-a'
assert u("\U0001f525") == 'n-a-1'
```

## Reusable slugifiers

### Slugifier

Pre-configure a slugifier for repeated use:

```python
from disarm import Slugifier

slug = Slugifier(separator="_", lang="de", max_length=50)
assert slug("Ärger im Büro") == 'aerger_im_buero'
assert slug("Über den Wolken") == 'ueber_den_wolken'
```

### UniqueSlugifier

Track previously generated slugs and append numeric suffixes for uniqueness:

```python
from disarm import UniqueSlugifier

unique = UniqueSlugifier()
assert unique("My Post") == 'my-post'
assert unique("My Post") == 'my-post-1'
assert unique("My Post") == 'my-post-2'

unique.reset()      # clear history
assert unique("My Post") == 'my-post'
```

#### External uniqueness check

Pass a callback for database-backed uniqueness:

<!--- skip: next -->
```python
def check_db(slug: str) -> bool:
    """Return True if slug already exists."""
    return db.slugs.exists(slug)

unique = UniqueSlugifier(check=check_db)
unique("My Post")  # queries check_db before returning
```

## Full pipeline

The slugification pipeline executes in this order:

1. Apply `replacements`
2. Decode HTML entities (if `entities=True`)
3. Decode decimal references (if `decimal=True`)
4. Decode hexadecimal references (if `hexadecimal=True`)
5. Transliterate (using `lang` if set), or keep Unicode (if `allow_unicode=True`)
6. Lowercase (if `lowercase=True`)
7. Apply `regex_pattern`
8. Replace non-alphanumeric with `separator`
9. Collapse consecutive separators
10. Remove `stopwords`
11. Truncate to `max_length` (respecting `word_boundary` and `save_order`)
12. Strip leading/trailing separators
