# Slugification

disarm generates URL-safe slugs from Unicode text. The `slugify` operation is parameter-compatible with [python-slugify](https://pypi.org/project/python-slugify/), so migration requires only changing the import.

## Basic usage

=== "Python"

    ```python
    from disarm import slugify

    assert slugify("Hello, World!") == "hello-world"
    assert slugify("My Blog Post — Draft #3") == "my-blog-post-draft-3"
    assert slugify("Ünïcödé Téxt") == "unicode-text"
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, SlugConfig};

    let cfg = SlugConfig::default();
    assert_eq!(api::try_slugify("Hello, World!", &cfg).unwrap(), "hello-world");
    assert_eq!(api::try_slugify("My Blog Post — Draft #3", &cfg).unwrap(), "my-blog-post-draft-3");
    assert_eq!(api::try_slugify("Ünïcödé Téxt", &cfg).unwrap(), "unicode-text");
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    Disarm.slugify("Hello, World!")           # => "hello-world"
    Disarm.slugify("My Blog Post — Draft #3")  # => "my-blog-post-draft-3"
    Disarm.slugify("Ünïcödé Téxt")             # => "unicode-text"
    ```

=== "Node"

    ```ts
    import { slugify } from 'disarm'

    slugify('Hello, World!') // => 'hello-world'
    slugify('My Blog Post — Draft #3') // => 'my-blog-post-draft-3'
    slugify('Ünïcödé Téxt') // => 'unicode-text'
    ```

## Parameters

### separator

The character used between words (default: `"-"`):

=== "Python"

    ```python
    assert slugify("hello world", separator="_") == "hello_world"
    assert slugify("hello world", separator=".") == "hello.world"
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    Disarm.slugify("hello world", separator: "_")  # => "hello_world"
    Disarm.slugify("hello world", separator: ".")  # => "hello.world"
    ```

=== "Node"

    ```ts
    import { slugify } from 'disarm'

    slugify('hello world', { separator: '_' }) // => 'hello_world'
    slugify('hello world', { separator: '.' }) // => 'hello.world'
    ```

### lowercase

Whether to lowercase the output (default: `True`):

```python
assert slugify("Hello World", lowercase=False) == "Hello-World"
```

### max_length

Truncate the slug to a maximum length (default: `0` = unlimited):

```python
assert slugify("a very long title here", max_length=10) == "a-very-lon"
```

### word_boundary

When combined with `max_length`, truncate at word boundaries: the slug keeps the whole
words that fit, up to the first that does not.

```python
assert slugify("a very long title here", max_length=10, word_boundary=True) == "a-very"
assert slugify("very long title here", max_length=9, word_boundary=True) == "very-long"
```

When not even the first word fits, it is cut as if `word_boundary` were off. Either way a
cut never leaves a trailing separator, whole or partial.

### stopwords

Words to remove from the slug, compared case-insensitively whether or not `lowercase` is
set:

```python
assert slugify("the quick brown fox", stopwords=["the", "brown"]) == "quick-fox"
assert slugify("The Quick Fox", stopwords=["the"], lowercase=False) == "Quick-Fox"
```

With `separator=""` the slug has no words, so nothing is removed.

### regex_pattern

Custom regex pattern for allowed characters:

```python
assert slugify("hello 123 world", regex_pattern=r"[^a-z]+") == "helloworld"
```

### replacements

Pre-transliteration string replacements:

```python
assert slugify("C++ Programming", replacements=[("C++", "cpp")]) == "cpp-programming"
```

### allow_unicode

Keep non-ASCII **letters, digits and combining marks** in the slug instead of
transliterating them to ASCII:

```python
assert slugify("日本語テスト", allow_unicode=True) == "日本語テスト"
assert slugify("Привет мир", allow_unicode=True) == "привет-мир"
assert slugify("Tiếng Việt", allow_unicode=True) == "tiếng-việt"
```

Everything outside those categories becomes a separator, exactly as it does on the
default ASCII path — format characters (bidi controls, ZWSP, ZWNBSP, soft hyphen, the
tag block), private use, noncharacters, surrogates, punctuation, symbols and emoji. That
includes the letter-like symbols, such as the circled Latin letters, which are `So`
although Unicode calls them alphabetic:

```python
assert slugify("file\u202egnp.exe", allow_unicode=True) == "file-gnp-exe"
assert slugify("a\u200bb", allow_unicode=True) == "a-b"
assert slugify("Hello 👋 World", allow_unicode=True) == "hello-world"
assert slugify("\u24b6dmin", allow_unicode=True) == "dmin"
```

This matches `django.utils.text.slugify(allow_unicode=True)`, which keeps `\w`. disarm
adds two things Django does not:

- **Combining marks**, capped at two per base character. Django drops them, which breaks
  Devanagari and Arabic. Two is the cap the `strip_zalgo` presets use, and what
  Vietnamese `ệ` needs. The cap counts the base's own marks, over its decomposition, as
  `strip_zalgo` does: `à` takes one more. A precomposed character that already carries
  more than two, such as polytonic Greek U+1F82 with three, is kept whole and takes none.
- **ZWJ and ZWNJ**, when they sit *between* two other kept characters. Both are
  orthographically required, so dropping them changes the word:

```python
assert slugify("می\u200cروم", allow_unicode=True) == "می\u200cروم"  # Persian ZWNJ
assert slugify("क\u094d\u200dष", allow_unicode=True) == "क\u094d\u200dष"  # Devanagari ZWJ
assert slugify("a\u200d", allow_unicode=True) == "a"  # never at a token edge
```

!!! warning "Not a security function"

    `allow_unicode` screens the same classes the ASCII path does, but `slugify` is not a
    sanitizer and makes no claim beyond "these categories do not reach the slug". For
    untrusted input reach for [`canonicalize`](../api/pipelines.md) or
    [`strip_obfuscation`](../api/pipelines.md) first.

`max_length` cuts on a **grapheme-cluster** boundary under `allow_unicode`, so a cut
never lands inside a cluster, and a joiner the cut would leave at the end is dropped. A
budget too small for the first cluster yields an empty slug, the same outcome an
all-stopword input already produces:

```python
assert slugify("한국어", allow_unicode=True, max_length=6) == "한국"
assert slugify("क\u094dषि", allow_unicode=True, max_length=9) == ""  # one 12-byte cluster
assert slugify("a\u200db", allow_unicode=True, max_length=4) == "a"  # not a + ZWJ
```

The Unicode-preserving path composes after lowercasing, so its slug is NFC even where
lowercasing creates a pair that composes: `T` + U+0308 has no precomposed form, `t` +
U+0308 does.

```python
assert slugify("T\u0308", allow_unicode=True) == "\u1e97"
```

With `separator=""` the words are joined with nothing, and the joined slug is composed
again, so two characters that compose across the join come out as the one they render
as, and slugifying the slug returns it unchanged:

```python
assert slugify("\u1100 \u1161", allow_unicode=True, separator="") == "\uac00"
```

### lang

Language profile for transliteration:

=== "Python"

    ```python
    assert slugify("Ärger im Büro", lang="de") == "aerger-im-buero"
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, SlugConfig};

    assert_eq!(api::try_slugify("Ärger im Büro", &SlugConfig::new().with_lang("de")).unwrap(), "aerger-im-buero");
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    Disarm.slugify("Ärger im Büro", lang: :de)  # => "aerger-im-buero"
    ```

=== "Node"

    ```ts
    import { slugify } from 'disarm'

    slugify('Ärger im Büro', { lang: 'de' }) // => 'aerger-im-buero'
    ```

Use `lang="auto"` to auto-detect the language from the script. For ambiguous
Cyrillic, auto-detection defaults to Russian:

```python
assert slugify("Москва", lang="auto") == "moskva"
assert slugify("ภาษาไทย", lang="auto") == "phasaaithy"
```

### entities, decimal, hexadecimal

Decode HTML entities and numeric character references:

```python
assert slugify("&amp; test &#38;") == "test"
```

A numeric reference is `&#`, an optional `x`, a run of digits and an optional `;`. With no
digit after the `&#` it is not a reference, and the text stays as written. One that names
a control character, a surrogate or no character at all is dropped, and only it: the
text after it is kept.

```python
assert slugify("Q&#A session") == "q-a-session"
assert slugify("issue &#12 fixed") == "issue-fixed"
```

### default

Fallback returned when the input has no sluggable characters (emoji,
punctuation, or zero-width only) and would otherwise slug to the empty string —
avoiding the routing hazard of multiple distinct inputs collapsing onto one
empty-slug URL:

```python
assert slugify("\U0001f525\U0001f525\U0001f525") == ""
assert slugify("\U0001f525\U0001f525\U0001f525", default="n-a") == "n-a"
```

The fallback is **sanitized through the same slug pipeline** before being
returned, so a caller-derived default (a username, a filename) cannot inject
path-traversal or URL metacharacters into output that is assumed URL-safe. It is
also subject to the same `max_length`:

```python
assert slugify("\U0001f525", default="../../etc/passwd") == "etc-passwd"
assert slugify("\U0001f525", default="a/b?c#d") == "a-b-c-d"
assert slugify("\U0001f525", default="this-is-long", max_length=5) == "this"
```

A `default` that is itself unsluggable sanitizes to `""`.

`default` is available on every entry point — `slugify()`, `Slugifier`,
`UniqueSlugifier`, and `Text.slugify`. On `UniqueSlugifier` the fallback is made
unique like any other slug:

```python
from disarm import UniqueSlugifier

u = UniqueSlugifier(default="n-a")
assert u("\U0001f525") == "n-a"
assert u("\U0001f525") == "n-a-1"
```

## Reusable slugifiers

### Slugifier

Pre-configure a slugifier for repeated use:

```python
from disarm import Slugifier

slug = Slugifier(separator="_", lang="de", max_length=50)
assert slug("Ärger im Büro") == "aerger_im_buero"
assert slug("Über den Wolken") == "ueber_den_wolken"
```

### UniqueSlugifier

Track previously generated slugs and append numeric suffixes for uniqueness:

```python
from disarm import UniqueSlugifier

unique = UniqueSlugifier()
assert unique("My Post") == "my-post"
assert unique("My Post") == "my-post-1"
assert unique("My Post") == "my-post-2"

unique.reset()  # clear history
assert unique("My Post") == "my-post"
```

With `max_length`, a suffixed slug is cut to fit by shortening the base, never the
suffix. The cut is the slug's own, so no separator or joiner is left before the suffix,
and at least one character of the base is kept; when the suffix leaves no room for one,
`InvalidArgumentError` is raised rather than returning a bare `-1`:

```python
unique = UniqueSlugifier(max_length=5)
assert unique("ab cd") == "ab-cd"
assert unique("ab cd") == "ab-1"
```

An input with nothing sluggable gives the empty slug every time. It is not suffixed or
recorded, and `check` is not called for it; pass `default` for a unique fallback.

```python
unique = UniqueSlugifier()
assert unique("\U0001f525") == ""
assert unique("\U0001f525") == ""
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
6. Lowercase (if `lowercase=True`); with `allow_unicode=True`, then compose to NFC
7. Apply `regex_pattern`
8. Replace non-alphanumeric with `separator`
9. Collapse consecutive separators
10. Remove `stopwords`
11. Truncate to `max_length` (respecting `word_boundary` and `save_order`)
12. Strip leading/trailing separators
