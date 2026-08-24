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

## has_bidi_conflict

::: disarm.has_bidi_conflict

---

## is_confusable

::: disarm.is_confusable

---

## unmapped_confusables

::: disarm.unmapped_confusables

---

## find_unmapped_confusables

::: disarm.find_unmapped_confusables

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

!!! note "Renamed from `is_safe_hostname` in 0.9.1 — with the boolean **inverted**"
    If you are upgrading from `is_safe_hostname`, the return value's polarity was flipped
    (`safe` → `suspicious`); a mechanical rename silently reverses your allow/deny branch.
    See the [Upgrading guide](../upgrading.md).

::: disarm.is_suspicious_hostname

### HostnameAnalysis

The second element of the tuple returned by `is_suspicious_hostname()`:

| Attribute | Type | Description |
|---|---|---|
| `suspicious` | `bool` | `True` if any label is mixed-script, contains a Latin-confusable character, or the hostname has a bidi-direction conflict, a bidi control character, or a zero-width/invisible character. An **any-character** confusable screen — it flags essentially every non-Latin hostname, so it is a *maximally conservative screen*, not a precise verdict |
| `scripts` | `list[str]` | Unicode scripts found across all labels |
| `mixed_script` | `bool` | `True` if any single label contains more than one script |
| `has_confusables` | `bool` | `True` if any label contains a Latin-confusable character |
| `bidi_conflict` | `bool` | `True` if the decoded hostname mixes strong LTR and RTL characters (the "BiDi Swap" precondition); **folded into** `suspicious` |
| `bidi_control` | `bool` | `True` if the decoded hostname carries a UAX #9 bidi control character — override (`U+202D`/`U+202E`), embedding (`U+202A`–`U+202C`), isolate (`U+2066`–`U+2069`) or directional mark (`U+200E`/`U+200F`/`U+061C`). Disjoint from `bidi_conflict`, which reads strong-direction *letters* only. **Folded into** `suspicious`; the characters are stripped from `canonical` |
| `has_invisible` | `bool` | `True` if the decoded hostname carries a zero-width or invisible-format character — `U+200B`–`U+200D`, `U+2060`–`U+2064`, `U+FEFF`, `U+180E`. Disjoint from `bidi_control`: these carry no direction at all. **Folded into** `suspicious`, and removed before any other field is computed, so they never reach `scripts`, `mixed_script` or `canonical` |
| `cross_label_script` | `bool` | `True` if the labels span more than one script; broader/noisier than `bidi_conflict` (fires on benign IDN ccTLDs like `google.рф`), so **not** folded into `suspicious` |
| `label_scripts` | `list[list[str]]` | Per-label resolved scripts, left to right |
| `whole_script_confusable` | `bool` | `True` if any label is single-script, non-Latin, whose confusable skeleton is entirely Latin (`аррӏе`→`apple`). A graded **signal, not a verdict** — **not** folded into `suspicious` (fires on `ру`→`py`, `оса`→`oca`) |
| `label_whole_script_confusable` | `list[bool]` | Per-label whole-script-confusable flags, parallel to `label_scripts` (exclude the TLD label for the precise policy) |
| `canonical` | `str` | Latin-normalized form of the hostname |

```python
from disarm import is_suspicious_hostname

suspicious, analysis = is_suspicious_hostname("google.com")
# suspicious = False, analysis.canonical = "google.com"

suspicious, analysis = is_suspicious_hostname("gооgle.com")  # Cyrillic о's
# suspicious = True, analysis.mixed_script = True, analysis.has_confusables = True

# Whole-script spoof: an all-Cyrillic label whose skeleton is Latin
suspicious, analysis = is_suspicious_hostname("аррӏе.com")
# analysis.whole_script_confusable = True
# analysis.label_whole_script_confusable = [True, False]  # spoof label, then the TLD
# analysis.canonical = "apple.com"
```

`suspicious` is a **maximally conservative screen**: because the confusable check is an any-character test and the most frequent Cyrillic/Greek letters are TR39 confusables, it flags essentially every non-Latin hostname — `москва.рф` as readily as `аррӏе.com`. **A not-suspicious result is not a safety guarantee**, and a suspicious one is not a precise verdict. For whole-script spoofs, use `whole_script_confusable` / `label_whole_script_confusable`: the precise, low-false-positive policy is `whole_script_confusable(non-TLD label) ∧ (TLD is Latin/ASCII)`, applied by the caller — disarm deliberately does not model registrable boundaries (no PSL), and the irreducible `оса`-style case (a real word that skeletons to Latin) needs a caller-supplied protected-name list. See the [Threat Model](https://github.com/raeq/disarm/blob/main/THREAT_MODEL.md).
