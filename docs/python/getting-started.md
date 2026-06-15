# disarm for Python

disarm ships as a prebuilt wheel — the Rust core is compiled in, so there is no
Rust toolchain to install. The package and the import share one name, `disarm`.

## Install

```bash
pip install disarm
```

Requires Python 3.10+. Wheels are published for Linux, macOS, and Windows; on
other platforms pip builds from source (which needs a Rust toolchain).

```python
import disarm
```

## Quick start

The two operations people most often confuse are *visual* confusable folding
(homoglyph defence) and *phonetic* transliteration (romanization) — see
[Which function do I want?](../concepts/which-function.md) for the distinction.

```python
from disarm import (
    normalize_confusables, strip_obfuscation, transliterate, slugify,
    is_suspicious_hostname,
)

# Visual (TR39) confusable folding — homoglyph defence
assert normalize_confusables("раypal") == "paypal"   # Cyrillic р/а → Latin
assert strip_obfuscation("рroduсt") == "product"

# Phonetic romanization — readable ASCII, NOT a security control.
# A language profile sharpens the output: the uk profile gives Київ → Kyiv.
assert transliterate("Київ", lang="uk") == "Kyiv"
assert slugify("Héllo Wörld") == "hello-world"

# Hostname / IDN spoof check (a False result is not a safety guarantee)
suspicious, _analysis = is_suspicious_hostname("аpple.com")
assert suspicious is True
```

## Errors

Fallible operations raise `disarm.DisarmError`; a single `except DisarmError`
catches everything disarm raises. See [Exceptions](../api/exceptions.md).

## Where next

- **Concepts** (shared across every language) — start with
  [Which function do I want?](../concepts/which-function.md), then the topic
  guides under *Guide* in the sidebar.
- **API reference** — the full Python surface is under
  [API Reference](../api/index.md).
- **Migrating** from `unidecode`, `python-slugify`, `confusable_homoglyphs`,
  `anyascii`, or `pathvalidate`? See [Migration](../migration/index.md).
