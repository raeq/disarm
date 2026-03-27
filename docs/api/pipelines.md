# Precompiled Pipelines

Ready-to-use multi-step text processing pipelines. Each is a single compiled Rust function with no pipeline construction overhead at call time.

## security_clean

::: translit.security_clean

### Pipeline steps

`NFKC → confusables → strip bidi/format → collapse_whitespace`

```python
from translit import security_clean

security_clean("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥")   # => "Real text"
security_clean("Ηello Ꮤorld")    # => "Hello World"  (Greek Η + Cherokee Ꮤ → Latin)
```

---

## ml_normalize

::: translit.ml_normalize

### Pipeline steps

`NFKC → emoji→text → [transliterate] → strip_accents → fold_case → collapse_whitespace`

```python
from translit import ml_normalize

ml_normalize("Café RÉSUMÉ")         # => "cafe resume"
ml_normalize("München", lang="de")  # => "muenchen"
ml_normalize("I ❤️ Python 🐍")      # => "i red heart python snake"
```

---

## catalog_key

::: translit.catalog_key

### Pipeline steps

`NFKC → transliterate → confusables → strip_accents → fold_case → collapse_whitespace`

```python
from translit import catalog_key

catalog_key("  Café  RÉSUMÉ  ")       # => "cafe resume"
catalog_key("Москва", lang="ru")      # => "moskva"
catalog_key("Москва", lang="auto")    # => "moskva" (auto-detects Russian)
catalog_key("Müller", lang="de")      # => "mueller"
```

---

## display_clean

::: translit.display_clean

### Pipeline steps

`strip_bidi` → `strip_control` → `strip_zero_width` → `collapse_whitespace`

```python
from translit import display_clean

display_clean("hello\x00world\u200b!")  # => "helloworld!"
display_clean("  spaced   out  ")       # => "spaced out"
display_clean("admin\u202Euser")        # => "adminuser" (bidi override stripped)
```

---

## search_key

::: translit.search_key

### Pipeline steps

`NFKC → transliterate → strip_accents → fold_case → collapse_whitespace`

```python
from translit import search_key

search_key("Café RÉSUMÉ")              # => "cafe resume"
search_key("Москва", lang="ru")        # => "moskva"
search_key("ΩMEGA", lang="auto")       # => "omega"
```

---

## sort_key

::: translit.sort_key

### Pipeline steps

`NFKC → transliterate → fold_case → collapse_whitespace`

```python
from translit import sort_key

sort_key("Über", lang="de")            # => "ueber"
sort_key("Война и мир", lang="ru")     # => "voyna i mir"
sort_key("Café")                       # => "cafe"
```

---

## sanitize_user_input

::: translit.sanitize_user_input

### Pipeline steps

`NFKC → strip_zalgo → confusables → strip_bidi → collapse_whitespace`

```python
from translit import sanitize_user_input

sanitize_user_input("Hello, world!")        # => "Hello, world!"
sanitize_user_input("p\u0430ypal")          # => "paypal" (Cyrillic а → Latin a)
sanitize_user_input("admin\u202Euser")      # => "adminuser" (bidi override stripped)
```

Unlike `security_clean`, this pipeline also strips zalgo text (excessive combining mark stacking). Unlike `catalog_key`/`search_key`, it does **not** transliterate — the original script is preserved.

---

## PRESETS

```python
from translit import PRESETS
```

Dict mapping preset function names to their ordered pipeline steps. Each value is a list of `(step_name, parameter)` tuples in execution order.

```python
>>> from translit import PRESETS
>>> PRESETS["security_clean"]
[('normalize', 'NFKC'), ('confusables', 'latin'), ('strip_bidi', None), ('collapse_whitespace', None)]
>>> PRESETS["sanitize_user_input"]
[('normalize', 'NFKC'), ('strip_zalgo', None), ('confusables', 'latin'), ('strip_bidi', None), ('collapse_whitespace', None)]
```

Use `PRESETS` to audit exactly which transforms a preset applies, or to build equivalent `TextPipeline` configurations.

---

## Policy Profiles

Named policy profiles provide pre-configured `TextPipeline` instances for common institutional and application workflows.

### get_pipeline

```python
from translit import get_pipeline

pipe = get_pipeline("scholarly_cyrillic_iso9")
pipe("Москва")   # → "moskva"
```

Returns a fresh `TextPipeline` configured for the named profile. Raises `TranslitError` for unknown profiles.

### list_profiles

```python
from translit import list_profiles

print(list_profiles())
# ['library_catalog_key_eu', 'ml_corpus_normalize', 'scholarly_cyrillic_iso9',
#  'search_index', 'web_input_sanitize']
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

See [Policy Templates](../policy-templates.md) for detailed usage guidance and institutional recipes.
