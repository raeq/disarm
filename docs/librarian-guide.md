# translit for Librarians and Catalogers

A guide to using translit for title normalization, catalog deduplication,
search index preparation, and bibliographic text processing.

Libraries deal with text that arrives in every encoding, script, and
typographic convention: full-width CJK punctuation, diacritical variants of
the same name, mixed-script transliterations, invisible Unicode characters,
and publisher-specific formatting quirks. translit provides a compiled
pipeline for normalizing this text into consistent forms suitable for
catalog matching, authority control, and search indexing.

---

## Quick Start: `catalog_key()`

translit provides `catalog_key()` — a precompiled pipeline for generating
canonical deduplication keys from bibliographic titles:

```python
from translit import catalog_key

catalog_key("Café")               # → "cafe"
catalog_key("CAFÉ")               # → "cafe"
catalog_key("café")               # → "cafe"

# All surface forms produce the same key
catalog_key("Ｔｈｅ Elements of Style")   # → "the elements of style"
catalog_key("The Éléments of Style")      # → "the elements of style"
catalog_key("THE ELEMENTS OF STYLE")      # → "the elements of style"

# Cyrillic with ISO 9 scholarly transliteration
catalog_key("Йога", strict_iso9=True)     # → "joga"

# Language-specific transliteration
catalog_key("Über allen Gipfeln", lang="de")  # → "ueber allen gipfeln"
```

`catalog_key()` executes a fixed Rust pipeline:
NFKC → confusables → [transliterate if lang/iso9] → strip_accents → fold_case → collapse_whitespace.

The confusable normalization step is important for catalogs — records
imported from heterogeneous sources may contain Cyrillic homoglyphs that
should match their Latin equivalents.

For more control, use `TextPipeline` directly (see below).

---

## The Core Task: Title Normalization for Deduplication

The same work can appear in a catalog under multiple surface forms that
should all resolve to one record. `catalog_key()` handles this, but
to understand what it does internally, here is the equivalent
`TextPipeline` configuration:

```python
from translit import TextPipeline

pipe = TextPipeline(
    normalize="NFKC",
    confusables=True,
    strip_accents=True,
    fold_case=True,
    collapse_whitespace=True,
)

titles = [
    "Ｔｈｅ Elements of Style",     # full-width Latin
    "The Éléments of Style",        # diacritical variants
    "The  Elements  of  Style",     # double spaces
    "THE ELEMENTS OF STYLE",        # all caps from OCR
]

normalized = set(pipe(t) for t in titles)
# → {"the elements of style"}  — one canonical form
```

All four variants collapse to the same normalized string. This is the
foundation for catalog deduplication, authority matching, and known-item
search.

---

## Normalization Forms: When to Use What

| Scenario | Normalization | Why |
|----------|---------------|-----|
| Catalog matching / dedup | NFKC | Collapses full-width, ligatures, compatibility variants |
| Display / storage | NFC | Preserves visual form, canonical composition |
| Accent-insensitive search | NFKC + strip_accents | "Éléments" matches "Elements" |
| Sort key generation | NFKC + transliterate + fold_case | Pure ASCII, case-folded |

### NFKC for Catalog Work

NFKC (Compatibility Composition) is the normalization form that matters
most for library applications. It resolves the variants that cause
duplicate records:

```python
from translit import normalize

# Full-width → standard width
normalize("Ｈｅｌｌｏ", form="NFKC")       # → "Hello"

# Ligatures → component characters
normalize("ﬁnancial", form="NFKC")       # → "financial"

# Circled/enclosed numbers → digits
normalize("①②③", form="NFKC")           # → "123"

# Superscripts → base characters
normalize("2ⁿᵈ Edition", form="NFKC")    # → "2nd Edition"

# Half-width Katakana → full-width
normalize("ﾊﾞﾅﾅ", form="NFKC")          # → "バナナ"
```

---

## Generating Sort Keys

Library catalogs need deterministic sort keys that place "À la recherche"
next to "A la recherche," not in a separate diacritical ghetto. translit
can generate ASCII sort keys from any script:

```python
from translit import TextPipeline

sort_pipe = TextPipeline(
    normalize="NFKC",
    transliterate=True,
    fold_case=True,
    collapse_whitespace=True,
)

titles = [
    "The Great Gatsby",
    "À la recherche du temps perdu",
    "Über allen Gipfeln",
    "Война и мир",
]

for t in sorted(titles, key=sort_pipe):
    print(f"  {sort_pipe(t):40s}  ←  {t}")
```

Output:
```
  a la recherche du temps perdu             ←  À la recherche du temps perdu
  the great gatsby                          ←  The Great Gatsby
  uber allen gipfeln                        ←  Über allen Gipfeln
  voyna i mir                               ←  Война и мир
```

All titles sort in a single ASCII collation sequence. No separate handling
for diacritics, Cyrillic, or special characters.

### Article Stripping for Filing

Many catalog systems file titles ignoring initial articles. Combine sort
key generation with article removal:

```python
import re

ARTICLES = re.compile(r"^(the|a|an|le|la|les|der|die|das|el|los|las)\s+", re.IGNORECASE)

def filing_key(title: str) -> str:
    normalized = sort_pipe(title)
    return ARTICLES.sub("", normalized)

filing_key("The Great Gatsby")      # → "great gatsby"
filing_key("Les Misérables")        # → "miserables"
filing_key("Der Zauberberg")        # → "zauberberg"
```

---

## Cyrillic Transliteration Standards

Library catalogs frequently need to romanize Cyrillic titles. translit
supports two standards:

### ISO 9:1995 (Scholarly / Library Standard)

ISO 9 is the standard specified by ALA-LC (American Library Association –
Library of Congress) romanization guidelines for most Cyrillic scripts. It
produces consistent, reversible results independent of source language:

```python
from translit import transliterate

transliterate("Война и мир", strict_iso9=True)
# → "Vojna i mir"

transliterate("Юность", strict_iso9=True)
# → "Junost"
```

### BGN/PCGN (Practical / Default)

The default romanization uses BGN/PCGN conventions, which are closer to
English phonetic expectations:

```python
transliterate("Война и мир")
# → "Voyna i mir"

transliterate("Юность")
# → "Yunost"
```

### Language-Specific Overrides

When the source language is known, language-specific romanization provides
the most accurate results:

```python
# Russian BGN/PCGN with sign markers
transliterate("большой", lang="ru")      # → "bol'shoy"

# Ukrainian KMU 2010
transliterate("Київ", lang="uk")          # → "Kyiv"

# Bulgarian streamlined system
transliterate("Щука", lang="bg")          # → "Shtuka"
```

### Choosing Between Standards

| Context | Standard | Flag |
|---------|----------|------|
| LC/OCLC catalog records | ISO 9 | `strict_iso9=True` |
| Patron-facing search | BGN/PCGN (default) | (no flag needed) |
| Ukrainian-specific records | KMU 2010 | `lang="uk"` |
| Bulgarian-specific records | Bulgarian streamlined | `lang="bg"` |

---

## Japanese Cataloging

Japanese records involve three scripts (hiragana, katakana, kanji) plus
half-width katakana from legacy systems. translit provides Modified Hepburn
romanization for kana and handles the half-width problem:

```python
from translit import transliterate, normalize

# Full-width Katakana
transliterate("ラーメン")             # → "ra-men"

# Hiragana
transliterate("すし")                 # → "sushi"

# Half-width Katakana (legacy MARC records)
transliterate("ｶﾀｶﾅ")               # → "katakana"

# Half-width with dakuten — normalize first
from translit import Text

Text("ﾊﾞﾅﾅ").normalize(form="NFKC").transliterate().value
# → "banana"
```

The NFKC normalization step is essential for half-width katakana with
combining dakuten/handakuten marks, as it merges them into precomposed
full-width forms that the transliteration table can handle correctly.

---

## Accent-Insensitive Search

For OPAC search, patrons should be able to find "Les Misérables" by
typing "les miserables." translit's accent stripping makes this possible:

```python
from translit import strip_accents, fold_case

def search_normalize(text: str) -> str:
    return fold_case(strip_accents(text))

search_normalize("Les Misérables")    # → "les miserables"
search_normalize("Ångström")          # → "angstrom"
search_normalize("naïve")             # → "naive"
```

Or as a pre-compiled pipeline for indexing:

```python
from translit import TextPipeline

search_pipe = TextPipeline(
    normalize="NFKC",
    strip_accents=True,
    fold_case=True,
    collapse_whitespace=True,
)

# Index both the original and the normalized form
for record in catalog:
    record.search_key = search_pipe(record.title)
```

---

## Detecting Mixed-Script Titles

Mixed-script text in catalog records is often a data quality issue — a
Cyrillic О substituted for a Latin O during OCR or data entry. translit
can flag these for review:

```python
from translit import is_mixed_script, detect_scripts, normalize_confusables

title = "Неllo World"  # Cyrillic Н + Latin ello

is_mixed_script(title)                # True
[s.value for s in detect_scripts(title)]  # ['Cyrillic', 'Latin']

# Auto-fix by normalizing confusables to Latin
normalize_confusables(title)          # → "Hello World"
```

This is particularly useful for batch quality control over catalog imports
and OCR output.

---

## Emoji in Modern Metadata

Modern metadata sources (social media archives, digital humanities corpora,
contemporary periodical indexes) increasingly contain emoji. translit can
expand these to searchable text:

```python
from translit import demojize

demojize("🔥 Hot Takes on AI")        # → "fire Hot Takes on AI"
demojize("🏳️‍🌈 Pride Collection")      # → "rainbow flag Pride Collection"
```

For catalog indexing, this means a search for "fire" will match a record
whose original title contained 🔥.

---

## Whitespace and Control Character Cleanup

OCR output and data imports frequently contain invisible control
characters, non-breaking spaces, zero-width joiners, and inconsistent
whitespace that can corrupt catalog records:

```python
from translit import collapse_whitespace

# Non-breaking space + em space
collapse_whitespace("Title\u00A0\u2003Here")   # → "Title Here"

# Multiple spaces from OCR
collapse_whitespace("The   Great   Gatsby")     # → "The Great Gatsby"
```

The `collapse_whitespace` step in `TextPipeline` also strips Unicode
control characters (U+0000–U+001F except whitespace) and zero-width
characters (ZWJ, ZWNJ, BOM, soft hyphen) that cause invisible data
corruption.

---

## The Text Builder for Ad-Hoc Processing

For interactive catalog cleanup or one-off processing in a Jupyter
notebook, the `Text` builder provides a chainable API:

```python
from translit import Text

result = (
    Text("  Ｔｈｅ  Éléments  of  Style  ")
    .normalize(form="NFKC")          # full-width → standard
    .strip_accents()             # É → E
    .fold_case()                 # T → t
    .collapse_whitespace()       # double spaces → single
    .value
)
# → "the elements of style"
```

---

## Putting It All Together: Catalog Import Pipeline

A complete pipeline for normalizing incoming catalog records. The
`catalog_key()` function handles the search/dedup key in one call;
use `TextPipeline` for sort keys and display normalization:

```python
from translit import catalog_key, display_clean, TextPipeline
from translit import is_mixed_script, detect_scripts

# Sort keys need transliteration (ASCII), so use TextPipeline
sort_pipe = TextPipeline(
    normalize="NFKC",
    transliterate=True,
    fold_case=True,
    collapse_whitespace=True,
)

for record in incoming_records:
    # Normalize for display (lightweight cleanup)
    record.display_title = display_clean(record.raw_title)

    # Generate dedup/search key (accent-insensitive, confusable-safe)
    record.search_key = catalog_key(record.raw_title)

    # Generate sort key (ASCII transliterated)
    record.sort_key = sort_pipe(record.raw_title)

    # Flag mixed-script records for review
    if is_mixed_script(record.raw_title):
        record.needs_review = True
        record.detected_scripts = [
            s.value for s in detect_scripts(record.raw_title)
        ]
```

---

## Handling Legacy Catalog Encodings

MARC records from older systems may be in ISO-8859-1, windows-1252, or
other legacy encodings rather than UTF-8. translit provides encoding
detection and conversion:

```python
from translit import detect_encoding, decode_to_utf8, catalog_key

# Detect encoding of a raw MARC field
encoding, confidence = detect_encoding(raw_bytes)

# Decode to UTF-8 (explicit encoding from MARC leader/008)
text, had_errors = decode_to_utf8(raw_bytes, encoding="ISO-8859-1")

# Decode to UTF-8 (auto-detect when metadata is missing)
text, had_errors = decode_to_utf8(raw_bytes)
if had_errors:
    record.needs_review = True  # lossy conversion flagged

# Then generate catalog key as usual
key = catalog_key(text)
```

**Caveat**: automatic encoding detection is probabilistic. Legacy catalog
records are often short (a title, an author name) which gives the detector
less signal. When the MARC leader specifies an encoding, always use it
explicitly rather than relying on auto-detection.

---

## Installation

```bash
pip install translit
```

Single wheel per platform. No Rust toolchain required for installation.
No runtime data downloads.
