# Language Profiles

Functions for querying and extending transliteration language profiles.

## list_langs

::: translit.list_langs

### Example

```python
from translit import list_langs

langs = list_langs()
print(langs)
# => ['ar', 'bg', 'ca', 'cs', 'cy', 'da', 'de', 'el', 'es', 'et',
#     'fi', 'fr', 'ga', 'hr', 'hu', 'is', 'it', 'ja', 'ko', 'lt',
#     'lv', 'mt', 'nl', 'no', 'pl', 'pt', 'ro', 'ru', 'sk', 'sl',
#     'sq', 'sr', 'sv', 'tr', 'uk', 'vi', 'zh']
```

Returns both built-in and user-registered language codes, sorted alphabetically.

---

## register_lang

::: translit.register_lang

### Example

```python
from translit import register_lang, transliterate

register_lang("eo", {
    "ĉ": "cx", "ĝ": "gx", "ĥ": "hx",
    "ĵ": "jx", "ŝ": "sx", "ŭ": "ux",
})

transliterate("ĉapelo", lang="eo")  # => "cxapelo"

# Verify registration
from translit import list_langs
assert "eo" in list_langs()
```

!!! warning
    This is a global, process-wide operation. Registered profiles persist for the lifetime of the Python process and are visible to all threads.

---

## register_replacements

::: translit.register_replacements

### Example

```python
from translit import register_replacements, transliterate

register_replacements({
    "©": "(c)",
    "®": "(R)",
    "™": "(TM)",
})

transliterate("Hello™ World©")  # => "Hello(TM) World(c)"
```

Replacements are applied as a pre-processing step before the character-by-character transliteration lookup. They are global and persist for the process lifetime.

---

## remove_replacement

::: translit.remove_replacement

### Example

```python
from translit import register_replacements, remove_replacement, transliterate

register_replacements({"©": "(c)", "®": "(R)"})
transliterate("©®")  # => "(c)(R)"

remove_replacement("©")  # => True  (was registered)
remove_replacement("©")  # => False (already removed)
transliterate("©®")      # => "(R)" — only ® replacement remains
```

---

## clear_replacements

::: translit.clear_replacements

### Example

```python
from translit import register_replacements, clear_replacements, transliterate

register_replacements({"©": "(c)", "®": "(R)"})
transliterate("©®")  # => "(c)(R)"

clear_replacements()
transliterate("©®")  # => "(c)(R)" is gone — falls back to default table
```

!!! note
    `clear_replacements()` removes all user-registered replacements. Built-in transliteration tables are not affected.
