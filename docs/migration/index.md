# Why Migrate to translit?

translit consolidates 8+ legacy Python Unicode text-processing libraries into a single, fast, MIT-licensed package — and, unlike any of them, provides **TR39 confusable analysis** as a first-class capability, a building block for [adversarial-text defense](../security/adversarial-defense.md).

> **If you use `unidecode` (or `ftfy`/`anyascii`) as a security/sanitization step, you should migrate for correctness, not just convenience.** Those tools map confusables *phonetically* and cannot reverse homoglyph attacks; `unidecode` can even degrade results. translit maps *visually* per TR39. See [From Unidecode](from-unidecode.md#unidecode-is-not-a-security-tool).

## The problem

A typical Django or Flask project that handles international text might depend on several of these packages:

| Package | Weekly downloads | License | Purpose |
|---|---|---|---|
| Unidecode | ~8M | GPL-2.0 | Unicode → ASCII |
| text-unidecode | ~6M | Artistic-1.0 | Unicode → ASCII |
| python-slugify | ~7M | MIT | Slug generation |
| awesome-slugify | ~50K | GPL-3.0 | Slug generation |
| anyascii | ~1M | ISC | Unicode → ASCII |
| confusable_homoglyphs | ~200K | MIT | Homoglyph detection |
| pathvalidate | ~2M | MIT | Filename sanitization |
| unicodedata2 | ~500K | PSF | Updated Unicode data |

That's 8 transitive dependencies, 4 different licenses (including GPL), and 8 different APIs to learn.

## The solution

translit replaces all of them with one import:

```python
# Before: 8 imports
from unidecode import unidecode
from slugify import slugify
from confusable_homoglyphs import confusables
import pathvalidate

# After: 1 import
import translit
```

## Comparison

| Feature | Legacy | translit |
|---|---|---|
| **Performance** | Pure Python | Rust via PyO3 ([benchmarks](../performance.md)) |
| **License** | Mixed GPL/Artistic/MIT | MIT |
| **API** | 8 different APIs | One coherent API |
| **Language profiles** | 0–5 languages | 83 built-in |
| **Type safety** | Partial | Full py.typed + stubs |
| **Adversarial defense (TR39)** | None | Built in — visual confusable mapping |
| **Confusable detection** | Separate package | Built in |
| **Filename sanitization** | Separate package | Built in |
| **Unicode version** | Varies (often outdated) | Current |

## Migration guides

Step-by-step migration from each legacy library:

- [From Unidecode / text-unidecode](from-unidecode.md) — drop-in `unidecode()` alias
- [From python-slugify / awesome-slugify](from-python-slugify.md) — parameter-compatible `slugify()`
- [From confusable_homoglyphs](from-confusable-homoglyphs.md)
- [From pathvalidate](from-pathvalidate.md)
- [From anyascii](from-anyascii.md)
