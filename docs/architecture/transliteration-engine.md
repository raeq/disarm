# Architecture: Transliteration Engine

How disarm converts Unicode text to ASCII, character by character.

## Design goals

The transliteration engine converts arbitrary Unicode strings to ASCII equivalents suitable for URLs, filenames, search indices, and cross-lingual display. The core tradeoff is speed vs. linguistic accuracy: disarm chooses O(1) per-character lookup with no sentence context, sacrificing disambiguation of polyphonic characters (see [Limitations](../limitations.md)) for predictable, high-throughput output.

## Cow return type

`transliterate_impl()` returns `Cow<'a, str>`. Pure-ASCII input (the common case in English-dominated workloads) is returned as `Borrowed` with zero allocation. Non-ASCII input builds an `Owned` string. The ASCII check uses `str::is_ascii()`, which compiles to a SIMD-friendly byte scan — sub-nanosecond for short strings.

## Capacity pre-sizing

Before processing, the engine samples the first non-ASCII codepoint to pick a buffer multiplier:

- CJK ideographs, Hangul, kana (U+3000–U+9FFF, U+AC00–U+D7AF, U+F900–U+FAFF): **4×** the input byte length — each character typically expands to a multi-letter pinyin/romaji syllable plus a space.
- Latin, Cyrillic, Arabic, and everything else: **1×** — most characters map to a single ASCII character.

This heuristic prevents reallocations for CJK-heavy input without over-allocating for Latin text.

## Auto-language resolution

When `lang="auto"` is passed, the engine resolves the language code before entering the main transliteration loop. `resolve_auto_lang()` scans the input for the first non-Latin, non-Common character, maps its script to a default ISO 639-1 code (e.g. Cyrillic → `"ru"`, Han → `"zh"`, Hiragana/Katakana → `"ja"`), and substitutes it for the `"auto"` sentinel. If no non-Latin script is found (Latin-only or empty input), `lang` becomes `None` and the default table is used.

This resolution happens once per call, after the ASCII fast path but before the per-character loop. It adds zero overhead when `lang` is `None` or an explicit code.

## Lookup priority

Each non-ASCII character goes through a fixed lookup chain:

1. **Strict ISO 9 mode** (`strict_iso9=True`): ISO 9 table → default table. Language overrides are bypassed entirely.
2. **Normal mode**: language-specific override (if `lang` is set, including auto-resolved) → default table.

This is a flat two-level dispatch, not a fallback chain. ISO 9 and language modes are mutually exclusive.

## Script transition spacing

Raw character-by-character concatenation produces unreadable output for CJK text: `北京市` → `beijingshi`. The engine tracks a `prev_class` byte to detect script transitions and insert spaces:

| Transition | Example | Spacing |
|---|---|---|
| Ideograph → ideograph | 北京 | space (each character is a "word") |
| Hangul → Hangul | 서울 | space (each syllable is distinct) |
| Kana → kana | ひらがな | no space (kana concatenate into words) |
| Ideograph ↔ kana | 東京タワー | space at boundary |
| CJK ↔ Latin | café北京 | space at boundary |

The `prev_class` variable (u8, 6 values) is updated per character. Combined with `last_appended: Option<char>` — which tracks the last character written to the output buffer — spacing decisions are O(1) with no backward scanning of the output string.

## Error modes

When a character has no mapping in any table, one of three modes applies:

| Mode | Behavior | Use case |
|---|---|---|
| `"replace"` | Substitute `replace_with` string (default `"[?]"`) | Debugging, visibility |
| `"ignore"` | Silently drop the character | URL slugs, filenames |
| `"preserve"` | Keep the original Unicode character | Mixed-script display |

## Range-based dispatch

`lookup_default()` dispatches by codepoint range before consulting the main table, routing characters to dedicated, higher-quality handlers:

- **CJK Unified Ideographs** (U+3400–U+9FFF, U+F900–U+FAFF) → Hanzi pinyin PHF table
- **Hangul Syllables** (U+AC00–U+D7AF) and compatibility jamo (U+3131–U+3163) → algorithmic romanization
- **Everything else** → flat BMP array (see [Data Tables](data-tables.md))

This avoids probing the 65K-entry flat array for scripts that have dedicated tables with better mappings.

## Abugida / virama handling

Brahmic scripts use inherent-vowel systems where a consonant carries an implicit "a" unless suppressed by a virama (halant). The engine handles this via the `IndicRole` enum:

- `Consonant` — carries inherent "a" in TSV (e.g. ka, ga, ta)
- `DependentVowel` — mātrā that replaces the inherent vowel
- `Virama` — suppresses the trailing "a" of the preceding consonant
- `None` — independent vowels, digits, punctuation

The `is_indic()` function identifies whether a codepoint belongs to a supported Brahmic range. Each script has a dedicated `*_char_role()` function (e.g. `tagalog_char_role`, `sundanese_char_role`) that classifies its codepoints into `IndicRole` variants. The `indic_char_role()` dispatcher routes to the correct function based on the codepoint range.

**Supported Brahmic scripts** (25 total): Devanagari, Bengali, Gurmukhi, Gujarati, Oriya, Tamil, Telugu, Kannada, Malayalam, Sinhala, Thai, Lao, Tibetan, Myanmar, Khmer, Balinese, Sundanese, Tai Tham, Cham, Batak, Buginese, Tagalog, Hanunoo, Buhid, Tagbanwa, Meetei Mayek.

## Unicode form mappings

The flat BMP array includes mechanical mappings for Unicode presentation forms and compatibility characters that appear in real-world data:

| Block | Range | Count | Mapping method |
|---|---|---|---|
| Fullwidth ASCII | FF01–FF5E | 94 | `codepoint - 0xFEE0` offset to ASCII equivalent |
| Halfwidth Hangul | FFA0–FFDC | 66 | Via compatibility jamo romanization |
| Enclosed/Circled | 2460–24FF | 160 | Extract value from Unicode name (①→1, Ⓐ→A) |
| Superscript/Subscript | 2070–209F | 29 | Map to base digit or letter |
| Roman Numerals | 2160–2188 | 41 | Multi-char values (Ⅱ→II, Ⅻ→XII) |
| Modifier Letters | 02B0–02FF | 80 | Superscript letter variants (ʰ→h, ʷ→w) |
| IPA Extensions | 0250–02AF | 96 | Closest ASCII approximation (ɑ→a, ʃ→sh, ŋ→ng) |
| Greek Extended | 1F00–1FFF | 233 | Strip breathing/accent → base Greek → Latin |
| Hangul Jamo | 1100–11FF | 256 | Matches CHOSEONG/JUNGSEONG/JONGSEONG arrays |
| Kangxi Radicals | 2F00–2FD5 | 214 | Decompose to CJK Unified → pinyin |
| CJK Compat Ideographs | F900–FAFF | 472 | Canonical decomposition target → pinyin |
