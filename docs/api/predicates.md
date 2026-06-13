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

## is_suspicious_hostname

::: disarm.is_suspicious_hostname

### HostnameAnalysis

The second element of the tuple returned by `is_suspicious_hostname()`:

| Attribute | Type | Description |
|---|---|---|
| `suspicious` | `bool` | `True` if a problem was detected (mixed-script or bundled-table confusable) |
| `scripts` | `list[str]` | Unicode scripts found across all labels |
| `mixed_script` | `bool` | `True` if any single label contains more than one script |
| `has_confusables` | `bool` | `True` if confusable homoglyphs found |
| `canonical` | `str` | Latin-normalized form of the hostname |

```python
from disarm import is_suspicious_hostname

suspicious, analysis = is_suspicious_hostname("google.com")
# suspicious = False, analysis.canonical = "google.com"

suspicious, analysis = is_suspicious_hostname("gооgle.com")  # Cyrillic о's
# suspicious = True, analysis.mixed_script = True, analysis.has_confusables = True
```

A hostname is flagged suspicious if any single label is mixed-script (draws on more than one Unicode script) or contains confusable homoglyphs. **A not-suspicious result is not a safety guarantee** — whole-script spoofs with no bundled-table confusable, and confusables outside the bundled table, are out of scope (see [Threat Model](https://github.com/raeq/disarm/blob/main/THREAT_MODEL.md)); branch on the granular fields plus your own policy.
