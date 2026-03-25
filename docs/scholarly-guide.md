# translit for Scholarly and Linguistic Use

A guide to translit's features for researchers, linguists, computational
linguists, NLP engineers, and digital humanities practitioners.

translit is a Rust+PyO3 Unicode text processing library offering
transliteration, emoji expansion, normalization, homoglyph detection, and
script analysis — all behind a single `pip install`. This document covers
each capability in the context of academic and linguistic workflows.

---

## ISO 9:1995 Scholarly Cyrillic Transliteration

ISO 9:1995 is the international standard for Cyrillic-to-Latin
transliteration used in linguistics, library cataloging (per GOST 7.79),
and academic publishing. It is pan-Cyrillic — language-independent and
fully reversible — making it the standard expected by peer reviewers and
indexing services.

translit defaults to BGN/PCGN-style practical romanization (the convention
on passports, maps, and signage), but provides a `strict_iso9` flag that
switches to the scholarly standard.

### Key Divergences

| Cyrillic | Default (BGN/PCGN) | `strict_iso9=True` (ISO 9) |
|----------|--------------------|-----------------------------|
| й / Й    | y / Y              | j / J                       |
| ю / Ю    | yu / Yu            | ju / Ju                     |
| я / Я    | ya / Ya            | ja / Ja                     |
| ё / Ё    | yo / Yo            | jo / Jo                     |
| х / Х    | kh / Kh            | h / H                       |
| ц / Ц    | ts / Ts            | c / C                       |
| ъ        | *(silent)*         | *(silent)*                  |
| ь        | *(silent)*         | *(silent)*                  |

Note: True ISO 9 produces Latin-with-diacritics (š, č, ž). The table above
shows the ASCII-flattened equivalents, which is the scholarly convention
when diacritics are unavailable (terminal output, filenames, search indices).

### Usage

```python
from translit import transliterate

# Default: BGN/PCGN practical romanization
transliterate("Йогурт")                        # → "Yogurt"
transliterate("юность")                         # → "yunost"

# ISO 9 scholarly standard
transliterate("Йогурт", strict_iso9=True)       # → "Jogurt"
transliterate("юность", strict_iso9=True)       # → "junost"
transliterate("хлеб",   strict_iso9=True)       # → "hleb"
transliterate("цирк",   strict_iso9=True)       # → "cirk"
```

### Interaction with Language Overrides

When `strict_iso9=True`, the ISO 9 table takes absolute priority. Language
overrides (`lang="ru"`, `lang="bg"`, etc.) are ignored for any character
present in the ISO 9 table. Characters not in the ISO 9 table fall through
to the default table as normal.

```python
# ISO 9 overrides lang="ru" BGN/PCGN soft-sign marking
transliterate("большой", lang="ru")                   # → "bol'shoy"
transliterate("большой", strict_iso9=True)             # → "bolshoj"
transliterate("большой", strict_iso9=True, lang="ru")  # → "bolshoj"  (ISO 9 wins)
```

### Pipeline and Builder Integration

```python
from translit import Text, TextPipeline

# Text builder
Text("Юность").transliterate(strict_iso9=True).fold_case().value
# → "junost"

# Pre-compiled pipeline for batch processing
pipe = TextPipeline(transliterate=True, strict_iso9=True, fold_case=True)
pipe("Юность")  # → "junost"
```

---

## GOST R 7.0.34-2014 Simplified Russian Transliteration

GOST R 7.0.34-2014 is the current Russian national standard for simplified
transliteration of Cyrillic to Latin, used in Russian bibliographic systems,
publishing, and document exchange. Unlike ISO 9, it is Russian-specific (not
pan-Cyrillic) and not designed to be reversible.

The standard uses pure character-by-character substitution with no
context-dependent rules.

### Key Divergences

| Cyrillic | Default (BGN/PCGN) | `gost7034=True` | `strict_iso9=True` (ISO 9) |
|----------|--------------------|-----------------|-----------------------------|
| х / Х    | kh / Kh            | **x / X**       | h / H                       |
| ц / Ц    | ts / Ts            | **c / C**       | c / C                       |
| щ / Щ    | shch / Shch        | **shh / Shh**   | shch / Shch                 |
| й / Й    | y / Y              | **j / J**       | j / J                       |
| ъ        | *(silent)*         | *(silent)*      | *(silent)*                  |
| ь        | *(silent)*         | *(silent)*      | *(silent)*                  |
| ё / Ё    | yo / Yo            | yo / Yo         | jo / Jo                     |
| ю / Ю    | yu / Yu            | yu / Yu         | ju / Ju                     |
| я / Я    | ya / Ya            | ya / Ya         | ja / Ja                     |

### Usage

```python
from translit import transliterate

# GOST R 7.0.34-2014
transliterate("хлеб", gost7034=True)      # → "xleb"
transliterate("цирк", gost7034=True)      # → "cirk"
transliterate("щука", gost7034=True)      # → "shhuka"
transliterate("Йогурт", gost7034=True)    # → "Jogurt"

# Characters not overridden by GOST fall through to default
transliterate("Москва", gost7034=True)    # → "Moskva"
transliterate("юность", gost7034=True)    # → "yunost"
```

### Mutual Exclusion with ISO 9

`gost7034` and `strict_iso9` are mutually exclusive. Setting both raises
a `ValueError`:

```python
transliterate("тест", gost7034=True, strict_iso9=True)
# → ValueError: strict_iso9 and gost7034 are mutually exclusive
```

### Pipeline and Builder Integration

```python
from translit import Text, TextPipeline

# Text builder
Text("хлеб").transliterate(gost7034=True).value
# → "xleb"

# Pre-compiled pipeline
pipe = TextPipeline(transliterate=True, gost7034=True, fold_case=True)
pipe("Щука")  # → "shhuka"
```

---

## Language-Specific Transliteration

translit ships 60 language profiles. Each profile provides override
mappings for characters whose standard romanization differs from the
pan-script defaults.

### Cyrillic Languages

| Code | Language   | Notable Overrides                            | Standard          |
|------|-----------|----------------------------------------------|-------------------|
| `ru` | Russian    | ъ → `"`, ь → `'` (sign markers)             | BGN/PCGN          |
| `uk` | Ukrainian  | Г→H, Ґ→G, Є→Ye, І→I, И→Y                   | KMU 2010          |
| `bg` | Bulgarian  | Ъ→A, Щ→Sht                                   | Streamlined system|
| `sr` | Serbian    | Ћ→C, Џ→Dz, Ђ→Dj                              | Practical ASCII   |

### European Languages

| Code | Language   | Notable Overrides                              |
|------|-----------|------------------------------------------------|
| `de` | German     | ä→ae, ö→oe, ü→ue, ẞ→SS (Duden)               |
| `no` | Norwegian  | Å→Aa, Ø→Oe, Æ→Ae                              |
| `sv` | Swedish    | Ä→Ae, Ö→Oe                                    |
| `tr` | Turkish    | Ç→C, Ğ→G, İ→I, Ö→O, Ş→S, Ü→U                |
| `el` | Greek      | Full alphabet (Α→A through ω→o)                |
| `vi` | Vietnamese | Full diacritical vowel set (96+ chars)          |
| `ga` | Irish      | Dot-above consonants: Ḃ→Bh, Ċ→Ch, Ḋ→Dh        |

### East Asian Languages

| Code | Language  | Coverage                                       |
|------|----------|------------------------------------------------|
| `ja` | Japanese  | Hiragana, Katakana, half-width Katakana (Hepburn)|
| `zh` | Chinese   | Hanzi → pinyin                                  |
| `ko` | Korean    | Hangul → romanization                           |

Full list of 60 codes: `am`, `ar`, `as`, `bg`, `bn`, `bo`, `ca`, `cs`, `cy`, `da`, `de`, `el`,
`es`, `et`, `fi`, `fr`, `ga`, `gu`, `he`, `hi`, `hr`, `hu`, `hy`, `is`, `it`, `ja`, `ka`, `km`, `kn`, `ko`, `lo`, `lt`,
`lv`, `ml`, `mr`, `mt`, `my`, `ne`, `nl`, `no`, `or`, `pa`, `pl`, `pt`, `ro`, `ru`, `sa`, `si`, `sk`,
`sl`, `sq`, `sr`, `sv`, `ta`, `te`, `th`, `tr`, `uk`, `vi`, `zh`.

### Auto-Detecting Language from Script

When processing multi-script corpora where the source language varies per
record, `lang="auto"` detects the dominant non-Latin script and selects the
appropriate profile:

```python
transliterate("Москва", lang="auto")      # → "Moskva" (Cyrillic → Russian)
transliterate("नमस्ते", lang="auto")        # → "namaste" (Devanagari → Hindi)
transliterate("ქართული", lang="auto")      # → "kartuli" (Georgian)
```

For ambiguous scripts (Cyrillic → Russian, Devanagari → Hindi, Han → Chinese),
the default may not match your source language. Pass an explicit code when
accuracy matters.

### Runtime Language Registration

For languages not covered by the built-in profiles, or for project-specific
romanization schemes, you can register custom tables at runtime:

```python
from translit import register_lang, transliterate

register_lang("my-project", {
    "ø": "oe",
    "Ø": "Oe",
})
transliterate("Ørsted", lang="my-project")  # → "Oersted"
```

---

## Japanese Kana Transliteration

translit includes Modified Hepburn romanization for the three kana blocks,
totaling 235 character mappings.

### Coverage

| Block               | Range           | Entries | Example                    |
|---------------------|-----------------|---------|----------------------------|
| Hiragana            | U+3041–U+3096   | 86      | すし → sushi               |
| Katakana            | U+30A1–U+30FE   | 90      | ラーメン → ra-men            |
| Half-width Katakana | U+FF65–U+FF9F   | 59      | ｶﾀｶﾅ → katakana            |

### Dakuten and Handakuten

Half-width Katakana uses combining dakuten (U+FF9E) and handakuten
(U+FF9F) as separate codepoints. Per-character transliteration cannot
resolve these combinations (ﾊﾞ as "ha" + voiced mark, not "ba"). The
recommended approach is NFKC normalization first, which merges half-width
forms into precomposed full-width equivalents:

```python
from translit import Text

# Without NFKC: dakuten is a separate character
Text("ﾊﾞﾅﾅ").transliterate().value                # → "hanana"

# With NFKC: precomposed full-width, dakuten resolved
Text("ﾊﾞﾅﾅ").normalize(form="NFKC").transliterate().value  # → "banana"
```

### Prolonged Sound Mark

The katakana prolonged sound mark ー (U+30FC) transliterates to a hyphen:
`ラーメン → ra-men`, `トーキョー → to-kiyo-`.

---

## Indic Script Transliteration

translit supports transliteration of 10 Brahmic scripts covering ~2 billion speakers.
All Brahmic scripts share a common alphasyllabic structure at consistent Unicode offsets,
enabling systematic romanization with virama/mātrā-aware processing.

### Coverage

| Script     | Block           | Entries | Example                    |
|------------|-----------------|---------|----------------------------|
| Devanagari | U+0900–U+097F   | ~89     | नमस्ते → namaste           |
| Bengali    | U+0980–U+09FF   | ~83     | কলকাতা → kalakata          |
| Gurmukhi   | U+0A00–U+0A7F   | ~76     | ਪੰਜਾਬੀ → panjabi           |
| Gujarati   | U+0A80–U+0AFF   | ~77     | ગુજરાતી → gujarati         |
| Odia       | U+0B00–U+0B7F   | ~78     | ଓଡିଆ → odia               |
| Tamil      | U+0B80–U+0BFF   | ~55     | தமிழ் → tamizh             |
| Telugu     | U+0C00–U+0C7F   | ~80     | తెలుగు → telugu            |
| Kannada    | U+0C80–U+0CFF   | ~80     | ಕನ್ನಡ → kannada            |
| Malayalam  | U+0D00–U+0D7F   | ~82     | മലയാളം → malayalam         |
| Sinhala    | U+0D80–U+0DFF   | ~80     | සිංහල → simhala            |

### Virama and Mātrā Handling

Brahmic consonants carry an inherent vowel "a". The engine detects virama
(halant) and dependent vowel signs (mātrā) to strip the inherent "a" before
appending the replacement:

```python
from translit import transliterate

transliterate("क")    # → "ka"  (bare consonant, inherent 'a')
transliterate("क्")   # → "k"   (virama suppresses 'a')
transliterate("की")   # → "ki"  (mātrā replaces 'a' with 'i')
transliterate("नमस्ते")  # → "namaste"
```

### Comparison with Standards

translit's Indic output is **ASCII-only** (no diacritics), intended for search
normalization, URL slugs, and text processing. For scholarly work requiring
diacritical marks, compare with:

| Standard     | Output         | Example          |
|-------------|----------------|------------------|
| translit    | ASCII          | namaste          |
| IAST        | Diacritical    | namastē          |
| ISO 15919   | Diacritical    | namastē          |
| UNGEGN      | Diacritical    | namastē          |
| ITRANS      | ASCII          | namaste          |

### Per-Script Notes

- **Tamil**: Does not have aspirated consonants (kha, gha, etc.) — those
  offsets are unassigned in Unicode. Includes unique ழ → "zha".
- **Bengali**: Includes special forms ড় → "ra", ঢ় → "rha", য় → "ya",
  and ৎ → "t".
- **Malayalam**: Includes chillu (atomic consonant) forms at U+0D7A–U+0D7F.

### Supported Languages

14 Indic language codes are registered: `as` (Assamese), `bn` (Bengali),
`gu` (Gujarati), `hi` (Hindi), `kn` (Kannada), `ml` (Malayalam),
`mr` (Marathi), `ne` (Nepali), `or` (Odia), `pa` (Punjabi),
`sa` (Sanskrit), `si` (Sinhala), `ta` (Tamil), `te` (Telugu). All use the default
transliteration table.

---

## Emoji Expansion for NLP

Emoji carry semantic content that is lost when standard NLP tokenizers
discard non-ASCII characters. translit's `demojize()` replaces emoji
sequences with their Unicode CLDR short-name descriptions, preserving
meaning for downstream models.

### How It Improves on Existing Tools

**Compared to the `emoji` package:**

- Handles multi-codepoint sequences correctly using longest-match-first
  scanning: ZWJ sequences (👨‍👩‍👧‍👦 → "family: man, woman, girl, boy"),
  flag pairs (🇫🇷 → "flag: France"), keycap sequences, and presentation
  selectors.
- Cleans up orphaned ZWJ (U+200D) and variation selectors (U+FE0F/U+FE0E)
  that leak into output when sequences partially match.
- Returns bare CLDR short names as plain text — no `:colons:`, no
  `_underscores_`, no formatting artifacts in your feature vectors.
- Compiled Rust matching engine with O(1) PHF lookups instead of Python
  regex scanning.

**Compared to NLTK's `TweetTokenizer` and emoji handling:**

- NLTK treats emoji as single tokens but does not expand their meaning.
  It preserves the emoji codepoint, which downstream bag-of-words or
  TF-IDF models cannot use. translit converts emoji to descriptive text
  that existing NLP pipelines can tokenize and embed.
- NLTK has no awareness of skin tone modifiers, ZWJ sequences, or flag
  pairs. A family emoji (👨‍👩‍👧‍👦) is four tokens in NLTK; in translit
  it is one description.
- `strip_modifiers=True` collapses skin tone and hair style variants to
  their base form, reducing feature sparsity in sentiment analysis and
  classification tasks.

**Compared to the `demoji` package:**

- `demoji` downloads emoji data at runtime and regex-matches. translit
  compiles CLDR data into the binary at build time — no network calls,
  no data directory, no version drift.
- `demoji` replaces emoji with empty string by default. translit replaces
  with descriptive text, preserving semantic content.

### Usage

```python
from translit import demojize

# Basic expansion
demojize("I love 🍕")
# → "I love pizza"

# Multi-codepoint ZWJ sequence
demojize("👨‍👩‍👧‍👦")
# → "family: man, woman, girl, boy"

# Skin tone modifier handling
demojize("👋🏽")
# → "waving hand: medium skin tone"

demojize("👋🏽", strip_modifiers=True)
# → "waving hand"

# Flag sequences
demojize("🇫🇷")
# → "flag: France"

# Error handling for unknown emoji
demojize("😀", errors="preserve")   # keep original if unknown
demojize("😀", errors="ignore")     # drop if unknown
demojize("😀", errors="replace", replace_with="[emoji]")
```

### Custom Emoji Providers

For working with historical corpora where emoji semantics have changed
across Unicode versions, translit supports pluggable providers:

```python
from translit import demojize, set_emoji_provider

class EmojiV12Provider:
    """Provider using Unicode Emoji 12.0 annotations."""
    def lookup(self, sequence: list[int]) -> str | None:
        # Return CLDR short name for this codepoint sequence,
        # or None to fall back to the built-in default
        ...

# Per-call override
demojize("🥱", provider=EmojiV12Provider())

# Global override (affects all subsequent demojize calls)
set_emoji_provider(EmojiV12Provider())

# Reset to built-in default
set_emoji_provider(None)
```

Providers implement a single method: `lookup(sequence: list[int]) -> str | None`.
The sequence is a list of Unicode codepoints (integers). Return the bare
text description or `None` to fall through to the default provider.

### Chaining Providers for Mixed-Era Corpora

When analyzing corpora spanning multiple Unicode Emoji versions, providers
can be chained so that newer annotations take precedence with older ones
as fallback:

```python
class ChainProvider:
    def __init__(self, *providers):
        self.providers = providers

    def lookup(self, sequence):
        for p in self.providers:
            result = p.lookup(sequence)
            if result is not None:
                return result
        return None

provider = ChainProvider(EmojiV16Provider(), EmojiV12Provider())
```

---

## Unicode Normalization

Normalization is a prerequisite for virtually all text comparison,
indexing, and analysis. translit exposes all four Unicode normalization
forms with O(1) form-check predicates.

| Form   | Use Case                                                      |
|--------|---------------------------------------------------------------|
| `NFC`  | Default storage and comparison. Precomposed characters.        |
| `NFD`  | Accent stripping (decompose, then filter combining marks).     |
| `NFKC` | Search normalization. Collapses compatibility variants (ﬁ→fi, ²→2, half-width→full-width). |
| `NFKD` | Full decomposition for analysis. Compatibility + canonical.    |

```python
from translit import normalize, is_normalized

normalize("café", form="NFD")          # decompose é → e + combining acute
normalize("ﬁ", form="NFKC")           # compatibility: ﬁ → fi
normalize("ﾊﾞﾅﾅ", form="NFKC")         # half-width katakana → full-width: バナナ

is_normalized("café", form="NFC")      # True (already composed)
is_normalized("café", form="NFD")      # False (composed, not decomposed)
```

---

## Confusable and Homoglyph Detection

Unicode TR39 defines characters that are visually confusable across
scripts — a concern for corpus integrity, phishing detection, and
cross-script search normalization.

```python
from translit import is_confusable, is_mixed_script, normalize_confusables

# Detect Cyrillic а (U+0430) masquerading as Latin a
is_confusable("раypal")                    # True
is_mixed_script("раypal")                  # True

# Normalize to canonical Latin forms
normalize_confusables("раypal")            # → "paypal"
```

### Script Detection

Identify which Unicode scripts are present in a text sample, returned
in order of first appearance:

```python
from translit import detect_scripts

detect_scripts("Hello World")              # [Script.LATIN]
detect_scripts("Привет мир")               # [Script.CYRILLIC]
detect_scripts("こんにちは世界")              # [Script.HIRAGANA, Script.HAN]
detect_scripts("Привет Hello こんにちは")    # [Script.CYRILLIC, Script.LATIN, Script.HIRAGANA]
```

translit recognizes 39 Unicode scripts, including all major world scripts,
Indic scripts, Southeast Asian scripts, and historical scripts (Runic,
Ogham).

---

## Transliteration Table Coverage

The default transliteration table contains approximately 1,200 character
mappings across these Unicode blocks:

| Block                        | Range           | Characters | Romanization System  |
|------------------------------|-----------------|------------|----------------------|
| Latin-1 Supplement           | U+00C0–U+00FF  | ~96        | Diacritic removal     |
| Latin Extended-A             | U+0100–U+017F  | ~128       | Diacritic removal     |
| Latin Extended-B             | U+0180–U+024F  | ~50        | Digraph normalization |
| Greek                        | U+0370–U+03FF  | ~48        | ISO 843 (simplified)  |
| Cyrillic                     | U+0400–U+04FF  | ~105       | BGN/PCGN (default)    |
| Latin Extended Additional    | U+1E00–U+1EFF  | ~256       | Diacritic removal     |
| Hiragana                     | U+3041–U+309F  | ~86        | Modified Hepburn      |
| Katakana                     | U+30A0–U+30FF  | ~90        | Modified Hepburn      |
| Half-width Katakana          | U+FF65–U+FF9F  | ~59        | Modified Hepburn      |
| Currency Symbols             | Various         | ~12        | Abbreviations (€→EUR) |
| Typographic Characters       | Various         | ~20        | ASCII equivalents     |
| Vulgar Fractions             | U+2150–U+215E  | 15         | Slash notation (⅓→1/3)|
| Superscripts                 | U+2070–U+207F  | 14         | Digit equivalents     |

In addition, 20 language-specific override tables provide national-standard
romanization when `lang=` is specified.

---

## The Text Builder and TextPipeline

translit offers two composition models for chaining transforms.

### Text Builder (Exploratory / Interactive)

Immutable, chainable API. Each method returns a new `Text` instance.
Suitable for interactive exploration, notebooks, and one-off processing:

```python
from translit import Text

result = (
    Text("  Привет 👋🏽  мир!  ")
    .normalize(form="NFC")
    .demojize(strip_modifiers=True)
    .transliterate(strict_iso9=True)
    .fold_case()
    .collapse_whitespace()
    .value
)
# → "privet waving hand mir!"
```

### TextPipeline (Batch / Production)

Pre-compiled pipeline that executes steps in fixed optimal order regardless
of construction order. Suitable for batch processing where the same
transform chain is applied to millions of records:

```python
from translit import TextPipeline

pipe = TextPipeline(
    normalize="NFKC",
    demojize=True,
    transliterate=True,
    strict_iso9=True,       # ISO 9 for Cyrillic
    lang="ja",              # Hepburn for Japanese (ignored for Cyrillic when iso9 is set)
    fold_case=True,
    collapse_whitespace=True,
)

# Apply to corpus
cleaned = [pipe(doc) for doc in corpus]
```

**Fixed execution order:**

1. Normalize (canonical form first)
2. Normalize confusables (script-aware homoglyph replacement)
3. Demojize (emoji → text, before transliteration)
4. Strip accents (NFD decompose + filter combining marks)
5. Transliterate (Unicode → ASCII)
6. Fold case (Unicode case folding: ß→ss, İ→i̇)
7. Collapse whitespace (normalize Unicode spaces, strip control chars)

---

## Accent Stripping

Strips diacritical marks while preserving base characters. Implemented as
NFD decomposition followed by removal of combining marks and NFC
recomposition:

```python
from translit import strip_accents

strip_accents("café")     # → "cafe"
strip_accents("naïve")    # → "naive"
strip_accents("résumé")   # → "resume"
```

This is distinct from transliteration: `strip_accents` preserves the
character as a base Latin letter, while `transliterate` may produce
multi-character ASCII equivalents (e.g., German ü→u via strip_accents
vs ü→ue via transliterate with `lang="de"`).

---

## Unicode Case Folding

Full Unicode case folding per CaseFolding.txt (Unicode 16.0). This is not
`.lower()` — it implements all 1,557 status-C and status-F mappings via a
compile-time PHF table, covering cases that Python's `str.lower()` misses:

```python
from translit import fold_case

fold_case("Straße")    # → "strasse"  (ß→ss)
fold_case("İstanbul")  # → "i̇stanbul" (Turkish İ→i̇)
fold_case("ﬁle")       # → "file"     (ﬁ→fi ligature decomposition)
fold_case("ϐ ϑ ϕ")    # → "β θ φ"    (Greek variant forms)
fold_case("\u00B5")    # → "μ"        (micro sign → Greek mu)
fold_case("\u017F")    # → "s"        (long s → s)
```

Covers Latin, Greek, Cyrillic, Armenian, Georgian Mtavruli, Cherokee,
Adlam, Deseret, Osage, Warang Citi, and fullwidth Latin. Produces
identical output to `str.casefold()`. Pure-ASCII strings take a
branchless fast path.

---

## Whitespace Normalization

Handles the full range of Unicode whitespace characters (13 variants),
control characters, and zero-width characters:

```python
from translit import collapse_whitespace

# Normalizes non-breaking spaces, em spaces, ideographic spaces, etc.
collapse_whitespace("hello\u00A0\u2003world")  # → "hello world"
```

---

## Error Handling Modes

All transform functions accept an `errors` parameter with three modes:

| Mode         | Behavior                                | Use Case                              |
|--------------|-----------------------------------------|---------------------------------------|
| `"replace"`  | Substitute unmappable chars with `replace_with` | Production pipelines (default)    |
| `"ignore"`   | Silently drop unmappable characters      | Search index construction             |
| `"preserve"` | Keep the original character unchanged    | Exploratory analysis, debugging       |

```python
from translit import transliterate

# CJK characters are fully transliterated (Hanzi → Pinyin)
transliterate("hello 世界")                          # → "hello shi jie"

# Error modes apply to characters with NO mapping (e.g., CJK Extension B)
transliterate("hello \U00020000", errors="replace")  # → "hello [?]"
transliterate("hello \U00020000", errors="ignore")   # → "hello "
transliterate("hello \U00020000", errors="preserve") # → "hello 𠀀"
```

---

## Performance

### Grapheme Cluster Analysis

For linguistic analysis that requires accurate character counts (e.g.,
graphotactic studies, syllable alignment), use `grapheme_len()` and
`grapheme_split()` instead of Python's `len()` and `list()`:

```python
from translit import grapheme_len, grapheme_split

# NFD-decomposed text: e + combining accent = 1 grapheme
grapheme_len("cafe\u0301")              # → 4 (len() returns 5)
grapheme_split("cafe\u0301")            # → ['c', 'a', 'f', 'é']

# Hangul: decomposed jamo sequence = 1 grapheme cluster
grapheme_len("\u1100\u1161\u11A8")      # → 1 (len() returns 3)
```

### Encoding Detection for Historical Texts

Digitized historical corpora often arrive in legacy encodings:

```python
from translit import detect_encoding, decode_to_utf8

encoding, confidence = detect_encoding(raw_bytes)
text, had_errors = decode_to_utf8(raw_bytes, encoding="ISO-8859-1")
```

Use `had_errors` to flag documents that need manual review.

---

## Performance

translit is implemented in Rust with PyO3 bindings. All table lookups use
compile-time perfect hash functions (PHF) for O(1) guaranteed access. There
is no runtime data loading, no regex compilation, and no Python-level
per-character iteration.

The `TextPipeline` class pre-compiles the step configuration at construction
time and processes text in a single Rust-side pass per step, minimizing
Python-to-Rust boundary crossings.

---

## Installation

```bash
pip install translit-rs
```

Single wheel per platform (abi3). No Rust toolchain required for
installation. No runtime data downloads.
