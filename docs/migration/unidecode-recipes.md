# Unidecode → translit recipes

A [survey of 58 real projects](https://github.com/raeq/translit/issues/88)
(beets, saleor, investpy, python-slugify, django-autoslug, …) found that
`unidecode` is almost never the last step. It sits inside a hand-rolled
normalisation pipeline — lowercase, strip, collapse, re-encode — and **every one
of those pipelines already has a single-call equivalent in translit**. The gap
is discoverability, not capability.

This page maps each observed pattern to its one-liner. The "after" snippets are
[executed and asserted in CI](../CONTRIBUTING.md#doc-test-recipes), so the
equivalences below cannot silently rot. The "before" snippets show the legacy
hand-rolled code and are not executed.

!!! tip "Why one call beats a pipeline"
    A hand-rolled pipeline bakes in an **ordering** decision — does `.lower()`
    run before or after transliteration? Get it wrong and `№5` slugs to `No5`
    instead of `no5` (see [the ordering footgun](#the-ordering-footgun)). The
    translit helper encapsulates the correct order so you never have to make
    that call.

## At a glance

| Hand-rolled with `unidecode` | translit one-liner |
|---|---|
| `re.sub(r"\W+", "-", unidecode(t).lower().strip())` | `slugify(t)` |
| `unidecode(name).replace(os.sep, "_")` | `sanitize_filename(name, platform=...)` |
| `unidecode(t).encode("ascii")` | `transliterate(t).encode("ascii")` |
| `unidecode(t.lower().strip())` for dict / search keys | `search_key(t)` / `catalog_key(t)` / `sort_key(t)` |
| `quote(unidecode(t))` | `quote(transliterate(t))` (or `slugify` for URLs) |

## URL slugs

<!--- skip: next -->
```python
# Before — hand-rolled slug
import re
from unidecode import unidecode

def slug(t):
    return re.sub(r"\W+", "-", unidecode(t).lower().strip()).strip("-")
```

```python
# After
from translit import slugify

assert slugify("Café del Mar!!") == "cafe-del-mar"
assert slugify("Хлеб с маслом") == "khleb-s-maslom"
```

`slugify()` lowercases, transliterates, replaces runs of non-word characters
with a single `-`, and trims — in the right order — so you do not re-implement
(and mis-order) the pipeline. See the [Slugification guide](../user-guide/slugification.md).

## Safe filenames

<!--- skip: next -->
```python
# Before — transliterate then patch path separators by hand
import os
from unidecode import unidecode

safe = unidecode("Naïve/Résumé.txt").replace(os.sep, "_")
```

```python
# After
from translit import sanitize_filename

assert sanitize_filename("Naïve/Résumé.txt") == "Naive_Resume.txt"
```

`sanitize_filename()` does more than swap separators: it removes OS-illegal
characters, handles Windows reserved names, and truncates to a byte budget.
Pick the rule set with `platform="universal" | "posix" | "windows"`. See
[Filename Sanitization](../user-guide/filenames.md).

## ASCII bytes

<!--- skip: next -->
```python
# Before
from unidecode import unidecode

raw = unidecode("Café").encode("ascii")
```

```python
# After
from translit import transliterate

assert transliterate("Café").encode("ascii") == b"Cafe"
```

`transliterate()` already guarantees ASCII-only output, so the `.encode("ascii")`
never raises `UnicodeEncodeError`. Use `errors="ignore" | "preserve" | "replace"`
to choose what happens to characters with no mapping.

## Dictionary / search keys

<!--- skip: next -->
```python
# Before — a casefolded, accent-folded lookup key
from unidecode import unidecode

key = unidecode("Café del Mar".lower().strip())
```

```python
# After — pick the helper that documents intent
from translit import search_key, catalog_key, sort_key

# For typical text the three coincide — use the name that fits the call site:
assert search_key("  Café  RÉSUMÉ  ") == "cafe resume"
assert catalog_key("Café del Mar") == "cafe del mar"
assert sort_key("Café del Mar") == "cafe del mar"
```

All three apply NFKC → transliterate → case-fold → collapse-whitespace, so for
plain text they produce the same key. They differ by the extra pass each adds:

- **`search_key`** — lightest; nothing extra. For search / lookup indexes.
- **`catalog_key`** — adds a [TR39 confusable](../user-guide/confusables.md) fold,
  which canonicalises look-alikes that *survive* transliteration (curly quotes,
  primes, and similar punctuation). Built for bibliographic de-duplication where
  typographic variants of the same title should collapse to one key.
- **`sort_key`** — strips bidi controls for stable ordering. (It currently
  coincides with `search_key` for typical input; use the name that documents the
  call site.)

The confusable fold is what sets `catalog_key` apart — typographic variants of a
title collapse to the same key:

```python
assert catalog_key('naïve “quote”') == "naive ''quote''"   # quotes folded
assert search_key('naïve “quote”') == 'naive "quote"'      # quotes preserved
```

That fold runs *after* transliteration, so it does **not** reverse cross-script
homoglyph spoofs (Cyrillic `р` is already romanised to `r` by then). For that,
see [confusable defense](../user-guide/confusables.md).

## URL-encoded query parameters

<!--- skip: next -->
```python
# Before
from urllib.parse import quote
from unidecode import unidecode

q = quote(unidecode("Café del Mar"))
```

```python
# After
from urllib.parse import quote
from translit import transliterate, slugify

assert quote(transliterate("Café del Mar")) == "Cafe%20del%20Mar"
# For a clean URL path segment, prefer a slug:
assert slugify("Café del Mar") == "cafe-del-mar"
```

## The ordering footgun

`#88` found pipelines that lowercase **before** transliterating. That order is
subtly wrong whenever transliteration *introduces* an uppercase letter. The
numero sign `№` expands to `No` — a capital `N` that a prior `.lower()` cannot
see:

```python
from translit import transliterate, search_key

# Lowercasing BEFORE transliteration misses the introduced capital:
assert transliterate("№5".lower()) == "No5"     # wrong — stray capital N
# Lowercasing AFTER transliteration is correct:
assert transliterate("№5").lower() == "no5"
# The translit helpers fold case after transliterating, so they get it right:
assert search_key("№5") == "no5"
```

This is exactly the class of bug the one-call helpers remove: the correct order
is baked in. When in doubt, reach for `slugify` / `search_key` /
`sanitize_filename` rather than re-assembling the steps.

## See also

- [Migrating from Unidecode](from-unidecode.md) — the drop-in alias and the
  security caveat (`unidecode` is not a confusable-defense tool).
- [Slugification](../user-guide/slugification.md),
  [Filename Sanitization](../user-guide/filenames.md),
  [Normalization](../user-guide/normalization.md).
