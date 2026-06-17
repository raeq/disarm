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

Six branches fire, in order; the first four need no lexicon and are
script-agnostic, so they port across writing systems.

| Kind | Fires on | Spared (false-positive guards) |
|---|---|---|
| `invisible` | a zero-width / formatting codepoint inside a Latin word | emoji ZWJ sequences; ZWJ/ZWNJ joiners in Indic & Arabic; soft hyphen |
| `bidi` | an LRO/RLO override anywhere, or an isolate inside a majority-Latin token (Trojan Source) | bare directional marks; LRE..PDF embeddings (RTL text, hashtags) |
| `zalgo` | excessive stacked combining marks | ordinary accents |
| `mixed_script` | Latin combined with Cyrillic or Greek in one token | CJK / Thai / kaomoji; legitimate unit symbols (`kΩ`, `µF`) |
| `bidi_mixed` | one token mixes strong left-to-right and strong right-to-left **letters** (`varonisו`), which can visually reorder ("BiDi Swap") — no `U+202x` override (that is `bidi`) | single-direction text (all-LTR or all-RTL); digits are neutral |
| `leet` | every out-of-place char substitutes a letter and the result is a common word (`fr33` → `free`) | a literal number that maps to no letter (`win32`, `Power5`, `21st`, `3pm`) |
| `segmentation` | dense separators splitting single letters into a real word (`v.i.a.g.r.a`) | multi-letter parts (`6-foot-6`); a lone separator (`e-mail`) |

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
