# Migrating from confusable_homoglyphs

disarm includes built-in confusable detection that replaces [confusable_homoglyphs](https://pypi.org/project/confusable-homoglyphs/).

## Quick migration

### Mixed-script detection

<!--- skip: next -->
```python
# Before
from confusable_homoglyphs import confusables
result = confusables.is_mixed_script("Неllo")  # detailed dict

# After
from disarm import is_mixed_script
result = is_mixed_script("Неllo")  # True
```

### Confusable detection

<!--- skip: next -->
```python
# Before
from confusable_homoglyphs import confusables
result = confusables.is_confusable("Неllo", greedy=True)  # detailed list of dicts

# After — greedy and preferred_aliases are accepted (with deprecation warning)
from disarm import is_confusable
result = is_confusable("Неllo")  # True
result = is_confusable("Неllo", greedy=True)  # accepted, warns
```

### Confusable normalization

```python
# confusable_homoglyphs has no normalization function

# disarm adds this capability
from disarm import normalize_confusables
assert normalize_confusables("Неllo") == 'Hello'
```

## API comparison

| confusable_homoglyphs | disarm | Notes |
|---|---|---|
| `confusables.is_mixed_script(s)` | `is_mixed_script(s)` | Returns `bool` instead of dict |
| `confusables.is_confusable(s)` | `is_confusable(s)` | Returns `bool` instead of list |
| — | `normalize_confusables(s)` | **New**: replace confusables |
| — | `detect_scripts(s)` | **New**: list scripts present |
| `categories.aliases_categories(c)` | Not available | Unicode category data |

## Behavioral differences

### Return types

confusable_homoglyphs returns detailed structured data (dicts with character info, aliases, script names). disarm returns simple booleans for detection and strings for normalization. If you need the detailed per-character breakdown, you'll need to keep confusable_homoglyphs.

### Script detection

<!--- skip: next -->
```python
# confusable_homoglyphs
from confusable_homoglyphs import confusables
confusables.is_mixed_script("Неllo")
# {'mixed': True, 'scripts': ['Cyrillic', 'Latin']}

# disarm — separate functions
from disarm import is_mixed_script, detect_scripts
is_mixed_script("Неllo")    # True
detect_scripts("Неllo")     # [Script.CYRILLIC, Script.LATIN]
```

## New features in disarm

- `normalize_confusables()` — actually replace confusables, not just detect them
- `detect_scripts()` — returns `Script` enum values
- `TextPipeline(confusables=True)` — integrate confusable normalization into a processing pipeline
- Rust implementation — see [performance benchmarks](../performance.md)
