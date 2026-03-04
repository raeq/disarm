# translit

**Fast Unicode transliteration, slugification, and text normalization — powered by Rust.**

translit is a single, MIT-licensed Python package that replaces a constellation of legacy Unicode text-processing libraries — [Unidecode](https://pypi.org/project/Unidecode/), [text-unidecode](https://pypi.org/project/text-unidecode/), [python-slugify](https://pypi.org/project/python-slugify/), [awesome-slugify](https://pypi.org/project/awesome-slugify/), [anyascii](https://pypi.org/project/anyascii/), [confusable_homoglyphs](https://pypi.org/project/confusable-homoglyphs/), [pathvalidate](https://pypi.org/project/pathvalidate/), and more — with a single, coherent API backed by compiled Rust.

---

## Why translit?

| | Legacy libraries | translit |
|---|---|---|
| **Performance** | Pure Python | Rust via PyO3 — [see benchmarks](performance.md) |
| **License** | Mixed (GPL, Artistic, MIT) | MIT |
| **API surface** | 8+ packages, 8+ APIs | One package, one API |
| **Unicode coverage** | Varies widely | Comprehensive, consistent tables |
| **Language awareness** | Limited or none | 37 built-in language profiles |
| **Type safety** | Partial or missing | Full py.typed + stub coverage |

---

## Installation

```bash
pip install translit
```

Wheels are available for Linux, macOS, and Windows on Python 3.9+.

---

## Quick start

### Transliterate Unicode to ASCII

```python
from translit import transliterate

transliterate("Ünïcödé téxt")       # => "Unicode text"
transliterate("北京市")              # => "bei jing shi"
transliterate("Ü", lang="de")       # => "Ue" (German rules)
```

### Generate URL-safe slugs

```python
from translit import slugify

slugify("My Blog Post!")             # => "my-blog-post"
slugify("Ärger im Büro", lang="de") # => "aerger-im-buero"
```

### Detect and normalize confusable characters

```python
from translit import is_confusable, normalize_confusables

is_confusable("Неllo")              # => True (Cyrillic Н)
normalize_confusables("Неllo")      # => "Hello"
```

### Sanitize filenames

```python
from translit import sanitize_filename

sanitize_filename("my<file>:v2.txt")  # => "my_file_v2.txt"
```

### Compose a text-cleaning pipeline

```python
from translit import TextPipeline

pipe = TextPipeline(
    normalize="NFC",
    confusables=True,
    strip_accents=True,
    fold_case=True,
    collapse_whitespace=True,
)
pipe("  Héllo\u200b Wörld  ")  # => "hello world"
```

---

## Feature overview

- **[Transliteration](user-guide/transliteration.md)** — Unicode → ASCII with 37 language profiles
- **[Slugification](user-guide/slugification.md)** — URL-safe slug generation, drop-in python-slugify replacement
- **[Normalization](user-guide/normalization.md)** — NFC / NFD / NFKC / NFKD Unicode normalization
- **[Confusable detection](user-guide/confusables.md)** — TR39 homoglyph detection and normalization
- **[Filename sanitization](user-guide/filenames.md)** — Cross-platform safe filenames
- **[Text cleaning](user-guide/text-cleaning.md)** — Accent stripping, full Unicode case folding (1,557 CaseFolding.txt mappings), whitespace collapse
- **[Text pipeline](user-guide/pipeline.md)** — Composable, pre-compiled multi-step processing
- **[Language support](user-guide/language-support.md)** — 37 built-in profiles, extensible via `register_lang()`

---

## Migrating from legacy libraries

translit provides parameter-compatible replacements for existing libraries:

- [From Unidecode / text-unidecode](migration/from-unidecode.md)
- [From python-slugify / awesome-slugify](migration/from-python-slugify.md)
- [From confusable_homoglyphs](migration/from-confusable-homoglyphs.md)
- [From pathvalidate](migration/from-pathvalidate.md)
- [From anyascii](migration/from-anyascii.md)

---

## License

translit is released under the [MIT License](https://github.com/raeq/translit/blob/main/LICENSE).
