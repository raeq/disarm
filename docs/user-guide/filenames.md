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

### preserve_extension

Whether to preserve the file extension during truncation (default: `True`):

```python
assert sanitize_filename("long_name.pdf", max_length=12, preserve_extension=True) == "long_nam.pdf"
assert sanitize_filename("long_name.pdf", max_length=12, preserve_extension=False) == "long_name.pd"
```

## Pipeline

The sanitization pipeline executes in this order:

1. Transliterate non-ASCII characters (using `lang` if set)
2. Strip OS-illegal characters (per `platform`)
3. Replace stripped characters with `separator`
4. Collapse consecutive separators
5. Handle reserved names (prefix with `_`)
6. Truncate to `max_length` (respecting `preserve_extension`)
7. Strip leading/trailing separators and dots
