# Exceptions

translit raises a small, unified exception hierarchy. Catch **`TranslitError`** to
handle any translit failure; catch a subclass to react to a specific category.

```text
ValueError                     (Python built-in)
└── TranslitError              base — catch this for "any translit error"
    ├── InvalidArgumentError   a bad argument value, or contradictory arguments
    ├── ResourceLimitError     a configured limit was exceeded
    └── UnsupportedError       a requested operation is not supported
```

```python
from translit import (
    TranslitError,
    InvalidArgumentError,
    ResourceLimitError,
    UnsupportedError,
)
```

`TranslitError` inherits from Python's built-in **`ValueError`**, so existing
`except ValueError` code keeps working unchanged. As of
[#183](https://github.com/raeq/translit/issues/183), **every error raised by
translit's native API** is a `TranslitError` (or a subclass) — including the
mutually-exclusive-flag checks, registration limits, and the unsupported
reverse-transliteration language, which were previously bare `ValueError`s that
`except TranslitError` silently missed.

> **One deliberate exception:** the `unidecode()` compatibility shim's
> `errors="strict"` mode raises a bare `ValueError` (not a `TranslitError`), to
> match the behaviour of the `unidecode` package it replaces. translit's own
> native strict mode (tracked in
> [#184](https://github.com/raeq/translit/issues/184)) will raise a `TranslitError`.

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

### `UnsupportedError`
A requested operation is not supported.

- Reverse transliteration for a language that has no reverse table (`target=`).
- Auto-detecting an encoding whose detected label translit does not support
  (`detect_encoding` / `decode_to_utf8` resolves a charset translit cannot decode).
  The separate *low-confidence* case — auto-detection that cannot commit to any
  label — raises the base `TranslitError` (see below), not `UnsupportedError`.

### `TranslitError` (base, directly)
State and data conditions that fit no category above: registrations sealed,
a missing/corrupt context dictionary, encoding-detection confidence too low.

## `TypeError` is *not* part of the hierarchy

Passing an argument of the wrong **type** (e.g. an `int` where a `str` is expected)
raises a plain `TypeError`, by design — that is a programming error, not a translit
domain error, and Python convention is to surface it as `TypeError`. If you want to
catch both translit domain errors and wrong-type errors, catch
`(TranslitError, TypeError)`.

## Examples

```python
from translit import transliterate, normalize, TranslitError, InvalidArgumentError

# Catch any translit error
try:
    normalize("text", form="INVALID")
except TranslitError as e:
    print(f"translit error: {e}")

# React to a specific category
try:
    transliterate("x", lang="de", target="ru")
except InvalidArgumentError:
    print("contradictory arguments")
```

Because `TranslitError` subclasses `ValueError`, you can also catch it as a
`ValueError`, or via a broader `Exception` handler.

## Error messages

Error messages name the offending value and (where applicable) the valid options or
remedy. They originate in the Rust core — with the `errors=`/`form=` text currently
mirrored verbatim in the Python wrapper as well (see the note below):

```text
form must be 'NFC', 'NFD', 'NFKC', or 'NFKD', got 'INVALID'
errors must be 'replace', 'ignore', or 'preserve', got 'unknown'
platform must be 'universal', 'windows', or 'posix', got 'bsd'
Invalid regex: <details from the regex engine>
```

> The `errors=`/`form=` checks are, for now, *also* validated in the Python wrapper with
> identical text; collapsing that duplication into the core is tracked in
> [#185](https://github.com/raeq/translit/issues/185).
