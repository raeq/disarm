# Migrating from confusable_homoglyphs

disarm includes built-in confusable detection that replaces [confusable_homoglyphs](https://pypi.org/project/confusable-homoglyphs/).

!!! note "Installing the libraries these examples compare against"
    The *Before* blocks import `confusable-homoglyphs`, which `pip install disarm` does not bring.
    Install what you need alongside it: `pip install confusable-homoglyphs`.
    `confusable-homoglyphs` is not in any disarm extra, so it has to be named explicitly.

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
- `unmapped_confusables()` / `find_unmapped_confusables()` — report which TR39 sources the
  bundled table does **not** fold, globally and for one input
- `CONFUSABLES_VERSION` — the `confusables.txt` release the tables were folded from
- Rust implementation — see [performance benchmarks](../performance.md)

### Knowing your coverage

`confusable_homoglyphs` gives no way to ask how current its table is, or which sources it
misses. Both questions are answerable here, which matters when you are replacing a
security control and need to state what the replacement does not catch:

```python
import disarm

# How current is the fold?
assert disarm.CONFUSABLES_VERSION.split(".")[0].isdigit()

# What does it not neutralize? Read as exposure, not as a score — this set is
# where an adaptive attacker goes once the mapped sources stop working.
exposure = disarm.unmapped_confusables()
assert isinstance(exposure, frozenset)

# Cyrillic а (U+0430) IS folded, so it is not exposure.
assert "\u0430" not in exposure
assert disarm.normalize_confusables("p\u0430ypal") == "paypal"

# The same question against one input, in `find_untranslatable`'s shape.
assert disarm.find_unmapped_confusables("p\u0430ypal") == []
```

Most of that set is out of scope rather than missing (a source folding to a non-Latin
target does not belong in a to-Latin table), and it includes five ASCII characters
because TR39 is a *skeleton* transform. See
[Knowing what is NOT covered](../user-guide/confusables.md#knowing-what-is-not-covered).
