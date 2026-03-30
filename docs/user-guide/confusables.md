# Confusable Detection

Unicode confusables (homoglyphs) are characters from different scripts that look visually identical or very similar. For example, Cyrillic "а" (U+0430) looks like Latin "a" (U+0061). Attackers exploit this for phishing, impersonation, and spoofing.

translit implements Unicode TR39 confusable detection and normalization with multi-target script support, auto-generated from the official [Unicode TR39 confusables.txt](https://www.unicode.org/Public/security/latest/confusables.txt) (version 17.0.0). The tables cover Cyrillic, Greek, Armenian, Georgian, CJK compatibility, mathematical symbols, fullwidth forms, and other visually confusable characters. Mappings are based on visual similarity, not phonetic equivalence.

## Detecting confusables

```python
from translit import is_confusable, is_mixed_script

# Cyrillic Н looks like Latin H
is_confusable("Неllo")              # => True
is_mixed_script("Неllo")            # => True

# Pure Latin — no confusables
is_confusable("Hello")              # => False
is_mixed_script("Hello")            # => False
```

## Normalizing confusables

Replace confusable characters with their target-script equivalents:

```python
from translit import normalize_confusables

# Cyrillic а, е, о → Latin a, e, o
normalize_confusables("Неllo Wоrld")    # => "Hello World"

# Greek omicron → Latin o
normalize_confusables("Ηellο")          # => "Hello"
```

### Target script

By default, confusables are normalized to Latin. You can specify a different target script to normalize *towards* that script instead:

```python
# Normalize to Latin (default) — non-Latin homoglyphs → Latin
normalize_confusables("раypal")                            # → "paypal"

# Normalize to Cyrillic — non-Cyrillic homoglyphs → Cyrillic
normalize_confusables("paypal", target_script="cyrillic")  # → "раураl"
```

### Supported target scripts

| Target | Mappings | Description |
|--------|----------|-------------|
| `"latin"` (default) | ~2,063 | Non-Latin → Latin. Cyrillic а→a, Greek Ρ→P, etc. |
| `"cyrillic"` | ~1,369 | Non-Cyrillic → Cyrillic. Latin A→А, p→р, etc. |

Characters without a confusable equivalent in the target script pass through unchanged. This is pure visual mapping — not transliteration. Latin `f` has no Cyrillic lookalike, so it stays as `f`.

## Script detection

Identify which Unicode scripts are present in a string:

```python
from translit import detect_scripts, Script

scripts = detect_scripts("Hello Мир")
# => [Script.LATIN, Script.CYRILLIC]

scripts = detect_scripts("東京 Tokyo")
# => [Script.HAN, Script.LATIN]
```

### The Script enum

`Script` enumerates the 39 Unicode scripts translit recognizes:

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
from translit import is_mixed_script, normalize_confusables

# Detect Latin homoglyphs in a "Cyrillic" domain
domain = "аpple.com"  # first "a" is Cyrillic
if is_mixed_script(domain):
    normalized = normalize_confusables(domain)
    print(f"Suspicious: looks like {normalized}")

# Detect Cyrillic homoglyphs injected into Russian text
text = "Банк pоссии"  # Latin 'p' and 'o' instead of Cyrillic
normalized = normalize_confusables(text, target_script="cyrillic")
# → "Банк россии" (Latin homoglyphs replaced with Cyrillic)
```

### Username validation

Ensure usernames don't contain confusable characters:

```python
from translit import is_confusable

def validate_username(name: str) -> bool:
    if is_confusable(name):
        raise ValueError("Username contains confusable characters")
    return True
```

### Search normalization

Normalize confusables before indexing for search:

```python
from translit import TextPipeline

index_pipeline = TextPipeline(
    normalize="NFKC",
    confusables=True,
    fold_case=True,
)
```
