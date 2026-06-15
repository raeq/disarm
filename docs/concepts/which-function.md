# Which function do I want?

This is the most important distinction in disarm, and the one newcomers most
often get wrong. disarm performs **two different mappings** that look similar but
are opposites, backed by two separate tables.

The common mistake is reaching for `transliterate` to defend against homoglyph
spoofing. It does the **opposite** mapping — it will turn a Cyrillic `р` into
`r` and leave the spoof readable.

| If you want to… | Use | Mapping | Example |
|---|---|---|---|
| **Defend against homoglyph / look-alike spoofing** | `normalize_confusables`, `strip_obfuscation` | **visual** (Unicode [TR39](https://www.unicode.org/reports/tr39/)) | Cyrillic `р` → Latin **`p`** |
| **Romanize text to readable ASCII** | `transliterate` | **phonetic / standards-based** (BGN/PCGN, ISO 9, GOST) | Cyrillic `р` → Latin **`r`**; `Київ` → `Kyiv` (`uk` profile) |
| **Flag spoofed hostnames / IDNs** | `is_suspicious_hostname` | analysis (no rewrite) | `аpple.com` → suspicious |

## Visual mapping — for security

`normalize_confusables` and `strip_obfuscation` fold *visually confusable*
characters to their prototypes, per Unicode TR39. A Cyrillic `р` (U+0440) and a
Latin `p` (U+0070) look identical, so the visual mapping sends the Cyrillic one
to `p`. This is what reverses a homoglyph substitution, and it is the basis of
disarm's [adversarial-text defence](../security/adversarial-defense.md).

## Phonetic mapping — for readability

`transliterate` is a **romanizer**: it maps by sound and by transliteration
standard, not by appearance. It sends Cyrillic `р` to `r` (its phonetic value),
producing readable ASCII like `Київ` → `Kyiv` (with the `uk` language profile).
This is the right tool for
catalog keys, slugs, and search indexing — but it is **not** a security control,
because it leaves a look-alike spoof intact.

## Rule of thumb

> If the goal is **"is this text trying to fool a human or a matcher?"**, use the
> **visual** functions. If the goal is **"make this text readable / indexable in
> ASCII"**, use **`transliterate`**. When in doubt, normalize confusables first,
> then transliterate.

The function names above are shared across every binding; only the spelling and
call convention change per language (see your language's *Getting started* page).
