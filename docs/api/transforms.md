# Core Transforms

Eight functions that transform text. All are pure functions — they never mutate the input.

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

## Batch APIs

The batch functions process multiple strings in a single Rust call, amortizing the Python → Rust boundary overhead (~4 µs per call). They return a `list[str]` in the same order as the input.

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
