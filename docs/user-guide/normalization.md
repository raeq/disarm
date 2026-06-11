# Normalization

Unicode normalization ensures that equivalent sequences of characters are represented identically. disarm provides fast normalization using the Rust `unicode-normalization` crate.

## Why normalize?

The same visible text can have multiple Unicode representations:

```python
# These look identical but are different byte sequences:
a = "\u00e9"       # U+00E9 (precomposed)
b = "\u0065\u0301" # U+0065 U+0301 (decomposed: e + combining acute)

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

```python
from disarm import normalize

# NFC: compose into single codepoints
assert normalize("e\u0301") == 'é'

# NFD: decompose into base + combining marks
assert normalize("é", form="NFD") == 'é'

# NFKC: compatibility + compose
assert normalize("ﬁnance", form="NFKC") == 'finance'
assert normalize("2²", form="NFKC") == '22'

# NFKD: compatibility + decompose
assert normalize("ﬁ", form="NFKD") == 'fi'
```

## Checking normalization

Test whether a string is already in a given form without performing the full normalization:

```python
from disarm import is_normalized

assert is_normalized("hello") == True
assert is_normalized("é", form="NFC") == True
assert is_normalized("é", form="NFD") == False
assert is_normalized("e\u0301", form="NFD") == True
```

## The NF enum

For programmatic use, the `NF` enum provides the four forms:

```python
from disarm import NF, normalize

assert normalize("ﬁ", form=NF.KC.value) == 'fi'
```

| Member | Value |
|---|---|
| `NF.C` | `"NFC"` |
| `NF.D` | `"NFD"` |
| `NF.KC` | `"NFKC"` |
| `NF.KD` | `"NFKD"` |

## When to use which form

- **NFC** — Default for most applications. Store and compare text in NFC.
- **NFD** — Use when you need to manipulate combining marks (e.g., `strip_accents()` uses NFD internally).
- **NFKC** — Use for search indexes and text matching where ﬁ should match fi.
- **NFKD** — Use for deep decomposition before further processing.

## Performance

Normalization is implemented in Rust via the `unicode-normalization` crate. Strings that are already in the target form are detected quickly via `is_normalized()` without allocation.
