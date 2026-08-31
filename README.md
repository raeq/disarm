# disarm

[![PyPI](https://img.shields.io/pypi/v/disarm?color=blue)](https://pypi.org/project/disarm/) [![Crates.io](https://img.shields.io/crates/v/disarm?color=blue)](https://crates.io/crates/disarm) [![Documentation](https://img.shields.io/badge/docs-disarm.dev-blue)](https://docs.disarm.dev/) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/raeq/disarm/blob/main/LICENSE)

**Make text that *looks* the same *compare* the same.**

`раypal.com` and `paypal.com` render identically and are different strings. disarm folds
those look-alikes to their Unicode [TR39](https://www.unicode.org/reports/tr39/) prototypes,
strips bidi overrides, zero-width and control characters, and flags spoofed hostnames — the
Unicode layer your validation, dedup, moderation and logging code is missing.

One pure-Rust core, with bindings for **Python, Rust, Ruby, Node.js, Java/Kotlin and C**.

```python
from disarm import canonicalize, is_suspicious_hostname

# One call for untrusted input: folds homoglyphs, removes bidi overrides,
# zero-width and control characters.
assert canonicalize("‮example​.com") == "example.com"
assert canonicalize("Ηello Ꮤorld") == "Hello World"  # Greek Η, Cherokee Ꮤ

# Analyse a hostname instead of rewriting it.
suspicious, analysis = is_suspicious_hostname("аpple.com")  # leading Cyrillic а
assert suspicious and analysis.canonical == "apple.com"
```

**[Try it in your browser](https://disarm.dev/tools/)** · **[Documentation](https://docs.disarm.dev/)** · **[API reference](docs/api/index.md)**

## Install

```bash
pip install disarm      # Python 3.10+   (wheels for Linux, macOS, Windows)
cargo add disarm        # Rust 1.81+     (pure Rust — no Python, no pyo3)
npm install disarm      # Node.js 14+
gem install disarm      # Ruby 3.1+
```

Java & Kotlin: `dev.disarm:disarm` on Maven Central. Getting started:
[Python](docs/python/getting-started.md) ·
[Rust](docs/rust/getting-started.md) ·
[Ruby](docs/ruby/getting-started.md) ·
[Node.js](docs/node/getting-started.md) ·
[Java & Kotlin](docs/java/getting-started.md)

## What it does

- **[Confusable folding & detection](docs/user-guide/confusables.md)** — TR39 *visual* mapping (`normalize_confusables`, `is_confusable`), plus [`unmapped_confusables()`](docs/user-guide/confusables.md#knowing-what-is-not-covered) so you can measure what the bundled table misses instead of assuming it
- **[Obfuscation stripping](docs/security/adversarial-defense.md)** — bidi controls, zero-width and invisible characters, zalgo, emoji (`strip_obfuscation`)
- **[Hostname / IDN analysis](docs/api/predicates.md#is_suspicious_hostname)** — mixed-script, whole-script-confusable and bidi checks for domains
- **[Ready-made pipelines](docs/api/pipelines.md)** — `canonicalize`, `canonicalize_strict`, `catalog_key`, `search_key`, `ml_normalize`, and [LLM/RAG profiles](docs/user-guide/llm-pipelines.md)
- **[Transliteration](docs/user-guide/transliteration.md)** — standards-based for Latin/Cyrillic/Greek (BGN/PCGN, ISO 9, GOST), including reverse; best-effort [coverage](docs/user-guide/language-support.md) for CJK, Indic, Arabic, Hebrew and more across 83 language profiles
- **[Normalization, slugs & filenames](docs/user-guide/normalization.md)** — NFC/NFD/NFKC/NFKD, full case folding, [URL-safe slugs](docs/user-guide/slugification.md), [cross-platform filenames](docs/user-guide/filenames.md), [grapheme clusters](docs/user-guide/graphemes.md), [encoding detection](docs/api/encoding.md)

```python
from disarm import slugify, strip_obfuscation, transliterate

assert strip_obfuscation("рroduсt") == "product"    # visual: Cyrillic р, с → p, c
assert transliterate("Київ", lang="uk") == "Kyiv"   # phonetic: BGN/PCGN romanization
assert slugify("Héllo Wörld") == "hello-world"
```

## Why not `unidecode` or `ftfy`?

The text-cleaning libraries already in most pipelines map confusables *phonetically* —
Cyrillic `р` becomes `r` — because they were built for encoding repair and ASCII conversion.
That leaves the spoof in place: `р` *sounds* like `r` but *looks* like `p`. disarm's TR39
mapping is *visual*, so it reverses the substitution. Over a broad sample of the TR39
confusable space it recovers **XMR 0.63–0.68**, where phonetic tools stay at or below
**0.19** and NFKC reaches **0.10** — the
**[benchmark](docs/security/adversarial-defense.md)** has the intervals and the residue this
leaves.

## Use from Rust

```rust
use disarm::api::{self, TargetScript};

// Visual (TR39) confusable folding — homoglyph defence
assert_eq!(api::normalize_confusables("раypal", TargetScript::Latin), "paypal");
// Phonetic romanization — readable ASCII, not a security control
assert_eq!(api::transliterate("Москва"), "Moskva");
assert!(api::is_suspicious_hostname("раypal.com").suspicious);
```

The public surface is [`disarm::api`](https://docs.rs/disarm/latest/disarm/api/) plus the
error types, and the [`DisarmStr`](https://docs.rs/disarm/latest/disarm/trait.DisarmStr.html)
trait gives the same operations method syntax. The crate is `unsafe_code = "forbid"`; the
`extension-module` feature (which pulls in `pyo3`) exists only to build the Python wheel.
Optional `log` feature emits metadata-only diagnostics, never your text. See the
[Rust guide](docs/rust/getting-started.md), the [semver policy](docs/RUST_API.md) and
[docs.rs/disarm](https://docs.rs/disarm).

## Scope — read this before you depend on it

> - **Defense in depth, not a complete control.** disarm folds the confusables it bundles
>   and strips the format characters it enumerates. The confusable space is larger than any
>   table, so measure your residue with `unmapped_confusables()` rather than inferring it.
>   [Threat model](THREAT_MODEL.md).
> - **Not an output sanitizer.** disarm normalizes *input*. It performs no escaping —
>   `<script>alert(1)</script>` passes through unchanged, and NFKC can even *surface* ASCII
>   metacharacters from fullwidth look-alikes. Keep encoding at the output sink (framework
>   auto-escaping, DOMPurify, parameterized queries); run disarm before it.
> - **`transliterate()` is not a security control.** It romanizes phonetically. For
>   homoglyph defense use `normalize_confusables()` / `strip_obfuscation()`.

`CONFUSABLES_VERSION` reports which `confusables.txt` release the bundled tables were folded
from, so a deployment can answer "am I stale?" without inferring it from behaviour
([provenance](docs/provenance.md)).

## Performance

A compiled Rust core with compile-time perfect-hash tables — no regex, no per-character
Python loops, no runtime data loading. Transliteration runs at ~450M chars/sec on Latin
(~38× Unidecode) and ~106M chars/sec on Cyrillic; slugification at ~712K slugs/sec (~10–24×
python-slugify); an already-ASCII `transliterate()` call returns the original `str` in ~65 ns
with zero allocation. Figures are hardware-dependent and directional — the methodology, the
short-string regime and the full results are in [docs/performance.md](docs/performance.md).

## Assurance

Beyond unit and property-based tests: `build.rs` fails the build if a table value is
non-ASCII or an entry count moves; every Hangul syllable (11,172), BMP codepoint (63,488),
CJK ideograph (20,992) and Indic block is tested individually; and seven stated invariants
(ASCII passthrough, idempotence, determinism, output bounds, …) are verified by exhaustive
enumeration and Hypothesis. Every Python example on this page is executed in CI. See
[exhaustive testing](docs/formal-verification.md).

## Migrating

`unidecode()`, `casefold()` and `remove_accents()` aliases, `sanitize_filename()` with
pathvalidate's kwargs, and `is_confusable()` with confusable_homoglyphs' `greedy` — see the
[migration guides](docs/migration/index.md). The `unidecode` alias is for *coverage*
compatibility only; for defense use the visual functions above.

## Architecture

Rust core with compile-time PHF (perfect hash function) tables for O(1) per-character lookup,
exposed to Python via PyO3 with the stable ABI (abi3-py39). The Chinese pinyin table contains
20,924 entries from the Unicode Unihan database; Korean romanization is purely algorithmic
(jamo decomposition, ~100 lines of Rust).

## Links

| | |
|---|---|
| **Documentation** | <https://docs.disarm.dev/> |
| **Source code** | <https://github.com/raeq/disarm> |
| **PyPI package** | <https://pypi.org/project/disarm/> |
| **Rust crate** | <https://crates.io/crates/disarm> |
| **Issue tracker** | <https://github.com/raeq/disarm/issues> |
| **Changelog** | <https://github.com/raeq/disarm/blob/main/CHANGELOG.md> |

## License

MIT
