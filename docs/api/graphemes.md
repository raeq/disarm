# Grapheme Clusters

Functions for working with user-perceived characters (extended grapheme clusters) as defined by UAX #29. These give correct results for emoji, combining characters, and complex scripts where Python's `len()` overcounts.

## grapheme_len

::: disarm.grapheme_len

```python
from disarm import grapheme_len

assert grapheme_len("café") == 4
assert grapheme_len("👨‍👩‍👧‍👦") == 1
assert grapheme_len("🇫🇷") == 1
assert grapheme_len("é") == 1
```

---

## grapheme_split

::: disarm.grapheme_split

```python
from disarm import grapheme_split

assert grapheme_split("café") == ['c', 'a', 'f', 'é']
assert grapheme_split("👨‍👩‍👧‍👦!") == ['👨\u200d👩\u200d👧\u200d👦', '!']
```

!!! note
    Input is limited to 10 MB to prevent excessive memory allocation. Raises `DisarmError` for larger inputs.

---

## grapheme_truncate

::: disarm.grapheme_truncate

```python
from disarm import grapheme_truncate

assert grapheme_truncate("Hello World", 5) == 'Hello'
assert grapheme_truncate("café", 3) == 'caf'
assert grapheme_truncate("👨‍👩‍👧‍👦🎉", 1) == '👨\u200d👩\u200d👧\u200d👦'
```

Unlike byte-level or codepoint-level truncation, `grapheme_truncate` never splits a grapheme cluster, which would corrupt emoji, combining sequences, or Hangul syllables.
