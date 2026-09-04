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

## replace_emoji

::: disarm.replace_emoji

### Three treatments, and which profile uses which

An emoji can be **named**, **replaced** or **kept**, and disarm does all three. Which one
is right is a property of the caller's text, not of the library:

| treatment | call | what it is for |
|---|---|---|
| name | `demojize(text)`, `TextPipeline(demojize=True)` | a reader or a model that needs the words |
| replace | `replace_emoji(text, s)`, `TextPipeline(demojize=s)` | text where an emoji is a delimiter |
| keep | every shipped preset and profile | screening, comparison and key building |

Naming and replacing read different tables, which is why they are separate functions
rather than one with a flag. Naming asks *what does CLDR call this?* and its domain is
the CLDR name table — wider than the emoji, so `demojize("x™y")` is `"x trade mark y"`.
Replacing asks *is this an emoji by the UCD's properties?* and its domain is the
emoji-presentation set, so `™` and `©` are left alone:

```python
from disarm import demojize, replace_emoji

assert demojize("x™y") == "x trade mark y"
assert replace_emoji("x™y") == "x™y"

# An emoji inside a word splits it for a subword tokenizer; removing it closes the split.
assert replace_emoji("aa🔥bb") == "aabb"
# Between two words, the same rule fuses them — so the caller picks the separator.
assert replace_emoji("stop🛑now", " ") == "stop now"
```

### Why no profile removes emoji

`llm_guardrail` keeps a visible emoji, and that is a measured decision rather than an
omission (#910). Naming inside a guardrail writes attacker-chosen English into the text
being screened — 1,272 distinct words across the `Emoji_Presentation` set. Removing costs
the opposite: over 144 emoji with the probe `stop<emoji>now`, removal fused the two words
**144 times out of 144**.

The attack this parameter answers is intra-word, where removal is the defence. #910's
probe is inter-word, where removal is the damage. No local rule tells the two apart, so
neither is a default and the caller says which their text is.

### What it reaches, and the vintage that decides

Removal covers the bundled `Emoji_Presentation` table, which is **UCD 15.1.0 —
1,205 code points** (`docs/provenance.md`). Every one of them is removed from between two
words; 14 code points assigned in later UCD releases are not in the table and survive,
`U+1FAE9` among them. That number moves with a table refresh rather than with this code,
and the refresh is its own change: bumping to 17.0.0 also narrows `Extended_Pictographic`
from 3,537 to 2,848 and moves three code points out, which other steps read.

---

## set_emoji_provider

::: disarm.set_emoji_provider

---

## strip_bidi

::: disarm.strip_bidi

---

## fold_punctuation

::: disarm.fold_punctuation

---

## strip_tags

::: disarm.strip_tags

---

## strip_variation_selectors

::: disarm.strip_variation_selectors

---

## strip_noncharacters

::: disarm.strip_noncharacters

---

## strip_pua

::: disarm.strip_pua

---

## strip_zalgo

::: disarm.strip_zalgo

Caps the number of combining marks per base character, preserving legitimate diacritics (é, ñ, ệ) while removing zalgo stacking abuse.

```python
from disarm import strip_zalgo

assert strip_zalgo("café") == "café"
assert strip_zalgo("Việt Nam") == "Việt Nam"

# Strip all combining marks (like strip_accents)
assert strip_zalgo("café", max_marks=0) == "cafe"
```

---

## List input (batch processing)

`transliterate`, `slugify`, `normalize`, and `strip_accents` accept either a single `str` or a `list[str]`. When a list is passed, all strings are processed in a single Rust call, amortizing the Python → Rust boundary overhead. The return type matches the input type.

Two `transliterate` modes are the exception and instead process a list item by item: reverse transliteration (`target=...`) and context-aware transliteration (`context=True`).

```python
from disarm import transliterate, slugify

titles = ["café résumé", "Straße nach München", "Москва"]

assert transliterate(titles) == ["cafe resume", "Strasse nach Munchen", "Moskva"]

assert slugify(titles, lang="de") == ["cafe-resume", "strasse-nach-muenchen", "moskva"]
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

assert unidecode("café") == "cafe"
assert casefold("Straße") == "strasse"
assert remove_accents("café") == "cafe"
```
