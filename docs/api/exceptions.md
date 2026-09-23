# Exceptions

disarm raises a small, unified exception hierarchy. Catch **`DisarmError`** to
handle any disarm failure; catch a subclass to react to a specific category.

```text
ValueError                     (Python built-in)
└── DisarmError              base — catch this for "any disarm error"
    ├── InvalidArgumentError   a bad argument value, or contradictory arguments
    ├── ResourceLimitError     a configured limit was exceeded
    └── UnsupportedError       a requested operation is not supported
```

```python
from disarm import (
    DisarmError,
    InvalidArgumentError,
    ResourceLimitError,
    UnsupportedError,
)
```

`DisarmError` inherits from Python's built-in **`ValueError`**, so existing
`except ValueError` code keeps working unchanged. As of
[#183](https://github.com/raeq/disarm/issues/183), **every error raised by
disarm's native API** is a `DisarmError` (or a subclass) — including the
mutually-exclusive-flag checks, registration limits, and the unsupported
reverse-transliteration language, which were previously bare `ValueError`s that
`except DisarmError` silently missed.

> **One deliberate exception:** the `unidecode()` compatibility shim's
> `errors="strict"` mode raises a bare `ValueError` (not a `DisarmError`), to
> match the behaviour of the `unidecode` package it replaces. disarm's own
> native strict mode (tracked in
> [#184](https://github.com/raeq/disarm/issues/184)) will raise a `DisarmError`.

## The categories

### `InvalidArgumentError`
An argument had an invalid value, or a combination of arguments was contradictory.

- An invalid normalization form (`form="INVALID"`), error mode (`errors="unknown"`),
  platform (`platform="bsd"`), emoji style, or target script.
- An unknown `lang` code, or an unknown encoding name.
- Mutually-exclusive arguments (e.g. `lang=` with `target=`, or `strict_iso9=True`
  with `gost7034=True`).
- A negative `max_length` / `max_graphemes`, or an out-of-range `min_confidence`.
- A `regex_pattern` that fails to compile, or `register_lang` keys that are not single
  characters.

### `ResourceLimitError`
A configured resource limit was exceeded.

- A batch larger than the maximum batch size.
- The registered-languages or replacements cap.
- A `regex_pattern` over the byte limit, or `UniqueSlugifier` exhausting its attempts.
- **Output** that grows past a limit — registered replacements expanding the input past
  10 MiB, or any step of a preset leaving the text more than 10 MiB **longer than the
  input** the preset was given. NFKC widens some code points by up to 18×, and
  `ml_normalize`'s emoji naming by up to 10× after it; the limit applies to whichever
  step does the growing. disarm does not cap input size (that is the caller's to bound):
  an input of any size that no step grows is accepted, and these two limits are the
  exceptions because both amplify by an amount an input-size check cannot foresee.
  `normalize(form="NFKC")` is deliberately not capped, because there the caller named
  the expansion.

  Until the Lean model in `formal/lean/Presets` (Finding 6), the preset limit was an
  absolute size checked after NFKC alone: 10.4 MB of `U+1FAF0` came out of `ml_normalize`
  as 106.6 MB, while 11 MiB of `a` after one `"` was refused as having "expanded".

### `UnsupportedError`
A requested operation is not supported.

- Reverse transliteration for a language that has no reverse table (`target=`).
- Auto-detecting an encoding whose detected label disarm does not support
  (`detect_encoding` / `decode_to_utf8` resolves a charset disarm cannot decode).
  The separate *low-confidence* case — auto-detection that cannot commit to any
  label — raises the base `DisarmError` (see below), not `UnsupportedError`.

### `DisarmError` (base, directly)
State and data conditions that fit no category above: registrations sealed,
a missing/corrupt context dictionary, encoding-detection confidence too low.

## `TypeError` is *not* part of the hierarchy

Passing an argument of the wrong **type** (e.g. an `int` where a `str` is expected)
raises a plain `TypeError`, by design — that is a programming error, not a disarm
domain error, and Python convention is to surface it as `TypeError`. If you want to
catch both disarm domain errors and wrong-type errors, catch
`(DisarmError, TypeError)`.

## Examples

```python
from disarm import transliterate, normalize, DisarmError, InvalidArgumentError

# Catch any disarm error
try:
    normalize("text", form="INVALID")
except DisarmError as e:
    print(f"disarm error: {e}")

# React to a specific category
try:
    transliterate("x", lang="de", target="ru")
except InvalidArgumentError:
    print("contradictory arguments")
```

Because `DisarmError` subclasses `ValueError`, you can also catch it as a
`ValueError`, or via a broader `Exception` handler.

## Error messages

Error messages name the offending value and (where applicable) the valid options or
remedy. Each `errors=` / `form=` / `platform=` value is validated **once, in the Rust
core** (#185) — the Python wrapper no longer keeps a hand-synced copy — so the message
text has a single source:

```text
form must be 'NFC', 'NFD', 'NFKC', or 'NFKD', got 'INVALID'
errors must be 'replace', 'ignore', or 'preserve', got 'unknown'
platform must be 'universal', 'windows', or 'posix', got 'bsd'
Invalid regex: <details from the regex engine>
```
