# Language Support

translit ships with a broad set of built-in language profiles and script mappings.
You can also register custom profiles at runtime.

## Coverage tiers

Coverage is wide, but the **quality guarantee differs by tier**. Read this before
choosing a profile for production:

| Tier | Scripts | What you get |
|---|---|---|
| **Core** (best-in-class) | Latin, Cyrillic, Greek | Standards-based romanization — BGN/PCGN (default), ISO 9-style ASCII (`strict_iso9`), GOST R 7.0.34 (`gost7034`) — plus [reverse transliteration](#reverse-transliteration) (ru/uk/el). This is what translit is built to do well. |
| **Compatibility** (best-effort) | CJK (Chinese/Japanese/Korean), Arabic, Hebrew, Devanagari & other Indic scripts, Thai, Lao | Context-free, character-by-character — the same approach as Unidecode/AnyAscii. For these scripts romanization is fundamentally lossy; this tier exists so translit is a complete drop-in, not because it is best-in-class here. |
| **Best-effort** | Georgian, Armenian, and a long tail of additional and historical scripts | Context-free coverage so input is never silently dropped. Approximate romanization for search/display, **not** a scholarly standard. |

For **security/defense** (homoglyph, bidi, zalgo, invisible-character handling), do not
rely on transliteration at all — see [Adversarial-Text Defense](../security/adversarial-defense.md).

## Built-in languages

### European languages

| Code | Language | Key overrides | Example |
|---|---|---|---|
| `bg` | Bulgarian | Ъ→A, Щ→Sht | Ъгъл → Agal |
| `ca` | Catalan | Ç→C, ŀ→l·l | Ça → Ca |
| `cs` | Czech | Č→C, Ř→R, Ž→Z | Říční → Ricni |
| `cy` | Welsh | Ŵ→W, Ŷ→Y | Ŵyr → Wyr |
| `da` | Danish | Æ→Ae, Ø→Oe, Å→Aa | Ærø → Aeroe |
| `de` | German | Ä→Ae, Ö→Oe, Ü→Ue, ß→ss | München → Muenchen |
| `el` | Greek | Full alphabet transliteration | Αθήνα → Athina |
| `es` | Spanish | Ñ→N | España → Espana |
| `et` | Estonian | Õ→O, Š→S, Ž→Z | Õlu → Olu |
| `fi` | Finnish | Ä→A, Ö→O | Ääkkönen → Aakkonen |
| `fr` | French | Ç→C, Œ→OE | Ça → Ca |
| `ga` | Irish | Ḃ→Bh, Ċ→Ch, Ḋ→Dh | Ṁáire → Mhaire |
| `hr` | Croatian | Č→C, Ć→C, Đ→D, Š→S, Ž→Z | Đurđevac → Durdevac |
| `hu` | Hungarian | Ő→O, Ű→U | Győr → Gyor |
| `is` | Icelandic | Ð→Dh, Þ→Th | Ísland → Island |
| `it` | Italian | À→A, È→E | Città → Citta |
| `lt` | Lithuanian | Ą→A, Ę→E, Ė→E, Į→I, Ų→U | Šiauliai → Siauliai |
| `lv` | Latvian | Ā→A, Č→C, Ģ→G, Ķ→K, Ļ→L, Ņ→N | Rīga → Riga |
| `mt` | Maltese | Ċ→C, Ġ→G, Ħ→H, Ż→Z | Għawdex → Ghawdex |
| `nl` | Dutch | IJ→IJ | IJmuiden → IJmuiden |
| `no` | Norwegian | Æ→Ae, Ø→Oe, Å→Aa | Ål → Aal |
| `pl` | Polish | Ą→A, Ć→C, Ę→E, Ł→L, Ń→N, Ó→O, Ś→S, Ź→Z, Ż→Z | Łódź → Lodz |
| `pt` | Portuguese | Ã→A, Õ→O, Ç→C | São Paulo → Sao Paulo |
| `ro` | Romanian | Ă→A, Â→A, Î→I, Ș→S, Ț→T | București → Bucuresti |
| `sk` | Slovak | Ä→A, Č→C, Ď→D, Ľ→L, Ň→N, Ô→O, Ŕ→R, Š→S, Ť→T, Ž→Z | Bratislava |
| `sl` | Slovenian | Č→C, Š→S, Ž→Z | Ljubljana |
| `sq` | Albanian | Ç→C, Ë→E | Shqipëria → Shqiperia |
| `sr` | Serbian | Full Cyrillic→Latin | Београд → Beograd |
| `sv` | Swedish | Ä→Ae, Ö→Oe, Å→Aa | Malmö → Malmoe |
| `tr` | Turkish | Ç→C, Ğ→G, İ→I, Ö→O, Ş→S, Ü→U | İstanbul → Istanbul |
| `uk` | Ukrainian | Г→H, Ґ→G, Є→Ye, Ї→Yi, І→I | Київ → Kyiv |

### Southeast Asian languages

| Code | Language | Key overrides | Example |
|---|---|---|---|
| `vi` | Vietnamese | Full diacritical vowel set | Hà Nội → Ha Noi |

### Semitic languages

| Code | Language | Notes |
|---|---|---|
| `ar` | Arabic | Basic transliteration (Buckwalter-derived) |
| `he` | Hebrew | Common Israeli romanization; Qof → q (SBL); presentation forms with dagesh |

### Iranian languages

| Code | Language | Notes |
|---|---|---|
| `fa` | Persian (Farsi) | UNGEGN-based romanization; ث→s, ذ→z, ض→z, ظ→z (Persian pronunciation) |

### Other Middle Eastern languages

| Code | Language | Script | Notes |
|---|---|---|---|
| `cop` | Coptic | Coptic | Coptic scholarly romanization |
| `syr` | Syriac | Syriac | Syriac script transliteration |

### Ethiopic languages

| Code | Language | Script | Notes |
|---|---|---|---|
| `am` | Amharic | Ethiopic | Syllable-based transliteration |

### African languages

| Code | Language | Script | Notes |
|---|---|---|---|
| `bax` | Bamum | Bamum | Bamum syllabary transliteration |
| `nqo` | N'Ko | N'Ko | Manding languages (N'Ko script) |
| `tzm` | Tamazight (Berber) | Tifinagh | Neo-Tifinagh script transliteration |
| `vai` | Vai | Vai | Vai syllabary transliteration |

### Caucasian languages

| Code | Language | Notes |
|---|---|---|
| `hy` | Armenian | BGN/PCGN romanization |
| `ka` | Georgian | National romanization |

### Indic languages

| Code | Language | Script | Example |
|---|---|---|---|
| `as` | Assamese | Bengali | — |
| `bn` | Bengali | Bengali | কলকাতা → kalakata |
| `gu` | Gujarati | Gujarati | ગુજરાતી → gujarati |
| `hi` | Hindi | Devanagari | नमस्ते → namaste |
| `kn` | Kannada | Kannada | ಕನ್ನಡ → kannada |
| `ml` | Malayalam | Malayalam | മലയാളം → malayalam |
| `mni` | Meitei | Meetei Mayek | Meetei Mayek script transliteration |
| `mr` | Marathi | Devanagari | — |
| `ne` | Nepali | Devanagari | — |
| `or` | Odia | Odia | ଓଡ଼ିଆ → odia |
| `pa` | Punjabi | Gurmukhi | ਗੁਰਮੁਖੀ → gurmukhi |
| `sa` | Sanskrit | Devanagari | — |
| `sat` | Santali | Ol Chiki | Ol Chiki script transliteration |
| `si` | Sinhala | Sinhala | සිංහල → simhala |
| `ta` | Tamil | Tamil | தமிழ் → tamizh |
| `te` | Telugu | Telugu | తెలుగు → telugu |

All 10 Brahmic scripts use virama/mātrā-aware transliteration: consonants carry an inherent "a" that is suppressed by virama (halant) or replaced by dependent vowel marks.

### Tibetan languages

| Code | Language | Script | Notes |
|---|---|---|---|
| `bo` | Tibetan | Tibetan | Indic-phonetic romanization (Hunterian-style aspiration markers; not Wylie) |

### Southeast Asian languages

| Code | Language | Script | Example |
|---|---|---|---|
| `ban` | Balinese | Balinese | Balinese script transliteration |
| `bug` | Buginese | Lontara | Lontara syllabary transliteration |
| `cjm` | Cham | Cham | Cham script transliteration |
| `khb` | Tai Lue | New Tai Lue | New Tai Lue script transliteration |
| `km` | Khmer | Khmer | ភាសាខ្មែរ → phasakhmaer |
| `lo` | Lao | Lao | ລາວ → lao |
| `my` | Myanmar (Burmese) | Myanmar | မြန်မာ → mrannma |
| `nod` | Northern Thai | Tai Tham (Lanna) | Tai Tham script transliteration |
| `su` | Sundanese | Sundanese | Sundanese script transliteration |
| `tdd` | Tai Le | Tai Le | Tai Le script transliteration |
| `th` | Thai | Thai | สวัสดี → sawatdi |

### Philippine languages

| Code | Language | Script | Notes |
|---|---|---|---|
| `tl` | Tagalog | Baybayin (Tagalog) | Baybayin script transliteration |

### Americas

| Code | Language | Script | Notes |
|---|---|---|---|
| `chr` | Cherokee | Cherokee | Cherokee syllabary transliteration |

### Lisu

| Code | Language | Script | Notes |
|---|---|---|---|
| `lis` | Lisu | Fraser script | Fraser/Lisu script transliteration |

### East Asian & other non-European languages

| Code | Language | Notes |
|---|---|---|
| `ja` | Japanese | Hiragana/Katakana → Hepburn; Kanji → Chinese pinyin fallback |
| `ja-kunrei` | Japanese (Kunrei-shiki) | し→si, ち→ti, つ→tu, ふ→hu; use for ISO/TR 11941 |
| `ko` | Korean | Hangul → Revised Romanization (algorithmic jamo decomposition) |
| `ru` | Russian | Full Cyrillic → Latin |
| `zh` | Chinese | Hanzi → toneless pinyin (20,924 characters from Unihan kMandarin) |

> **Toned pinyin**: Pass `tones=True` to `transliterate()` for diacritical pinyin output (e.g., `"běi jīng"` instead of `"bei jing"`). Coverage includes the ~2,000 most common characters.

### CJK examples

```python
from translit import transliterate, slugify

# Chinese
transliterate("北京市")             # => "bei jing shi"
slugify("北京烤鸭")                # => "bei-jing-kao-ya"

# Korean
transliterate("서울")               # => "seo ul"
slugify("대한민국")                # => "dae-han-min-gug"

# Japanese (hiragana/katakana use Hepburn; kanji use Chinese pinyin)
transliterate("ひらがな")           # => "hiragana"
transliterate("東京タワー")         # => "dong jing tawa-"
transliterate("東京タワー", lang="ja")  # => "dong jing tawa" (ー dropped)
```

## Reverse transliteration

translit can convert romanized Latin text back to native script for selected languages using the `target` parameter:

```python
from translit import transliterate, reverse_langs

transliterate("Moskva", target="ru")    # → "Москва"
transliterate("Kyiv", target="uk")      # → "Київ" (approximate)
transliterate("Athina", target="el")    # → "Αθηνα"

# List supported languages
reverse_langs()                         # → ["el", "ru", "uk"]
```

Reverse transliteration uses greedy longest-match scanning to handle digraphs and trigraphs (e.g., `"shch"` → `щ`). See [Limitations](../limitations.md#reverse-transliteration-is-approximate) for round-trip degradation details.

## Auto-detecting language from script

When you don't know the language of the input text, pass `lang="auto"` to automatically detect the dominant non-Latin script and select the appropriate language profile:

```python
from translit import transliterate, slugify, LANG_AUTO

# Detects Cyrillic → uses Russian ("ru") profile
transliterate("Москва", lang="auto")         # => "Moskva"

# Detects Thai → uses Thai ("th") profile
transliterate("ภาษาไทย", lang="auto")         # => Thai transliteration

# Detects Devanagari → uses Hindi ("hi") profile
transliterate("नमस्ते", lang="auto")           # => "namaste"

# Detects Hangul → uses Korean ("ko") profile
slugify("한국어", lang="auto")                 # => Korean romanization slug

# Works with all call sites
from translit import TextPipeline, Slugifier

pipe = TextPipeline(transliterate=True, lang="auto")
pipe("こんにちは")    # => Japanese transliteration

s = Slugifier(lang="auto")
s("東京タワー")      # => CJK slug
```

### How auto-detection works

1. Scans the input for the first non-Latin, non-Common character
2. For ambiguous scripts, scans for exclusive discriminator characters
3. Maps the detected script (and discriminated language) to a language code
4. Falls back to default (no language override) if the text is Latin-only or the script has no mapping

For a detailed walkthrough of the three-stage detection pipeline, discriminator
tables, and fail-safe guarantees, see [Language Detection](language-detection.md).

### Script-to-language mapping

For **unambiguous scripts** (one script = one language), detection is immediate:

| Script | Default language |
|---|---|
| Georgian | `ka` |
| Armenian | `hy` |
| Thai | `th` |
| Hangul | `ko` |
| Hiragana / Katakana | `ja` |
| Greek | `el` |
| Thaana | `dv` (Dhivehi) |
| Bengali, Tamil, Telugu, Kannada, Malayalam, Gujarati, Gurmukhi, Odia, Sinhala | respective language |
| Ethiopic, Tibetan, Lao, Myanmar, Khmer, Mongolian, Javanese, Hebrew | respective language |
| Balinese | `ban` |
| Bamum | `bax` |
| Buginese (Lontara) | `bug` |
| Cham | `cjm` |
| Cherokee | `chr` |
| Coptic | `cop` |
| Lisu (Fraser) | `lis` |
| Meetei Mayek | `mni` |
| N'Ko | `nqo` |
| New Tai Lue | `khb` |
| Ol Chiki | `sat` |
| Sundanese | `su` |
| Syriac | `syr` |
| Tagalog (Baybayin) | `tl` |
| Tai Le | `tdd` |
| Tai Tham (Lanna) | `nod` |
| Tifinagh | `tzm` |
| Vai | `vai` |

### Character-level discrimination for ambiguous scripts

For scripts shared by multiple languages, translit scans for **exclusive characters** — codepoints that appear in exactly one language's alphabet among the profiles we support:

| Script | Exclusive characters | Detected language |
|---|---|---|
| Cyrillic | ґ Ґ ї Ї є Є і І | `uk` (Ukrainian) |
| Cyrillic | ђ Ђ ћ Ћ љ Љ њ Њ џ Џ ј Ј | `sr` (Serbian) |
| Cyrillic | ө Ө ү Ү | `mn` (Mongolian) |
| Arabic | پ چ ژ گ | `fa` (Persian) |
| Latin | ơ Ơ ư Ư | `vi` (Vietnamese) |
| Latin | İ ı | `tr` (Turkish) |
| Latin | ß ẞ | `de` (German) |

If **no** exclusive characters are found, the script default is used (Cyrillic → `ru`, Arabic → `ar`, Latin → no override). If exclusive characters from **two different languages** appear in the same text (e.g., Ukrainian ї and Serbian ћ), detection falls back to the script default — this is the fail-safe guarantee.

```python
# Ukrainian detected by exclusive ї
transliterate("Київ", lang="auto")   # → uses uk profile

# Persian detected by exclusive پ
transliterate("پارسی", lang="auto")  # → uses fa profile

# German detected by ß
transliterate("Straße", lang="auto") # → uses de profile

# No exclusive chars → safe default
transliterate("Москва", lang="auto") # → uses ru (unchanged)
```

For scripts that remain ambiguous after discrimination (Devanagari, Han), pass an explicit language code when accuracy matters.

!!! tip
    Use the `LANG_AUTO` constant for type safety:
    ```python
    from translit import LANG_AUTO, transliterate
    transliterate("Москва", lang=LANG_AUTO)
    ```

## Using language profiles

### With functions

```python
from translit import transliterate, slugify, sanitize_filename

transliterate("Ürümqi", lang="de")         # => "Ueruemqi"
slugify("Ärger im Büro", lang="de")        # => "aerger-im-buero"
sanitize_filename("Ärger.txt", lang="de")  # => "Aerger.txt"
```

### With classes

```python
from translit import Slugifier, TextPipeline

slug = Slugifier(lang="de", separator="_")
pipe = TextPipeline(transliterate=True, lang="fr")
```

### Language constants

Pre-defined constants for type safety:

```python
from translit import LANG_DE, LANG_FR, transliterate

transliterate("Ä", lang=LANG_DE)  # => "Ae"
transliterate("Ç", lang=LANG_FR)  # => "C"
```

## Listing available languages

```python
from translit import list_langs

print(list_langs())
# => ['am', 'ar', 'as', 'bg', 'bn', 'bo', 'ca', 'cs', 'cy', 'da', 'de', 'dv', 'el',
#     'es', 'et', 'fa', 'fi', 'fr', 'ga', 'gu', 'he', 'hi', 'hr', 'hu', 'hy',
#     'is', 'it', 'ja', 'jv', 'ka', 'km', 'kn', 'ko', 'lo', 'lt', 'lv', 'ml', 'mn',
#     'mr', 'mt', 'my', 'ne', 'nl', 'no', 'or', 'pa', 'pl', 'pt', 'ro', 'ru', 'sa',
#     'si', 'sk', 'sl', 'sq', 'sr', 'sv', 'ta', 'te', 'th', 'tr', 'uk', 'vi', 'zh']
```

## Custom language profiles

### register_lang

Register a new language profile or override an existing one:

```python
from translit import register_lang, transliterate

# Register Esperanto
register_lang("eo", {
    "ĉ": "cx",
    "ĝ": "gx",
    "ĥ": "hx",
    "ĵ": "jx",
    "ŝ": "sx",
    "ŭ": "ux",
})

transliterate("ĉapelo", lang="eo")  # => "cxapelo"
```

!!! warning
    `register_lang()` is a global operation. Registered profiles persist for the lifetime of the Python process. They are not thread-local.

### register_replacements

Register global pre-transliteration string replacements:

```python
from translit import register_replacements, transliterate

register_replacements({
    "©": "(c)",
    "®": "(R)",
    "™": "(TM)",
})

transliterate("Hello™ World©")  # => "Hello(TM) World(c)"
```

## Norwegian variants

Both `"no"` and `"nb"` (Bokmål) map to the same Norwegian profile. `"nn"` (Nynorsk) also uses the same mappings. Use any of these codes interchangeably.

## Historical and ancient scripts (best-effort tier)

These belong to the **best-effort** coverage tier: included so input is never silently
dropped, not maintained as a focus area. translit includes transliteration mappings for
several historical and ancient writing systems:

| Script | Unicode Block | Example |
|---|---|---|
| Runic (Elder/Younger Futhark) | U+16A0–U+16FF | ᚠᚢᚦᚨᚱᚲ → futhark |
| Ogham | U+1680–U+169F | ᚑᚌᚐᚋ → ogam |
| Gothic | U+10330–U+1034F | 𐌲𐌿𐍄 → gut |
| Old Persian Cuneiform | U+103A0–U+103D5 | 𐎠𐎭𐎶 → adama |
| Linear B Syllabary | U+10000–U+1007F | 𐀀𐀁𐀂 → aei |
| Cherokee | U+13A0–U+13FF | ᏣᎳᎩ → tsalagi |
| Canadian Aboriginal Syllabics | U+1400–U+167F | ᐃᓄᒃᑎᑐᑦ → inoktwetwiit |
| Mongolian | U+1800–U+18AF | ᠮᠣᠩᠭᠣᠯ → monggol |

These mappings provide approximate romanizations suitable for search indexing and display purposes. They are not intended as scholarly transliteration standards.
