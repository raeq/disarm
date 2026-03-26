# Grapheme Clusters

Unicode text is more complex than it appears. A single user-perceived "character" can be composed of multiple Unicode codepoints — combining accents, emoji modifiers, ZWJ sequences, regional indicator pairs, and Hangul jamo all create situations where Python's `len()` gives a misleading count.

translit provides three functions for working with **extended grapheme clusters** as defined by [UAX #29](https://www.unicode.org/reports/tr29/), giving correct results where `len()` overcounts.

## The Problem

```python
text = "café"            # 4 characters, right?
len(text)                # => 4 ✓ (precomposed é = 1 codepoint)

# But with decomposed é (e + combining acute accent):
import unicodedata
text_nfd = unicodedata.normalize("NFD", "café")
len(text_nfd)            # => 5 ✗ (e + ◌́ counted separately)

# Emoji are worse:
len("👨‍👩‍👧‍👦")               # => 7 (4 person codepoints + 3 ZWJ joiners)
len("🇬🇧")               # => 2 (two regional indicator symbols)
len("👋🏽")               # => 2 (wave + skin tone modifier)
```

Python's `len()` counts **codepoints**, not **user-perceived characters**. For correct character counting, splitting, and truncation, you need grapheme cluster segmentation.

## Functions

### grapheme_len

Count the number of user-perceived characters:

```python
from translit import grapheme_len

grapheme_len("café")                 # => 4
grapheme_len("cafe\u0301")           # => 4 (NFD: e + combining accent = 1 grapheme)

# Emoji
grapheme_len("👨‍👩‍👧‍👦")                    # => 1 (family ZWJ sequence)
grapheme_len("🇬🇧")                    # => 1 (flag = 2 regional indicators = 1 grapheme)
grapheme_len("👋🏽")                    # => 1 (hand + skin tone modifier)
grapheme_len("🏳️‍🌈")                    # => 1 (rainbow flag)

# Complex scripts
grapheme_len("\u1100\u1161\u11A8")   # => 1 (Hangul jamo sequence = 1 syllable)
grapheme_len("नमस्ते")                # => 4 (Devanagari with conjuncts)
```

### grapheme_split

Split text into individual grapheme clusters:

```python
from translit import grapheme_split

grapheme_split("café")               # => ['c', 'a', 'f', 'é']
grapheme_split("cafe\u0301")         # => ['c', 'a', 'f', 'é']  (combining accent stays with e)

grapheme_split("👨‍👩‍👧‍👦!")               # => ['👨‍👩‍👧‍👦', '!']
grapheme_split("🇫🇷🇬🇧")               # => ['🇫🇷', '🇬🇧']  (two flags, not four indicators)
grapheme_split("Hi 👋🏽")              # => ['H', 'i', ' ', '👋🏽']
```

!!! note
    Input is limited to 10 MB to prevent excessive memory allocation. Raises `TranslitError` for larger inputs.

### grapheme_truncate

Truncate text to a maximum number of grapheme clusters without splitting any cluster:

```python
from translit import grapheme_truncate

grapheme_truncate("Hello World", 5)  # => "Hello"
grapheme_truncate("café", 3)         # => "caf"
grapheme_truncate("cafe\u0301s", 4)  # => "café"  (combining accent stays with the e)

# Emoji are never split
grapheme_truncate("👨‍👩‍👧‍👦🎉", 1)         # => "👨‍👩‍👧‍👦"  (family emoji = 1 grapheme)
grapheme_truncate("Hi 👩‍👩‍👧‍👦!", 4)        # => "Hi 👩‍👩‍👧‍👦"  (family counts as 1)
grapheme_truncate("🇬🇧🇫🇷🇩🇪", 2)        # => "🇬🇧🇫🇷"  (two flags)
```

Unlike byte-level slicing (`text[:n]`) or codepoint-level slicing, `grapheme_truncate` never produces corrupted output — no broken emoji, no orphaned combining marks, no split Hangul syllables.

## Text Builder

All grapheme functions are also available on the `Text` builder:

```python
from translit import Text

t = Text("Hello 👨‍👩‍👧‍👦!")

# Predicates (non-chaining)
t.grapheme_len()                     # => 8
t.grapheme_split()                   # => ['H', 'e', 'l', 'l', 'o', ' ', '👨‍👩‍👧‍👦', '!']

# Transform (chaining)
t.grapheme_truncate(7).value         # => "Hello 👨‍👩‍👧‍👦"
```

## When to Use Grapheme Functions

### Use grapheme_len instead of len() when:

- **Enforcing character limits** — user-facing limits like "280 characters" should count what users see, not codepoints
- **Validating input length** — username or field length validation
- **Character-level ML tokenization** — splitting text into "characters" for character-level models
- **Display width estimation** — though note that display width also depends on font metrics, not just grapheme count

### Use grapheme_truncate instead of slicing when:

- **Truncating user-visible text** — preview snippets, title shortening
- **Database field length enforcement** — preventing corruption of combining sequences at boundaries
- **API response truncation** — ensuring valid Unicode output
- **Slug length limits** — though `slugify(max_length=)` already handles this for ASCII output

### Use grapheme_split instead of list() when:

- **Character-level tokenization** — NLP pipelines that need individual characters
- **Character frequency analysis** — counting character distributions
- **Grapheme-aware iteration** — processing text one user-perceived character at a time

## Codepoints vs Graphemes vs Bytes

A comparison showing how different counting methods diverge:

| Text | `len(b)` bytes | `len(s)` codepoints | `grapheme_len(s)` |
|------|:-:|:-:|:-:|
| `"hello"` | 5 | 5 | 5 |
| `"café"` (NFC) | 5 | 4 | 4 |
| `"café"` (NFD) | 6 | 5 | 4 |
| `"👨‍👩‍👧‍👦"` | 25 | 7 | 1 |
| `"🇬🇧"` | 8 | 2 | 1 |
| `"👋🏽"` | 8 | 2 | 1 |
| `"नमस्ते"` | 18 | 6 | 4 |
| `"한"` (precomposed) | 3 | 1 | 1 |
| `"한"` (jamo) | 9 | 3 | 1 |

## Normalization Interaction

Grapheme cluster boundaries can differ between NFC and NFD forms of the same text. For consistent results, normalize before counting:

```python
from translit import normalize, grapheme_len

text = "é"  # might be NFC or NFD depending on source
normalized = normalize(text, form="NFC")
count = grapheme_len(normalized)     # => 1 (regardless of original form)
```

In practice, `grapheme_len` gives the same count for NFC and NFD forms of the same text — the grapheme cluster algorithm handles both. But normalizing first ensures deterministic byte-level results from `grapheme_split` and `grapheme_truncate`.

## Limitations

- **Display width is not grapheme count.** East Asian characters (CJK) are typically double-width in monospace fonts, but `grapheme_len` counts them as 1. For terminal column-width calculation, you need a separate width estimation library.
- **Newer emoji sequences.** The `unicode-segmentation` crate's tables must be updated to correctly segment newly standardized ZWJ emoji sequences. Between updates, a brand-new emoji may be split across multiple clusters.
- **Rendering varies.** "User-perceived character" is ultimately a rendering question. Not all systems agree on cluster boundaries, particularly for complex emoji. See [Limitations](../limitations.md#grapheme-cluster-segmentation) for details.

## Performance

Grapheme operations use the Rust `unicode-segmentation` crate, which implements UAX #29 with precomputed lookup tables. Performance is in the sub-microsecond range for typical inputs:

| Function | Input | Time |
|----------|-------|------|
| `grapheme_len` | ASCII string | ~100 ns |
| `grapheme_len` | Emoji string | ~260 ns |
| `grapheme_split` | ASCII string | ~285 ns |
| `grapheme_split` | Emoji string | ~516 ns |
