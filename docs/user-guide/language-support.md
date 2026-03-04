# Language Support

translit ships with 37 built-in language profiles that provide language-specific transliteration rules. You can also register custom profiles at runtime.

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
| `vi` | Vietnamese | Full diacritical vowel set | Hà Nội → Ha Noi |

### Non-European languages

| Code | Language | Notes |
|---|---|---|
| `ar` | Arabic | Basic transliteration |
| `ja` | Japanese | Hiragana/Katakana → Hepburn; Kanji → Chinese pinyin fallback |
| `ko` | Korean | Hangul → Revised Romanization (algorithmic jamo decomposition) |
| `ru` | Russian | Full Cyrillic → Latin |
| `zh` | Chinese | Hanzi → toneless pinyin (20,924 characters from Unihan kMandarin) |

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
# => ['ar', 'bg', 'ca', 'cs', 'cy', 'da', 'de', 'el', 'es', 'et',
#     'fi', 'fr', 'ga', 'hr', 'hu', 'is', 'it', 'ja', 'ko', 'lt',
#     'lv', 'mt', 'nl', 'no', 'pl', 'pt', 'ro', 'ru', 'sk', 'sl',
#     'sq', 'sr', 'sv', 'tr', 'uk', 'vi', 'zh']
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
