# Architecture: Emoji Plugin System

This document describes the architecture for emoji-to-text expansion in disarm. The design adds a `demojize()` transform that converts emoji sequences to textual descriptions, integrated into the existing `Text` builder and `TextPipeline`. Emoji data is supplied through a plugin system that allows runtime selection of emoji version, language, and data source.

## Problem

Emoji are increasingly common in informal text. NLP pipelines that strip non-ASCII lose the semantic signal emoji carry. Existing Python solutions (`emoji`, `demoji`, `emot`) work but sit outside the Unicode normalization pipeline, forcing users to coordinate multiple libraries with no ordering guarantees.

NLP corpora are archival. A researcher analysing 2016 tweets needs Emoji 3.0 annotations; someone processing current chat logs needs Emoji 16.0. Unicode adds and occasionally redefines emoji every year. A single compiled-in table cannot serve both use cases without bloating the binary or going stale.

## Design Principles

Three rules govern the split between core and plugins:

1. **Core owns the matching engine.** The algorithm that scans text for multi-codepoint emoji sequences (ZWJ joins, skin tone modifiers, flag pairs, keycap sequences) lives in the `disarm` core crate. Plugins never implement scanning logic.

2. **Plugins supply data only.** A plugin is a mapping from emoji codepoint sequences to textual descriptions. It implements a trait, registers itself, and the core engine calls into it during scanning. Plugins carry no processing logic beyond returning strings.

3. **Default works without plugins.** The core crate ships with a built-in provider covering the latest Unicode Emoji version (English short names from CLDR). Users who need nothing else never install a plugin.

## Core Components

### The `EmojiProvider` Trait

<!--- rust-skip -->
```rust
pub trait EmojiProvider: Send + Sync {
    /// Return the textual expansion for an emoji sequence, or None if unknown.
    fn lookup(&self, sequence: &[char]) -> Option<&str>;

    /// The Unicode Emoji version this provider covers (e.g. "16.0").
    fn emoji_version(&self) -> &str;

    /// Whether this provider has annotations for the given language.
    fn supports_lang(&self, lang: &str) -> bool;
}
```

Providers are stateless data lookups. The trait is intentionally minimal — no scanning, no pipeline awareness, no configuration. A provider's only job is to answer "what text does this emoji sequence map to?"

### The Matching Engine

The core scanning algorithm handles the complexity that plugins must not:

- **Longest-match-first scanning.** Modern emoji are multi-codepoint: 👨‍👩‍👧‍👦 (family) is 7 codepoints joined by U+200D (ZWJ). The engine scans left-to-right and always tries the longest possible sequence before falling back to shorter subsequences or individual codepoints.

- **Modifier handling.** Skin tone modifiers (U+1F3FB–U+1F3FF), hair modifiers, and presentation selectors (U+FE0E/U+FE0F) are consumed as part of the base emoji sequence, not treated as independent codepoints.

- **Flag sequences.** Regional indicator pairs (U+1F1E6–U+1F1FF) are matched as pairs. Odd-length runs leave the trailing indicator unmatched.

- **Keycap sequences.** Digit/symbol + U+FE0F + U+20E3 patterns are matched as a unit.

The engine delegates to the registered provider for the actual sequence-to-text mapping. If the provider returns `None`, the engine applies the standard `errors` parameter behaviour (`"replace"`, `"ignore"`, `"preserve"`) already used by `transliterate()`.

### Built-in Default Provider

The core crate compiles a default provider using PHF, covering the latest Unicode Emoji version with English CLDR short names. This provider is always available and requires no runtime data loading.

<!--- rust-skip -->
```rust
// Compiled into the binary at build time
static DEFAULT_EMOJI: phf::Map<&[u32], &str> = phf_map! {
    &[0x1F600] => "grinning face",
    &[0x1F602] => "face with tears of joy",
    &[0x1F1FA, 0x1F1F8] => "flag: United States",
    &[0x1F468, 0x200D, 0x1F469, 0x200D, 0x1F467, 0x200D, 0x1F466] => "family: man, woman, girl, boy",
    // ~4,500 entries
};
```

## Plugin Architecture

### Plugin Crates

Each plugin is a separate Rust crate with a PyO3 wrapper, published as an independent pip package:

| Package | Contents | Typical Size |
|---|---|---|
| `disarm` | Core engine + latest English CLDR (default) | ~2 MB |
| `disarm-emoji-15` | Emoji 15.1 (2023) CLDR annotations | ~400 KB |
| `disarm-emoji-14` | Emoji 14.0 (2021) CLDR annotations | ~350 KB |
| `disarm-emoji-12` | Emoji 12.0 (2019) CLDR annotations | ~300 KB |
| `disarm-emoji-legacy` | Pre-standard platform emoji (carriers, early Android/Samsung) | ~200 KB |
| `disarm-emoji-multilingual` | CLDR annotations for 20+ languages, latest version | ~3 MB |

Each versioned plugin covers the complete emoji set defined by that Unicode Emoji version, including sequences that were later removed or redefined. This is critical for historical corpus analysis: the Emoji 12.0 plugin knows about emoji as they existed in 2019, not as they exist today.

### Compiled vs. File-based Plugins

Two plugin types are supported:

**Compiled plugins** (primary path). The plugin crate compiles CLDR data into a PHF map at build time. Zero runtime cost, no file I/O, no data directory to manage. This is the default for versioned release plugins.

<!--- rust-skip -->
```rust
// In crate disarm-emoji-15
pub struct Emoji15Provider;

impl EmojiProvider for Emoji15Provider {
    fn lookup(&self, sequence: &[char]) -> Option<&str> {
        EMOJI_15_TABLE.get(sequence).copied()
    }
    fn emoji_version(&self) -> &str { "15.1" }
    fn supports_lang(&self, lang: &str) -> bool { lang == "en" }
}
```

**File-based plugins** (escape hatch). A generic provider loads annotations from a compact binary format at runtime. This serves researchers who need custom annotations, proprietary emoji sets, or languages not covered by a compiled plugin.

<!--- skip: next -->
```python
from disarm.emoji import FileProvider

provider = FileProvider("/path/to/custom-emoji-data.bin")
```

The binary format is a simple sequence-to-string map serialised with MessagePack or FlatBuffers. A CLI tool (`disarm-emoji-pack`) converts CLDR XML to this format.

### Registration and Selection

On the Python side, providers are registered with the core and selected per-call or globally:

<!--- skip: next -->
```python
import disarm
from disarm_emoji_15 import Emoji15Provider
from disarm_emoji_12 import Emoji12Provider

# Per-call: pass a provider explicitly
Text("I love 😂").demojize(provider=Emoji15Provider())

# Global: set a session-wide default
disarm.set_emoji_provider(Emoji12Provider())
Text("I love 😂").demojize()  # uses Emoji 12.0

# Reset to built-in default
disarm.set_emoji_provider(None)
```

On the Rust side, the global provider is stored behind a `RwLock<Arc<dyn EmojiProvider>>`, matching the existing pattern used by `LANG_TABLES` in `src/tables/mod.rs`. Per-call providers bypass the global entirely.

### Provider Chaining

For mixed-era corpora, providers can be stacked in fallback order:

<!--- skip: next -->
```python
from disarm.emoji import ChainProvider

provider = ChainProvider([
    Emoji16Provider(),    # Try newest first
    Emoji12Provider(),    # Catch emoji removed after 12.0
    EmojiLegacyProvider() # Catch pre-standard platform emoji
])

Text(old_text).demojize(provider=provider)
```

`ChainProvider` calls each provider's `lookup()` in order and returns the first non-`None` result. This handles the historical removal problem: an emoji dropped from Emoji 16.0 will still be resolved by the Emoji 12.0 provider in the chain.

## Pipeline Integration

### Position in the Processing Order

Emoji expansion slots into the existing pipeline between normalization and transliteration:

1. **Normalize** — Unicode normalization (NFC/NFD/NFKC/NFKD)
2. **Confusables** — Replace homoglyphs
3. **Demojize** — Expand emoji to text *(new)*
4. **Strip accents** — Remove combining marks
5. **Transliterate** — Convert to ASCII
6. **Fold case** — Case folding
7. **Collapse whitespace** — Whitespace normalization

This ordering is deliberate. Emoji expansion runs after normalization because some emoji sequences have NFC/NFD variants. It runs before transliteration because the expanded text (e.g. "face with tears of joy") is already ASCII and needs no further transliteration.

### Text Builder

```python
from disarm import Text

result = (Text("Hello 🌍!")
    .normalize(form="NFC")
    .demojize()
    .transliterate()
    .fold_case()
    .value)
assert result == "hello globe showing europe-africa!"
```

### TextPipeline

`TextPipeline` gains a `demojize` boolean parameter, consistent with the existing flags (`transliterate`, `confusables`, `strip_accents`, `fold_case`, `collapse_whitespace`). The pipeline uses the global provider and the `lang` already configured on the pipeline.

```python
from disarm import TextPipeline

pipe = TextPipeline(
    normalize="NFC",
    demojize=True,
    transliterate=True,
    fold_case=True,
)
assert pipe("Hello 🌍!") == "hello globe showing europe-africa!"
```

The corresponding bitflag is added to `PipelineSteps`:

<!--- rust-skip -->
```rust
const DEMOJIZE = 0b0100_0000;
```

### The `lang` Parameter

When `demojize(lang="de")` is called, the provider must supply German-language annotations. If the active provider does not support the requested language (`supports_lang()` returns `False`), the engine falls back to English. This is consistent with how `transliterate(lang=...)` falls back to the default table. In `TextPipeline`, the existing `lang` parameter applies to both `transliterate` and `demojize`.

## Output

`demojize()` always returns the bare CLDR short name as plain text. There is no `format` parameter — wrapping output in colons, brackets, or other delimiters is trivial in Python and composable with existing disarm transforms:

```python
from disarm import demojize, Text

assert demojize("I love 😂") == "I love face with tears of joy"

# Slack-style tokens — compose with slugify
assert Text("😂").demojize().slugify(separator="_").value == "face_with_tears_of_joy"
```

## Data Sourcing

All built-in and versioned plugin data derives from Unicode CLDR emoji annotations. The CLDR provides two annotation types per emoji per language:

- **Short name**: A canonical label (e.g. "grinning face"). This is what `demojize()` returns.
- **Keywords**: A set of descriptive terms (e.g. "face", "grin"). Not used in the default output but available via the provider API for advanced NLP use (topic tagging, feature expansion).

CLDR data is released under the Unicode License, which is compatible with MIT.

## Known Challenges

**Binary size.** The default English provider adds approximately 400 KB of compiled PHF data to the core crate. This is acceptable given the existing transliteration tables already contribute similar overhead. Multilingual data is deliberately kept in separate plugin crates to avoid inflating the core.

**ZWJ combinatorial explosion.** ZWJ sequences are theoretically open-ended — any base emoji can be joined with any other. In practice, only vendor-supported sequences are rendered as single glyphs. The matching engine should handle unknown ZWJ sequences gracefully (decompose into components and expand each individually) rather than treating the entire sequence as unmapped.

**Skin tone in output.** "Woman raising hand: medium-dark skin tone" is verbose. For NLP, the skin tone modifier often adds noise. A `strip_modifiers=True` option on `demojize()` would collapse all skin tone variants to their base form ("woman raising hand").

**Emoji as grapheme clusters.** Python's `len("👨‍👩‍👧‍👦")` returns 7 (codepoints), but the user sees one glyph. The matching engine operates on codepoints, not grapheme clusters, but `Text.len()` should document this discrepancy.

**Version detection heuristic.** The "auto" version mode (scan text, infer era) is expensive and unreliable — an Emoji 3.0 codepoint might appear in a 2024 document. This mode is deferred to a future release. Users should select an explicit version or use `ChainProvider` for mixed corpora.

## What This Architecture Does NOT Cover

- **Emojize** (text→emoji conversion). This is the inverse operation and is out of scope. disarm is a text normalization library; its transforms are lossy by design.
- **Emoji rendering or display.** disarm operates on codepoint sequences, not glyphs.
- **Sentiment analysis.** Mapping emoji to sentiment scores is an NLP task, not a transliteration task. Plugins provide textual descriptions only.
- **Platform-specific rendering differences.** The 🔫 codepoint maps to "water pistol" in current CLDR regardless of how it rendered on a specific platform in 2015. Historical rendering metadata is not in scope.
