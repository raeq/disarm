# Policy Templates

Pre-built configurations for common institutional and application workflows. Each template is a named policy profile available via `get_pipeline()`, or a recommended `TextPipeline` configuration.

---

## Using Policy Profiles

```python
from disarm import get_pipeline, list_profiles

# See all available profiles
print(list_profiles())

# Get a configured pipeline
pipe = get_pipeline("scholarly_cyrillic_iso9")
result = pipe("Москва")
```

Each call to `get_pipeline()` returns a fresh `TextPipeline` instance.

---

## Available Profiles

### scholarly_cyrillic_iso9

**Use case:** Academic publishing, linguistic research, library cataloging of Cyrillic texts.

```python
pipe = get_pipeline("scholarly_cyrillic_iso9")
assert pipe("Юность") == 'junost'
assert pipe("Москва") == 'moskva'
```

| Property | Value |
|----------|-------|
| Steps | NFKC → transliterate (ISO 9) → fold_case → collapse_whitespace |
| Output charset | UTF-8 (ISO 9 diacritics preserved before case folding) |
| Reversibility | Partially (case folding is lossy) |
| Script coverage | All Cyrillic scripts |

### library_catalog_key_eu

**Use case:** European public library catalog deduplication, bibliographic key generation.

```python
pipe = get_pipeline("library_catalog_key_eu")
assert pipe("München — Bayern") == 'munchen - bayern'
assert pipe("Città di Firenze") == 'citta di firenze'
```

| Property | Value |
|----------|-------|
| Steps | NFKC → transliterate → confusables → strip_accents → fold_case → collapse_whitespace |
| Output charset | ASCII |
| Reversibility | No (lossy) |
| Script coverage | All 83 language profiles |

### web_input_sanitize

**Use case:** Web form input cleaning, comment sanitization, display-safe text.

```python
pipe = get_pipeline("web_input_sanitize")
assert pipe("  Hello   World  ") == 'Hello World'
```

| Property | Value |
|----------|-------|
| Steps | NFKC → confusables → collapse_whitespace |
| Output charset | UTF-8 (original script preserved) |
| Reversibility | No (NFKC is lossy for some characters) |
| Security | Folds TR39 confusable homoglyphs |

!!! note
    To also handle zalgo text and bidi injection, use the `normalize_user_input()` precompiled pipeline instead — it includes `strip_zalgo` and `strip_bidi` steps that `TextPipeline` does not support.

### ml_corpus_normalize

**Use case:** NLP/ML text preprocessing, corpus normalization, embedding preparation.

```python
pipe = get_pipeline("ml_corpus_normalize")
assert pipe("Héllo WÖRLD 🎉") == 'hello world party popper'
```

| Property | Value |
|----------|-------|
| Steps | NFKC → demojize → strip_accents → fold_case → collapse_whitespace |
| Output charset | ASCII + emoji names |
| Reversibility | No (lossy) |
| Script coverage | All scripts |

### search_index

**Use case:** Full-text search index generation, cross-language search keys.

```python
pipe = get_pipeline("search_index")
assert pipe("München") == 'munchen'
assert pipe("Москва") == 'moskva'
```

| Property | Value |
|----------|-------|
| Steps | NFKC → transliterate → strip_accents → fold_case → collapse_whitespace |
| Output charset | ASCII |
| Reversibility | No (lossy) |
| Script coverage | All 83 language profiles |

---

## Precompiled Pipelines vs Policy Profiles

Policy profiles use `TextPipeline` (Python-configurable steps). For maximum performance and security coverage, use the **precompiled pipelines** instead — they run entirely in Rust:

| Need | Use |
|------|-----|
| Security-critical input normalization | `normalize_user_input()` |
| Catalog/bibliography keys | `catalog_key()` |
| Search index keys | `search_key()` |
| Sort-friendly keys | `sort_key()` |
| Security canonicalization | `security_clean()` |
| ML preprocessing | `ml_normalize()` |

Policy profiles are best for **custom workflows** where you need the flexibility of `TextPipeline` parameters, or when you want symbolic profile names in configuration files.

---

## Custom Institutional Profiles

Organizations can define their own profiles by constructing `TextPipeline` directly:

```python
from disarm import TextPipeline

# Government/legal: strict ASCII, no transliteration (preserve originals)
legal_clean = TextPipeline(
    normalize="NFKC",
    confusables=True,
    fold_case=True,
    collapse_whitespace=True,
)

# Archive/museum: preserve script, minimal normalization
archive_clean = TextPipeline(
    normalize="NFC",
    collapse_whitespace=True,
)
```
