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

## find_key_collisions

::: disarm.find_key_collisions

```python
from disarm import find_key_collisions

find_key_collisions(["groß.txt", "gross.txt", "other.txt"], key="fold_case")
# [KeyCollision(key="gross.txt", values=["groß.txt", "gross.txt"], indices=[0, 1])]

find_key_collisions(["admin", "аdmin"], key="canonicalize")
# [KeyCollision(key="admin", values=["admin", "аdmin"], indices=[0, 1])]

find_key_collisions(["a.txt", "b.txt"], key="fold_case")
# []
```

Every other function on this page answers about one string. This one answers about
a set, because a collision is not a property of a single string: `groß.txt` is an
ordinary German filename, and `аdmin` is only a problem next to `admin`. It is the
question node-tar's `PathReservations` guard failed to ask before extracting two
paths in parallel (CVE-2026-23950), and the one a registry has to ask before
accepting a second `admin` (CVE-2013-7236). Those two want opposite policies from
the same answer — refuse the batch, or refuse the registration — so the function
reports and decides nothing.

Each result is a `KeyCollision` with three fields:

| Field | Meaning |
|---|---|
| `key` | The reduced form every member of the group shares. |
| `values` | The distinct inputs that reduce to it, in order of first appearance. |
| `indices` | Every position in the input list, ascending. Not parallel to `values`: a value repeated verbatim appears once there and once per occurrence here. |

A group is reported only when it holds two or more *distinct* inputs. The same
name twice is the same name twice, which a reservation table already handles.

### The return is not a partition, and the two counts do not add

A name that collides with nothing never appears in the result, so the groups do not
cover the input. The quantity a registry usually wants next — *after reduction, how
many distinct identities does this batch hold?* — is not returned, and has to be
derived. There is one correct spelling:

```text
reduced = len(set(values)) - sum(len(g.values) for g in groups) + len(groups)
```

`values` and `indices` have **different denominators by design**, which is why the
table above says they are not parallel. The consequence is that they cannot be added
to each other, and it is easy to miss, because every example on this page is
duplicate-free and all four plausible spellings agree on a duplicate-free batch:

```python
from disarm import find_key_collisions

names = ["admin", "admin", "Admin"]
groups = find_key_collisions(names, key="fold_case")
assert groups[0].values == ["admin", "Admin"]  # distinct inputs: two
assert groups[0].indices == [0, 1, 2]  # occurrences: three

by_values = sum(len(g.values) for g in groups)
by_indices = sum(len(g.indices) for g in groups)

assert len(set(names)) - by_values + len(groups) == 1  # correct
assert len(names) - by_values + len(groups) == 2  # counts a repeat
assert len(set(names)) - by_indices + len(groups) == 0  # mixed denominators
assert len(names) - by_indices + len(groups) == 1  # right by cancellation
```

Three names, one identity. Measured over 400 duplicate-free batches, all four
spellings agree with the truth; over 400 of the same batches with one repeat
injected, only the first does.

!!! note "One reduced slot can hold unrelated values"

    Every key builder maps some non-empty input to `""`, so a reduced count can
    include a slot holding several strings that have nothing to do with each other.
    `["", "\u200b", "\u0301\u0302", "bob"]` reduces to 2 under `search_key`, and one
    of those two is the empty key. Tracked separately in
    [#728](https://github.com/raeq/disarm/issues/728).

---

## is_case_fold_stable

::: disarm.is_case_fold_stable

```python
from disarm import is_case_fold_stable

is_case_fold_stable("gross.txt")  # True
is_case_fold_stable("groß.txt")  # False — folds to gross.txt, so the two collide
is_case_fold_stable("ﬁle")  # False — folds to file
is_case_fold_stable("ΟΔΟΣ")  # False — lowercases to οδος, folds to οδοσ
```

Use it before a name becomes a key: a reservation table, a username registry, an
extraction path. `False` says the value shares its folded form with some other
string, which is the precondition node-tar's `PathReservations` guard missed in
CVE-2026-23950. It says nothing about intent, since `groß` is an ordinary German
word, so the predicate is kept out of
[anomaly detection](../user-guide/anomaly-detection.md) and the response is the
caller's to choose: reserve both forms, reject the name, or key the table on
[`fold_case`](transforms.md#fold_case) instead of `str.lower()`.

---

## is_canonical

::: disarm.is_canonical

```python
from disarm import canonicalize, has_anomalies, is_canonical

is_canonical("paypal.com")  # True
is_canonical("ｐａｙｐａｌ.ｃｏｍ")  # False — fullwidth, canonicalizes to paypal.com
is_canonical("abc", preset="search_key")  # True
```

### Generation path and verification path

The two are different questions and the answers do not substitute for one another.

| | ask | function |
|---|---|---|
| **Generation path** | *what should I store?* | [`canonicalize`](pipelines.md#canonicalize) and the other presets |
| **Verification path** | *may I accept what I was handed?* | `is_canonical` |

Normalize on the way in and the verification path never comes up, because the stored
value is canonical by construction. It comes up wherever bytes arrive already bound to a
decision — a signed payload whose signature covers the original bytes, a primary key that
already has rows pointing at it, an identifier a third party will re-derive. Silently
recomputing the canonical form there defends the comparison you are about to make and
leaves the non-canonical representation in circulation, still able to reach a system that
compares differently.

### `has_anomalies` does not answer this

The obvious accept gate — reject if [`has_anomalies`](../user-guide/anomaly-detection.md), otherwise take the
bytes as given — is not a canonicity check. Over every assigned code point (UCD 16.0.0,
excluding unassigned and surrogates):

| | count |
|---|---|
| clean to the detector **and** not canonical | 142,760 (5,292 excluding the Private Use Area) |
| flagged by the detector **and** already canonical | 0 |

The relationship is one-way: the detector never fires on text the canonicalizer would
leave alone, but it stays silent on 5,292 non-PUA code points that are not their own
canonical form, including CJK compatibility ideographs, Arabic presentation forms,
Kangxi radicals and all of fullwidth Latin.

Widening the detector is the wrong fix. `ＮＨＫ` is how a Japanese broadcaster writes its
own name and `㎏` is an ordinary unit, so a detector that flagged them is one callers
switch off — that is what [#633](https://github.com/raeq/disarm/issues/633) and
[#907](https://github.com/raeq/disarm/issues/907) were about. `has_anomalies` answers
*does this look disguised*; `is_canonical` answers *is this already the form I store*.

---

## is_normalized

::: disarm.is_normalized

---

## is_zalgo

::: disarm.is_zalgo

```python
from disarm import is_zalgo

is_zalgo("café")  # False (1 combining mark — normal)
is_zalgo("Việt Nam")  # False (2 combining marks — normal)
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
| `has_confusables` | `bool` | `True` if any label contains a Latin-confusable character. Read *after* the UTS #46 mapping and NFKC, so it cannot see a compatibility form by construction — `ｇoogle.com` is already `google.com` by then, and `False` is the correct answer. `canonical` differing from the input while this stays `False` means `compat_fold`, not a defect |
| `bidi_conflict` | `bool` | `True` if the decoded hostname mixes strong LTR and RTL characters (the "BiDi Swap" precondition); **folded into** `suspicious` |
| `bidi_control` | `bool` | `True` if the decoded hostname carries a UAX #9 bidi control character — override (`U+202D`/`U+202E`), embedding (`U+202A`–`U+202C`), isolate (`U+2066`–`U+2069`) or directional mark (`U+200E`/`U+200F`/`U+061C`). Disjoint from `bidi_conflict`, which reads strong-direction *letters* only. **Folded into** `suspicious`; the characters are stripped from `canonical` |
| `has_invisible` | `bool` | `True` if the decoded hostname carries an invisible character of any class: zero-width (`U+200B`–`U+200D`, `U+2060`–`U+2064`, `U+FEFF`, `U+180E`), tag (`U+E0000`–`U+E007F`), variation selector (`U+FE00`–`U+FE0F`, `U+E0100`–`U+E01EF`), noncharacter (`U+FDD0`–`U+FDEF` and the last two of every plane), private use (`U+E000`–`U+F8FF`, planes 15 and 16). Disjoint from `bidi_control`: these carry no direction at all. RFC 5892 puts the tag, variation-selector, noncharacter and private-use classes in DISALLOWED outright; `U+200C`/`U+200D` are CONTEXTJ (conditionally permitted) and the screen flags them anyway, as a deliberate fail-closed policy. **Folded into** `suspicious`, and removed per label before any other field is computed, so they never reach `scripts`, `mixed_script` or `canonical` |
| `compat_fold` | `bool` | `True` if any label carried a Unicode **compatibility form** before normalization (#709) — fullwidth (`ｇoogle`), ligature (`ﬁle`), Roman numeral (`Ⅰ`BM), mathematical alphanumeric (`𝗀𝗈𝗈𝗀𝗅𝖾`), circled, superscript. The predicate is RFC 5892 §2.1's, applied **per code point**: `toNFKC(c) != c` is DISALLOWED in an IDN label, so IDNA2008 disallows the whole set. **Folded into** `suspicious`, on the same footing as `bidi_control` and `has_invisible`. The threat is a blocklist bypass rather than a lookalike — `ｅvil.com` is absent from a blocked set, screens clean, and resolves to `evil.com`. Per character, not "NFKC changed the label", which would fire on legitimate decomposed input (`한국.kr` in conjoining jamo). The one field read from the **raw** input |
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
