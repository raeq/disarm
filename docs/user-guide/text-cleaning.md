# Text Cleaning

disarm provides three low-level text cleaning functions that operate on individual aspects of Unicode text. These are building blocks — for multi-step cleaning, see [TextPipeline](pipeline.md).

## strip_accents

Remove diacritical marks while preserving base characters:

=== "Python"

    ```python
    from disarm import strip_accents

    assert strip_accents("café") == 'cafe'
    assert strip_accents("naïve") == 'naive'
    assert strip_accents("résumé") == 'resume'
    assert strip_accents("Ångström") == 'Angstrom'
    assert strip_accents("São Paulo") == 'Sao Paulo'
    ```

=== "Rust"

    ```rust
    use disarm::api;

    assert_eq!(api::strip_accents("café"), "cafe");
    assert_eq!(api::strip_accents("naïve"), "naive");
    assert_eq!(api::strip_accents("résumé"), "resume");
    assert_eq!(api::strip_accents("Ångström"), "Angstrom");
    assert_eq!(api::strip_accents("São Paulo"), "Sao Paulo");
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    Disarm.strip_accents("café")      # => "cafe"
    Disarm.strip_accents("naïve")     # => "naive"
    Disarm.strip_accents("résumé")    # => "resume"
    Disarm.strip_accents("Ångström")  # => "Angstrom"
    Disarm.strip_accents("São Paulo") # => "Sao Paulo"
    ```

=== "Node"

    ```ts
    import { stripAccents } from 'disarm'

    stripAccents('café') // => 'cafe'
    stripAccents('naïve') // => 'naive'
    stripAccents('résumé') // => 'resume'
    stripAccents('Ångström') // => 'Angstrom'
    stripAccents('São Paulo') // => 'Sao Paulo'
    ```

### How it works

1. NFD decompose — split precomposed characters into base + combining marks
2. Filter — remove all combining diacritical marks (U+0300–U+036F)
3. NFC recompose — rejoin remaining sequences

!!! note
    `strip_accents()` is distinct from `transliterate()`. Stripping accents preserves the original script (e.g., Cyrillic stays Cyrillic), while transliteration converts everything to ASCII.

## strip_zalgo

Remove excessive combining marks (zalgo text abuse) while preserving legitimate diacritics:

=== "Python"

    ```python
    from disarm import strip_zalgo, is_zalgo

    # Legitimate diacritics are preserved
    assert strip_zalgo("café") == 'café'
    assert strip_zalgo("Việt Nam") == 'Việt Nam'

    # Zalgo stacking is stripped to max_marks (default: 2)
    is_zalgo("café")             # False
    is_zalgo("ḧ̸̡̢̧̛̗̱́̑̾̊̿̏̒̓̕ě̵̢̧̛̗̱̈́̑̾̊̿̏̒̓̕l̸̡̢̧̛̗̱̈́̑̾̊̿̏̒̓̕l̸̡̢̧̛̗̱̈́̑̾̊̿̏̒̓̕o")  # True
    ```

=== "Rust"

    ```rust
    use disarm::api;

    // Legitimate diacritics are preserved
    assert_eq!(api::strip_zalgo("café", 2), "café");
    assert_eq!(api::strip_zalgo("Việt Nam", 2), "Việt Nam");

    // Zalgo stacking is stripped to max_marks (default: 2)
    assert_eq!(api::is_zalgo("café", 3), false);
    ```

=== "Ruby"

    ```ruby
    # Legitimate diacritics are preserved; zalgo stacking is capped
    Disarm.strip_zalgo("café")   # => "café"
    Disarm.zalgo?("café")        # => false
    ```

=== "Node"

    ```ts
    import { stripZalgo, isZalgo } from 'disarm'

    stripZalgo('café') // => 'café'
    isZalgo('café') // => false
    ```

### strip_zalgo vs strip_accents

| Function | Purpose | `café` | Zalgo `h̷̑ȇ̷l̷̑l̷̑ȏ̷` |
|---|---|---|---|
| `strip_zalgo()` | Remove excess marks only | `café` | `hello` |
| `strip_accents()` | Remove **all** marks | `cafe` | `hello` |

Use `strip_zalgo()` when you want to preserve legitimate diacritics in multilingual text. Use `strip_accents()` when you want fully ASCII-compatible output.

## fold_case

Full Unicode case folding per CaseFolding.txt (Unicode 16.0) — a more thorough alternative to `.lower()`. Backed by a compile-time PHF table containing all 1,557 status-C and status-F mappings:

=== "Python"

    ```python
    from disarm import fold_case

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

=== "Rust"

    ```rust
    use disarm::api;

    // Latin
    assert_eq!(api::fold_case("HELLO"), "hello");
    assert_eq!(api::fold_case("Straße"), "strasse");
    assert_eq!(api::fold_case("ﬁnance"), "finance");

    // Greek variant forms
    assert_eq!(api::fold_case("ς"), "σ");

    // Scripts that .lower() misses entirely
    assert_eq!(api::fold_case("\u{00B5}"), "μ");
    assert_eq!(api::fold_case("\u{017F}"), "s");
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    # Latin
    Disarm.fold_case("HELLO")    # => "hello"
    Disarm.fold_case("Straße")   # => "strasse"
    Disarm.fold_case("ﬁnance")   # => "finance"

    # Greek variant forms
    Disarm.fold_case("ς")        # => "σ"
    ```

=== "Node"

    ```ts
    import { foldCase } from 'disarm'

    foldCase('HELLO') // => 'hello'
    foldCase('Straße') // => 'strasse'
    foldCase('ﬁnance') // => 'finance'
    foldCase('ς') // => 'σ'
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

Fold every run of Unicode whitespace to a single ASCII space and trim the ends.
Since #433 this folds **whitespace only** — it does not delete control or
zero-width characters (see the note below).

=== "Python"

    ```python
    from disarm import collapse_whitespace

    # Collapse runs of whitespace
    assert collapse_whitespace("hello   world") == 'hello world'

    # Normalize Unicode whitespace variants
    assert collapse_whitespace("hello world") == 'hello world'
    assert collapse_whitespace("hello world") == 'hello world'
    ```

=== "Rust"

    ```rust
    use disarm::api;

    // Fold runs of whitespace
    assert_eq!(api::collapse_whitespace("hello   world"), "hello world");

    // Normalize Unicode whitespace variants
    assert_eq!(api::collapse_whitespace("hello\u{00a0}world"), "hello world");
    assert_eq!(api::collapse_whitespace("hello\u{2003}world"), "hello world");
    ```

=== "Ruby"

    ```ruby
    Disarm.collapse_whitespace("  hello   world  ")  # => "hello world"
    ```

=== "Node"

    ```ts
    import { collapseWhitespace } from 'disarm'

    collapseWhitespace('  hello   world  ') // => 'hello world'
    ```

### Line controls and blank-rendering code points fold to a space (#433)

The line controls — VT, FF, CR, NEL, and the information separators
(U+001C–U+001F) — are Unicode whitespace, so they **fold to a single space**
rather than being deleted (deleting them silently joined the surrounding
tokens). Blank-rendering code points that no whitespace category reaches — the
Braille blank (U+2800) and the Hangul fillers (U+115F, U+1160, U+3164, U+FFA0) —
fold too.

```python
assert collapse_whitespace("a\rb") == 'a b'          # carriage return → space
assert collapse_whitespace("a⠀b") == 'a b'    # Braille blank → space
assert collapse_whitespace("aㅤb") == 'a b'    # Hangul filler → space
```

### Stripping control and zero-width characters

`collapse_whitespace` no longer deletes control or zero-width characters — that
is a separate concern, so a non-whitespace control (NUL) or a zero-width space
passes through unchanged:

```python
assert collapse_whitespace("hello\x00world") == 'hello\x00world'
assert collapse_whitespace("hello​world") == 'hello​world'
```

To also delete them, run the dedicated steps first. The `security_clean` /
`normalize_user_input` presets already do this internally; to compose it
yourself, build a [`TextPipeline`](../api/pipelines.md) with the `strip_control`,
`strip_zero_width`, and `collapse_whitespace` steps (Rust, Node, and Ruby also
expose the standalone `strip_control_chars` / `strip_zero_width_chars` primitives
directly; Python exposes them only as pipeline steps).

Zero-width characters handled by the `strip_zero_width` step:

- U+200B Zero Width Space (ZWSP)
- U+200C Zero Width Non-Joiner (ZWNJ)
- U+200D Zero Width Joiner (ZWJ)
- U+FEFF Byte Order Mark / Zero Width No-Break Space
- U+2060 Word Joiner
