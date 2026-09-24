# Filename Sanitization

`sanitize_filename()` converts arbitrary Unicode strings into safe filenames that work across operating systems. It handles transliteration, illegal character removal, reserved name detection, and length truncation.

!!! note "These examples are executed in CI"
    Every `python` block on this page runs against the shipped wheel and its
    asserted outputs are checked, so the results below cannot silently rot
    (see #154). Each `assert` is the guaranteed return value.

## Basic usage

=== "Python"

    ```python
    from disarm import sanitize_filename

    assert sanitize_filename("my<file>:v2.txt") == "my_file_v2.txt"
    assert sanitize_filename("café résumé.pdf") == "cafe_resume.pdf"
    assert sanitize_filename("../../../etc/passwd") == "_.etcpasswd"
    assert sanitize_filename("CON.txt") == "_CON.txt"  # Windows reserved name
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, Platform};

    // sanitize_filename(text, separator, max_length, platform, lang, preserve_extension)
    assert_eq!(api::sanitize_filename("my<file>:v2.txt", "_", 255, Platform::Universal, None, true).unwrap(), "my_file_v2.txt");
    assert_eq!(api::sanitize_filename("café résumé.pdf", "_", 255, Platform::Universal, None, true).unwrap(), "cafe_resume.pdf");
    assert_eq!(api::sanitize_filename("../../../etc/passwd", "_", 255, Platform::Universal, None, true).unwrap(), "_.etcpasswd");
    // CON.txt is a Windows reserved name
    assert_eq!(api::sanitize_filename("CON.txt", "_", 255, Platform::Universal, None, true).unwrap(), "_CON.txt");
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    Disarm.sanitize_filename("my<file>:v2.txt")  # => "my_file_v2.txt"
    Disarm.sanitize_filename("café résumé.pdf")  # => "cafe_resume.pdf"
    Disarm.sanitize_filename("CON.txt")          # => "_CON.txt"
    ```

=== "Node"

    ```ts
    import { sanitizeFilename } from 'disarm'

    sanitizeFilename('my<file>:v2.txt') // => 'my_file_v2.txt'
    sanitizeFilename('café résumé.pdf') // => 'cafe_resume.pdf'
    sanitizeFilename('CON.txt') // => '_CON.txt'
    ```

## Parameters

### separator

Character used to replace illegal characters (default: `"_"`):

=== "Python"

    ```python
    assert sanitize_filename("hello:world", separator="-") == "hello-world"
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, Platform};

    assert_eq!(api::sanitize_filename("hello:world", "-", 255, Platform::Universal, None, true).unwrap(), "hello-world");
    ```

=== "Ruby"

    ```ruby
    Disarm.sanitize_filename("hello:world", separator: "-")  # => "hello-world"
    ```

=== "Node"

    ```ts
    import { sanitizeFilename } from 'disarm'

    sanitizeFilename('hello:world', { separator: '-' }) // => 'hello-world'
    ```

The separator is inserted *after* the illegal characters are removed, so it is held to
the same rules: printable, non-space ASCII, no character illegal on the platform, and no
path separator (`/` or `\`, on every platform). Anything else raises
`InvalidArgumentError` rather than putting a `/`, a NUL or a bidi control back into the
name. The empty separator is allowed and simply drops what it would have replaced.

```python
from disarm import InvalidArgumentError

assert sanitize_filename("hello:world", separator="") == "helloworld"
for bad in ["/", "\\", " ", "\x00", "\u202e"]:
    try:
        sanitize_filename("../etc/passwd", separator=bad)
    except InvalidArgumentError:
        pass
    else:
        raise AssertionError(f"separator {bad!r} was accepted")
```

### max_length

Maximum filename length in bytes (default: `255`):

```python
assert len(sanitize_filename("a" * 300)) == 255
```

When `preserve_extension=True`, the extension is counted toward the limit and preserved:

```python
assert sanitize_filename("a" * 300 + ".pdf", max_length=20) == "aaaaaaaaaaaaaaaa.pdf"
```

### platform

Target platform for sanitization rules:

=== "Python"

    ```python
    # Universal (default) — safe on all platforms
    assert sanitize_filename("my:file?.txt", platform="universal") == "my_file.txt"

    # POSIX — only / and NUL are illegal
    assert sanitize_filename("my:file?.txt", platform="posix") == "my:file?.txt"

    # Windows — additionally forbids < > : " | ? * and reserved names
    assert sanitize_filename("CON.txt", platform="windows") == "_CON.txt"
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, Platform};

    // Universal (default) — safe on all platforms
    assert_eq!(api::sanitize_filename("my:file?.txt", "_", 255, Platform::Universal, None, true).unwrap(), "my_file.txt");

    // POSIX — only / and NUL are illegal
    assert_eq!(api::sanitize_filename("my:file?.txt", "_", 255, Platform::Posix, None, true).unwrap(), "my:file?.txt");

    // Windows — additionally forbids < > : " | ? * and reserved names
    assert_eq!(api::sanitize_filename("CON.txt", "_", 255, Platform::Windows, None, true).unwrap(), "_CON.txt");
    ```

=== "Ruby"

    ```ruby
    # Universal (default) — safe on all platforms
    Disarm.sanitize_filename("my:file?.txt", platform: :universal)  # => "my_file.txt"
    # POSIX — only / and NUL are illegal
    Disarm.sanitize_filename("my:file?.txt", platform: :posix)      # => "my:file?.txt"
    # Windows — additionally forbids < > : " | ? * and reserved names
    Disarm.sanitize_filename("CON.txt", platform: :windows)         # => "_CON.txt"
    ```

=== "Node"

    ```ts
    import { sanitizeFilename } from 'disarm'

    sanitizeFilename('my:file?.txt', { platform: 'universal' }) // => 'my_file.txt'
    sanitizeFilename('my:file?.txt', { platform: 'posix' }) // => 'my:file?.txt'
    sanitizeFilename('CON.txt', { platform: 'windows' }) // => '_CON.txt'
    ```

| Platform | Illegal characters | Reserved names |
|---|---|---|
| `"universal"` | Union of POSIX + Windows rules | CON, PRN, AUX, NUL, COM1–9, LPT1–9 |
| `"posix"` | `/`, NUL | None |
| `"windows"` | `< > : " / \\ \| ? *`, control chars | CON, PRN, AUX, NUL, COM1–9, LPT1–9 |

### lang

Language profile for transliteration of non-ASCII characters:

=== "Python"

    ```python
    # German profile expands umlauts (ä → ae)
    assert sanitize_filename("Ärger.txt", lang="de") == "Aerger.txt"

    # Default profile strips the diaeresis (ä → a)
    assert sanitize_filename("Ärger.txt") == "Arger.txt"
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, Platform};

    // German profile expands umlauts (ä → ae)
    assert_eq!(api::sanitize_filename("Ärger.txt", "_", 255, Platform::Universal, Some("de"), true).unwrap(), "Aerger.txt");

    // Default profile strips the diaeresis (ä → a)
    assert_eq!(api::sanitize_filename("Ärger.txt", "_", 255, Platform::Universal, None, true).unwrap(), "Arger.txt");
    ```

=== "Ruby"

    ```ruby
    # German profile expands umlauts (ä → ae)
    Disarm.sanitize_filename("Ärger.txt", lang: "de")  # => "Aerger.txt"
    # Default profile strips the diaeresis (ä → a)
    Disarm.sanitize_filename("Ärger.txt")              # => "Arger.txt"
    ```

=== "Node"

    ```ts
    import { sanitizeFilename } from 'disarm'

    sanitizeFilename('Ärger.txt', { lang: 'de' }) // => 'Aerger.txt'
    sanitizeFilename('Ärger.txt') // => 'Arger.txt'
    ```

### preserve_extension

Whether to preserve the file extension during truncation (default: `True`):

```python
assert sanitize_filename("long_name.pdf", max_length=12, preserve_extension=True) == "long_nam.pdf"
assert sanitize_filename("long_name.pdf", max_length=12, preserve_extension=False) == "long_name.pd"
```

## Pipeline

The sanitization pipeline executes in this order:

1. Transliterate non-ASCII characters (using `lang` if set), collapsing `..` runs before
   and after
2. Strip OS-illegal characters (per `platform`)
3. Replace stripped characters with `separator` (never at the start of the name)
4. Collapse consecutive separators
5. Strip trailing separators, and leading and trailing dots and spaces, repeating until
   none is left (`"a._._"` loses both layers in one pass)
6. Handle reserved names (prefix with `_`)
7. Truncate to `max_length` (respecting `preserve_extension`)
8. Strip leading and trailing dots and spaces from the whole name, then check it for a
   reserved name once more, as Windows reads it: the part before the first dot

Steps 2–8 then run again on their own output until it stops changing, so the result is a
fixed point: sanitizing a sanitized name returns it unchanged. One pass is not always
enough — truncation can end a stem on a separator, and an extension that cleans to
nothing moves the split to an earlier dot — and a name that changes on the second call
defeats deduplication between systems that sanitize a different number of times.

```python
for text, kwargs in [
    ("_.x.*", {}),
    ("ab_cd", {"max_length": 3, "preserve_extension": False}),
    ("a.bcd.txt", {"max_length": 6}),
    ("*.con", {}),
    ("a" + ".*" * 9, {"preserve_extension": False}),
]:
    once = sanitize_filename(text, **kwargs)
    assert sanitize_filename(once, **kwargs) == once

assert (
    sanitize_filename("*.con") == "_con"
)  # the stem sanitizes away; the name is still not a device
```
