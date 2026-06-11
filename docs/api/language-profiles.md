# Language Profiles

Functions for querying and extending transliteration language profiles.

## list_langs

::: disarm.list_langs

### Example

```python
from disarm import list_langs

langs = list_langs()
assert langs == ['am', 'ar', 'as', 'ban', 'bax', 'bg', 'bn', 'bo', 'bug', 'ca', 'chr', 'cjm', 'cop', 'cs', 'cy', 'da', 'de', 'dv', 'el', 'es', 'et', 'fa', 'fi', 'fr', 'ga', 'gu', 'he', 'hi', 'hr', 'hu', 'hy', 'is', 'it', 'ja', 'ja-kunrei', 'jv', 'ka', 'khb', 'km', 'kn', 'ko', 'lis', 'lo', 'lt', 'lv', 'ml', 'mn', 'mni', 'mr', 'mt', 'my', 'ne', 'nl', 'no', 'nod', 'nqo', 'or', 'pa', 'pl', 'pt', 'ro', 'ru', 'sa', 'sat', 'si', 'sk', 'sl', 'sq', 'sr', 'su', 'sv', 'syr', 'ta', 'tdd', 'te', 'th', 'tl', 'tr', 'tzm', 'uk', 'vai', 'vi', 'zh']
```

Returns both built-in and user-registered language codes, sorted alphabetically.

!!! tip
    Use `lang="auto"` to auto-detect the language from the dominant non-Latin script in the input, instead of specifying a code manually. See [Language Support](../user-guide/language-support.md#auto-detecting-language-from-script) for details.

---

## register_lang

::: disarm.register_lang

### Example

```python
from disarm import register_lang, transliterate

register_lang("eo", {
    "ĉ": "cx", "ĝ": "gx", "ĥ": "hx",
    "ĵ": "jx", "ŝ": "sx", "ŭ": "ux",
})

assert transliterate("ĉapelo", lang="eo") == 'cxapelo'

# Verify registration
from disarm import list_langs
assert "eo" in list_langs()
```

!!! warning
    This is a global, process-wide operation. Registered profiles persist for the lifetime of the Python process and are visible to all threads.

---

## register_replacements

::: disarm.register_replacements

### Example

```python
from disarm import register_replacements, transliterate

register_replacements({
    "©": "(c)",
    "®": "(R)",
    "™": "(TM)",
})

assert transliterate("Hello™ World©") == 'Hello(TM) World(c)'
```

Replacements are applied as a pre-processing step before the character-by-character transliteration lookup. They are global and persist for the process lifetime.

---

## remove_replacement

::: disarm.remove_replacement

### Example

```python
from disarm import register_replacements, remove_replacement, transliterate

register_replacements({"©": "(c)", "®": "(R)"})
assert transliterate("©®") == '(c)(R)'

assert remove_replacement("©") == True
assert remove_replacement("©") == False
assert transliterate("©®") == '(c)(R)'
```

---

## clear_replacements

::: disarm.clear_replacements

### Example

```python
from disarm import register_replacements, clear_replacements, transliterate

register_replacements({"©": "(c)", "®": "(R)"})
assert transliterate("©®") == '(c)(R)'

clear_replacements()
assert transliterate("©®") == '(c)(R)'
```

!!! note
    `clear_replacements()` removes all user-registered replacements. Built-in transliteration tables are not affected.
