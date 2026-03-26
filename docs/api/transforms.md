# Core Transforms

Functions that transform text. All are pure functions — they never mutate the input.

## transliterate

::: translit.transliterate

---

## slugify

::: translit.slugify

---

## normalize

::: translit.normalize

---

## normalize_confusables

::: translit.normalize_confusables

---

## sanitize_filename

::: translit.sanitize_filename

---

## strip_accents

::: translit.strip_accents

---

## fold_case

::: translit.fold_case

---

## collapse_whitespace

::: translit.collapse_whitespace

---

## demojize

::: translit.demojize

---

## set_emoji_provider

::: translit.set_emoji_provider

---

## strip_bidi

::: translit.strip_bidi

---

## strip_zalgo

::: translit.strip_zalgo

Caps the number of combining marks per base character, preserving legitimate diacritics (é, ñ, ệ) while removing zalgo stacking abuse.

```python
from translit import strip_zalgo

strip_zalgo("café")           # => "café"  (1 mark — preserved)
strip_zalgo("Việt Nam")       # => "Việt Nam"  (2 marks — preserved)

# Strip all combining marks (like strip_accents)
strip_zalgo("café", max_marks=0)  # => "cafe"
```

---

## Batch APIs

The batch functions process multiple strings in a single Rust call, amortizing the Python → Rust boundary overhead (~240 ns per call). They return a `list[str]` in the same order as the input.

### transliterate_batch

::: translit.transliterate_batch

### slugify_batch

::: translit.slugify_batch

### normalize_batch

::: translit.normalize_batch

### strip_accents_batch

::: translit.strip_accents_batch

### Example

```python
from translit import transliterate_batch, slugify_batch

titles = ["café résumé", "Straße nach München", "Москва"]

transliterate_batch(titles)
# => ["cafe resume", "Strasse nach Munchen", "Moskva"]

slugify_batch(titles, lang="de")
# => ["cafe-resume", "strasse-nach-muenchen", "moskva"]
```

For large datasets, batch APIs are significantly faster than calling the scalar function in a Python loop. See [Performance](../performance.md) for benchmarks.

## Compatibility aliases

The following aliases are provided for migration convenience:

| Alias | Target | Matches |
|---|---|---|
| `unidecode` | `transliterate` | Unidecode / text-unidecode |
| `ascii_fold` | `transliterate` | Elasticsearch ICU folding |
| `casefold` | `fold_case` | `str.casefold()` |
| `remove_accents` | `strip_accents` | sklearn / ML ecosystems |

```python
from translit import unidecode, casefold, remove_accents

unidecode("café")        # => "cafe"
casefold("Straße")       # => "strasse"
remove_accents("café")   # => "cafe"
```
