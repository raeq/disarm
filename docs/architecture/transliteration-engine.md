# Architecture: Transliteration Engine

How translit converts Unicode text to ASCII, character by character.

## Design goals

The transliteration engine converts arbitrary Unicode strings to ASCII equivalents suitable for URLs, filenames, search indices, and cross-lingual display. The core tradeoff is speed vs. linguistic accuracy: translit chooses O(1) per-character lookup with no sentence context, sacrificing disambiguation of polyphonic characters (see [Limitations](../limitations.md)) for predictable, high-throughput output.

## Cow return type

`transliterate_impl()` returns `Cow<'a, str>`. Pure-ASCII input (the common case in English-dominated workloads) is returned as `Borrowed` with zero allocation. Non-ASCII input builds an `Owned` string. The ASCII check uses `str::is_ascii()`, which compiles to a SIMD-friendly byte scan — sub-nanosecond for short strings.

## Capacity pre-sizing

Before processing, the engine samples the first non-ASCII codepoint to pick a buffer multiplier:

- CJK ideographs, Hangul, kana (U+3000–U+9FFF, U+AC00–U+D7AF, U+F900–U+FAFF): **4×** the input byte length — each character typically expands to a multi-letter pinyin/romaji syllable plus a space.
- Latin, Cyrillic, Arabic, and everything else: **1×** — most characters map to a single ASCII character.

This heuristic prevents reallocations for CJK-heavy input without over-allocating for Latin text.

## Lookup priority

Each non-ASCII character goes through a fixed lookup chain:

1. **Strict ISO 9 mode** (`strict_iso9=True`): ISO 9 table → default table. Language overrides are bypassed entirely.
2. **Normal mode**: language-specific override (if `lang` is set) → default table.

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
