# Slugification

translit generates URL-safe slugs from Unicode text. The `slugify()` function is parameter-compatible with [python-slugify](https://pypi.org/project/python-slugify/), so migration requires only changing the import.

## Basic usage

```python
from translit import slugify

slugify("Hello, World!")                # => "hello-world"
slugify("My Blog Post — Draft #3")     # => "my-blog-post-draft-3"
slugify("Ünïcödé Téxt")                # => "unicode-text"
```

## Parameters

### separator

The character used between words (default: `"-"`):

```python
slugify("hello world", separator="_")   # => "hello_world"
slugify("hello world", separator=".")   # => "hello.world"
```

### lowercase

Whether to lowercase the output (default: `True`):

```python
slugify("Hello World", lowercase=False) # => "Hello-World"
```

### max_length

Truncate the slug to a maximum length (default: `0` = unlimited):

```python
slugify("a very long title here", max_length=10)
# => "a-very-lon"
```

### word_boundary

When combined with `max_length`, truncate at word boundaries:

```python
slugify("a very long title here", max_length=10, word_boundary=True)
# => "a-very"
```

### stopwords

Words to remove from the slug:

```python
slugify("the quick brown fox", stopwords=["the", "brown"])
# => "quick-fox"
```

### regex_pattern

Custom regex pattern for allowed characters:

```python
slugify("hello 123 world", regex_pattern=r"[^a-z]+")
# => "helloworld"
```

### replacements

Pre-transliteration string replacements:

```python
slugify("C++ Programming", replacements=[("C++", "cpp")])
# => "cpp-programming"
```

### allow_unicode

Keep non-ASCII characters in the slug:

```python
slugify("日本語テスト", allow_unicode=True)
# => "日本語テスト"
```

### lang

Language profile for transliteration:

```python
slugify("Ärger im Büro", lang="de")
# => "aerger-im-buero"
```

### entities, decimal, hexadecimal

Decode HTML entities and numeric character references:

```python
slugify("&amp; test &#38;")           # => "test"
```

## Reusable slugifiers

### Slugifier

Pre-configure a slugifier for repeated use:

```python
from translit import Slugifier

slug = Slugifier(separator="_", lang="de", max_length=50)
slug("Ärger im Büro")     # => "aerger_im_buero"
slug("Über den Wolken")   # => "ueber_den_wolken"
```

### UniqueSlugifier

Track previously generated slugs and append numeric suffixes for uniqueness:

```python
from translit import UniqueSlugifier

unique = UniqueSlugifier()
unique("My Post")   # => "my-post"
unique("My Post")   # => "my-post-1"
unique("My Post")   # => "my-post-2"

unique.reset()      # clear history
unique("My Post")   # => "my-post"
```

#### External uniqueness check

Pass a callback for database-backed uniqueness:

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
