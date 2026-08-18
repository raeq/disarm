# Confusable Detection

Unicode confusables (homoglyphs) are characters from different scripts that look visually identical or very similar. For example, Cyrillic "а" (U+0430) looks like Latin "a" (U+0061). Attackers exploit this for phishing, impersonation, and spoofing.

disarm implements Unicode TR39 confusable detection and normalization with multi-target script support, auto-generated from the official [Unicode TR39 confusables.txt](https://www.unicode.org/Public/security/latest/confusables.txt) (version 17.0.0). The tables cover Cyrillic, Greek, Armenian, Georgian, CJK compatibility, mathematical symbols, fullwidth forms, and other visually confusable characters. Mappings are based on visual similarity, not phonetic equivalence.

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
    assert normalize_confusables("Неllo Wоrld") == 'Hello World'

    # Greek omicron → Latin o
    assert normalize_confusables("Ηellο") == 'Hello'
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
assert strip_obfuscation("pаypаl") == "paypal"          # same recovery
assert strip_obfuscation("José Martínez") == "Jose Martinez"   # different fidelity
```

Neither is wrong; they answer different questions. Accent destruction is a property of
the bundle, not of confusable mapping. See
[what each entry point costs you](../security/adversarial-defense.md#what-each-entry-point-costs-you)
for the full threat-model-to-entry-point table.

### Target script

By default, confusables are normalized to Latin. You can specify a different target script to normalize *towards* that script instead:

=== "Python"

    ```python
    # Normalize to Latin (default) — non-Latin homoglyphs → Latin
    assert normalize_confusables("раypal") == 'paypal'

    # Normalize to Cyrillic — non-Cyrillic homoglyphs → Cyrillic
    assert normalize_confusables("paypal", target_script="cyrillic") == 'раураӏ'
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
| `"latin"` (default) | ~2,063 | Non-Latin → Latin. Cyrillic а→a, Greek Ρ→P, etc. |
| `"cyrillic"` | ~1,369 | Non-Cyrillic → Cyrillic. Latin A→А, p→р, etc. |

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
assert normalize_confusables("\u0456\u0308") == "i"    # і + ◌̈ composes to ї, which folds
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
assert normalized == 'Банк россии'
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
