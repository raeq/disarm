# Transliteration

Transliteration converts Unicode text to ASCII by replacing each character with its closest ASCII equivalent. translit uses hand-curated lookup tables with support for 83 language-specific override profiles.

## Basic usage

```python
from translit import transliterate

transliterate("café")                # => "cafe"
transliterate("naïve")               # => "naive"
transliterate("Москва")             # => "Moskva"
```

## Language profiles

When a `lang` parameter is provided, language-specific mapping overrides apply before the default table:

```python
# German
transliterate("Ärger über Ölförderung", lang="de")
# => "Aerger ueber Oelfoerderung"

# Without lang — default mapping
transliterate("Ärger über Ölförderung")
# => "Arger uber Olforderung"

# Norwegian
transliterate("Ål i Ørsta", lang="no")
# => "Aal i Oersta"

# Swedish
transliterate("Malmö Ängby", lang="sv")
# => "Malmoe Aengby"

# Turkish
transliterate("İstanbul çağı", lang="tr")
# => "Istanbul cagi"
```

### Auto-detecting the language

When the source language is unknown, `lang="auto"` detects the dominant non-Latin script and selects the appropriate language profile automatically:

```python
transliterate("Москва", lang="auto")          # => "Moskva" (Cyrillic → Russian)
transliterate("ภาษาไทย", lang="auto")          # => Thai transliteration
transliterate("café", lang="auto")             # => "cafe" (Latin-only → default table)
transliterate("Hello Москва", lang="auto")     # => "Hello Moskva" (first non-Latin script wins)
```

For ambiguous scripts like Cyrillic (shared by Russian, Ukrainian, Bulgarian, etc.), auto-detection uses a default (Russian for Cyrillic). Pass an explicit code when the language is known.

### How overrides work

The transliteration pipeline for each character:

1. **Language-specific table** — checked first if `lang` is set
2. **Default table** — comprehensive Unicode → ASCII mappings
3. **Error mode** — applied if no mapping exists

This means most characters use the default table. Language overrides only change characters where a specific language has different conventions (e.g., German ü→ue vs default ü→u).

## Error modes

The `errors` parameter controls what happens when a character has no transliteration mapping:

=== "replace (default)"

    ```python
    transliterate("text ♠ here", errors="replace")
    # => "text [?] here"

    transliterate("text ♠ here", errors="replace", replace_with="")
    # => "text  here"

    transliterate("text ♠ here", errors="replace", replace_with="?")
    # => "text ? here"
    ```

=== "ignore"

    ```python
    transliterate("text ♠ here", errors="ignore")
    # => "text  here"
    ```

=== "preserve"

    ```python
    transliterate("text ♠ here", errors="preserve")
    # => "text ♠ here"
    ```

## Coverage

### Latin scripts

Full coverage of:

- **Latin-1 Supplement** (U+00C0–U+00FF) — À through ÿ
- **Latin Extended-A** (U+0100–U+017F) — all 128 characters (Ā, ă, Ą, ć, Č, đ, ē, ğ, ħ, ĩ, ĳ, ĸ, ľ, ł, ń, ŋ, ō, œ, ř, ś, š, ţ, ŧ, ũ, ű, ŵ, ŷ, ź, ž)
- **Latin Extended-B** (U+0180–U+024F) — Romanian Ș/Ț, Vietnamese Ơ/Ư, digraphs DZ/LJ/NJ
- **Latin Extended Additional** (U+1E00–U+1EFF) — full Vietnamese vowel set (96 chars), Welsh Ŵ/Ŷ, Irish dot-above consonants

### Non-Latin scripts

- **Greek** (Α–ω) — full alphabet
- **Cyrillic** (А–я plus extended) — Russian, Ukrainian, Bulgarian, Serbian/Macedonian, Belarusian
- **CJK** — Chinese (Hanzi → Pinyin, 20,924 characters), Japanese (Hiragana/Katakana → Hepburn romaji; Kanji via Chinese pinyin fallback), Korean (Hangul → Revised Romanization, algorithmic)
- **Arabic, Hebrew, Devanagari, Thai** — basic transliteration

### CJK transliteration

Chinese characters are mapped to toneless pinyin from the Unicode Unihan database:

```python
transliterate("北京市")       # → "bei jing shi"
transliterate("中国人民")     # → "zhong guo ren min"
slugify("北京烤鸭")          # → "bei-jing-kao-ya"
```

Korean Hangul syllables are decomposed algorithmically into jamo components and romanized using the Revised Romanization standard:

```python
transliterate("서울")         # → "seo ul"
transliterate("대한민국")     # → "dae han min gug"
slugify("대한민국")          # → "dae-han-min-gug"
```

Japanese hiragana and katakana use Modified Hepburn romanization. Kanji (shared with Chinese) fall back to Chinese pinyin readings:

```python
transliterate("ひらがな")     # → "hiragana"
transliterate("カタカナ")     # → "katakana"
transliterate("東京タワー")   # → "dong jing tawa-"
```

See [Limitations](../limitations.md) for details on context-free mapping trade-offs.

## Reverse transliteration

The `target` parameter converts romanized Latin text **back** to a native script:

```python
from translit import transliterate, reverse_langs

# Latin → Cyrillic
transliterate("Moskva", target="ru")     # → "Москва"
transliterate("Kyiv", target="uk")       # → "Київ" (approximate)

# Latin → Greek
transliterate("Athina", target="el")     # → "Αθηνα"

# List supported target languages
reverse_langs()                          # → ["el", "ru", "uk"]
```

The `target` parameter is **mutually exclusive** with `lang` — you are either going forward (Unicode → ASCII via `lang`) or backward (Latin → native via `target`), not both. Forward-only parameters (`errors`, `replace_with`, `strict_iso9`, `gost7034`, `tones`) raise `ValueError` when used with `target`.

Reverse transliteration uses greedy longest-match scanning to handle digraphs and trigraphs correctly (e.g., `"shch"` → `щ` rather than `ш` + `ch`).

!!! warning
    Reverse transliteration is **approximate**, not lossless. Many-to-one forward mappings cannot be inverted (e.g., both Й and Ы → `Y`; reverse always picks one). See [Limitations](../limitations.md#reverse-transliteration-is-approximate) for details and round-trip examples.

### Symbols and punctuation

- **Currencies**: € → EUR, £ → GBP, ¥ → JPY, ¢ → c, ₣ → Fr, ₤ → L, ₧ → Pts, ₨ → Rs, ₩ → W, ₫ → d, ₱ → P, ₴ → UAH, ₹ → Rs, ₺ → TL, ₽ → RUB, ₿ → BTC, ฿ → B
- **Typography**: « → `<<`, » → `>>`, „ → `"`, ‰ → o/oo, © → (c), ® → (R), ™ → TM, † → +, ‡ → ++, • → *, … → ..., – → -, — → -, ‹ → <, › → >
- **Mathematical**: × → x, ÷ → /, ± → +-
- **Vulgar fractions**: ¼ → 1/4, ½ → 1/2, ¾ → 3/4, ⅓ → 1/3, ⅔ → 2/3, ⅕ → 1/5, ⅖ → 2/5, ⅗ → 3/5, ⅘ → 4/5, ⅙ → 1/6, ⅚ → 5/6, ⅐ → 1/7, ⅛ → 1/8, ⅜ → 3/8, ⅝ → 5/8, ⅞ → 7/8, ⅑ → 1/9, ⅒ → 1/10
- **Superscripts**: ⁰–⁹ → 0–9, ⁺ → +, ⁻ → -, ⁼ → =, ⁽ → (, ⁾ → )

## Drop-in replacement

`translit.unidecode()` is a direct alias for `transliterate()` with default settings:

```python
from translit import unidecode

unidecode("café")  # => "cafe"
```

See [Migrating from Unidecode](../migration/from-unidecode.md) for details.
