# disarm

[![PyPI](https://img.shields.io/pypi/v/disarm?color=blue)](https://pypi.org/project/disarm/) [![Crates.io](https://img.shields.io/crates/v/disarm?color=blue)](https://crates.io/crates/disarm) [![Documentation](https://img.shields.io/badge/docs-disarm.dev-blue)](https://docs.disarm.dev/) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/raeq/disarm/blob/main/LICENSE)

**Identify malicious attacks hiding in text.**

`раypal.com` — Cyrillic `а` (U+0430) and `р` (U+0440) — renders identically to
`paypal.com` and is a different string. disarm finds that substitution and folds it back to
its Unicode [TR39](https://www.unicode.org/reports/tr39/) prototype, strips bidi overrides,
zero-width and control characters, and flags spoofed hostnames — the Unicode layer your
validation, dedup, moderation and logging code is missing.

One pure-Rust core, with bindings for **Python, Rust, Ruby, Node.js, Java/Kotlin and C**.

Every attack below is written with escapes, because that is the whole problem: pasted as
literal characters, these strings are indistinguishable from the clean ones on this page.

```python
from disarm import canonicalize, is_suspicious_hostname

# U+202E is a right-to-left override and U+200B a zero-width space. Neither is
# visible, and both survive a copy-paste straight into your database.
assert canonicalize("\u202eexample\u200b.com") == "example.com"

# U+0397 is Greek capital eta and U+13D4 Cherokee letter wa. They render as H and W.
assert canonicalize("\u0397ello \u13d4orld") == "Hello World"

# Cyrillic small a (U+0430) standing in for Latin a: renders as "apple.com".
suspicious, analysis = is_suspicious_hostname("\u0430pple.com")
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

## disarm capabilities

- **[Confusable folding & detection](docs/user-guide/confusables.md)** — TR39 *visual* mapping (`normalize_confusables`, `is_confusable`), plus [`unmapped_confusables()`](docs/user-guide/confusables.md#knowing-what-is-not-covered) so you can measure what the bundled table misses instead of assuming it
- **[Obfuscation stripping](docs/security/adversarial-defense.md)** — bidi controls, zero-width and invisible characters, zalgo, emoji (`strip_obfuscation`)
- **[Hostname / IDN analysis](docs/api/predicates.md#is_suspicious_hostname)** — mixed-script, whole-script-confusable and bidi checks for domains
- **[Ready-made pipelines](docs/api/pipelines.md)** — `canonicalize`, `canonicalize_strict`, `catalog_key`, `search_key`, `ml_normalize`, and [LLM/RAG profiles](docs/user-guide/llm-pipelines.md)
- **[Transliteration](docs/user-guide/transliteration.md)** — standards-based for Latin/Cyrillic/Greek (BGN/PCGN, ISO 9, GOST), including reverse; best-effort [coverage](docs/user-guide/language-support.md) for CJK, Indic, Arabic, Hebrew and more across 83 language profiles
- **[Normalization, slugs & filenames](docs/user-guide/normalization.md)** — NFC/NFD/NFKC/NFKD, full case folding, [URL-safe slugs](docs/user-guide/slugification.md), [cross-platform filenames](docs/user-guide/filenames.md), [grapheme clusters](docs/user-guide/graphemes.md), [encoding detection](docs/api/encoding.md)

```python
from disarm import canonicalize, collapse_whitespace, slugify, strip_obfuscation, transliterate

# Cyrillic er (U+0440) and es (U+0441) folded to Latin p and c — visual (TR39) mapping.
assert strip_obfuscation("\u0440rodu\u0441t") == "product"

# No-break space (U+00A0), ideographic space (U+3000), thin space (U+2009) and a
# line separator (U+2028) all collapse to one plain ASCII space.
assert collapse_whitespace("Ada\u00a0\u3000Lovelace\u2009\u2028King") == "Ada Lovelace King"

# Their zero-width look-alikes are not whitespace at all — U+200B and U+FEFF are
# format characters, so neither str.split() nor collapse_whitespace touches them.
assert collapse_whitespace("A\u200bB\ufeffC") == "A\u200bB\ufeffC"
assert canonicalize("A\u200bB\ufeffC") == "ABC"

# Phonetic romanization: a different mapping, and not a defence.
assert transliterate("Київ", lang="uk") == "Kyiv"
assert slugify("Héllo Wörld") == "hello-world"
```

## Performance & benchmarks

Two things get measured, because a fold that is fast and wrong is worthless: whether the
mapping actually reverses an attack, and what it costs per character.

**Does it work?** On the XMR confusable-recovery metric, measured over a broad sample of the
TR39 space, disarm's *visual* mapping scores **0.63–0.68** against **≤ 0.19** for *phonetic*
transliterators (`unidecode`, `anyascii`, `uroman`) and **0.10** for NFKC — from a study of
435,864 observations across six attack types, three downstream tasks and two model
architectures. →
[the evidence](https://docs.disarm.dev/security/adversarial-defense.html#evidence) ·
[what it does not cover](https://docs.disarm.dev/security/adversarial-defense.html#coverage-and-limits)

**What does it cost?** ~450M chars/sec transliterating Latin (~38× Unidecode), ~106M
chars/sec on Cyrillic, ~712K slugs/sec (~10–24× python-slugify), and ~65 ns for an
already-ASCII call, which returns the original `str` with zero allocation. Figures are
hardware-dependent and directional, not guarantees. →
[full results](https://docs.disarm.dev/performance.html#results) ·
[how to read them](https://docs.disarm.dev/performance.html#how-to-read-these-numbers) ·
[where disarm is slower](https://docs.disarm.dev/performance.html#where-disarm-is-slower)

## One core, six languages

The Rust core does the work; each binding is a native-feeling API over it, not a
transliterated one — `snake_case` and `?` predicates in Ruby, `camelCase` with options
objects and `.d.ts` types in Node, builders and a `DisarmException` hierarchy in Java,
`String` extensions in Kotlin. The *behaviour* is shared, so a fold in Python and a fold in
Ruby give the same answer; the *surface* is the ecosystem's every time.

| Language | Package | Getting started |
|---|---|---|
| Python 3.10+ | `disarm` on [PyPI](https://pypi.org/project/disarm/) | [guide](docs/python/getting-started.md) |
| Rust 1.81+ | `disarm` on [crates.io](https://crates.io/crates/disarm) | [guide](docs/rust/getting-started.md) · [docs.rs](https://docs.rs/disarm) |
| Ruby 3.1+ | `disarm` on RubyGems | [guide](docs/ruby/getting-started.md) |
| Node.js 14+ | `disarm` on npm | [guide](docs/node/getting-started.md) |
| Java / Kotlin | `dev.disarm:disarm`, `dev.disarm:disarm-kotlin` on Maven Central | [guide](docs/java/getting-started.md) |
| C / other FFI | C ABI and `disarm.h` | [bindings/cabi](https://github.com/raeq/disarm/tree/main/bindings/cabi) |

Wheels, gems and native addons are precompiled, so no binding needs a local Rust toolchain.
The core crate is `unsafe_code = "forbid"`, and its `extension-module` feature exists only to
build the Python wheel — Rust consumers get pure Rust. What a new binding must deliver is
written down in [BINDINGS.md](BINDINGS.md).

## Limitations: read this before deploying disarm

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
