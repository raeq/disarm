<!-- AUTO-GENERATED from README.md + docs/_index_nav.md -->
<!-- Do not edit directly. Run: bash scripts/generate_docs_index.sh -->

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

**[Try it in your browser](https://disarm.dev/tools/)** · **[Documentation](https://docs.disarm.dev/)** · **[API reference](api/index.md)**

## Install

```bash
pip install disarm      # Python 3.10+   (wheels for Linux, macOS, Windows)
cargo add disarm        # Rust 1.81+     (pure Rust — no Python, no pyo3)
npm install disarm      # Node.js 14+
gem install disarm      # Ruby 3.1+
```

Java & Kotlin: `dev.disarm:disarm` on Maven Central. Getting started:
[Python](python/getting-started.md) ·
[Rust](rust/getting-started.md) ·
[Ruby](ruby/getting-started.md) ·
[Node.js](node/getting-started.md) ·
[Java & Kotlin](java/getting-started.md)

## What it does

- **[Confusable folding & detection](user-guide/confusables.md)** — TR39 *visual* mapping (`normalize_confusables`, `is_confusable`), plus [`unmapped_confusables()`](user-guide/confusables.md#knowing-what-is-not-covered) so you can measure what the bundled table misses instead of assuming it
- **[Obfuscation stripping](security/adversarial-defense.md)** — bidi controls, zero-width and invisible characters, zalgo, emoji (`strip_obfuscation`)
- **[Hostname / IDN analysis](api/predicates.md#is_suspicious_hostname)** — mixed-script, whole-script-confusable and bidi checks for domains
- **[Ready-made pipelines](api/pipelines.md)** — `canonicalize`, `canonicalize_strict`, `catalog_key`, `search_key`, `ml_normalize`, and [LLM/RAG profiles](user-guide/llm-pipelines.md)
- **[Transliteration](user-guide/transliteration.md)** — standards-based for Latin/Cyrillic/Greek (BGN/PCGN, ISO 9, GOST), including reverse; best-effort [coverage](user-guide/language-support.md) for CJK, Indic, Arabic, Hebrew and more across 83 language profiles
- **[Normalization, slugs & filenames](user-guide/normalization.md)** — NFC/NFD/NFKC/NFKD, full case folding, [URL-safe slugs](user-guide/slugification.md), [cross-platform filenames](user-guide/filenames.md), [grapheme clusters](user-guide/graphemes.md), [encoding detection](api/encoding.md)

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
**[benchmark](security/adversarial-defense.md)** has the intervals and the residue this
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
[Rust guide](rust/getting-started.md), the [semver policy](RUST_API.md) and
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
([provenance](provenance.md)).

## Performance

A compiled Rust core with compile-time perfect-hash tables — no regex, no per-character
Python loops, no runtime data loading. Transliteration runs at ~450M chars/sec on Latin
(~38× Unidecode) and ~106M chars/sec on Cyrillic; slugification at ~712K slugs/sec (~10–24×
python-slugify); an already-ASCII `transliterate()` call returns the original `str` in ~65 ns
with zero allocation. Figures are hardware-dependent and directional — the methodology, the
short-string regime and the full results are in [performance.md](performance.md).

## Assurance

Beyond unit and property-based tests: `build.rs` fails the build if a table value is
non-ASCII or an entry count moves; every Hangul syllable (11,172), BMP codepoint (63,488),
CJK ideograph (20,992) and Indic block is tested individually; and seven stated invariants
(ASCII passthrough, idempotence, determinism, output bounds, …) are verified by exhaustive
enumeration and Hypothesis. Every Python example on this page is executed in CI. See
[exhaustive testing](formal-verification.md).

## Migrating

`unidecode()`, `casefold()` and `remove_accents()` aliases, `sanitize_filename()` with
pathvalidate's kwargs, and `is_confusable()` with confusable_homoglyphs' `greedy` — see the
[migration guides](migration/index.md). The `unidecode` alias is for *coverage*
compatibility only; for defense use the visual functions above.


---

## User Guide

Core concepts and usage for each feature area.

- **Getting Started** — install + quickstart for [Python](python/getting-started.md) · [Rust](rust/getting-started.md) · [Ruby](ruby/getting-started.md) · [Node.js](node/getting-started.md) · [Java & Kotlin](java/getting-started.md)
- **[Adversarial-Text Defense](security/adversarial-defense.md)** — TR39 visual confusable mapping vs phonetic transliteration, the XMR benchmark, and why it matters
- **[Transliteration](user-guide/transliteration.md)** — Unicode → ASCII with language profiles, plus reverse (Latin → native script)
- **[Slugification](user-guide/slugification.md)** — URL-safe slug generation, drop-in python-slugify replacement
- **[Normalization](user-guide/normalization.md)** — NFC / NFD / NFKC / NFKD Unicode normalization
- **[Confusable Detection](user-guide/confusables.md)** — TR39 homoglyph detection and normalization, and which sources the bundled table does not cover
- **[Filename Sanitization](user-guide/filenames.md)** — Cross-platform safe filenames
- **[Text Cleaning](user-guide/text-cleaning.md)** — Accent stripping, case folding, whitespace collapse
- **[Grapheme Clusters](user-guide/graphemes.md)** — User-perceived character counting, splitting, and truncation
- **[Text Pipeline](user-guide/pipeline.md)** — Composable, pre-compiled multi-step processing
- **[Language Support](user-guide/language-support.md)** — Built-in profiles, auto-detection, custom profiles
- **[Abjad Scripts](user-guide/abjad-transliteration.md)** — Context-aware Arabic, Persian, and Hebrew with dictionary-based vowel restoration
- **[Language Detection](user-guide/language-detection.md)** — How `lang="auto"` works: script identification, character-level discrimination, fail-safe fallbacks

---

- **[Policy Templates](policy-templates.md)** — Named institutional presets for libraries, web apps, ML, and more
- **[CLI](cli.md)** — Command-line usage, piping, and shell integration

---

## API Reference

Complete function signatures, parameters, and return types.

- **[Overview](api/index.md)** — API reference index
- **[Core Transforms](api/transforms.md)** — `transliterate`, `slugify`, `normalize`, `sanitize_filename`, `strip_accents`, `strip_zalgo`, `fold_case`, `collapse_whitespace`, `demojize`, `strip_bidi` (all accept `str` or `list[str]`)
- **[Precompiled Pipelines](api/pipelines.md)** — `canonicalize`, `ml_normalize`, `catalog_key`, `strip_format`, `search_key`, `sort_key`, `canonicalize_strict`, `PRESETS`, `get_pipeline`, `list_profiles`
- **[Classes](api/classes.md)** — `Text`, `Slugifier`, `UniqueSlugifier`, `TextPipeline`, compatibility aliases
- **[Predicates & introspection](api/predicates.md)** — `detect_scripts`, `inspect_auto_lang`, `is_mixed_script`, `is_confusable`, `is_ascii`, `is_normalized`, `is_zalgo`, `is_suspicious_hostname`, `unmapped_confusables`, `find_unmapped_confusables`
- **[Grapheme Clusters](api/graphemes.md)** — `grapheme_len`, `grapheme_split`, `grapheme_truncate`
- **[Encoding Detection](api/encoding.md)** — `detect_encoding`, `decode_to_utf8`
- **[Language Profiles](api/language-profiles.md)** — `list_langs`, `register_lang`, `register_replacements`
- **[Enums & Types](api/enums.md)** — `Script`, `NF`, `EmojiProvider`, type aliases, language constants
- **[Exceptions](api/exceptions.md)** — `DisarmError`

---

## Reference

- **[Language Reference](reference.md)** — All languages: codes, names, reference texts, and per-language transliteration rule tables
- **[Provenance](provenance.md)** — Standards and sources behind every transliteration mapping

---

## Architecture

Internal design documentation for contributors and advanced users.

- **[Transliteration Engine](architecture/transliteration-engine.md)** — PHF lookup, language table chain, Indic virama handling
- **[Data Tables](architecture/data-tables.md)** — TSV format, build.rs code generation, compile-time PHF
- **[Pipeline](architecture/pipeline.md)** — TextPipeline internals, execution order, step bitflags
- **[Emoji Engine](architecture/emoji-engine.md)** — Emoji detection, the `EmojiProvider` protocol and custom providers, pure-Rust path
- **[Security](architecture/security.md)** — Confusable detection, hostname validation, bidi stripping
- **[Performance](architecture/performance.md)** — Optimization strategies, PHF tables, batch amortization
- **[Testing & Guarantees](architecture/testing-guarantees.md)** — Test philosophy, property-based testing, security invariants, CI matrix
- **[Exhaustive Testing](formal-verification.md)** — Compile-time assertions, exhaustive domain coverage, stated invariants (I1–I7)
- **[Transliteration Comparison](architecture/transliteration-comparison.md)** — Character-level diff vs Unidecode and anyascii

---

## Benchmarks

- **[Performance Overview](performance.md)** — Benchmark results: throughput and per-call speedups vs Unidecode, python-slugify, and pathvalidate
- **[Benchmark Suite](benchmarks.md)** — How to run benchmarks, Criterion and timeit configurations

---

## Migration Guides

Parameter-compatible replacements for existing libraries.

- **[Migration Overview](migration/index.md)** — Feature comparison matrix
- **[From Unidecode / text-unidecode](migration/from-unidecode.md)** — Drop-in `unidecode()` alias
- **[From python-slugify / awesome-slugify](migration/from-python-slugify.md)** — Parameter-compatible `slugify()`
- **[From confusable_homoglyphs](migration/from-confusable-homoglyphs.md)** — Script detection and normalization
- **[From pathvalidate](migration/from-pathvalidate.md)** — Filename sanitization
- **[From anyascii](migration/from-anyascii.md)** — Language-aware transliteration

---

## Other

- **[Limitations](limitations.md)** — Known constraints, edge cases, and design trade-offs
