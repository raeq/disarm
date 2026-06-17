# Migrating from Unidecode

disarm provides a drop-in replacement for both [Unidecode](https://pypi.org/project/Unidecode/) and [text-unidecode](https://pypi.org/project/text-unidecode/).

> **Already wrapping `unidecode` in a pipeline?** Most hand-rolled
> `unidecode(...)` pipelines (slugs, filenames, search keys, URL-encoding) have a
> single-call disarm equivalent. See [Unidecode → disarm
> recipes](unidecode-recipes.md) for the pattern-by-pattern mapping.

## Quick migration

### Option 1: Drop-in alias

<!--- skip: next -->
```python
# Before
from unidecode import unidecode

# After — one-line change
from disarm import unidecode
```

The `disarm.unidecode()` function is a direct alias for `transliterate()` with default settings. It accepts a single string argument and returns ASCII text.

> **Coverage compatibility, not endorsement.** The alias exists to make migration a
> one-line change. It is the right tool for romanization (slugs, ASCII keys,
> search-fold) — but the *wrong* tool for security. See
> [Unidecode is not a security tool](#unidecode-is-not-a-security-tool) below.

### Option 2: Use transliterate directly

<!--- skip: next -->
```python
# Before
from unidecode import unidecode
result = unidecode("café")

# After
from disarm import transliterate
result = transliterate("café")
```

`transliterate()` provides additional features not available in Unidecode:

```python
from disarm import transliterate

# Language-specific transliteration
assert transliterate("München", lang="de") == 'Muenchen'

# Error handling modes
assert transliterate("♠", errors="ignore") == ''
assert transliterate("♠", errors="preserve") == '♠'
assert transliterate("♠", errors="replace",
              replace_with="?") == '?'
```

## API comparison

| Unidecode | disarm | Notes |
|---|---|---|
| `unidecode(s)` | `unidecode(s)` | Direct alias |
| `unidecode(s)` | `transliterate(s)` | Full-featured alternative |
| `unidecode_expect_ascii(s)` | `transliterate(s, errors="replace")` | Default behavior |
| `unidecode_expect_nonascii(s)` | `transliterate(s, errors="preserve")` | Keep unmapped chars |

## Behavioral differences

### Transliteration tables

disarm uses its own hand-curated transliteration tables. Most common mappings are identical to Unidecode, but some edge cases may differ. A [detailed character-level comparison](../architecture/transliteration-comparison.md) across all 83 supported languages shows:

- **49,089 codepoints** across all Unicode blocks tested comprehensively (no sampling)
- **48,415** mapped by disarm vs **47,408** by Unidecode — disarm has broader coverage overall, with 1,136 characters only disarm maps vs 129 only Unidecode maps
- Most differences are systematic: CJK pinyin casing (~20K), Korean romanization (~3.7K), inherent vowel handling in Brahmic scripts, and language-specific national standards

```python
from disarm import unidecode

# Identical in both
assert unidecode("café") == 'cafe'
assert unidecode("北京") == 'bei jing'

# May differ for obscure characters
# disarm aims for more linguistically accurate results
```

### License

| | Unidecode | text-unidecode | disarm |
|---|---|---|---|
| License | GPL-2.0 | Artistic-1.0 | MIT |

If your project requires MIT licensing, disarm is a safe replacement.

## Unidecode is not a security tool

If you reach for `unidecode` to "sanitize" untrusted text — to strip homoglyphs,
invisible characters, or other Unicode trickery — switch to disarm's defense
functions, and not just for the speed.

Unidecode (like `anyascii`, `cyrtranslit`, `uroman`) maps confusable characters
**phonetically**: Cyrillic `р` (U+0440) → Latin `r`, by sound. A homoglyph attacker
replaces Latin `p` with the identical-looking Cyrillic `р`, so phonetic mapping yields
`r` — *not* the original `p` — and the attack survives. Worse, on invisible-character
attacks `unidecode` expands zero-width characters into visible ASCII sequences,
introducing spurious tokens that can *degrade* downstream model accuracy.

disarm maps **visually** per [Unicode TR39](https://www.unicode.org/reports/tr39/)
(Cyrillic `р` → Latin `p`), which reverses the substitution **for confusables in the TR39
table**. Measured over a broad sample of the TR39 confusable space (1,314 single-codepoint
sources), visual TR39 mapping recovers XMR 0.634 / 0.682 (95% CI 0.603–0.664 / 0.652–0.710)
— neutralizing ~95% of sources — where phonetic tools stay at or below 0.19
([XMR v2 note](https://doi.org/10.5281/zenodo.20618323)).
It is a defense-in-depth layer, not a complete control — see the
[Threat Model](https://github.com/raeq/disarm/blob/main/THREAT_MODEL.md).

```python
# Wrong tool for defense — phonetic mapping, attack survives
from disarm import unidecode
assert unidecode("рroduсt") == 'rrodust'

# Right tools — visual TR39 mapping
from disarm import strip_obfuscation, normalize_confusables
assert normalize_confusables("рroduсt") == 'product'
assert strip_obfuscation("рroduсt") == 'product'
```

See [Adversarial-Text Defense](../security/adversarial-defense.md) for the full
evidence and the XMR benchmark.

## text-unidecode migration

text-unidecode has the same API as Unidecode. The migration is identical:

<!--- skip: next -->
```python
# Before
from text_unidecode import unidecode

# After
from disarm import unidecode
```
