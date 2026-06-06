# Migrating from Unidecode

translit provides a drop-in replacement for both [Unidecode](https://pypi.org/project/Unidecode/) and [text-unidecode](https://pypi.org/project/text-unidecode/).

## Quick migration

### Option 1: Drop-in alias

```python
# Before
from unidecode import unidecode

# After — one-line change
from translit import unidecode
```

The `translit.unidecode()` function is a direct alias for `transliterate()` with default settings. It accepts a single string argument and returns ASCII text.

> **Coverage compatibility, not endorsement.** The alias exists to make migration a
> one-line change. It is the right tool for romanization (slugs, ASCII keys,
> search-fold) — but the *wrong* tool for security. See
> [Unidecode is not a security tool](#unidecode-is-not-a-security-tool) below.

### Option 2: Use transliterate directly

```python
# Before
from unidecode import unidecode
result = unidecode("café")

# After
from translit import transliterate
result = transliterate("café")
```

`transliterate()` provides additional features not available in Unidecode:

```python
# Language-specific transliteration
transliterate("München", lang="de")          # => "Muenchen"

# Error handling modes
transliterate("♠", errors="ignore")          # => ""
transliterate("♠", errors="preserve")        # => "♠"
transliterate("♠", errors="replace",
              replace_with="?")              # => "?"
```

## API comparison

| Unidecode | translit | Notes |
|---|---|---|
| `unidecode(s)` | `unidecode(s)` | Direct alias |
| `unidecode(s)` | `transliterate(s)` | Full-featured alternative |
| `unidecode_expect_ascii(s)` | `transliterate(s, errors="replace")` | Default behavior |
| `unidecode_expect_nonascii(s)` | `transliterate(s, errors="preserve")` | Keep unmapped chars |

## Behavioral differences

### Transliteration tables

translit uses its own hand-curated transliteration tables. Most common mappings are identical to Unidecode, but some edge cases may differ. A [detailed character-level comparison](../architecture/transliteration-comparison.md) across all 83 supported languages shows:

- **49,089 codepoints** across all Unicode blocks tested comprehensively (no sampling)
- **48,415** mapped by translit vs **47,408** by Unidecode — translit has broader coverage overall, with 1,136 characters only translit maps vs 129 only Unidecode maps
- Most differences are systematic: CJK pinyin casing (~20K), Korean romanization (~3.7K), inherent vowel handling in Brahmic scripts, and language-specific national standards

```python
# Identical in both
unidecode("café")       # => "cafe"
unidecode("北京")       # => "bei jing"

# May differ for obscure characters
# translit aims for more linguistically accurate results
```

### License

| | Unidecode | text-unidecode | translit |
|---|---|---|---|
| License | GPL-2.0 | Artistic-1.0 | MIT |

If your project requires MIT licensing, translit is a safe replacement.

## Unidecode is not a security tool

If you reach for `unidecode` to "sanitize" untrusted text — to strip homoglyphs,
invisible characters, or other Unicode trickery — switch to translit's defense
functions, and not just for the speed.

Unidecode (like `anyascii`, `cyrtranslit`, `uroman`) maps confusable characters
**phonetically**: Cyrillic `р` (U+0440) → Latin `r`, by sound. A homoglyph attacker
replaces Latin `p` with the identical-looking Cyrillic `р`, so phonetic mapping yields
`r` — *not* the original `p` — and the attack survives. Worse, on invisible-character
attacks `unidecode` expands zero-width characters into visible ASCII sequences,
introducing spurious tokens that can *degrade* downstream model accuracy.

translit maps **visually** per [Unicode TR39](https://www.unicode.org/reports/tr39/)
(Cyrillic `р` → Latin `p`), which actually reverses the substitution. In a controlled
benchmark, visual TR39 mapping achieves perfect homoglyph recovery where phonetic tools
recover roughly half.

```python
# Wrong tool for defense — phonetic mapping, attack survives
from translit import unidecode
unidecode("рroduсt")       # → "rrodust"  (р→r, с→s by sound — the spoof is NOT reversed)

# Right tools — visual TR39 mapping
from translit import strip_obfuscation, normalize_confusables
normalize_confusables("рroduсt")   # → "product"
strip_obfuscation("рroduсt")       # → "product"  (also strips zalgo/bidi/invisible/emoji)
```

See [Adversarial-Text Defense](../security/adversarial-defense.md) for the full
evidence and the XMR benchmark.

## text-unidecode migration

text-unidecode has the same API as Unidecode. The migration is identical:

```python
# Before
from text_unidecode import unidecode

# After
from translit import unidecode
```
