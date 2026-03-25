# Enums & Types

## Script

```python
from translit import Script
```

Enum of Unicode script identifiers returned by `detect_scripts()`.

### Major world scripts

| Member | Value |
|---|---|
| `Script.LATIN` | `"Latin"` |
| `Script.CYRILLIC` | `"Cyrillic"` |
| `Script.GREEK` | `"Greek"` |
| `Script.ARABIC` | `"Arabic"` |
| `Script.HEBREW` | `"Hebrew"` |

### Indic scripts

| Member | Value |
|---|---|
| `Script.DEVANAGARI` | `"Devanagari"` |
| `Script.BENGALI` | `"Bengali"` |
| `Script.GURMUKHI` | `"Gurmukhi"` |
| `Script.GUJARATI` | `"Gujarati"` |
| `Script.ORIYA` | `"Oriya"` |
| `Script.TAMIL` | `"Tamil"` |
| `Script.TELUGU` | `"Telugu"` |
| `Script.KANNADA` | `"Kannada"` |
| `Script.MALAYALAM` | `"Malayalam"` |
| `Script.SINHALA` | `"Sinhala"` |

### East Asian scripts

| Member | Value |
|---|---|
| `Script.HAN` | `"Han"` |
| `Script.HIRAGANA` | `"Hiragana"` |
| `Script.KATAKANA` | `"Katakana"` |
| `Script.HANGUL` | `"Hangul"` |

### Southeast Asian scripts

| Member | Value |
|---|---|
| `Script.THAI` | `"Thai"` |
| `Script.LAO` | `"Lao"` |
| `Script.MYANMAR` | `"Myanmar"` |
| `Script.KHMER` | `"Khmer"` |
| `Script.BALINESE` | `"Balinese"` |
| `Script.JAVANESE` | `"Javanese"` |
| `Script.TAI_LE` | `"Tai_Le"` |
| `Script.NEW_TAI_LUE` | `"New_Tai_Lue"` |

### Central/North Asian scripts

| Member | Value |
|---|---|
| `Script.TIBETAN` | `"Tibetan"` |
| `Script.MONGOLIAN` | `"Mongolian"` |

### Caucasian scripts

| Member | Value |
|---|---|
| `Script.GEORGIAN` | `"Georgian"` |
| `Script.ARMENIAN` | `"Armenian"` |

### African scripts

| Member | Value |
|---|---|
| `Script.ETHIOPIC` | `"Ethiopic"` |
| `Script.NKO` | `"Nko"` |
| `Script.VAI` | `"Vai"` |

### Middle Eastern scripts

| Member | Value |
|---|---|
| `Script.SYRIAC` | `"Syriac"` |
| `Script.THAANA` | `"Thaana"` |
| `Script.COPTIC` | `"Coptic"` |

### Americas

| Member | Value |
|---|---|
| `Script.CHEROKEE` | `"Cherokee"` |
| `Script.CANADIAN_ABORIGINAL` | `"Canadian_Aboriginal"` |

### Historical European scripts

| Member | Value |
|---|---|
| `Script.RUNIC` | `"Runic"` |
| `Script.OGHAM` | `"Ogham"` |

### Meta-scripts

| Member | Value |
|---|---|
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

## EmojiProvider

```python
from translit import EmojiProvider
```

Protocol for custom emoji name providers. Implement this to supply your own emoji-to-text mappings for `demojize()` and `set_emoji_provider()`.

```python
class FrenchEmoji:
    def lookup(self, sequence: list[int]) -> str | None:
        table = {(0x1F600,): "visage souriant"}
        return table.get(tuple(sequence))

from translit import demojize
demojize("hello 😀", provider=FrenchEmoji())
```

### Required method

| Method | Signature | Description |
|---|---|---|
| `lookup` | `(self, sequence: list[int]) -> str \| None` | Return text name for an emoji codepoint sequence, or `None` if not recognized |

The `sequence` argument is a list of Unicode codepoints forming the emoji (e.g., `[0x1F468, 0x200D, 0x1F469]` for a ZWJ sequence).

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

### Auto-detection

`LANG_AUTO` — pass as `lang="auto"` to auto-detect the language from the dominant non-Latin script in the input text. See [Language Support](../user-guide/language-support.md#auto-detecting-language-from-script) for the full script-to-language mapping.
