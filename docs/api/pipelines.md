# Precompiled Pipelines

Ready-to-use multi-step text processing pipelines. Each is a single compiled Rust function with no pipeline construction overhead at call time.

!!! warning "Renamed in 0.11 (#430)"
    Three presets were renamed to describe their mechanism rather than imply a
    safety outcome. The old names are **deprecated aliases**, behave identically,
    and are **removed in 1.0**:

    | Old name | New name |
    |---|---|
    | `security_clean` | `canonicalize` |
    | `display_clean` | `strip_format` |
    | `normalize_user_input` | `canonicalize_strict` |

## canonicalize

::: disarm.canonicalize

### Pipeline steps

`NFKC → strip bidi/format → strip invisibles (#413) → strip_control → strip_zero_width → collapse_whitespace → strip_zalgo (#429) → NFC → confusables → NFC`

```python
from disarm import canonicalize

assert canonicalize("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥") == 'Real text'
assert canonicalize("Ηello Ꮤorld") == 'Hello World'
```

---

## ml_normalize

::: disarm.ml_normalize

### Pipeline steps

`NFKC → emoji→text → [transliterate] → strip_accents → fold_case → strip_control → strip_zero_width → collapse_whitespace`

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

`NFKC → fold_case → transliterate → confusables → strip_accents → fold_case → strip_control → strip_zero_width → collapse_whitespace`

```python
from disarm import catalog_key

assert catalog_key("  Café  RÉSUMÉ  ") == 'cafe resume'
assert catalog_key("Москва", lang="ru") == 'moskva'
assert catalog_key("Москва", lang="auto") == 'moskva'
assert catalog_key("Müller", lang="de") == 'mueller'
```

---

## strip_format

::: disarm.strip_format

### Pipeline steps

`strip_bidi` → `strip invisibles (#413, rendering policy)` → `strip_control` → `strip_zero_width` → `collapse_whitespace`

```python
from disarm import strip_format

assert strip_format("hello\x00world\u200b!") == 'helloworld!'
assert strip_format("  spaced   out  ") == 'spaced out'
assert strip_format("admin\u202Euser") == 'adminuser'
```

---

## search_key

::: disarm.search_key

### Pipeline steps

`NFKC → fold_case → transliterate → strip_accents → fold_case → strip_control → strip_zero_width → collapse_whitespace`

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

`NFKC → strip_bidi → fold_case → transliterate-non-Latin → fold_case → strip_control → strip_zero_width → collapse_whitespace`

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

## canonicalize_strict

::: disarm.canonicalize_strict

### Pipeline steps

`NFKC → strip_bidi → strip_zero_width → strip_control → strip invisibles (#413) → strip_zalgo → confusables → collapse_whitespace → NFC`

```python
from disarm import canonicalize_strict

assert canonicalize_strict("Hello, world!") == 'Hello, world!'
assert canonicalize_strict("p\u0430ypal") == 'paypal'
assert canonicalize_strict("admin\u202Euser") == 'adminuser'
```

Unlike `canonicalize`, this pipeline also strips zalgo text (excessive combining mark stacking). Unlike `catalog_key`/`search_key`, it does **not** transliterate — the original script is preserved.

---

## strip_obfuscation

::: disarm.strip_obfuscation

### Pipeline steps

`NFKC → strip_zalgo(0) → strip_bidi → strip_zero_width → demojize → strip invisibles (#413) → confusables → strip_accents → strip_control → collapse_whitespace`

```python
from disarm import strip_obfuscation

# Homoglyphs (Greek/Cyrillic) folded, bidi override removed, emoji expanded.
assert strip_obfuscation("Ηеllо‮Wоrld \U0001F600") == "HelloWorld grinning face"
# Strips ALL combining marks (zalgo and accents) but preserves case.
assert strip_obfuscation("Cáfé") == "Cafe"
```

Maximum-strength deobfuscation for content moderation, anti-phishing, and spam/NLP preprocessing. Strips every combining mark (zalgo **and** accents), resolves homoglyphs by TR39 visual similarity (Cyrillic `р`→`p`, not phonetic `р`→`r`), and expands emoji to text. **Preserves case** — case is meaningful, not deception. Confusable normalization runs *after* `demojize` so typographic punctuation inside emoji names is folded too. Does **not** transliterate; chain `transliterate()` on the result if you also need phonetic romanization.

---

## PRESETS

```python
from disarm import PRESETS
```

Dict mapping preset function names to their ordered pipeline steps. Each value is a list of `(step_name, parameter)` tuples in execution order.

```python
assert PRESETS["canonicalize"] == [('normalize', 'NFKC'), ('strip_bidi', None), ('strip_invisibles', 'comparison'), ('strip_control', None), ('strip_zero_width', None), ('collapse_whitespace', None), ('strip_zalgo', None), ('normalize', 'NFC'), ('confusables', 'latin'), ('normalize', 'NFC')]
assert PRESETS["canonicalize_strict"] == [('normalize', 'NFKC'), ('strip_bidi', None), ('strip_zero_width', None), ('strip_control', None), ('strip_invisibles', 'comparison'), ('strip_zalgo', None), ('confusables', 'latin'), ('collapse_whitespace', None), ('normalize', 'NFC')]
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
