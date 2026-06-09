# Text Cleaning

translit provides three low-level text cleaning functions that operate on individual aspects of Unicode text. These are building blocks — for multi-step cleaning, see [TextPipeline](pipeline.md).

## strip_accents

Remove diacritical marks while preserving base characters:

```python
from translit import strip_accents

assert strip_accents("café") == 'cafe'
assert strip_accents("naïve") == 'naive'
assert strip_accents("résumé") == 'resume'
assert strip_accents("Ångström") == 'Angstrom'
assert strip_accents("São Paulo") == 'Sao Paulo'
```

### How it works

1. NFD decompose — split precomposed characters into base + combining marks
2. Filter — remove all combining diacritical marks (U+0300–U+036F)
3. NFC recompose — rejoin remaining sequences

!!! note
    `strip_accents()` is distinct from `transliterate()`. Stripping accents preserves the original script (e.g., Cyrillic stays Cyrillic), while transliteration converts everything to ASCII.

## strip_zalgo

Remove excessive combining marks (zalgo text abuse) while preserving legitimate diacritics:

```python
from translit import strip_zalgo, is_zalgo

# Legitimate diacritics are preserved
assert strip_zalgo("café") == 'café'
assert strip_zalgo("Việt Nam") == 'Việt Nam'

# Zalgo stacking is stripped to max_marks (default: 2)
is_zalgo("café")             # False
is_zalgo("ḧ̸̡̢̧̛̗̱́̑̾̊̿̏̒̓̕ě̵̢̧̛̗̱̈́̑̾̊̿̏̒̓̕l̸̡̢̧̛̗̱̈́̑̾̊̿̏̒̓̕l̸̡̢̧̛̗̱̈́̑̾̊̿̏̒̓̕o")  # True
```

### strip_zalgo vs strip_accents

| Function | Purpose | `café` | Zalgo `h̷̑ȇ̷l̷̑l̷̑ȏ̷` |
|---|---|---|---|
| `strip_zalgo()` | Remove excess marks only | `café` | `hello` |
| `strip_accents()` | Remove **all** marks | `cafe` | `hello` |

Use `strip_zalgo()` when you want to preserve legitimate diacritics in multilingual text. Use `strip_accents()` when you want fully ASCII-compatible output.

## fold_case

Full Unicode case folding per CaseFolding.txt (Unicode 16.0) — a more thorough alternative to `.lower()`. Backed by a compile-time PHF table containing all 1,557 status-C and status-F mappings:

```python
from translit import fold_case

# Latin
assert fold_case("HELLO") == 'hello'
assert fold_case("Straße") == 'strasse'
assert fold_case("İstanbul") == 'i̇stanbul'
assert fold_case("ﬁnance") == 'finance'
assert fold_case("ﬂight") == 'flight'

# Greek variant forms
assert fold_case("ϐ ϑ ϕ ϖ ϰ ϱ") == 'β θ φ π κ ρ'
assert fold_case("ς") == 'σ'

# Scripts that .lower() misses entirely
assert fold_case("\u00B5") == 'μ'
assert fold_case("\u017F") == 's'
assert fold_case("\u1C90") == 'ა'
assert fold_case("\U0001E900") == '𞤢'
```

### When to use fold_case vs .lower()

| Operation | `ß` | `İ` | `ﬁ` | `µ` | `ſ` | `ς` |
|---|---|---|---|---|---|---|
| `.lower()` | `ß` | `i̇` | `ﬁ` | `µ` | `ſ` | `ς` |
| `fold_case()` | `ss` | `i̇` | `fi` | `μ` | `s` | `σ` |

Use `fold_case()` when you need case-insensitive comparison that handles the full Unicode case folding rules. It covers Latin, Greek, Cyrillic, Armenian (including the և→եւ ligature), Georgian Mtavruli, Cherokee, Adlam, Deseret, Osage, Warang Citi, and fullwidth Latin. Pure-ASCII strings take a branchless fast path with no table lookup.

!!! tip
    `fold_case()` produces identical output to Python's `str.casefold()` — but runs in Rust.

## collapse_whitespace

Normalize all Unicode whitespace variants to single ASCII spaces:

```python
from translit import collapse_whitespace

# Collapse runs of whitespace
assert collapse_whitespace("hello   world") == 'hello world'

# Normalize Unicode whitespace variants
assert collapse_whitespace("hello\u00a0world") == 'hello world'

assert collapse_whitespace("hello\u2003world") == 'hello world'
```

### Control characters

By default, control characters (U+0000–U+001F, U+007F–U+009F) are stripped:

```python
assert collapse_whitespace("hello\x00world") == 'helloworld'

# Keep control characters
assert collapse_whitespace("hello\x00world", strip_control=False) == 'hello\x00world'
```

### Zero-width characters

By default, zero-width characters are stripped:

```python
assert collapse_whitespace("hello\u200bworld") == 'helloworld'

assert collapse_whitespace("hello\ufeffworld") == 'helloworld'

# Keep zero-width characters
assert collapse_whitespace("hello\u200bworld", strip_zero_width=False) == 'hello\u200bworld'
```

Zero-width characters handled:

- U+200B Zero Width Space (ZWSP)
- U+200C Zero Width Non-Joiner (ZWNJ)
- U+200D Zero Width Joiner (ZWJ)
- U+FEFF Byte Order Mark / Zero Width No-Break Space
- U+2060 Word Joiner
