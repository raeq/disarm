# Normalization

Unicode normalization ensures that equivalent sequences of characters are represented identically. disarm provides fast normalization using the Rust `unicode-normalization` crate.

## Why normalize?

The same visible text can have multiple Unicode representations:

```python
# These look identical but are different byte sequences:
a = "\u00e9"  # U+00E9 (precomposed)
b = "\u0065\u0301"  # U+0065 U+0301 (decomposed: e + combining acute)

assert (a == b) == False
```

Normalization resolves this by converting to a canonical form.

## Normalization forms

| Form | Name | Description |
|---|---|---|
| **NFC** | Canonical Decomposition + Composition | Precomposed characters. Most common for storage and comparison. |
| **NFD** | Canonical Decomposition | Decomposed characters. Useful for accent stripping. |
| **NFKC** | Compatibility Decomposition + Composition | Like NFC but also normalizes compatibility characters (ﬁ→fi, ²→2). |
| **NFKD** | Compatibility Decomposition | Like NFD with compatibility decomposition. |

## Basic usage

=== "Python"

    ```python
    from disarm import normalize

    # NFC: compose into single codepoints
    assert normalize("e\u0301") == "é"

    # NFD: decompose into base + combining marks
    assert normalize("é", form="NFD") == "é"

    # NFKC: compatibility + compose
    assert normalize("ﬁnance", form="NFKC") == "finance"
    assert normalize("2²", form="NFKC") == "22"

    # NFKD: compatibility + decompose
    assert normalize("ﬁ", form="NFKD") == "fi"
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, NormalizationForm};

    // NFC: compose into single codepoints
    assert_eq!(api::normalize("e\u{0301}", NormalizationForm::Nfc), "é");
    // NFD: decompose into base + combining marks
    assert_eq!(api::normalize("é", NormalizationForm::Nfd), "é");
    // NFKC: compatibility + compose
    assert_eq!(api::normalize("ﬁnance", NormalizationForm::Nfkc), "finance");
    // NFKD: compatibility + decompose
    assert_eq!(api::normalize("ﬁ", NormalizationForm::Nfkd), "fi");
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    # form: is :nfc (default), :nfd, :nfkc, or :nfkd
    Disarm.normalize("ﬁnance", form: :nfkc)   # => "finance"
    Disarm.normalize("2²", form: :nfkc)       # => "22"
    Disarm.normalize("ﬁ", form: :nfkd)        # => "fi"
    ```

=== "Node"

    ```ts
    import { normalize } from 'disarm'

    normalize('ﬁnance', { form: 'NFKC' }) // => 'finance'
    normalize('2²', { form: 'NFKC' }) // => '22'
    normalize('ﬁ', { form: 'NFKD' }) // => 'fi'
    ```

## Checking normalization

Test whether a string is already in a given form without performing the full normalization:

=== "Python"

    ```python
    from disarm import is_normalized

    assert is_normalized("hello") == True
    assert is_normalized("é", form="NFC") == True
    assert is_normalized("é", form="NFD") == False
    assert is_normalized("e\u0301", form="NFD") == True
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, NormalizationForm};

    assert_eq!(api::is_normalized("hello", NormalizationForm::Nfc), true);
    assert_eq!(api::is_normalized("é", NormalizationForm::Nfc), true);
    assert_eq!(api::is_normalized("é", NormalizationForm::Nfd), false);
    assert_eq!(api::is_normalized("e\u{0301}", NormalizationForm::Nfd), true);
    ```

=== "Ruby"

    ```ruby
    Disarm.normalized?("hello")            # => true
    Disarm.normalized?("ﬁ", form: :nfkc)   # => false
    ```

=== "Node"

    ```ts
    import { isNormalized } from 'disarm'

    isNormalized('hello') // => true
    isNormalized('ﬁ', { form: 'NFKC' }) // => false
    ```

## The NF enum

For programmatic use, the `NF` enum provides the four forms:

```python
from disarm import NF, normalize

assert normalize("ﬁ", form=NF.KC.value) == "fi"
```

| Member | Value |
|---|---|
| `NF.C` | `"NFC"` |
| `NF.D` | `"NFD"` |
| `NF.KC` | `"NFKC"` |
| `NF.KD` | `"NFKD"` |

## Stream-Safe Text Format

UAX #15 defines a bound on how many non-starters may follow one starter — 30 — so that
text can be processed in fixed-size buffers without a normalization boundary landing
inside one. `stream_safe()` enforces it by inserting `U+034F COMBINING GRAPHEME JOINER`.

```python
from disarm import stream_safe, is_normalized_stream_safe, normalize

assert stream_safe("Hello world") == "Hello world"

long_stack = "a" + "\u0301" * 40
assert "\u034f" in stream_safe(long_stack)
```

This is an **interoperability** primitive. Three things it is not:

**Not canonically equivalent.** It inserts a character, so the output is a different
string and normalizes differently. Never build a comparison key from it — use
`search_key()` or `canonicalize()`.

```python
assert stream_safe(long_stack) != long_stack
assert normalize(stream_safe(long_stack), form="NFC") != normalize(long_stack, form="NFC")
```

**Not a zalgo control.** Thirty non-starters is far above anything a reader would call
stacking abuse, and this function makes no judgement about whether text is abusive.
`strip_zalgo()` answers that question, with a different bound and a different purpose.
Ordinary stacking abuse passes straight through:

```python
zalgo = "a" + "\u0301" * 8
assert stream_safe(zalgo) == zalgo  # under the bound
```

Legitimate stacking is nowhere near it either — Hebrew points, Arabic harakat and Indic
conjuncts are all untouched.

**Not a size bound.** The presets already cap produced output; `stream_safe()` does not
change how much text a call can return.

### The predicate is a conjunction

`is_normalized_stream_safe(text, form=...)` answers *"is this normalized **and**
stream-safe"*, not *"is this stream-safe"*. That is what the underlying Unicode predicate
computes, and the name says so rather than leaving it to be discovered:

```python
assert not is_normalized_stream_safe("e\u0301")  # stream-safe, but not NFC
assert is_normalized_stream_safe(normalize("e\u0301", form="NFC"))
```

## When to use which form

- **NFC** — Default for most applications. Store and compare text in NFC.
- **NFD** — Use when you need to manipulate combining marks (e.g., `strip_accents()` uses NFD internally).
- **NFKC** — Use for search indexes and text matching where ﬁ should match fi.
- **NFKD** — Use for deep decomposition before further processing.

## Performance

Normalization is implemented in Rust via the `unicode-normalization` crate. Strings that are already in the target form are detected quickly via `is_normalized()` without allocation.
