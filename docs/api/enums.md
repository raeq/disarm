# Enums & Types

## Script

```python
from translit import Script
```

Enum of Unicode script identifiers returned by `detect_scripts()`.

| Member | Value |
|---|---|
| `Script.LATIN` | `"Latin"` |
| `Script.CYRILLIC` | `"Cyrillic"` |
| `Script.GREEK` | `"Greek"` |
| `Script.ARABIC` | `"Arabic"` |
| `Script.HEBREW` | `"Hebrew"` |
| `Script.DEVANAGARI` | `"Devanagari"` |
| `Script.HAN` | `"Han"` |
| `Script.HIRAGANA` | `"Hiragana"` |
| `Script.KATAKANA` | `"Katakana"` |
| `Script.HANGUL` | `"Hangul"` |
| `Script.THAI` | `"Thai"` |
| `Script.GEORGIAN` | `"Georgian"` |
| `Script.ARMENIAN` | `"Armenian"` |
| `Script.ETHIOPIC` | `"Ethiopic"` |
| `Script.BENGALI` | `"Bengali"` |
| `Script.TAMIL` | `"Tamil"` |
| `Script.TELUGU` | `"Telugu"` |
| `Script.KANNADA` | `"Kannada"` |
| `Script.MALAYALAM` | `"Malayalam"` |
| `Script.GUJARATI` | `"Gujarati"` |
| `Script.GURMUKHI` | `"Gurmukhi"` |
| `Script.TIBETAN` | `"Tibetan"` |
| `Script.MYANMAR` | `"Myanmar"` |
| `Script.KHMER` | `"Khmer"` |
| `Script.LAO` | `"Lao"` |
| `Script.SINHALA` | `"Sinhala"` |
| `Script.COMMON` | `"Common"` |
| `Script.INHERITED` | `"Inherited"` |

## NF

```python
from translit import NF
```

Enum of Unicode normalization forms.

| Member | Value | Description |
|---|---|---|
| `NF.C` | `"NFC"` | Canonical Decomposition + Composition |
| `NF.D` | `"NFD"` | Canonical Decomposition |
| `NF.KC` | `"NFKC"` | Compatibility Decomposition + Composition |
| `NF.KD` | `"NFKD"` | Compatibility Decomposition |

## Type aliases

Defined in `translit._types`:

### ErrorMode

```python
ErrorMode = Literal["replace", "ignore", "preserve"]
```

Controls behavior when a character has no transliteration mapping.

| Value | Behavior |
|---|---|
| `"replace"` | Substitute with `replace_with` string |
| `"ignore"` | Silently drop the character |
| `"preserve"` | Keep the original character unchanged |

### Platform

```python
Platform = Literal["universal", "posix", "windows"]
```

Target platform for filename sanitization rules.

### NormalizationForm

```python
NormalizationForm = Literal["NFC", "NFD", "NFKC", "NFKD"]
```

Unicode normalization form identifier.

## Language constants

Pre-defined string constants for language codes:

```python
from translit import LANG_DE, LANG_FR, LANG_ES  # etc.
```

### European

`LANG_BG`, `LANG_CA`, `LANG_CS`, `LANG_CY`, `LANG_DA`, `LANG_DE`, `LANG_EL`, `LANG_ES`, `LANG_ET`, `LANG_FI`, `LANG_FR`, `LANG_GA`, `LANG_HR`, `LANG_HU`, `LANG_IS`, `LANG_IT`, `LANG_LT`, `LANG_LV`, `LANG_MT`, `LANG_NL`, `LANG_NO`, `LANG_PL`, `LANG_PT`, `LANG_RO`, `LANG_SK`, `LANG_SL`, `LANG_SQ`, `LANG_SR`, `LANG_SV`, `LANG_TR`, `LANG_UK`, `LANG_VI`

### Non-European

`LANG_AR`, `LANG_JA`, `LANG_KO`, `LANG_RU`, `LANG_ZH`
