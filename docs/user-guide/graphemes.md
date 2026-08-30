# Grapheme Clusters

Unicode text is more complex than it appears. A single user-perceived "character" can be composed of multiple Unicode codepoints — combining accents, emoji modifiers, ZWJ sequences, regional indicator pairs, and Hangul jamo all create situations where a naive codepoint count is misleading.

disarm provides functions for working with **extended grapheme clusters** as defined by [UAX #29](https://www.unicode.org/reports/tr29/), giving correct results where a codepoint count overcounts.

## The Problem

A naive length is a count of **codepoints**, not user-perceived characters. In Python, `len()` exhibits this:

```python
text = "café"  # 4 characters, right?
assert len(text) == 4

# But with decomposed é (e + combining acute accent):
import unicodedata

text_nfd = unicodedata.normalize("NFD", "café")
assert len(text_nfd) == 5

# Emoji are worse:
assert len("👨‍👩‍👧‍👦") == 7
assert len("🇬🇧") == 2
assert len("👋🏽") == 2
```

A codepoint count is not a count of **user-perceived characters**. For correct character counting, splitting, and truncation, you need grapheme cluster segmentation.

## Functions

### grapheme_len

Count the number of user-perceived characters:

=== "Python"

    ```python
    from disarm import grapheme_len

    assert grapheme_len("café") == 4
    assert grapheme_len("cafe\u0301") == 4

    # Emoji
    assert grapheme_len("👨‍👩‍👧‍👦") == 1
    assert grapheme_len("🇬🇧") == 1
    assert grapheme_len("👋🏽") == 1
    assert grapheme_len("🏳️‍🌈") == 1

    # Complex scripts
    assert grapheme_len("\u1100\u1161\u11a8") == 1
    assert grapheme_len("नमस्ते") == 3
    ```

=== "Rust"

    ```rust
    use disarm::api;

    assert_eq!(api::grapheme_len("café"), 4);
    assert_eq!(api::grapheme_len("👨‍👩‍👧‍👦"), 1);
    assert_eq!(api::grapheme_len("🇬🇧"), 1);
    assert_eq!(api::grapheme_len("नमस्ते"), 3);
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    Disarm.grapheme_len("café")     # => 4
    Disarm.grapheme_len("👨‍👩‍👧‍👦")    # => 1
    Disarm.grapheme_len("🇬🇧")       # => 1
    Disarm.grapheme_len("नमस्ते")     # => 3
    ```

=== "Node"

    ```ts
    import { graphemeLen } from 'disarm'

    graphemeLen('café') // => 4
    graphemeLen('👨‍👩‍👧‍👦') // => 1
    graphemeLen('🇬🇧') // => 1
    graphemeLen('नमस्ते') // => 3
    ```

### grapheme_split

Split text into individual grapheme clusters:

=== "Python"

    ```python
    from disarm import grapheme_split

    assert grapheme_split("café") == ["c", "a", "f", "é"]
    assert grapheme_split("cafe\u0301") == ["c", "a", "f", "é"]

    assert grapheme_split("👨‍👩‍👧‍👦!") == ["👨\u200d👩\u200d👧\u200d👦", "!"]
    assert grapheme_split("🇫🇷🇬🇧") == ["🇫🇷", "🇬🇧"]
    assert grapheme_split("Hi 👋🏽") == ["H", "i", " ", "👋🏽"]
    ```

=== "Rust"

    ```rust
    use disarm::api;

    assert_eq!(api::grapheme_split("café"), ["c", "a", "f", "é"]);
    assert_eq!(api::grapheme_split("🇫🇷🇬🇧"), ["🇫🇷", "🇬🇧"]);
    assert_eq!(api::grapheme_split("Hi 👋🏽"), ["H", "i", " ", "👋🏽"]);
    ```

=== "Ruby"

    ```ruby
    Disarm.grapheme_split("café")    # => ["c", "a", "f", "é"]
    Disarm.grapheme_split("🇫🇷🇬🇧")     # => ["🇫🇷", "🇬🇧"]
    ```

=== "Node"

    ```ts
    import { graphemeSplit } from 'disarm'

    graphemeSplit('café') // => ['c', 'a', 'f', 'é']
    graphemeSplit('🇫🇷🇬🇧') // => ['🇫🇷', '🇬🇧']
    ```

!!! note
    The **Python** binding caps `grapheme_split` input at 10 MB (raising `DisarmError`) to bound memory allocation; this guard has no counterpart in the Rust or Ruby APIs.

### grapheme_truncate

Truncate text to a maximum number of grapheme clusters without splitting any cluster:

=== "Python"

    ```python
    from disarm import grapheme_truncate

    assert grapheme_truncate("Hello World", 5) == "Hello"
    assert grapheme_truncate("café", 3) == "caf"
    assert grapheme_truncate("cafe\u0301s", 4) == "café"

    # Emoji are never split
    assert grapheme_truncate("👨‍👩‍👧‍👦🎉", 1) == "👨\u200d👩\u200d👧\u200d👦"
    assert grapheme_truncate("Hi 👩‍👩‍👧‍👦!", 4) == "Hi 👩\u200d👩\u200d👧\u200d👦"
    assert grapheme_truncate("🇬🇧🇫🇷🇩🇪", 2) == "🇬🇧🇫🇷"
    ```

=== "Rust"

    ```rust
    use disarm::api;

    assert_eq!(api::grapheme_truncate("Hello World", 5), "Hello");
    assert_eq!(api::grapheme_truncate("café", 3), "caf");

    // Emoji are never split
    assert_eq!(api::grapheme_truncate("🇬🇧🇫🇷🇩🇪", 2), "🇬🇧🇫🇷");
    ```

=== "Ruby"

    ```ruby
    Disarm.grapheme_truncate("Hello World", 5)  # => "Hello"
    Disarm.grapheme_truncate("café", 3)         # => "caf"
    # Emoji and flags are never split
    Disarm.grapheme_truncate("🇬🇧🇫🇷🇩🇪", 2)      # => "🇬🇧🇫🇷"
    ```

=== "Node"

    ```ts
    import { graphemeTruncate } from 'disarm'

    graphemeTruncate('Hello World', 5) // => 'Hello'
    graphemeTruncate('café', 3) // => 'caf'
    graphemeTruncate('🇬🇧🇫🇷🇩🇪', 2) // => '🇬🇧🇫🇷'
    ```

Unlike byte-level slicing (`text[:n]`) or codepoint-level slicing, `grapheme_truncate` never produces corrupted output — no broken emoji, no orphaned combining marks, no split Hangul syllables.

## Text Builder

All grapheme functions are also available on the `Text` builder:

```python
from disarm import Text

t = Text("Hello 👨‍👩‍👧‍👦!")

# Predicates (non-chaining)
assert t.grapheme_len() == 8
assert t.grapheme_split() == ["H", "e", "l", "l", "o", " ", "👨\u200d👩\u200d👧\u200d👦", "!"]

# Transform (chaining)
assert t.grapheme_truncate(7).value == "Hello 👨\u200d👩\u200d👧\u200d👦"
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
from disarm import normalize, grapheme_len

text = "é"  # might be NFC or NFD depending on source
normalized = normalize(text, form="NFC")
count = grapheme_len(normalized)
assert count == 1
```

In practice, `grapheme_len` gives the same count for NFC and NFD forms of the same text — the grapheme cluster algorithm handles both. But normalizing first ensures deterministic byte-level results from `grapheme_split` and `grapheme_truncate`.

## Best Practices

### Username validation

Sanitize input first, then enforce a grapheme-aware length limit:

```python
from disarm import canonicalize_strict, grapheme_len, grapheme_truncate


def validate_username(raw: str, max_graphemes: int = 30) -> str:
    clean = canonicalize_strict(raw)
    if grapheme_len(clean) > max_graphemes:
        clean = grapheme_truncate(clean, max_graphemes)
    return clean
```

### Post/tweet fields

Use `strip_format` for lightweight sanitization and `grapheme_truncate` for the character limit:

```python
from disarm import strip_format, grapheme_truncate


def prepare_post(raw: str, max_graphemes: int = 280) -> str:
    clean = strip_format(raw)
    return grapheme_truncate(clean, max_graphemes)
```

### Database column truncation

When storing text in a column with a character limit, truncate by grapheme clusters — never by bytes or codepoints, which can split emoji or combining sequences:

```python
from disarm import canonicalize, grapheme_truncate


def safe_for_db(raw: str, max_graphemes: int = 255) -> str:
    clean = canonicalize(raw)
    return grapheme_truncate(clean, max_graphemes)
```

### ML corpus preparation

Normalize text before truncating to a token-budget-friendly length:

```python
from disarm import ml_normalize, grapheme_truncate


def prepare_for_model(raw: str, max_graphemes: int = 4096) -> str:
    clean = ml_normalize(raw)
    return grapheme_truncate(clean, max_graphemes)
```

## Terminal column width

`grapheme_len` counts clusters; it does **not** tell you how many terminal
columns text occupies (a CJK character is one cluster but two columns). Use
`terminal_width` and `grapheme_width` for that — measured per grapheme cluster
over [UAX #11 East Asian Width](https://www.unicode.org/reports/tr11/):

=== "Python"

    ```python
    from disarm import terminal_width, grapheme_width

    assert terminal_width("hello") == 5
    assert terminal_width("世界") == 4  # wide CJK: 2 columns each
    assert terminal_width("cafe\u0301") == 4  # NFD: "e" + combining acute (U+0301, 0 columns)
    assert terminal_width("a😀") == 3  # emoji cluster occupies 2 columns
    assert grapheme_width("👨‍👩‍👧‍👦") == 2  # one ZWJ cluster, 2 columns
    ```

=== "Rust"

    ```rust
    use disarm::api;

    assert_eq!(api::terminal_width("hello", false), 5);
    assert_eq!(api::terminal_width("世界", false), 4); // wide CJK: 2 columns each
    assert_eq!(api::terminal_width("a😀", false), 3);  // emoji cluster occupies 2 columns
    assert_eq!(api::grapheme_width("👨‍👩‍👧‍👦", false), 2); // one ZWJ cluster, 2 columns
    ```

=== "Ruby"

    ```ruby
    Disarm.terminal_width("hello")    # => 5
    Disarm.terminal_width("世界")      # => 4
    Disarm.terminal_width("a😀")      # => 3
    Disarm.grapheme_width("👨‍👩‍👧‍👦")    # => 2
    ```

=== "Node"

    ```ts
    import { terminalWidth, graphemeWidth } from 'disarm'

    terminalWidth('hello') // => 5
    terminalWidth('世界') // => 4
    terminalWidth('a😀') // => 3
    graphemeWidth('👨‍👩‍👧‍👦') // => 2
    ```

East Asian **Ambiguous** characters are 1 column by default (matching modern
UTF-8 terminals); pass `ambiguous_wide=True` for legacy double-width CJK
terminals:

=== "Python"

    ```python
    assert terminal_width("¡") == 1
    assert terminal_width("¡", ambiguous_wide=True) == 2
    ```

=== "Rust"

    ```rust
    use disarm::api;

    assert_eq!(api::terminal_width("¡", false), 1);
    assert_eq!(api::terminal_width("¡", true), 2);
    ```

=== "Ruby"

    ```ruby
    Disarm.terminal_width("¡")                       # => 1
    Disarm.terminal_width("¡", ambiguous_wide: true) # => 2
    ```

=== "Node"

    ```ts
    import { terminalWidth } from 'disarm'

    terminalWidth('¡') // => 1
    terminalWidth('¡', { ambiguousWide: true }) // => 2
    ```

This measures **terminal cells**, not pixels or font metrics. Tabs are not
expanded and newlines are not modelled — layout that depends on tab stops or
wrapping is the caller's responsibility. Emoji-ZWJ and ambiguous widths are
inherently terminal-dependent; disarm's policy is fixed (ambiguous = 1 unless
`ambiguous_wide`, and an emoji-presented cluster = 2).

## Limitations

- **Display width is terminal cells, not pixels.** `terminal_width` /
  `grapheme_width` report monospace **column** counts (UAX #11), not font-metric
  or pixel widths, which depend on the rendering stack.
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
