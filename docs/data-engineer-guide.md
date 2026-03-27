# translit for Data Engineers

A guide to using translit for text normalization, deduplication, encoding
handling, and identifier generation in ETL pipelines, data warehouses,
and workflow orchestration systems.

Data engineering pipelines ingest text from dozens of sources — user forms,
third-party APIs, legacy databases, CSV exports, web scrapes — each with
its own encoding, normalization form, and character conventions. translit
provides compiled Rust transforms that standardize text at ingestion time,
before it reaches your warehouse or downstream consumers.

---

## Quick Start: `catalog_key()`

The most common data engineering need is a canonical key for deduplication
and matching. `catalog_key()` produces a normalized, lowercase, ASCII string
from any Unicode input:

```python
from translit import catalog_key

catalog_key("Café Résumé")           # → "cafe resume"
catalog_key("CAFÉ RÉSUMÉ")           # → "cafe resume"
catalog_key("café résumé")           # → "cafe resume"

# All three inputs produce the same key — ready for dedup
```

`catalog_key()` executes a fixed Rust pipeline:
NFKC → transliterate → confusables → strip_accents → fold_case → collapse_whitespace.

This handles ligatures (`ﬁ` → `fi`), fullwidth characters (`Ｈｅｌｌｏ` → `Hello`),
accented variants, Cyrillic/Greek lookalikes, and case differences — all in
a single compiled pass.

---

## Deduplication and Record Matching

### The Problem

The same entity appears in different databases with different surface forms:

| Source A | Source B | Source C |
|---|---|---|
| `"Müller, Hans"` | `"MUELLER, HANS"` | `"Mueller Hans"` |
| `"São Paulo"` | `"Sao Paulo"` | `"SAO PAULO"` |
| `"Ångström"` | `"Angstrom"` | `"ÅNGSTRÖM"` |

Direct string equality fails. Even lowercasing and stripping whitespace
misses accent and transliteration differences.

### The Solution

Generate a canonical key for each record and match on that:

```python
from translit import catalog_key

records = [
    "Müller, Hans",
    "MUELLER, HANS",
    "Mueller Hans",
]

keys = [catalog_key(r) for r in records]
# ['muller, hans', 'mueller, hans', 'mueller hans']
```

For German-aware matching where `ü` → `ue` (not `u`), pass `lang="de"`:

```python
from translit import catalog_key

catalog_key("Müller", lang="de")     # → "mueller"
catalog_key("Mueller")               # → "mueller"
# Now they match
```

When the source language is unknown (e.g., multi-lingual data feeds), use
`lang="auto"` to detect the script and apply the appropriate language profile:

```python
catalog_key("Москва", lang="auto")    # → "moskva" (detects Cyrillic → Russian)
catalog_key("ภาษาไทย", lang="auto")   # → Thai romanization (detects Thai)
catalog_key("café", lang="auto")      # → "cafe" (Latin-only → default table)
```

### Batch Deduplication

For large datasets, use the batch APIs to amortize Python↔Rust overhead:

```python
from translit import transliterate_batch, strip_accents_batch

names = ["Müller", "São Paulo", "Ångström"] * 1000  # 3000 records

# Single boundary crossing for all 3000 strings
ascii_names = transliterate_batch(names)
clean_names = strip_accents_batch(names)
```

Batch APIs process up to 100,000 strings per call. For larger datasets,
chunk your input:

```python
from translit import transliterate_batch

def chunked(lst, size=50_000):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

results = []
for chunk in chunked(massive_list):
    results.extend(transliterate_batch(chunk))
```

---

## Search and Sort Keys

### search_key()

`search_key()` produces a case-insensitive, accent-insensitive, script-insensitive
lookup key — ideal for search indexes, WHERE clauses, and fuzzy matching:

```python
from translit import search_key

search_key("Café RÉSUMÉ")              # → "cafe resume"
search_key("café résumé")              # → "cafe resume"
search_key("CAFE RESUME")              # → "cafe resume"
# All three match

search_key("Москва", lang="ru")        # → "moskva"
search_key("ΩMEGA")                    # → "omega"
```

Pipeline: `NFKC → transliterate → strip_accents → fold_case → collapse_whitespace`

Like `catalog_key()` but without confusable normalization — lighter and
faster for search indexes where homoglyph attacks are not a concern.

### sort_key()

`sort_key()` generates keys for consistent alphabetical ordering across
scripts. Unlike `search_key()`, it preserves base accented characters so
that sort order respects diacritics:

```python
from translit import sort_key

sort_key("Über", lang="de")            # → "ueber"
sort_key("Война и мир", lang="ru")     # → "voyna i mir"

# Sort multilingual titles together
titles = ["Über alles", "Under pressure", "Москва"]
sorted(titles, key=lambda t: sort_key(t, lang="auto"))
# Sorts by ASCII transliteration: moskva, uber alles, under pressure
```

Pipeline: `NFKC → transliterate → fold_case → collapse_whitespace`

### Choosing the Right Key

| Function | Strips accents | Confusable-safe | Use case |
|---|---|---|---|
| `catalog_key()` | Yes | Yes | Dedup keys, record matching |
| `search_key()` | Yes | No | Search indexes, WHERE clauses |
| `sort_key()` | No | No | Alphabetical ordering |

---

## Text Normalization for ETL

### Unicode Normalization

The same character can be encoded multiple ways in Unicode. Without
normalization, exact-match joins and GROUP BY clauses silently split
what should be a single group:

```python
from translit import normalize, is_normalized

# These look identical but differ at the codepoint level
a = "caf\u00e9"               # é as precomposed (NFC)
b = "cafe\u0301"              # e + combining acute (NFD)

a == b                         # False!
normalize(a) == normalize(b)   # True (both become NFC)

# Check whether normalization is needed
is_normalized(a, form="NFC")   # True (already NFC)
is_normalized(b, form="NFC")   # False (NFD form)
```

**Which form to use:**

| Form | Use case |
|---|---|
| **NFC** | Default for most pipelines. Composes characters. |
| **NFKC** | Maximum normalization — collapses ligatures (`ﬁ` → `fi`), fullwidth (`Ｈ` → `H`), superscripts (`²` → `2`). Best for dedup. |
| **NFD** | Decomposed form. Useful when you need to strip combining marks. |
| **NFKD** | Decomposed + compatibility. Rarely needed directly. |

```python
from translit import normalize

normalize("ﬁnancial", form="NFKC")   # → "financial"
normalize("Ｈｅｌｌｏ", form="NFKC")   # → "Hello"
normalize("H₂O", form="NFKC")        # → "H2O"
normalize("①②③", form="NFKC")       # → "123"
```

### Whitespace and Control Characters

Data from web scrapes, OCR, and legacy systems often contains invisible
characters that break downstream processing:

```python
from translit import collapse_whitespace

# Non-breaking spaces, em spaces, zero-width characters
collapse_whitespace("hello\u00A0\u2003world")       # → "hello world"
collapse_whitespace("  tabs\there\ttoo  ")           # → "tabs here too"
collapse_whitespace("a\u200Bb\u200Bc")               # → "abc"
```

`collapse_whitespace()` normalizes all 13 Unicode whitespace variants to
a single ASCII space, strips control characters (C0/C1), and removes
zero-width joiners/spaces. Leading and trailing whitespace is trimmed.

### Case Folding

For case-insensitive matching, use `fold_case()` instead of `.lower()`.
It handles the full Unicode specification including characters where
`.lower()` gives incorrect results:

```python
from translit import fold_case

fold_case("Straße")         # → "strasse"  (ß → ss)
fold_case("İstanbul")       # → "i̇stanbul" (Turkish İ)
fold_case("ﬁle")            # → "file"     (ligature fi → f + i)
```

---

## Encoding Detection and Conversion

Legacy systems, CSV exports, and FTP feeds often arrive in non-UTF-8
encodings. translit provides detection and conversion using Firefox's
chardetng algorithm:

```python
from translit import detect_encoding, decode_to_utf8

# Read raw bytes from a legacy source
with open("legacy_export.csv", "rb") as f:
    raw = f.read()

# Detect encoding
encoding, confidence = detect_encoding(raw)
# e.g. ('windows-1252', 0.87)

# Convert to UTF-8
text, had_errors = decode_to_utf8(raw, encoding=encoding)
if had_errors:
    print(f"Warning: lossy conversion from {encoding}")
```

For auto-detection without an explicit encoding:

```python
from translit import decode_to_utf8

text, had_errors = decode_to_utf8(raw_bytes)
```

**Important**: automatic encoding detection is probabilistic. A high
confidence score does not guarantee correctness. For critical pipelines,
always prefer explicit encoding metadata (HTTP headers, BOM, schema
definitions) over detection.

---

## Identifier and Slug Generation

### Safe Column and Table Names

When generating identifiers from user input or external metadata,
`slugify()` produces clean, safe strings:

```python
from translit import slugify

# User-provided dataset names → safe identifiers
slugify("Q4 Revenue (Final)")         # → "q4-revenue-final"
slugify("Ärger im Büro", lang="de")   # → "aerger-im-buero"
slugify("日本語テスト")                # → "ri-ben-yu-tesuto"

# With underscore separator for SQL-friendly names
slugify("Q4 Revenue", separator="_")  # → "q4_revenue"
```

### Safe Filenames for Pipeline Artifacts

When writing output files from pipeline stages, use `sanitize_filename()`
to handle OS-specific restrictions:

```python
from translit import sanitize_filename

# User-provided report names → safe filenames
sanitize_filename("Q4 Report <final>.xlsx")
# → "Q4_Report_final.xlsx"

sanitize_filename("résumé.pdf", lang="fr")
# → "resume.pdf"

# Cross-platform safety (handles Windows reserved names)
sanitize_filename("CON.txt")
# → "_CON.txt"
```

### Bounded-Length Identifiers

When target systems have column width limits:

```python
from translit import slugify

slugify("A Very Long Dataset Name That Exceeds Limits", max_length=20)
# → "a-very-long-dataset"

# Word-boundary truncation avoids cutting mid-word
slugify(
    "International Revenue Report",
    max_length=25,
    word_boundary=True,
)
# → "international-revenue"
```

---

## Building Custom Pipelines with TextPipeline

When your ETL needs a specific combination of transforms, build a
reusable pipeline:

```python
from translit import TextPipeline

# Data warehouse ingestion: maximum normalization
warehouse_pipe = TextPipeline(
    normalize="NFKC",
    confusables=True,
    strip_accents=True,
    transliterate=True,
    fold_case=True,
    collapse_whitespace=True,
)

warehouse_pipe("  Café Müller™  ")   # → "cafe mullertm"
warehouse_pipe("Ｈｅｌｌｏ Ｗörld")   # → "hello world"
```

The pipeline always executes steps in a fixed optimal order regardless of
flag order:
normalize → confusables → demojize → strip_accents → transliterate → fold_case → strip_control → strip_zero_width → collapse_whitespace.

### Common Pipeline Configurations

**Search index normalization:**
```python
search_pipe = TextPipeline(
    normalize="NFC",
    strip_accents=True,
    fold_case=True,
    collapse_whitespace=True,
)
# "café" and "CAFE" produce the same index key
```

**Cross-system identifier matching:**
```python
match_pipe = TextPipeline(
    normalize="NFKC",
    confusables=True,
    transliterate=True,
    fold_case=True,
    collapse_whitespace=True,
)
# Handles Cyrillic lookalikes, fullwidth chars, accents
```

**Minimal cleanup (preserve Unicode):**
```python
clean_pipe = TextPipeline(
    normalize="NFC",
    collapse_whitespace=True,
)
# Just normalize encoding and whitespace, keep all scripts
```

---

## Script Detection for Data Quality

Detect which Unicode scripts are present in a column to identify data
quality issues like mixed-script entries:

```python
from translit import detect_scripts, is_mixed_script, Script

# Flag suspicious entries in a customer name column
is_mixed_script("John Smith")         # False — pure Latin
is_mixed_script("Jоhn Smith")         # True — Cyrillic о mixed with Latin

# Get the specific scripts
detect_scripts("Jоhn Smith")          # [Script.LATIN, Script.CYRILLIC]
```

This is useful for:

- **Data quality checks**: flag records where Latin and Cyrillic characters
  are mixed (potential data entry errors or homoglyph issues)
- **Routing**: send records to language-specific processing branches
- **Validation**: ensure a column that should be Latin-only doesn't
  contain unexpected scripts

---

## Confusable and Homoglyph Normalization

Cyrillic `а` (U+0430) looks identical to Latin `a` (U+0061) but they
are different codepoints. Without normalization, these create phantom
duplicates in your data:

```python
from translit import normalize_confusables, is_confusable

# Detect
is_confusable("pаypal")             # True (Cyrillic а)

# Normalize
normalize_confusables("pаypal")     # → "paypal" (all Latin)
```

Enable `confusables=True` in `TextPipeline` to handle this automatically
during ingestion.

---

## Integration Patterns

### Airflow Task

```python
from translit import TextPipeline, transliterate_batch

pipe = TextPipeline(
    normalize="NFKC",
    fold_case=True,
    collapse_whitespace=True,
)

def normalize_column(records, column):
    """Normalize a text column in a batch of records."""
    texts = [r[column] for r in records]
    normalized = [pipe(t) for t in texts]
    for record, clean in zip(records, normalized):
        record[column] = clean
    return records
```

### pandas DataFrame

```python
from translit import fold_case, strip_accents

import pandas as pd

df = pd.DataFrame({"name": ["Müller", "MÜLLER", "mueller"]})

# Vectorized via .apply()
df["name_key"] = df["name"].apply(fold_case)
df["name_ascii"] = df["name"].apply(strip_accents)
```

For larger DataFrames, use the batch API to avoid per-row Python overhead:

```python
from translit import transliterate_batch

names = df["name"].tolist()
df["name_ascii"] = transliterate_batch(names)
```

### PySpark UDF

```python
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

from translit import catalog_key

catalog_key_udf = F.udf(catalog_key, StringType())

df = df.withColumn("match_key", catalog_key_udf(F.col("name")))
```

For better performance in Spark, consider using `mapPartitions` with
batch APIs instead of row-level UDFs.

---

## Precompiled Pipelines Reference

translit ships with precompiled pipelines optimized for common data
engineering tasks:

| Pipeline | Steps | Use case |
|---|---|---|
| `catalog_key()` | NFKC → transliterate → confusables → strip_accents → fold_case → collapse_ws | Dedup keys, record matching |
| `search_key()` | NFKC → transliterate → strip_accents → fold_case → collapse_ws | Search index keys |
| `sort_key()` | NFKC → transliterate → fold_case → collapse_ws | Sort ordering |
| `ml_normalize()` | NFKC → demojize → strip_accents → fold_case → collapse_ws | Feature engineering |
| `security_clean()` | NFKC → confusables → strip_bidi → collapse_ws | Input sanitization |
| `sanitize_user_input()` | NFKC → strip_zalgo → confusables → strip_bidi → collapse_ws | Web form input |
| `display_clean()` | strip_bidi → collapse_ws | UI text cleanup |

Each pipeline is a single compiled Rust function — no pipeline construction
overhead at call time.

---

## Performance

translit is compiled Rust with O(1) compile-time perfect hash tables.
There is no regex compilation, no Python-level per-character iteration,
and no runtime data loading.

Key numbers for data engineering workloads:

| Operation | Throughput |
|---|---|
| Transliterate (Latin) | 450M chars/sec |
| Transliterate (Cyrillic) | 130M chars/sec |
| Slugify | 849K slugs/sec |
| Batch transliterate (100 strings) | 2.8× faster than loop |
| vs. Unidecode | 18–38× faster |
| vs. python-slugify | 10–24× faster |

For full benchmark methodology and results, see
[performance benchmarks](performance.md).

---

## Installation

```bash
pip install translit-rs
```

Single wheel per platform (abi3). No Rust toolchain required. No runtime
data downloads. No network calls during import. Replaces `unidecode`,
`text-unidecode`, `python-slugify`, and `anyascii` as a single dependency.
