# Precompiled Pipelines

Ready-to-use multi-step text processing pipelines. Each is a single compiled Rust function with no pipeline construction overhead at call time.

## security_clean

::: translit.security_clean

### Pipeline steps

`NFKC → confusables → strip bidi/format → collapse_whitespace`

```python
from translit import security_clean

assert security_clean("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥") == 'Real text'
assert security_clean("Ηello Ꮤorld") == 'Hello World'
```

---

## ml_normalize

::: translit.ml_normalize

### Pipeline steps

`NFKC → emoji→text → [transliterate] → strip_accents → fold_case → collapse_whitespace`

```python
from translit import ml_normalize

assert ml_normalize("Café RÉSUMÉ") == 'cafe resume'
assert ml_normalize("München", lang="de") == 'muenchen'
assert ml_normalize("I ❤️ Python 🐍") == 'i red heart python snake'
```

---

## catalog_key

::: translit.catalog_key

### Pipeline steps

`NFKC → transliterate → confusables → strip_accents → fold_case → collapse_whitespace`

```python
from translit import catalog_key

assert catalog_key("  Café  RÉSUMÉ  ") == 'cafe resume'
assert catalog_key("Москва", lang="ru") == 'moskva'
assert catalog_key("Москва", lang="auto") == 'moskva'
assert catalog_key("Müller", lang="de") == 'mueller'
```

---

## display_clean

::: translit.display_clean

### Pipeline steps

`strip_bidi` → `strip_control` → `strip_zero_width` → `collapse_whitespace`

```python
from translit import display_clean

assert display_clean("hello\x00world\u200b!") == 'helloworld!'
assert display_clean("  spaced   out  ") == 'spaced out'
assert display_clean("admin\u202Euser") == 'adminuser'
```

---

## search_key

::: translit.search_key

### Pipeline steps

`NFKC → transliterate → strip_accents → fold_case → collapse_whitespace`

```python
from translit import search_key

assert search_key("Café RÉSUMÉ") == 'cafe resume'
assert search_key("Москва", lang="ru") == 'moskva'
assert search_key("ΩMEGA", lang="auto") == 'omega'
```

---

## sort_key

::: translit.sort_key

### Pipeline steps

`NFKC → transliterate → fold_case → collapse_whitespace`

```python
from translit import sort_key

assert sort_key("Über", lang="de") == 'ueber'
assert sort_key("Война и мир", lang="ru") == 'voyna i mir'
assert sort_key("Café") == 'cafe'
```

---

## sanitize_user_input

::: translit.sanitize_user_input

### Pipeline steps

`NFKC → strip_bidi → strip_zero_width → strip_zalgo → confusables → collapse_whitespace`

```python
from translit import sanitize_user_input

assert sanitize_user_input("Hello, world!") == 'Hello, world!'
assert sanitize_user_input("p\u0430ypal") == 'paypal'
assert sanitize_user_input("admin\u202Euser") == 'adminuser'
```

Unlike `security_clean`, this pipeline also strips zalgo text (excessive combining mark stacking). Unlike `catalog_key`/`search_key`, it does **not** transliterate — the original script is preserved.

---

## PRESETS

```python
from translit import PRESETS
```

Dict mapping preset function names to their ordered pipeline steps. Each value is a list of `(step_name, parameter)` tuples in execution order.

```python
assert PRESETS["security_clean"] == [('normalize', 'NFKC'), ('confusables', 'latin'), ('strip_bidi', None), ('collapse_whitespace', None)]
assert PRESETS["sanitize_user_input"] == [('normalize', 'NFKC'), ('strip_bidi', None), ('strip_zero_width', None), ('strip_control', None), ('strip_zalgo', None), ('confusables', 'latin'), ('collapse_whitespace', None)]
```

Use `PRESETS` to audit exactly which transforms a preset applies, or to build equivalent `TextPipeline` configurations.

---

## Policy Profiles

Named policy profiles provide pre-configured `TextPipeline` instances for common institutional and application workflows.

### get_pipeline

```python
from translit import get_pipeline

pipe = get_pipeline("scholarly_cyrillic_iso9")
assert pipe("Москва") == 'moskva'
```

Returns a fresh `TextPipeline` configured for the named profile. Raises `TranslitError` for unknown profiles.

### list_profiles

```python
from translit import list_profiles

print(list_profiles())
# ['library_catalog_key_eu', 'llm_guardrail', 'ml_corpus_normalize',
#  'rag_ingest', 'scholarly_cyrillic_iso9', 'search_index', 'web_input_sanitize']
```

Returns sorted list of available profile names.

### Available profiles

| Profile | Steps | Output |
|---------|-------|--------|
| `scholarly_cyrillic_iso9` | NFKC → transliterate (ISO 9) → fold_case → collapse_whitespace | UTF-8 |
| `library_catalog_key_eu` | NFKC → transliterate → confusables → strip_accents → fold_case → collapse_whitespace | ASCII |
| `web_input_sanitize` | NFKC → confusables → collapse_whitespace | UTF-8 |
| `ml_corpus_normalize` | NFKC → demojize → strip_accents → fold_case → collapse_whitespace | ASCII |
| `search_index` | NFKC → transliterate → strip_accents → fold_case → collapse_whitespace | ASCII |
| `llm_guardrail` | NFKC → strip_zalgo(0) → strip_bidi → demojize → strip_accents → confusables → fold_case → strip_control → strip_zero_width → collapse_whitespace | UTF-8 |
| `rag_ingest` | NFKC → strip_bidi → strip_accents → transliterate → strip_control → strip_zero_width → collapse_whitespace | ASCII |

`llm_guardrail` hardens text against prompt-injection and homoglyph/zalgo/bidi obfuscation before it reaches an LLM (digits are never remapped to letters). `rag_ingest` canonicalizes documents for retrieval pipelines while preserving case.

See [Policy Templates](../policy-templates.md) for detailed usage guidance and institutional recipes.
