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

`NFKC → confusables → [transliterate] → strip_accents → fold_case → collapse_whitespace`

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

`strip_control` → `strip_zero_width` → `collapse_whitespace`

```python
from translit import display_clean

display_clean("hello\x00world\u200b!")  # => "helloworld!"
display_clean("  spaced   out  ")       # => "spaced out"
```

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
```

Use `PRESETS` to audit exactly which transforms a preset applies, or to build equivalent `TextPipeline` configurations.
