# Confusable Detection

Unicode confusables (homoglyphs) are characters from different scripts that look visually identical or very similar. For example, Cyrillic "а" (U+0430) looks like Latin "a" (U+0061). Attackers exploit this for phishing, impersonation, and spoofing.

disarm implements Unicode TR39 confusable detection and normalization with multi-target script support, auto-generated from the official [Unicode TR39 confusables.txt](https://www.unicode.org/Public/security/latest/confusables.txt) (version 17.0.0). The tables cover Cyrillic, Greek, Armenian, Georgian, CJK compatibility, mathematical symbols, fullwidth forms, and other visually confusable characters. Mappings are based on visual similarity, not phonetic equivalence.

Two smaller sets are layered on top of the generated table. `confusables_supplement.tsv`
adds cross-script pairs TR39 leaves without a shared prototype (#336/#342). Since #597,
`confusables_attested.tsv` adds 31 codepoints **attested in real attacker text** — mined
from the BitCore subset of the BitAbuse corpus — that TR39 does not list as sources at
all. Twenty-three are optical twins of a Latin letter (`ɴ`→`n`, `ʍ`→`m`, `ʀ`→`r`). Eight
are not: seven are glyphs an attacker used *positionally* rather than because they look
like the letter (`ժ`→`d`, `ᚱ`→`r`, `Ⴝ`→`s`), and one is a reading convention (`щ`→`w`).
For those rows the rule is **observed attacker substitution**, which is wider than visual
confusability. Unicode would not accept them upstream, and they are marked tier `2a` and
`2b` in that file.

## Detecting confusables

=== "Python"

    ```python
    from disarm import is_confusable, is_mixed_script

    # Cyrillic Н looks like Latin H
    assert is_confusable("Неllo") == True
    assert is_mixed_script("Неllo") == True

    # Pure Latin — no confusables
    assert is_confusable("Hello") == False
    assert is_mixed_script("Hello") == False
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, TargetScript};

    // Cyrillic Н looks like Latin H
    assert_eq!(api::is_confusable("Неllo", TargetScript::Latin), true);
    assert_eq!(api::is_mixed_script("Неllo"), true);

    // Pure Latin — no confusables
    assert_eq!(api::is_confusable("Hello", TargetScript::Latin), false);
    assert_eq!(api::is_mixed_script("Hello"), false);
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    # Cyrillic Н looks like Latin H
    Disarm.confusable?("Неllo")   # => true

    # Pure Latin — no confusables
    Disarm.confusable?("Hello")   # => false
    ```

=== "Node"

    ```ts
    import { isConfusable } from 'disarm'

    isConfusable('Неllo') // => true
    isConfusable('Hello') // => false
    ```

## Normalizing confusables

Replace confusable characters with their target-script equivalents:

=== "Python"

    ```python
    from disarm import normalize_confusables

    # Cyrillic а, е, о → Latin a, e, o
    assert normalize_confusables("Неllo Wоrld") == "Hello World"

    # Greek omicron → Latin o
    assert normalize_confusables("Ηellο") == "Hello"
    ```

=== "Rust"

    ```rust
    use disarm::api::{self, TargetScript};

    // Cyrillic а, е, о → Latin a, e, o
    assert_eq!(api::normalize_confusables("Неllo Wоrld", TargetScript::Latin), "Hello World");

    // Greek omicron → Latin o
    assert_eq!(api::normalize_confusables("Ηellο", TargetScript::Latin), "Hello");
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    # Cyrillic а, е, о → Latin a, e, o
    Disarm.normalize_confusables("Неllo Wоrld")   # => "Hello World"

    # Greek omicron → Latin o
    Disarm.normalize_confusables("Ηellο")         # => "Hello"
    ```

=== "Node"

    ```ts
    import { normalizeConfusables } from 'disarm'

    normalizeConfusables('Неllo Wоrld') // => 'Hello World'
    normalizeConfusables('Ηellο') // => 'Hello'
    ```

### The result is a fixed point

Folding runs until nothing more changes, so `normalize_confusables` is idempotent and
its output is never itself confusable. That second property is the one that matters:
the fold exists to produce a skeleton two identifiers can be compared on, and a skeleton
the library's own detector still flags is no use for that.

One pass is not enough, because folding and canonical composition expose work for each
other in both directions. A fold can expose a composition — `¥` + U+0300 folds to `Y` +
U+0300, which composes to `Ỳ`. A composition can expose a fold — `Ҫ` + U+0327 composes
to `Ç`, itself a confusable, which folds to `C`.

The guarantee holds identically in every binding. It has not always: until #586 the
loop ran only on the path Python uses, so the same call returned a half-folded,
still-confusable result in Rust, Node, Ruby, Java, Kotlin and the C ABI.

### It keeps your diacritics

`normalize_confusables` maps confusable characters and touches nothing else. Accented
Latin is not confusable with anything, so it comes through intact — which makes this the
right primitive when the text is a real name and a homoglyph attack is still possible:

```python
from disarm import normalize_confusables, strip_obfuscation

assert normalize_confusables("José Martínez") == "José Martínez"
assert normalize_confusables("naïve café") == "naïve café"

# …while still recovering the attack. Cyrillic а, U+0430:
assert normalize_confusables("pаypаl") == "paypal"
```

The wider `strip_obfuscation` bundle recovers the same attack but also runs
`strip_accents`, so it does not preserve the name:

```python
assert strip_obfuscation("pаypаl") == "paypal"  # same recovery
assert strip_obfuscation("José Martínez") == "Jose Martinez"  # different fidelity
```

Neither is wrong; they answer different questions. Accent destruction is a property of
the bundle, not of confusable mapping. See
[what each entry point costs you](../security/adversarial-defense.md#what-each-entry-point-costs-you)
for the full threat-model-to-entry-point table.

### Digit policy

disarm folds a non-Latin digit to the ASCII **digit**; upstream TR39 folds most of them
to a Latin **letter** — `०` to `o`, `೦` to `O`, `١` to `l`. Neither is wrong. disarm's
reading is right for prose, where a Devanagari zero really is a zero and folding it to a
letter corrupts the number. TR39's is right for an identifier *skeleton*, whose only job
is to make two confusable identifiers collide; it does not care whether the collision
target reads sensibly.
Three of the 45 divergent rows do not land on a letter: `٠` (U+0660) and `۰` (U+06F0)
fold to `.`, and `𑣣` (U+118E3) folds to the two characters `rn`. If the skeleton feeds a
label- or path-shaped key, that extra `.` changes its structure. Every value in the
override set is ASCII — `build.rs` asserts it — so nothing else needs guarding.


The two differ on 45 rows and agree on everything else. Reach for `tr39` when
comparing against a TR39-derived benchmark, and leave the default alone for text.

The policy is scoped to the Latin target. The override rows are generated from the
Latin table and carry TR39's Latin-script targets, so they mean nothing for another
script — with the target set to Cyrillic the policy is a no-op and the fold stays
numeric.

```python
from disarm import normalize_confusables

# Devanagari zeros. Numeric keeps the number; tr39 makes the skeleton collide.
assert normalize_confusables("g००gle") == "g00gle"
assert normalize_confusables("g००gle", digit_policy="tr39") == "google"

# Arabic-Indic 5 and 0: the number 50, or the skeleton "o."
assert normalize_confusables("٥٠") == "50"
assert normalize_confusables("٥٠", digit_policy="tr39") == "o."

# Everything outside those rows is identical under both.
assert normalize_confusables("pаypal", digit_policy="tr39") == "paypal"
```

The presets (`canonicalize`, `catalog_key`, `search_key`, …) have no such switch and
always fold numerically: they serve prose and keys, where the numeric reading is
unambiguously right. Hostname analysis is likewise unaffected — changing the skeleton it
compares against would silently change what `is_suspicious_hostname` flags.

### Target script

By default, confusables are normalized to Latin. You can specify a different target script to normalize *towards* that script instead:

=== "Python"

    ```python
    # Normalize to Latin (default) — non-Latin homoglyphs → Latin
    assert normalize_confusables("раypal") == "paypal"

    # Normalize to Cyrillic — non-Cyrillic homoglyphs → Cyrillic
    assert normalize_confusables("paypal", target_script="cyrillic") == "раураӏ"
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    # Normalize to Latin (default) — non-Latin homoglyphs → Latin
    Disarm.normalize_confusables("раypal")                       # => "paypal"

    # Normalize to Cyrillic — non-Cyrillic homoglyphs → Cyrillic
    Disarm.normalize_confusables("paypal", target: :cyrillic)    # => "раураӏ"
    ```

=== "Node"

    ```ts
    import { normalizeConfusables } from 'disarm'

    normalizeConfusables('раypal') // => 'paypal'
    normalizeConfusables('paypal', { target: 'cyrillic' }) // => 'раураӏ'
    ```

### Supported target scripts

| Target | Mappings | Description |
|--------|----------|-------------|
| `"latin"` (default) | 2,220 | Non-Latin → Latin. Cyrillic а→a, Greek Ρ→P, etc. |
| `"cyrillic"` | 1,349 | Non-Cyrillic → Cyrillic. Latin A→А, p→р, etc. |

Characters without a confusable equivalent in the target script pass through unchanged. This is pure visual mapping — not transliteration. Latin `f` has no Cyrillic lookalike, so it stays as `f`.

## Script detection

Identify which Unicode scripts are present in a string:

=== "Python"

    ```python
    from disarm import detect_scripts, Script

    scripts = detect_scripts("Hello Мир")
    assert scripts == [Script.LATIN, Script.CYRILLIC]

    scripts = detect_scripts("東京 Tokyo")
    assert scripts == [Script.HAN, Script.LATIN]
    ```

=== "Rust"

    ```rust
    use disarm::api;

    assert_eq!(api::detect_scripts("Hello Мир"), vec!["Latin", "Cyrillic"]);
    assert_eq!(api::detect_scripts("東京 Tokyo"), vec!["Han", "Latin"]);
    ```

### The Script enum

`Script` enumerates the 39 Unicode scripts disarm recognizes:

**Major world scripts:**

| Script | Example characters |
|---|---|
| `LATIN` | A–Z, a–z, À–ÿ |
| `CYRILLIC` | А–Я, а–я |
| `GREEK` | Α–Ω, α–ω |
| `ARABIC` | ع, ب, ت |
| `HEBREW` | א, ב, ג |

**Indic scripts:**

| Script | Example characters |
|---|---|
| `DEVANAGARI` | अ, आ, इ |
| `BENGALI` | অ, আ, ই |
| `GURMUKHI` | ਅ, ਆ, ਇ |
| `GUJARATI` | અ, આ, ઇ |
| `ORIYA` | ଅ, ଆ, ଇ |
| `TAMIL` | அ, ஆ, இ |
| `TELUGU` | అ, ఆ, ఇ |
| `KANNADA` | ಅ, ಆ, ಇ |
| `MALAYALAM` | അ, ആ, ഇ |
| `SINHALA` | අ, ආ, ඇ |

**East Asian scripts:**

| Script | Example characters |
|---|---|
| `HAN` | 中, 文, 字 |
| `HIRAGANA` | あ, い, う |
| `KATAKANA` | ア, イ, ウ |
| `HANGUL` | 가, 나, 다 |

**Southeast Asian scripts:**

| Script | Example characters |
|---|---|
| `THAI` | ก, ข, ค |
| `LAO` | ກ, ຂ, ຄ |
| `MYANMAR` | က, ခ, ဂ |
| `KHMER` | ក, ខ, គ |
| `BALINESE` | ᬅ, ᬆ, ᬇ |
| `JAVANESE` | ꦄ, ꦆ, ꦈ |
| `TAI_LE` | ᥐ, ᥑ, ᥒ |
| `NEW_TAI_LUE` | ᦀ, ᦁ, ᦂ |

**Central/North Asian scripts:**

| Script | Example characters |
|---|---|
| `TIBETAN` | ཀ, ཁ, ག |
| `MONGOLIAN` | ᠠ, ᠡ, ᠢ |

**Caucasian scripts:**

| Script | Example characters |
|---|---|
| `GEORGIAN` | ა, ბ, გ |
| `ARMENIAN` | Ա, Բ, Գ |

**African scripts:**

| Script | Example characters |
|---|---|
| `ETHIOPIC` | ሀ, ለ, ሐ |
| `NKO` | ߊ, ߋ, ߌ |
| `VAI` | ꔀ, ꔁ, ꔂ |

**Middle Eastern scripts:**

| Script | Example characters |
|---|---|
| `SYRIAC` | ܐ, ܒ, ܓ |
| `THAANA` | ހ, ށ, ނ |
| `COPTIC` | Ⲁ, Ⲃ, Ⲅ |

**Americas:**

| Script | Example characters |
|---|---|
| `CHEROKEE` | Ꭰ, Ꭱ, Ꭲ |
| `CANADIAN_ABORIGINAL` | ᐁ, ᐂ, ᐃ |

**Historical European scripts:**

| Script | Example characters |
|---|---|
| `RUNIC` | ᚠ, ᚡ, ᚢ |
| `OGHAM` | ᚁ, ᚂ, ᚃ |

**Meta-scripts:**

| Script | Description |
|---|---|
| `COMMON` | Digits, punctuation, whitespace |
| `INHERITED` | Combining diacritical marks |

## Contraction: when two letters impersonate one

The confusable tables map one codepoint to one-or-more, so **expansion** has always
worked. **Contraction** — recognising that `rn` may stand in for `m` — could not be
expressed at all, because the source column of both tables is a single hex codepoint in
every row. That made it a schema change before it was a data change.

It now exists, and it is **off by default and confined to hostname analysis**:

```python
from disarm import is_suspicious_hostname

_s, off = is_suspicious_hostname("arnazon.com")
assert off.canonical == "arnazon.com"

_s, on = is_suspicious_hostname("arnazon.com", contractions=True)
assert on.canonical == "amazon.com"
```

### It changes `canonical`, not the verdict

`contractions=True` does **not** make the boolean flip. `arnazon.com` is all-ASCII Latin:
there is no mixed script and no cross-script confusable, so there is no evidence for a
"suspicious" verdict, and disarm does not know that `amazon` is a brand worth
impersonating.

```python
suspicious, analysis = is_suspicious_hostname("arnazon.com", contractions=True)
assert suspicious is False
assert analysis.canonical == "amazon.com"
```

The signal is in `canonical`. Compare it against your own brand or allow list — that is
the comparison the option exists to make possible. Branching on the boolean alone will
see nothing change, which is the same
[reports-a-fact, not-a-verdict](../security/adversarial-defense.md) split the rest of the
hostname surface follows.

### Why it is not a default, and not in `normalize_confusables`

Unconditional contraction is **worse than none**. `rn` → `m` is right for `arnazon` and
wrong for `earnings`, `turnip`, and `born`:

```python
from disarm import normalize_confusables

# The general fold never contracts, at any setting.
assert normalize_confusables("earnings") == "earnings"
assert normalize_confusables("arnazon") == "arnazon"
```

A hostname is the one place where the threat model justifies those false positives and
where there is no running prose to corrupt. A general-text contraction mode, if it ever
lands, needs its own disambiguation story.

### The rules, and why there are only three

| Rule | Provenance |
|---|---|
| `rn` → `m` | Upstream. TR39 reduces `m` to the sequence `rn`, and 17 distinct sources fold *to* `rn` — the dominant multi-character target in the file. |
| `vv` → `w` | disarm addition. Not in TR39; long-documented in IDN homograph literature. |
| `cl` → `d` | disarm addition. Not in TR39; the third commonly-cited ASCII digraph attack. |

Every rule is a false-positive source, so the bar is "documented real-world technique",
not "plausible".

Matching is **leftmost-longest** over an Aho-Corasick automaton, and applied **per label**,
so a digraph can never form across a dot:

```python
_s, a = is_suspicious_hostname("vvv.com", contractions=True)
assert a.canonical == "wv.com"  # leftmost wins, never "vw"

_s, b = is_suspicious_hostname("var.net", contractions=True)
assert b.canonical == "var.net"  # the r and n are in different labels
```

One pass is a fixed point by construction: `build.rs` asserts no rule's output occurs
inside any rule's input, so a pass can never expose a fresh match. A data edit that
introduced such a chain would fail the build.

## Knowing what is NOT covered

Coverage is not a score. A tool that folds 95% of known confusable sources is not 95%
safe — it is one query away from the other 5%, and an adaptive attacker will find that
query. What matters for deployment is knowing *which* sources go uncovered.

Two accessors answer that, both read-only over the compiled tables.

`unmapped_confusables()` is the global set — every source in the bundled
`confusables.txt` that disarm's table does not fold:

```python
from disarm import unmapped_confusables, normalize_confusables, find_unmapped_confusables

unmapped = unmapped_confusables()

# Cyrillic а (U+0430) folds, so it is covered — not exposure.
assert normalize_confusables("\u0430") == "a"
assert "\u0430" not in unmapped
```

`find_unmapped_confusables()` answers the same question about one input, and is the
confusables analogue of [`find_untranslatable`](transliteration.md). It returns
`(character, byte_offset)` pairs in order, the same convention:

```python
# A folded homoglyph is coverage, so the scan is silent on it.
assert normalize_confusables("p\u0430ypal") == "paypal"
assert find_unmapped_confusables("p\u0430ypal") == []

assert find_unmapped_confusables("hello") == []
```

Composition runs exactly as it does in the fold, so a *decomposed* homoglyph whose
precomposed form is mapped counts as covered — otherwise the report would disagree with
what the transform actually does:

```python
assert normalize_confusables("\u0456\u0308") == "i"  # і + ◌̈ composes to ї, which folds
assert find_unmapped_confusables("\u0456\u0308") == []
```

### Reading the result

Most of the global set is **out of scope**, not missing. A source whose upstream target
is non-Latin has no business in the to-Latin table, and the two bundled tables have
genuinely different coverage — pass `target_script="cyrillic"` to ask about the other
one. Check [`CONFUSABLES_VERSION`](../provenance.md) before reading any one codepoint as
a defect.

The set also contains five **ASCII** characters — `%`, `0`, `1`, `I` and `m`:

```python
assert sorted(c for c in unmapped if c.isascii()) == ["%", "0", "1", "I", "m"]
```

TR39 is a *skeleton* transform: it reduces `m` to `rn`, `I` and `1` to `l`, and `0` to
`O`. Those rows make the five ASCII characters upstream sources. disarm does not apply
them, because folding a legitimate ASCII `m` to `rn` corrupts prose. They are reported
rather than filtered out — a coverage report that quietly drops rows reads as coverage it
does not have — so a scan over ordinary English will report the letter `m`. Filter on
your own threat model at the call site.

## Use cases

### Anti-phishing

Detect domain names that use mixed scripts to impersonate legitimate sites:

```python
from disarm import is_mixed_script, normalize_confusables

# Detect Latin homoglyphs in a "Cyrillic" domain
domain = "аpple.com"  # first "a" is Cyrillic
if is_mixed_script(domain):
    normalized = normalize_confusables(domain)
    print(f"Suspicious: looks like {normalized}")

# Detect Cyrillic homoglyphs injected into Russian text
text = "Банк pоссии"  # Latin 'p' and 'o' instead of Cyrillic
normalized = normalize_confusables(text, target_script="cyrillic")
assert normalized == "Банк россии"
```

### Username validation

Ensure usernames don't contain confusable characters:

```python
from disarm import is_confusable


def validate_username(name: str) -> bool:
    if is_confusable(name):
        raise ValueError("Username contains confusable characters")
    return True
```

### Search normalization

Normalize confusables before indexing for search:

```python
from disarm import TextPipeline

index_pipeline = TextPipeline(
    normalize="NFKC",
    confusables=True,
    fold_case=True,
)
```
