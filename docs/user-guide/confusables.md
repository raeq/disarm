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
    # Cyrillic а, е, о → Latin a, e, o
    Disarm.normalize_confusables("Неllo Wоrld")   # => "Hello World"

    # Greek omicron → Latin o
    Disarm.normalize_confusables("Ηellο")         # => "Hello"
    ```

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
    # Normalize to Latin (default) — non-Latin homoglyphs → Latin
    Disarm.normalize_confusables("раypal")                       # => "paypal"

    # Normalize to Cyrillic — non-Cyrillic homoglyphs → Cyrillic
    Disarm.normalize_confusables("paypal", target: :cyrillic)    # => "раураӏ"
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

    api::detect_scripts("Hello Мир");   // => [Script::Latin, Script::Cyrillic]
    api::detect_scripts("東京 Tokyo");    // => [Script::Han, Script::Latin]
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
