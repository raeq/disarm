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
| `invisible` | a zero-width / formatting codepoint inside a Latin word; a run of **tag**, **variation-selector**, zero-width or **Private Use Area** characters standing on their own (#700, #812); the twelve `Default_Ignorable` `Cf` code points that are invisible by property rather than by name — Duployan `U+1BCA0`–`U+1BCA3` and musical `U+1D173`–`U+1D17A` (#813) | emoji ZWJ sequences; ZWJ/ZWNJ joiners in Indic & Arabic; soft hyphen; a **single** Private Use Area code point, which is an icon-font glyph — it takes four in a row, the same reason `strip_format` keeps the block at all (#413); the 29 `Cf` code points that render and carry meaning, such as the Arabic number signs and the Egyptian hieroglyph layout controls |
| `bidi` | an LRO/RLO override anywhere; an isolate or an LRE..PDF embedding in a token that is majority-Latin **or has no letters at all** (`12<isolate>34` — a bare account number is exactly the carrier, so numeric tokens are in scope, Trojan Source, #643); an `RLM`/`ALM` immediately before a run of European numbers in the same context — `Transfer <RLM>100 200 300 to Bob` renders `Transfer 300 200 100 to Bob` (#741) | `LRM`, which produced no reordering over any carrier measured; `RLM`/`ALM` anywhere other than in front of a number run, so RTL prose and hashtags do not fire |
| `zalgo` | excessive stacked combining marks | ordinary accents |
| `enclosing_mark` | two or more **enclosing marks** (`Me`) in one token — `I⃝g⃝n⃝o⃝r⃝e⃝`. Its own kind rather than a `zalgo` finding, because it is a different fact: not "too many marks" but a mark whose category is never an accent. One per base is below every threshold — `is_zalgo` fires above three, `strip_zalgo` keeps two — so the class was clean at every surface while `strip_obfuscation` removed it (#724) | keycap sequences (`1️⃣` is `1` + `U+FE0F` + `U+20E3`, and the variation selector is what makes it an RGI keycap); Cyrillic `Me` on a Cyrillic base, which is historic notation; a single enclosing mark, which is a character someone may have typed |
| `mixed_numbers` | one token drawing digits from more than one **decimal numbering system** — UTS #39 §5.3. `1٢۳４५` reads as `12345` and is five systems; `12٣` is two. Digits carry the script of nothing, so `mixed_script` cannot see the common shape: a token that is mostly ASCII with one substituted digit is one script to every other check here, and the whole class was clean at every surface (#777) | a **single** system, however unusual — `٢٠٢٤` is a year and `२०२४` is the same year in Devanagari. The check is about mixing, not about which digits |
| `duplicate_mark` | the **same** nonspacing mark twice in a row on one base — UTS #39 §5.4. `á́` renders indistinguishably from `á`, so it is a spelling of a word that no keyboard produces and no reader can tell apart. Below every zalgo threshold by design: two marks is ordinary, and it is the *repetition* rather than the count that carries no information (#835) | a repeated mark of combining class 0, which is positioned rather than stacked — a doubled Devanagari matra is an orthography question, not this one; and two **different** marks on one base, which is how stacked diacritics normally work (`ế`) |
| `mixed_script` | Latin combined with Cyrillic or Greek in one token | CJK / Thai / kaomoji; legitimate unit symbols (`kΩ`, `µF`) |
| `bidi_mixed` | one token mixes strong left-to-right and strong right-to-left **letters** (`varonisו`), which can visually reorder ("BiDi Swap") — no `U+202x` override (that is `bidi`) | single-direction text (all-LTR or all-RTL); digits are neutral |
| `leet` | every out-of-place char substitutes a letter and **either** the decode is a lexicon word (`fr33` → `free`) **or**, at five characters and up, it is one edit from one (`1ogin` → `iogin` → `login`). The second path exists because `1` decodes to `i`, not `l` — correct, but it means a `1`-for-`l` spoof never decodes exactly and the exact path can never see it (#825) | a literal number that maps to no letter (`win32`, `Power5`, `21st`, `3pm`); a one-edit decode shorter than five characters, where the neighbourhood is dense enough that `k8s` and `co2` start reading as words |
| `segmentation` | dense separators splitting single letters into a real word (`v.i.a.g.r.a`) | multi-letter parts (`6-foot-6`); a lone separator (`e-mail`) |
| `control` | a non-whitespace control anywhere in the token — `NUL`, `ESC`, `BEL`, `DEL`, the C1 block. Never legitimate in text, and the introducer for terminal-escape injection and leading-blank blocklist bypass | the whitespace-class controls (TAB, LF, VT, FF, CR, `U+001C`–`U+001F`, NEL), which are real separators `collapse_whitespace` folds to a space |
| `compat_fold` | a token mixing a Unicode **compatibility** form with ASCII, where the non-ASCII part folds *to ASCII* — `ａdmin`, `ｅxample.com`, `＜script＞`. `canonicalize` performs that fold as its first step, so the class was neutralized and reported clean | ordinary fullwidth typography with no ASCII letter (`ＮＨＫ`, `Ｑ＆Ａ`, `１９９５年`, `ＣＤ－ＲＯＭ`); unit symbols whose fold is Greek, not ASCII (`kΩ`, `µF`), and the squared CJK units that do fold to ASCII but carry no letter (`10㎏` → `10kg`, `5㎞` → `5km`); and a token spelled *wholly* in a compatibility form (`ｐａｙｐａｌ`), which cannot be told from `ＮＨＫ` by character class |
| `confusable` | a token where the **confusable fold** — not NFKC — produces ASCII the input did not carry: `pɑypal` (`U+0251`), `gıthub` (`U+0131`), `ord∶end` (`U+2236` → `:`). `canonicalize` has two ASCII-producing steps and `compat_fold` reported only the first; the second is the largest table disarm ships and the detector never consulted it. The slice with no compatibility decomposition is also single-script, so `mixed_script` cannot see it either. 232 code points reach ASCII by the fold alone, 76 producing one of `: = % & ? # / \` | text where every letter folds to Latin and none is ASCII — `Привет`, `Ελλάδα`, which is the whole-legitimate-non-Latin-web over-flagging #545 removed from `is_suspicious_hostname`; accented Latin, which the fold leaves alone (`café`, `naïve`, `straße`); unit symbols (`µF`, `kΩ`); and a word boundary — `IT-специалист` is two words, judged separately |

### The `bidi` kind is a judgement, not a census (#778)

The row above spares `LRM` everywhere and `RLM`/`ALM` outside a number run, on purpose: a
lone directional mark is ordinary in right-to-left text, and reporting one would fire on
any page that uses it. So the kind answers **9 of the 12** UAX #9 controls.

When the question is the census rather than the judgement — a filename, an identifier, a
source file, anywhere the caller has already decided their input should carry no bidi
control at all — use `has_bidi_control`, which answers all twelve and applies no context:

```python
from disarm import has_bidi_conflict, has_bidi_control, inspect_anomalies

assert has_bidi_control("\u200e")  # a mark counts
assert inspect_anomalies("\u200e").kinds == []  # and is deliberately not an anomaly

assert has_bidi_control("invoice\u202egpj.exe")  # so does an override
assert not has_bidi_conflict("invoice\u202egpj.exe")  # which reads letters, not controls
```

The three predicates are disjoint answers to different questions: `has_bidi_control` is the
raw set, `inspect_anomalies` is the judged subset, and `has_bidi_conflict` reads
strong-direction **letters** and is structurally blind to controls altogether.


!!! note "`canonicalize` preserves enclosing marks; `strip_obfuscation` removes them"

    That asymmetry is deliberate and is the same one the accent-preserving decision
    (#429) produces: `canonicalize` caps stacked marks rather than deleting them, because
    `café` and `Việt` must survive, and it does not read the mark's category.

    #724 §3 asks whether it should strip `Me` specifically — no enclosing mark is an
    accent, so doing so would not weaken #429. The argument is sound and the change is
    **not** made here: it moves `canonicalize` output for 13 code points, which is a
    `### Changed (breaking)` entry and a decision of its own rather than a side effect of
    adding a detector rule. Until then, `inspect_anomalies` reports the class and
    `strip_obfuscation` removes it — screen with the first, clean with the second, and do
    not read a clean `canonicalize` as a claim that the text carries no enclosing mark.


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

One input carrying three different hazards — a right-to-left override, a zero-width
space and a Cyrillic `ԁ` standing in for Latin `d`:

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
