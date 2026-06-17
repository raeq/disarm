# Precompiled Pipelines

Ready-to-use multi-step text processing pipelines. Each is a single compiled Rust function with no pipeline construction overhead at call time.

## security_clean

::: disarm.security_clean

### Pipeline steps

`NFKC → strip bidi/format → strip invisibles (#413) → collapse_whitespace → NFC → confusables → NFC → (path-separator neutralization)`

```python
from disarm import security_clean

assert security_clean("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥") == 'Real text'
assert security_clean("Ηello Ꮤorld") == 'Hello World'
```

---

## ml_normalize

::: disarm.ml_normalize

### Pipeline steps

`NFKC → emoji→text → [transliterate] → strip_accents → fold_case → collapse_whitespace`

```python
from disarm import ml_normalize

assert ml_normalize("Café RÉSUMÉ") == 'cafe resume'
assert ml_normalize("München", lang="de") == 'muenchen'
assert ml_normalize("I ❤️ Python 🐍") == 'i red heart python snake'
```

---

## catalog_key

::: disarm.catalog_key

### Pipeline steps

`NFKC → transliterate → confusables → strip_accents → fold_case → collapse_whitespace`

```python
from disarm import catalog_key

assert catalog_key("  Café  RÉSUMÉ  ") == 'cafe resume'
assert catalog_key("Москва", lang="ru") == 'moskva'
assert catalog_key("Москва", lang="auto") == 'moskva'
assert catalog_key("Müller", lang="de") == 'mueller'
```

---

## display_clean

::: disarm.display_clean

### Pipeline steps

`strip_bidi` → `strip invisibles (#413, rendering policy)` → `strip_control` → `strip_zero_width` → `collapse_whitespace`

```python
from disarm import display_clean

assert display_clean("hello\x00world\u200b!") == 'helloworld!'
assert display_clean("  spaced   out  ") == 'spaced out'
assert display_clean("admin\u202Euser") == 'adminuser'
```

---

## search_key

::: disarm.search_key

### Pipeline steps

`NFKC → transliterate → strip_accents → fold_case → collapse_whitespace`

```python
from disarm import search_key

assert search_key("Café RÉSUMÉ") == 'cafe resume'
assert search_key("Москва", lang="ru") == 'moskva'
assert search_key("ΩMEGA", lang="auto") == 'omega'
```

---

## sort_key

::: disarm.sort_key

### Pipeline steps

`NFKC → strip_bidi → transliterate-non-Latin → fold_case → collapse_whitespace`

Unlike `search_key`, `sort_key` **preserves base accented characters** so
accented and unaccented forms stay distinct and the accent survives for a
locale-aware collator. Non-Latin scripts are still folded to a consistent Latin
form; Latin letters (including accented ones) are kept verbatim, so `lang` only
affects non-Latin runs. (The key is a normalized string, not a UCA weight key —
pass it to a Unicode collator when linguistically-correct order matters.)

```python
from disarm import search_key, sort_key

# accents preserved for ordering (contrast search_key, which folds them away)
assert sort_key("Über") == 'über'
assert search_key("Über") == 'uber'
# a language profile never expands an accented Latin letter in a sort key
assert sort_key("Über", lang="de") == 'über'
# non-Latin scripts are still folded to Latin so titles interfile
assert sort_key("Война и мир", lang="ru") == 'voyna i mir'
assert sort_key("Café") == 'café'
```

---

## normalize_user_input

::: disarm.normalize_user_input

### Pipeline steps

`NFKC → strip_bidi → strip_zero_width → strip_control → strip invisibles (#413) → strip_zalgo → confusables → collapse_whitespace → NFC → (path-separator neutralization)`

```python
from disarm import normalize_user_input

assert normalize_user_input("Hello, world!") == 'Hello, world!'
assert normalize_user_input("p\u0430ypal") == 'paypal'
assert normalize_user_input("admin\u202Euser") == 'adminuser'
```

Unlike `security_clean`, this pipeline also strips zalgo text (excessive combining mark stacking). Unlike `catalog_key`/`search_key`, it does **not** transliterate — the original script is preserved.

---

## PRESETS

```python
from disarm import PRESETS
```

Dict mapping preset function names to their ordered pipeline steps. Each value is a list of `(step_name, parameter)` tuples in execution order.

```python
assert PRESETS["security_clean"] == [('normalize', 'NFKC'), ('strip_bidi', None), ('strip_invisibles', 'comparison'), ('collapse_whitespace', None), ('normalize', 'NFC'), ('confusables', 'latin'), ('normalize', 'NFC')]
assert PRESETS["normalize_user_input"] == [('normalize', 'NFKC'), ('strip_bidi', None), ('strip_zero_width', None), ('strip_control', None), ('strip_invisibles', 'comparison'), ('strip_zalgo', None), ('confusables', 'latin'), ('collapse_whitespace', None), ('normalize', 'NFC')]
```

Use `PRESETS` to audit exactly which transforms a preset applies, or to build equivalent `TextPipeline` configurations.

---

## Policy Profiles

Named policy profiles provide pre-configured `TextPipeline` instances for common institutional and application workflows.

### get_pipeline

```python
from disarm import get_pipeline

pipe = get_pipeline("scholarly_cyrillic_iso9")
assert pipe("Москва") == 'moskva'
```

Returns a fresh `TextPipeline` configured for the named profile. Raises `DisarmError` for unknown profiles.

### list_profiles

```python
from disarm import list_profiles

print(list_profiles())
# ['library_catalog_key_eu', 'llm_guardrail', 'ml_corpus_normalize',
#  'normalize_web_input', 'rag_ingest', 'scholarly_cyrillic_iso9', 'search_index']
```

Returns sorted list of available profile names.

### Available profiles

| Profile | Steps | Output |
|---------|-------|--------|
| `scholarly_cyrillic_iso9` | NFKC → transliterate (ISO 9) → fold_case → collapse_whitespace | UTF-8 |
| `library_catalog_key_eu` | NFKC → transliterate → confusables → strip_accents → fold_case → collapse_whitespace | ASCII |
| `normalize_web_input` | NFKC → confusables → collapse_whitespace | UTF-8 |
| `ml_corpus_normalize` | NFKC → demojize → strip_accents → fold_case → collapse_whitespace | ASCII |
| `search_index` | NFKC → transliterate → strip_accents → fold_case → collapse_whitespace | ASCII |
| `llm_guardrail` | NFKC → strip_zalgo(0) → strip_bidi → demojize → strip_accents → confusables → fold_case → strip_control → strip_zero_width → collapse_whitespace | UTF-8 |
| `rag_ingest` | NFKC → strip_bidi → strip_accents → transliterate → strip_control → strip_zero_width → collapse_whitespace | ASCII |

`llm_guardrail` hardens text against prompt-injection and homoglyph/zalgo/bidi obfuscation before it reaches an LLM (digits are never remapped to letters). `rag_ingest` canonicalizes documents for retrieval pipelines while preserving case.

!!! note "Homoglyph handling: `rag_ingest` romanizes, it does not visually-fold (#258)"
    The two guardrail profiles canonicalize homoglyphs differently, and the
    distinction matters for spoof resistance:

    - **`llm_guardrail`** runs `confusables` *without* `transliterate`, so a
      Cyrillic look-alike of "paypal" (`раураl`) is **visually folded** to
      `paypal` — it collides with the real Latin term (good for "treat the spoof
      as the word it imitates").
    - **`rag_ingest`** runs `transliterate`, which **phonetically romanizes** the
      same input to `raural` — a *distinct* key, so the spoof does not
      impersonate the real term, and legitimate non-Latin text still romanizes
      for retrieval (`Москва → Moskva`).

    These are deliberate trade-offs of the fixed step order (transliterate runs
    before confusables; running confusables first would mangle legitimate
    Cyrillic/Greek into mixed-script gibberish). Adding `confusables` to
    `rag_ingest` would be a no-op — transliterate has already consumed the
    non-Latin characters. **If you need homoglyph spoofs folded onto the term
    they imitate, use `llm_guardrail` (or a dedicated `confusables` pass), not
    `rag_ingest`.**

See [Policy Templates](../policy-templates.md) for detailed usage guidance and institutional recipes.
