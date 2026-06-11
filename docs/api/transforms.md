# Core Transforms

Functions that transform text. All are pure functions — they never mutate the input.

## transliterate

::: disarm.transliterate

---

## slugify

::: disarm.slugify

---

## normalize

::: disarm.normalize

---

## normalize_confusables

::: disarm.normalize_confusables

---

## sanitize_filename

::: disarm.sanitize_filename

---

## strip_accents

::: disarm.strip_accents

---

## fold_case

::: disarm.fold_case

---

## collapse_whitespace

::: disarm.collapse_whitespace

---

## demojize

::: disarm.demojize

---

## set_emoji_provider

::: disarm.set_emoji_provider

---

## strip_bidi

::: disarm.strip_bidi

---

## strip_zalgo

::: disarm.strip_zalgo

Caps the number of combining marks per base character, preserving legitimate diacritics (é, ñ, ệ) while removing zalgo stacking abuse.

```python
from disarm import strip_zalgo

assert strip_zalgo("café") == 'café'
assert strip_zalgo("Việt Nam") == 'Việt Nam'

# Strip all combining marks (like strip_accents)
assert strip_zalgo("café", max_marks=0) == 'cafe'
```

---

## List input (batch processing)

`transliterate`, `slugify`, `normalize`, and `strip_accents` accept either a single `str` or a `list[str]`. When a list is passed, all strings are processed in a single Rust call, amortizing the Python → Rust boundary overhead. The return type matches the input type.

Two `transliterate` modes are the exception and instead process a list item by item: reverse transliteration (`target=...`) and context-aware transliteration (`context=True`).

```python
from disarm import transliterate, slugify

titles = ["café résumé", "Straße nach München", "Москва"]

assert transliterate(titles) == ['cafe resume', 'Strasse nach Munchen', 'Moskva']

assert slugify(titles, lang="de") == ['cafe-resume', 'strasse-nach-muenchen', 'moskva']
```

For large datasets, passing a list is significantly faster than calling the function in a Python loop. See [Performance](../performance.md) for benchmarks.

## Compatibility aliases

The following aliases are provided for migration convenience:

| Alias | Target | Matches |
|---|---|---|
| `unidecode` | `transliterate` | Unidecode / text-unidecode |
| `ascii_fold` | `transliterate` | Elasticsearch ICU folding |
| `casefold` | `fold_case` | `str.casefold()` |
| `remove_accents` | `strip_accents` | sklearn / ML ecosystems |

```python
from disarm import unidecode, casefold, remove_accents

assert unidecode("café") == 'cafe'
assert casefold("Straße") == 'strasse'
assert remove_accents("café") == 'cafe'
```
