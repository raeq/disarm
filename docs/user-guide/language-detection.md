# Language Detection

How disarm's `lang="auto"` detection works, from script identification through character-level discrimination to fail-safe fallbacks.

## Overview

When `lang="auto"` is passed to `transliterate()`, `slugify()`, `catalog_key()`, or any other function that accepts a `lang` parameter, disarm runs a three-stage detection pipeline:

1. **Script identification** — find the dominant non-Latin, non-Common script
2. **Character-level discrimination** — scan for exclusive characters that uniquely identify a language within ambiguous scripts
3. **Fallback** — use the script's default language mapping

The entire pipeline is deterministic, O(n), and fail-safe: if detection is uncertain, it falls back to the safe default rather than guessing.

=== "Python"

    ```python
    from disarm import transliterate

    # Stage 1: Cyrillic detected → ambiguous script
    # Stage 2: ї found → Ukrainian discriminator hit
    # Stage 3: returns "uk"
    assert transliterate("Київ", lang="auto") == 'Kyiv'
    ```

=== "Rust"

    ```rust
    use disarm::api::Transliterate;

    // Stage 1: Cyrillic detected → ambiguous script
    // Stage 2: ї found → Ukrainian discriminator hit
    // Stage 3: returns "uk"
    assert_eq!(Transliterate::new().lang("auto").run("Київ"), "Kyiv");
    ```

=== "Ruby"

    ```ruby
    require "disarm"

    # Cyrillic detected → ї discriminator → Ukrainian
    Disarm.transliterate("Київ", lang: "auto")  # => "Kyiv"
    ```

---

## Stage 1: Script Identification

disarm classifies each character by its Unicode script property using a static table of 42 scripts with binary search lookup. The first non-Latin, non-Common, non-Inherited character determines the **primary script**.

=== "Python"

    ```python
    from disarm import detect_scripts, Script

    assert detect_scripts("Москва") == [Script.CYRILLIC]
    assert detect_scripts("東京タワー") == [Script.HAN, Script.KATAKANA]
    assert detect_scripts("Hello World") == [Script.LATIN]
    ```

=== "Rust"

    ```rust
    use disarm::api;

    assert_eq!(api::detect_scripts("Москва"), vec!["Cyrillic"]);
    assert_eq!(api::detect_scripts("東京タワー"), vec!["Han", "Katakana"]);
    assert_eq!(api::detect_scripts("Hello World"), vec!["Latin"]);
    ```

=== "Ruby"

    ```ruby
    Disarm.detect_scripts("Москва")       # => ["Cyrillic"]
    Disarm.detect_scripts("Hello World")  # => ["Latin"]
    Disarm.mixed_script?("Moсква")        # => true
    ```

For Latin-only text, no language override is applied (stage 2 may still detect Latin discriminators like Vietnamese or Turkish characters).

### Unambiguous scripts

Many scripts map to exactly one language in disarm's profile set. Detection is immediate with no further analysis needed:

| Script | Language | Code |
|---|---|---|
| Georgian | Georgian | `ka` |
| Armenian | Armenian | `hy` |
| Thai | Thai | `th` |
| Hangul | Korean | `ko` |
| Hiragana / Katakana | Japanese | `ja` |
| Greek | Greek | `el` |
| Thaana | Dhivehi | `dv` |
| Bengali | Bengali | `bn` |
| Tamil | Tamil | `ta` |
| Telugu | Telugu | `te` |
| Kannada | Kannada | `kn` |
| Malayalam | Malayalam | `ml` |
| Gujarati | Gujarati | `gu` |
| Gurmukhi | Punjabi | `pa` |
| Odia | Odia | `or` |
| Sinhala | Sinhala | `si` |
| Ethiopic | Amharic | `am` |
| Tibetan | Tibetan | `bo` |
| Lao | Lao | `lo` |
| Myanmar | Burmese | `my` |
| Khmer | Khmer | `km` |
| Hebrew | Hebrew | `he` |
| Javanese | Javanese | `jv` |

For these scripts, `lang="auto"` is equivalent to passing the explicit code.

### Ambiguous scripts

Three scripts are shared by multiple languages in disarm's profile set:

| Script | Languages | Default |
|---|---|---|
| **Cyrillic** | Russian, Ukrainian, Serbian, Bulgarian, Mongolian | `ru` |
| **Arabic** | Arabic, Persian | `ar` |
| **Latin** | German, Turkish, Vietnamese, + 20 others | *(no override)* |

These proceed to stage 2.

---

## Stage 2: Character-Level Discrimination

For ambiguous scripts, disarm scans up to the first **2,000 characters** looking for **exclusive characters** — codepoints that appear in exactly one language's alphabet among all supported profiles for that script.

### Discriminator table

| Script | Exclusive characters | Detected language |
|---|---|---|
| Cyrillic | ґ Ґ ї Ї є Є і І | `uk` (Ukrainian) |
| Cyrillic | ђ Ђ ћ Ћ љ Љ њ Њ џ Џ ј Ј | `sr` (Serbian) |
| Cyrillic | ө Ө ү Ү | `mn` (Mongolian) |
| Arabic | پ چ ژ گ | `fa` (Persian) |
| Latin | ơ Ơ ư Ư | `vi` (Vietnamese) |
| Latin | İ ı | `tr` (Turkish) |
| Latin | ß ẞ | `de` (German) |

### Algorithm

```
for each character in text[0..2000]:
    if character is an exclusive discriminator for this script:
        return the associated language  ← first hit wins, bail early
return None  ← no discriminator found, use default
```

Key properties:

- **First-hit-wins**: scanning stops at the first discriminator character found. This is a performance optimization — for well-formed text, a single exclusive character is sufficient for identification.
- **2,000-character cap**: avoids scanning entire documents. The first 2K characters are sufficient for discrimination in practice.
- **No conflict resolution**: if a text contains exclusive characters from two different languages (e.g., Ukrainian ї and Serbian ћ), whichever appears first wins. This is intentional — such mixed text is rare and artificial.

### Examples

=== "Python"

    ```python
    from disarm import transliterate

    # Ukrainian: ї is exclusive to Ukrainian Cyrillic
    assert transliterate("Київ", lang="auto") == 'Kyiv'

    # Serbian: ћ is exclusive to Serbian Cyrillic
    assert transliterate("Београд", lang="auto") == 'Beograd'

    # Persian: پ is exclusive to Persian Arabic
    assert transliterate("پارسی", lang="auto") == 'parsy'

    # Vietnamese: ơ is exclusive to Vietnamese Latin
    assert transliterate("Hà Nội", lang="auto") == 'Ha Noi'

    # German: ß is exclusive to German Latin
    assert transliterate("Straße", lang="auto") == 'Strasse'

    # No discriminator: Москва has no exclusive chars
    assert transliterate("Москва", lang="auto") == 'Moskva'
    ```

=== "Rust"

    ```rust
    use disarm::api::Transliterate;

    // Ukrainian: ї is exclusive to Ukrainian Cyrillic
    assert_eq!(Transliterate::new().lang("auto").run("Київ"), "Kyiv");

    // Serbian: ћ is exclusive to Serbian Cyrillic
    assert_eq!(Transliterate::new().lang("auto").run("Београд"), "Beograd");

    // Persian: پ is exclusive to Persian Arabic
    assert_eq!(Transliterate::new().lang("auto").run("پارسی"), "parsy");

    // Vietnamese: ơ is exclusive to Vietnamese Latin
    assert_eq!(Transliterate::new().lang("auto").run("Hà Nội"), "Ha Noi");

    // German: ß is exclusive to German Latin
    assert_eq!(Transliterate::new().lang("auto").run("Straße"), "Strasse");

    // No discriminator: Москва has no exclusive chars
    assert_eq!(Transliterate::new().lang("auto").run("Москва"), "Moskva");
    ```

=== "Ruby"

    ```ruby
    # ї is exclusive to Ukrainian; ћ to Serbian
    Disarm.transliterate("Київ", lang: "auto")     # => "Kyiv"
    Disarm.transliterate("Београд", lang: "auto")  # => "Beograd"
    # No discriminator: Москва falls back to the script default (ru)
    Disarm.transliterate("Москва", lang: "auto")   # => "Moskva"
    ```

---

## Stage 3: Fallback

If no discriminator is found:

- **Ambiguous scripts** fall back to their default language: Cyrillic → `ru`, Arabic → `ar`, Han → `zh`, Devanagari → `hi`
- **Latin-only text** receives no language override (default transliteration table)
- **Non-Latin Latin-discriminator text**: if the text contains only Latin characters but includes discriminators (ơ, İ, ß), the Latin discriminator table is consulted

---

## Fail-Safe Guarantee

The discriminator system is designed to **never produce a worse result** than the previous script-default approach:

1. Discriminators can only **upgrade** detection (from script default to a more specific language)
2. If no discriminator is found, the result is identical to not using `lang="auto"` at all
3. Discriminator characters are selected to have **zero ambiguity** — each appears in exactly one supported language profile for its script

This means `lang="auto"` is always at least as good as the script default, and often better.

---

## Limitations

- **Bulgarian vs Russian**: Bulgarian Cyrillic uses the same character set as Russian (no exclusive characters). `lang="auto"` defaults to `ru` for both. Pass `lang="bg"` explicitly for Bulgarian text.
- **Mongolian Cyrillic vs Russian**: Mongolian is detected only when ө or ү appear. Standard Russian characters in Mongolian text are not distinguished.
- **Devanagari languages**: Hindi, Marathi, Nepali, and Sanskrit all use Devanagari. `lang="auto"` defaults to `hi` for all. Since the default Devanagari transliteration table is used by all four, this has no practical impact.
- **Han characters**: Chinese and Japanese kanji share the same Unicode block. `lang="auto"` defaults to `zh` (Chinese pinyin). For Japanese readings, pass `lang="ja"` explicitly.
- **Mixed-script text**: when text contains multiple scripts (e.g., "Hello Мир"), the first non-Latin, non-Common script determines the language. Latin portions use the default table regardless.
- **Short text**: very short strings (1-3 characters) may not contain any discriminator characters, falling back to the script default.

---

## Inspecting Detection Results

Use `inspect_auto_lang()` to see exactly how the detection pipeline resolved for a given text. This is useful for logging, auditing, and debugging:

=== "Python"

    ```python
    from disarm import inspect_auto_lang

    result = inspect_auto_lang("Київ")
    # {
    #     'script': 'Cyrillic',
    #     'chosen_lang': 'uk',
    #     'reason': 'discriminator',
    #     'discriminators_hit': ['ї']
    # }

    result = inspect_auto_lang("Москва")
    # {
    #     'script': 'Cyrillic',
    #     'chosen_lang': 'ru',
    #     'reason': 'script_default',
    #     'discriminators_hit': []
    # }

    result = inspect_auto_lang("Straße")
    # {
    #     'script': None,
    #     'chosen_lang': 'de',
    #     'reason': 'latin_discriminator',
    #     'discriminators_hit': ['ß']
    # }
    ```

=== "Rust"

    ```rust
    use disarm::api;

    let kyiv = api::inspect_auto_lang("Київ");
    assert_eq!(kyiv.script.as_deref(), Some("Cyrillic"));
    assert_eq!(kyiv.chosen_lang.as_deref(), Some("uk"));
    assert_eq!(kyiv.reason, "discriminator");
    assert_eq!(kyiv.discriminators_hit, vec!["ї"]);

    let moscow = api::inspect_auto_lang("Москва");
    assert_eq!(moscow.script.as_deref(), Some("Cyrillic"));
    assert_eq!(moscow.chosen_lang.as_deref(), Some("ru"));
    assert_eq!(moscow.reason, "script_default");
    assert!(moscow.discriminators_hit.is_empty());

    let strasse = api::inspect_auto_lang("Straße");
    assert_eq!(strasse.script, None);
    assert_eq!(strasse.chosen_lang.as_deref(), Some("de"));
    assert_eq!(strasse.reason, "latin_discriminator");
    assert_eq!(strasse.discriminators_hit, vec!["ß"]);
    ```

=== "Ruby"

    ```ruby
    Disarm.inspect_auto_lang("Київ")  # => { script: "Cyrillic", chosen_lang: "uk", reason: "discriminator", discriminators_hit: ["ї"] }
    Disarm.inspect_auto_lang("Straße") # => { script: nil, chosen_lang: "de", reason: "latin_discriminator", discriminators_hit: ["ß"] }
    ```

### Return value

The fields map to each binding's idiom — Python dict keys, Ruby hash keys
(Symbols), and Rust `AutoLangInspection` fields:

| Key | Description |
|-----|-------------|
| `script` | Primary non-Latin script detected; absent / `nil` / `None` for Latin/ASCII |
| `chosen_lang` | Resolved language code; absent / `nil` / `None` if no language matched |
| `reason` | Detection reason: `"unambiguous_script"`, `"discriminator"`, `"script_default"`, `"latin_discriminator"`, or `"no_detection"` |
| `discriminators_hit` | Discriminator characters that triggered the match (empty if none) |

---

## When NOT to Use lang="auto"

`lang="auto"` is a convenience for bulk or unknown-source text. Do **not** use it when:

- **The language is already known** — bibliographic records, catalog entries, and curated datasets should always pass an explicit `lang` code.
- **Legal or official names** — personal names, place names in legal documents, and citations require the correct language profile. Auto-detection may default to the wrong language for ambiguous scripts.
- **Short text** — 1-3 character strings rarely contain discriminators and will fall back to the script default, which may not be correct.
- **Reproducibility matters** — auto-detection depends on text content; the same function with explicit `lang` always produces the same mapping.

```python
# Do this:
transliterate("Софія", lang="bg")   # Known to be Bulgarian

# Not this:
transliterate("Софія", lang="auto")  # Defaults to Russian (no Bulgarian discriminators)
```

---

## Integration with Pipelines

`lang="auto"` works with all disarm entry points:

<!--- skip: next -->
```python
from disarm import (
    transliterate, slugify, catalog_key, search_key, sort_key,
    TextPipeline, Slugifier, Text, LANG_AUTO,
)

# Functions
transliterate("Київ", lang="auto")
catalog_key("Москва", lang="auto")
search_key("Straße", lang="auto")
sort_key("Війна і мир", lang="auto")

# Classes
pipe = TextPipeline(transliterate=True, lang="auto")
slug = Slugifier(lang="auto")

# Text builder
Text("Київ").transliterate(lang="auto").value

# Type-safe constant
transliterate("Москва", lang=LANG_AUTO)
```

---

## See Also

- [Language Support](language-support.md) — full list of 83 language profiles and their override rules
- [Language Reference](../reference.md) — per-language transliteration tables and reference texts
- [Limitations](../limitations.md) — known constraints of context-free transliteration
