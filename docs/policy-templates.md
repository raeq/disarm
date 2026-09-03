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

The three profiles that fold confusables — `llm_guardrail`, `normalize_web_input` and
`library_catalog_key_eu` — take the fold's `digit_policy` at construction (#646). The
default reads a confusable digit as the digit it means; `"tr39"` reads it as the letter
it resembles, which is what a spoof screen wants:

```python
from disarm import get_pipeline

# U+0A66 GURMUKHI ZERO standing in for "o"
assert get_pipeline("llm_guardrail")("g੦ogle") == "g0ogle"
assert get_pipeline("llm_guardrail", digit_policy="tr39")("g੦ogle") == "google"
```

A profile with no confusables step refuses a non-default policy rather than keeping a
setting that would never run. `rag_ingest` is the one to know about: it recovers by
transliteration, not by a fold.

---

## Available Profiles

### scholarly_cyrillic_iso9

**Use case:** Academic publishing, linguistic research, library cataloging of Cyrillic texts.

```python
pipe = get_pipeline("scholarly_cyrillic_iso9")
assert pipe("Юность") == "junost"
assert pipe("Москва") == "moskva"
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
assert pipe("München — Bayern") == "munchen - bayern"
assert pipe("Città di Firenze") == "citta di firenze"
```

| Property | Value |
|----------|-------|
| Steps | NFKC → transliterate → confusables → strip_accents → fold_case → collapse_whitespace |
| Output charset | ASCII |
| Reversibility | No (lossy) |
| Script coverage | All 83 language profiles |

### normalize_web_input

**Use case:** Lightweight Unicode normalization of web form input (NFKC + confusable-folding). This is *input* normalization, **not** output sanitization — it performs no escaping and is not an XSS/HTML/SQL defense (see [Threat Model](https://github.com/raeq/disarm/blob/main/THREAT_MODEL.md)). It is intentionally lighter than `canonicalize_strict()` (no bidi/zero-width/control/zalgo stripping); use that function for adversarial input.

```python
pipe = get_pipeline("normalize_web_input")
assert pipe("  Hello   World  ") == "Hello World"
```

| Property | Value |
|----------|-------|
| Steps | NFKC → confusables → collapse_whitespace |
| Output charset | UTF-8 (original script preserved) |
| Reversibility | No (NFKC is lossy for some characters) |
| Confusables | Folds TR39 confusable homoglyphs (not an output/injection defense) |

!!! note
    To also handle zalgo text and bidi injection, use the `canonicalize_strict()` precompiled pipeline instead — it includes `strip_zalgo` and `strip_bidi` steps that `TextPipeline` does not support.

### ml_corpus_normalize

**Use case:** NLP/ML text preprocessing, corpus normalization, embedding preparation.

```python
pipe = get_pipeline("ml_corpus_normalize")
assert pipe("Héllo WÖRLD 🎉") == "hello world party popper"
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
assert pipe("München") == "munchen"
assert pipe("Москва") == "moskva"
```

| Property | Value |
|----------|-------|
| Steps | NFKC → transliterate → strip_accents → fold_case → collapse_whitespace |
| Output charset | ASCII |
| Reversibility | No (lossy) |
| Script coverage | All 83 language profiles |

### code_context

**Use case:** Screening source code without rewriting it: the homoglyph class is reported rather than folded, because line structure, indentation and case are the contract.

The only structure-preserving profile. Every other profile ends in `collapse_whitespace`,
which folds a line break to a space by design — measured over 465 files of this repository,
all thirteen other surfaces collapse every file to a single line. It also applies no
confusable fold, and that is the design point: exactly three ASCII characters are TR39
sources (`"`, `` ` ``, `|`), all three are load-bearing syntax, and folding them breaks 287
of 287 Python files. So this profile neutralizes the invisible, bidi and control classes in
the text and leaves the homoglyph class to `inspect_anomalies`, `is_confusable` and
`is_mixed_script` to report.

```python
pipe = get_pipeline("code_context")
assert pipe('x = "a" | b') == 'x = "a" | b'
```

---

### llm_guardrail

**Use case:** Screening untrusted text before it reaches a model prompt, folding homoglyphs onto the term they imitate.

Folds a spoof onto the term it imitates, which is what a screen in front of a model wants:
a Cyrillic look-alike of `paypal` becomes `paypal`. `demojize` is deliberately **off** —
glossing an attacker-chosen emoji writes attacker-chosen English into the prompt, and over
the emoji-presentation set that reaches 1,272 distinct words including `stop`, `end`, `new`,
`key` and `no`.

```python
pipe = get_pipeline("llm_guardrail")
assert pipe("раураl") == "paypal"  # Cyrillic р, а, у — folded onto the term it imitates
```

---

### rag_ingest

**Use case:** Normalizing retrieved documents for a RAG index, romanizing legitimate non-Latin text rather than folding homoglyphs onto Latin.

**Not a homoglyph screen, and the difference is easy to miss.** This profile recovers by
*transliteration*, so `Москва` becomes `Moskva` and stays retrievable, while a Cyrillic
look-alike of `paypal` romanizes to `raural` rather than folding to `paypal`. Transliterate
runs before the fold in the fixed step order, so adding a confusable step here would be a
no-op. For homoglyph-spoof folding, use `llm_guardrail`.

```python
pipe = get_pipeline("rag_ingest")
assert pipe("Москва") == "Moskva"  # retrievable, and the case is kept
assert pipe("раураl") == "raural"  # romanized, not folded — llm_guardrail gives "paypal"
```

---

---

## Precompiled Pipelines vs Policy Profiles

Policy profiles use `TextPipeline` (Python-configurable steps). For maximum performance and security coverage, use the **precompiled pipelines** instead — they run entirely in Rust:

| Need | Use |
|------|-----|
| Unicode input normalization | `canonicalize_strict()` |
| Catalog/bibliography keys | `catalog_key()` |
| Search index keys | `search_key()` |
| Sort-friendly keys | `sort_key()` |
| Security canonicalization | `canonicalize()` |
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
