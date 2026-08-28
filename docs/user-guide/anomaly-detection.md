# Anomaly Detection

`has_anomalies` / `inspect_anomalies` flag text that carries **out-of-place
characters disguising a real word** — a cross-script homoglyph, a bidi-direction
conflict, leet, a single-letter segmentation, a zero-width / bidi control, or
zalgo. Like
[`is_suspicious_hostname`](../api/predicates.md#is_suspicious_hostname), the
detector reports a **technical fact** and leaves the malicious-or-not judgement to
the caller — it never claims intent.

!!! note "Defensive publication"
    This detector is described publicly as **prior art** so the method stays freely
    usable and cannot be patented by others. See
    [issue #389](https://github.com/raeq/disarm/issues/389) for the dated record.

## Detected classes

Eight branches fire. Six need no lexicon — only `leet` and `segmentation` do.

The table below is grouped by kind, not by evaluation order. `control` is checked
**first**, ahead of the ASCII fast-path, because `NUL`, `ESC`, `BEL` and `DEL` are
themselves ASCII: a check placed after that fast-path would never see the vectors it
exists for. The remaining branches split on `!tok.is_ascii()`, so `invisible`, `bidi`,
`zalgo`, `bidi_mixed` and `mixed_script` only run on non-ASCII tokens, and `leet` and
`segmentation` run last on everything.

Most branches are script-agnostic and port across writing systems. `mixed_script` is the
exception — it is anchored on Latin, and fires on Latin combined with Cyrillic or Greek.

| Kind | Fires on | Spared (false-positive guards) |
|---|---|---|
| `invisible` | a zero-width / formatting codepoint inside a Latin word | emoji ZWJ sequences; ZWJ/ZWNJ joiners in Indic & Arabic; soft hyphen |
| `bidi` | an LRO/RLO override anywhere, or an isolate inside a majority-Latin token (Trojan Source) | bare directional marks; LRE..PDF embeddings (RTL text, hashtags) |
| `zalgo` | excessive stacked combining marks | ordinary accents |
| `mixed_script` | Latin combined with Cyrillic or Greek in one token | CJK / Thai / kaomoji; legitimate unit symbols (`kΩ`, `µF`) |
| `bidi_mixed` | one token mixes strong left-to-right and strong right-to-left **letters** (`varonisו`), which can visually reorder ("BiDi Swap") — no `U+202x` override (that is `bidi`) | single-direction text (all-LTR or all-RTL); digits are neutral |
| `leet` | every out-of-place char substitutes a letter and the result is a common word (`fr33` → `free`) | a literal number that maps to no letter (`win32`, `Power5`, `21st`, `3pm`) |
| `segmentation` | dense separators splitting single letters into a real word (`v.i.a.g.r.a`) | multi-letter parts (`6-foot-6`); a lone separator (`e-mail`) |
| `control` | a non-whitespace control anywhere in the token — `NUL`, `ESC`, `BEL`, `DEL`, the C1 block. Never legitimate in text, and the introducer for terminal-escape injection and leading-blank blocklist bypass | the whitespace-class controls (TAB, LF, VT, FF, CR, `U+001C`–`U+001F`, NEL), which are real separators `collapse_whitespace` folds to a space |
| `compat_fold` | a token mixing a Unicode **compatibility** form with ASCII, where the non-ASCII part folds *to ASCII* — `ａdmin`, `ｅxample.com`, `＜script＞`. `canonicalize` performs that fold as its first step, so the class was neutralized and reported clean | ordinary fullwidth typography with no ASCII letter (`ＮＨＫ`, `Ｑ＆Ａ`, `１９９５年`, `ＣＤ－ＲＯＭ`); unit symbols whose fold is Greek, not ASCII (`kΩ`, `µF`), and the squared CJK units that do fold to ASCII but carry no letter (`10㎏` → `10kg`, `5㎞` → `5km`); and a token spelled *wholly* in a compatibility form (`ｐａｙｐａｌ`), which cannot be told from `ＮＨＫ` by character class |

The **leet** and **segmentation** branches take a caller-supplied **lexicon** — a
set of common words for the language being protected. The defining rule: a real
leet attack *substitutes* a letter, whereas `win32` carries a *literal* number
that maps to no letter, so requiring every out-of-place character to be a real
letter-substitution that yields a common word rejects the literals.

## Usage

=== "Python"

    ```python
    from disarm import has_anomalies, inspect_anomalies

    words = {"free", "paypal"}

    # leet: "fr33" decodes to "free"
    assert has_anomalies("get fr33 now", words)
    # a literal number is not a substitution, so "win32" is spared
    assert not has_anomalies("the win32 api", words)

    report = inspect_anomalies("log in to paypаl", {"paypal"})  # Cyrillic а
    assert report.anomalous
    assert report.kinds == ["mixed_script"]
    assert report.findings[0].kind == "mixed_script"
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, AnomalyKind};
    use std::collections::HashSet;

    let words: HashSet<String> = ["free", "paypal"].iter().map(|s| s.to_string()).collect();

    assert!(api::has_anomalies("get fr33 now", &words));
    assert!(!api::has_anomalies("the win32 api", &words));

    let report = api::inspect_anomalies("log in to paypаl", &words);
    assert!(report.anomalous);
    assert_eq!(report.kinds, vec![AnomalyKind::MixedScript]);
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    # the lexicon is a common-word collection (Array or Set)
    Disarm.has_anomalies?("get fr33 now", ["free"])  # => true
    Disarm.has_anomalies?("the win32 api", ["free"]) # => false

    Disarm.inspect_anomalies("log in to paypаl", ["paypal"])[:kinds] # => ["mixed_script"]
    ```

=== "Node"

    ```ts
    import { hasAnomalies, inspectAnomalies } from 'disarm'

    // the lexicon is a Set or array of common words
    hasAnomalies('get fr33 now', ['free'])  // => true
    hasAnomalies('the win32 api', ['free']) // => false

    inspectAnomalies('log in to paypаl', ['paypal']).kinds // => ['mixed_script']
    ```

## The report

`inspect_anomalies` returns a report with `anomalous`, `kinds` (the anomaly kinds
that fired, in first-appearance order), `findings`, and `reason` (the first
finding's plain-language sentence). Each **finding** carries the offending
`kind`, `token`, byte `start`/`end` span, `detail` (the codepoint, the scripts,
or the decoded word), and its own `reason`.

A `False` result is not a safety guarantee — it means only that none of the six
branches fired on the lexicon you supplied. Compose this with your own policy, as
you would the hostname analysis.

## Checking a transform at the seam

Run `has_anomalies` on the **output** of a transform and it tells you whether that
transform left something behind. The check needs no new API and is the cheapest way
to find out you picked the wrong function.

One input, three overrides in it — a right-to-left override, a zero-width space and
a Cyrillic `ԁ`:

```python
from disarm import (
    canonicalize,
    has_anomalies,
    inspect_anomalies,
    ml_normalize,
    normalize_confusables,
)

hostile = "\u202eexample\u200b.com\u0501"

# canonicalize clears all three: nothing is left to report.
assert canonicalize(hostile) == "example.comd"
assert has_anomalies(canonicalize(hostile)) is False

# ml_normalize is not a security preset. The override survives, and the seam
# check is what tells you so.
assert has_anomalies(ml_normalize(hostile)) is True
assert inspect_anomalies(ml_normalize(hostile)).kinds == ["bidi"]

# normalize_confusables folds the homoglyph and nothing else.
assert inspect_anomalies(normalize_confusables(hostile)).kinds == ["invisible"]
```

### The guidance only runs one way

!!! warning "A clean result is not an all-clear"
    **If `has_anomalies` is still true after you clean, you used the wrong function
    for your input.** A false result does not mean you chose right — the anomaly
    panel does not cover every class a transform can leave behind.

    Reported recall across 645 adversarial vectors is **42.6%**: 130 of 305
    wrong-choice failures are visible at the seam, at zero false positives,
    splitting as confusables 43%, bidi 58%, PUA 0%. Those figures are not ours and
    we have not reproduced them; the mechanism above is measured here.

    At that recall this is a useful alarm and a useless all-clear. Wire it into CI
    as an acceptance test and it will read "clean" on well over half the inputs that
    are not. The PUA column is the sharpest case: private-use characters are not an
    anomaly kind, so every transform that forwards one is reported clean.

    See [#643](https://github.com/raeq/disarm/issues/643) for classes the panel
    does not cover.
