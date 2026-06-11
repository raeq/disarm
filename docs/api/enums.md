# Enums & Types

## Script

```python
from disarm import Script
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
| `Script.TAI_LE` | `"TaiLe"` |
| `Script.NEW_TAI_LUE` | `"NewTaiLue"` |

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
| `Script.NKO` | `"NKo"` |
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
| `Script.CANADIAN_ABORIGINAL` | `"CanadianAboriginal"` |

### Historical European scripts

| Member | Value |
|---|---|
| `Script.RUNIC` | `"Runic"` |
| `Script.OGHAM` | `"Ogham"` |
| `Script.GOTHIC` | `"Gothic"` |

### Ancient Near Eastern scripts

| Member | Value |
|---|---|
| `Script.OLD_PERSIAN` | `"OldPersian"` |
| `Script.CUNEIFORM` | `"Cuneiform"` |
| `Script.LINEAR_B` | `"LinearB"` |

### Meta-scripts

| Member | Value |
|---|---|
| `Script.COMMON` | `"Common"` |
| `Script.INHERITED` | `"Inherited"` |

## NF

```python
from disarm import NF
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
from disarm import EmojiProvider
```

Protocol for custom emoji name providers. Implement this to supply your own emoji-to-text mappings for `demojize()` and `set_emoji_provider()`.

```python
class FrenchEmoji:
    def lookup(self, sequence: list[int]) -> str | None:
        table = {(0x1F600,): "visage souriant"}
        return table.get(tuple(sequence))

from disarm import demojize
demojize("hello 😀", provider=FrenchEmoji())
```

### Required method

| Method | Signature | Description |
|---|---|---|
| `lookup` | `(self, sequence: list[int]) -> str \| None` | Return text name for an emoji codepoint sequence, or `None` if not recognized |

The `sequence` argument is a list of Unicode codepoints forming the emoji (e.g., `[0x1F468, 0x200D, 0x1F469]` for a ZWJ sequence).

## Type aliases

Defined in `disarm._types`:

### ErrorMode

<!--- skip: next -->
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

<!--- skip: next -->
```python
Platform = Literal["universal", "posix", "windows"]
```

Target platform for filename sanitization rules.

### NormalizationForm

<!--- skip: next -->
```python
NormalizationForm = Literal["NFC", "NFD", "NFKC", "NFKD"]
```

Unicode normalization form identifier.

## Language constants

Pre-defined string constants for language codes:

```python
from disarm import LANG_DE, LANG_FR, LANG_ES  # etc.
```

### European

`LANG_BG`, `LANG_CA`, `LANG_CS`, `LANG_CY`, `LANG_DA`, `LANG_DE`, `LANG_EL`, `LANG_ES`, `LANG_ET`, `LANG_FI`, `LANG_FR`, `LANG_GA`, `LANG_HR`, `LANG_HU`, `LANG_IS`, `LANG_IT`, `LANG_LT`, `LANG_LV`, `LANG_MT`, `LANG_NL`, `LANG_NO`, `LANG_PL`, `LANG_PT`, `LANG_RO`, `LANG_RU`, `LANG_SK`, `LANG_SL`, `LANG_SQ`, `LANG_SR`, `LANG_SV`, `LANG_TR`, `LANG_UK`

### Semitic

`LANG_HE`

### Caucasian

`LANG_HY`, `LANG_KA`

### South Asian (Indic)

`LANG_AS`, `LANG_BN`, `LANG_GU`, `LANG_HI`, `LANG_KN`, `LANG_ML`, `LANG_MR`, `LANG_NE`, `LANG_OR`, `LANG_PA`, `LANG_SA`, `LANG_SI`, `LANG_TA`, `LANG_TE`

### Southeast Asian

`LANG_KM`, `LANG_LO`, `LANG_MY`, `LANG_TH`, `LANG_VI`

### Middle Eastern

`LANG_AR`, `LANG_DV`, `LANG_FA`

### East Asian

`LANG_JA`, `LANG_KO`, `LANG_ZH`

### Central/North Asian

`LANG_BO`, `LANG_MN`

### African

`LANG_AM`, `LANG_JV`

### Auto-detection

`LANG_AUTO` — pass as `lang="auto"` to auto-detect the language from the dominant non-Latin script in the input text. See [Language Support](../user-guide/language-support.md#auto-detecting-language-from-script) for the full script-to-language mapping.

## Introspection

```python
from disarm import list_langs, list_scripts

assert list_langs() == ['am', 'ar', 'as', 'ban', 'bax', 'bg', 'bn', 'bo', 'bug', 'ca', 'chr', 'cjm', 'cop', 'cs', 'cy', 'da', 'de', 'dv', 'el', 'es', 'et', 'fa', 'fi', 'fr', 'ga', 'gu', 'he', 'hi', 'hr', 'hu', 'hy', 'is', 'it', 'ja', 'ja-kunrei', 'jv', 'ka', 'khb', 'km', 'kn', 'ko', 'lis', 'lo', 'lt', 'lv', 'ml', 'mn', 'mni', 'mr', 'mt', 'my', 'ne', 'nl', 'no', 'nod', 'nqo', 'or', 'pa', 'pl', 'pt', 'ro', 'ru', 'sa', 'sat', 'si', 'sk', 'sl', 'sq', 'sr', 'su', 'sv', 'syr', 'ta', 'tdd', 'te', 'th', 'tl', 'tr', 'tzm', 'uk', 'vai', 'vi', 'zh']
assert list_scripts() == ['Arabic', 'Armenian', 'Balinese', 'Bamum', 'Bengali', 'Buginese', 'CanadianAboriginal', 'Cham', 'Cherokee', 'Common', 'Coptic', 'Cuneiform', 'Cyrillic', 'Devanagari', 'Ethiopic', 'Georgian', 'Gothic', 'Greek', 'Gujarati', 'Gurmukhi', 'Han', 'Hangul', 'Hebrew', 'Hiragana', 'Inherited', 'Javanese', 'Kannada', 'Katakana', 'Khmer', 'Lao', 'Latin', 'LinearB', 'Lisu', 'Malayalam', 'MeeteiMayek', 'Mongolian', 'Myanmar', 'NKo', 'NewTaiLue', 'Ogham', 'OlChiki', 'OldPersian', 'Oriya', 'Runic', 'Sinhala', 'Sundanese', 'Syriac', 'Tagalog', 'TaiLe', 'TaiTham', 'Tamil', 'Telugu', 'Thaana', 'Thai', 'Tibetan', 'Tifinagh', 'Vai']
```

| Function | Returns |
|---|---|
| `list_langs()` | Sorted list of available language codes (`str`) |
| `list_scripts()` | Sorted list of recognized Script enum values (`str`) |
