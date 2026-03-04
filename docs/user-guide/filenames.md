# Filename Sanitization

`sanitize_filename()` converts arbitrary Unicode strings into safe filenames that work across operating systems. It handles transliteration, illegal character removal, reserved name detection, and length truncation.

## Basic usage

```python
from translit import sanitize_filename

sanitize_filename("my<file>:v2.txt")
# => "my_file_v2.txt"

sanitize_filename("café résumé.pdf")
# => "cafe_resume.pdf"

sanitize_filename("../../../etc/passwd")
# => "_.etcpasswd"

sanitize_filename("CON.txt")
# => "_CON.txt"  (Windows reserved name)
```

## Parameters

### separator

Character used to replace illegal characters (default: `"_"`):

```python
sanitize_filename("hello:world", separator="-")
# => "hello-world"
```

### max_length

Maximum filename length in bytes (default: `255`):

```python
sanitize_filename("a" * 300)
# => "aaa...aaa" (truncated to 255)
```

When `preserve_extension=True`, the extension is counted toward the limit and preserved:

```python
sanitize_filename("a" * 300 + ".pdf", max_length=20)
# => "aaaaaaaaaaaaaaaa.pdf"
```

### platform

Target platform for sanitization rules:

```python
# Universal (default) — safe on all platforms
sanitize_filename("my:file?.txt", platform="universal")
# => "my_file.txt"

# POSIX — only / and NUL are illegal
sanitize_filename("my:file?.txt", platform="posix")
# => "my:file?.txt"

# Windows — additionally forbids < > : " | ? * and reserved names
sanitize_filename("CON.txt", platform="windows")
# => "_CON.txt"
```

| Platform | Illegal characters | Reserved names |
|---|---|---|
| `"universal"` | Union of POSIX + Windows rules | CON, PRN, AUX, NUL, COM1–9, LPT1–9 |
| `"posix"` | `/`, NUL | None |
| `"windows"` | `< > : " / \\ \| ? *`, control chars | CON, PRN, AUX, NUL, COM1–9, LPT1–9 |

### lang

Language profile for transliteration of non-ASCII characters:

```python
sanitize_filename("Ärger.txt", lang="de")
# => "Aerger.txt"

sanitize_filename("Ärger.txt")
# => "Arger.txt"
```

### preserve_extension

Whether to preserve the file extension during truncation (default: `True`):

```python
sanitize_filename("long_name.pdf", max_length=12, preserve_extension=True)
# => "long_nam.pdf"

sanitize_filename("long_name.pdf", max_length=12, preserve_extension=False)
# => "long_name.pd"
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
