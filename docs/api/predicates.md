# Predicates

Functions that inspect text and return boolean or structured results without modifying the input.

## detect_scripts

::: disarm.detect_scripts

---

## inspect_auto_lang

::: disarm.inspect_auto_lang

```python
from disarm import inspect_auto_lang

inspect_auto_lang("Київ")
# {'script': 'Cyrillic', 'chosen_lang': 'uk', 'reason': 'discriminator', 'discriminators_hit': ['ї']}

inspect_auto_lang("Москва")
# {'script': 'Cyrillic', 'chosen_lang': 'ru', 'reason': 'script_default', 'discriminators_hit': []}

inspect_auto_lang("hello")
# {'script': None, 'chosen_lang': None, 'reason': 'no_detection', 'discriminators_hit': []}
```

See [Language Detection](../user-guide/language-detection.md#inspecting-detection-results) for details.

---

## is_mixed_script

::: disarm.is_mixed_script

---

## is_confusable

::: disarm.is_confusable

---

## is_ascii

::: disarm.is_ascii

---

## is_normalized

::: disarm.is_normalized

---

## is_zalgo

::: disarm.is_zalgo

```python
from disarm import is_zalgo

is_zalgo("café")          # False (1 combining mark — normal)
is_zalgo("Việt Nam")      # False (2 combining marks — normal)
# Zalgo: 'a' with 20 stacked combining graves
is_zalgo("a" + "\u0300" * 20)  # True
```

---

## is_safe_hostname

::: disarm.is_safe_hostname

### SafeHostnameDetails

The second element of the tuple returned by `is_safe_hostname()`:

| Attribute | Type | Description |
|---|---|---|
| `safe` | `bool` | `True` if no homoglyph spoofing detected |
| `scripts` | `list[str]` | Unicode scripts found across all labels |
| `mixed_script` | `bool` | `True` if multiple scripts detected |
| `has_confusables` | `bool` | `True` if confusable homoglyphs found |
| `canonical` | `str` | Latin-normalized form of the hostname |

```python
from disarm import is_safe_hostname

safe, details = is_safe_hostname("google.com")
# safe = True, details.canonical = "google.com"

safe, details = is_safe_hostname("gооgle.com")  # Cyrillic о's
# safe = False, details.mixed_script = True, details.has_confusables = True
```

A hostname is considered unsafe if it contains mixed high-risk scripts (Cyrillic+Latin, Greek+Latin) or confusable homoglyphs.
