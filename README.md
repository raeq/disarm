# disarm

[![PyPI](https://img.shields.io/pypi/v/disarm?color=blue)](https://pypi.org/project/disarm/) [![Crates.io](https://img.shields.io/crates/v/disarm?color=blue)](https://crates.io/crates/disarm) [![Documentation](https://img.shields.io/badge/docs-disarm.dev-blue)](https://docs.disarm.dev/) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/raeq/disarm/blob/main/LICENSE)

**Identify malicious attacks hiding in text.**

`раypal.com` — Cyrillic `а` (U+0430) and `р` (U+0440) — renders identically to
`paypal.com` and is a different string. disarm finds that substitution and folds it back to
its Unicode [TR39](https://www.unicode.org/reports/tr39/) prototype, strips bidi overrides,
zero-width and control characters, and flags spoofed hostnames — the Unicode layer your
validation, dedup, moderation and logging code is missing.

One pure-Rust core, with bindings for **Python, Rust, Ruby, Node.js, Java/Kotlin and C**.

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

- **[Confusable folding](docs/user-guide/confusables.md)** — TR39 visual mapping, plus what it misses
- **[Obfuscation stripping](docs/security/adversarial-defense.md)** — bidi controls, zero-width characters, zalgo, emoji
- **[Hostname / IDN analysis](docs/api/predicates.md#is_suspicious_hostname)** — mixed-script, whole-script and bidi checks
- **[Ready-made pipelines](docs/api/pipelines.md)** — `canonicalize`, `catalog_key`, `search_key`, LLM and RAG profiles
- **[Transliteration](docs/user-guide/transliteration.md)** — BGN/PCGN, ISO 9 and GOST; 83 language profiles
- **[Normalization, slugs & filenames](docs/user-guide/normalization.md)** — case folding, graphemes, encoding detection
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

**Does it work?** On the XMR confusable-recovery metric, disarm's *visual* mapping scores
**0.63–0.68**, against **≤ 0.19** for *phonetic* transliterators (`unidecode`, `anyascii`,
`uroman`) and **0.10** for NFKC. →
[the evidence](https://docs.disarm.dev/security/adversarial-defense.html#evidence) ·
[what it misses](https://docs.disarm.dev/security/adversarial-defense.html#coverage-and-limits)

**What does it cost?** ~450M chars/sec on Latin (~38× Unidecode), ~106M on Cyrillic, ~712K
slugs/sec (~10–24× python-slugify), ~65 ns for an already-ASCII call. Hardware-dependent and
directional, not guarantees. →
[full results](https://docs.disarm.dev/performance.html#results) ·
[how to read them](https://docs.disarm.dev/performance.html#how-to-read-these-numbers) ·
[where disarm is slower](https://docs.disarm.dev/performance.html#where-disarm-is-slower)

Both come from *"Fire Extinguishers Full of Gasoline"*: 435,864 observations over eight
tools, six attack types, three tasks and two model architectures.
[Zenodo](https://doi.org/10.5281/zenodo.20618323) ·
[CITATION.cff](https://github.com/raeq/disarm/blob/main/CITATION.cff)

## Bindings: one core, six languages

Each binding reads like its own ecosystem — `snake_case` in Ruby, `camelCase` and `.d.ts` in
Node, builders in Java — over one shared core, so every language returns the same answer.

| Language | Package | Getting started |
|---|---|---|
| Python 3.10+ | `disarm` on [PyPI](https://pypi.org/project/disarm/) | [guide](docs/python/getting-started.md) |
| Rust 1.81+ | `disarm` on [crates.io](https://crates.io/crates/disarm) | [guide](docs/rust/getting-started.md) · [docs.rs](https://docs.rs/disarm) |
| Ruby 3.1+ | `disarm` on RubyGems | [guide](docs/ruby/getting-started.md) |
| Node.js 14+ | `disarm` on npm | [guide](docs/node/getting-started.md) |
| Java / Kotlin | `dev.disarm:disarm`, `dev.disarm:disarm-kotlin` on Maven Central | [guide](docs/java/getting-started.md) |
| C / other FFI | C ABI and `disarm.h` | [bindings/cabi](https://github.com/raeq/disarm/tree/main/bindings/cabi) |

Wheels, gems and addons are precompiled — no local Rust toolchain needed. The core crate is
`unsafe_code = "forbid"` and stays pure Rust; [BINDINGS.md](BINDINGS.md) is the bar a new
binding has to meet.

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

Found a bypass? Report it under the [security policy](SECURITY.md) rather than in a public
issue.

## Links

| | |
|---|---|
| **Documentation** | <https://docs.disarm.dev/> |
| **Source code** | <https://github.com/raeq/disarm> |
| **PyPI package** | <https://pypi.org/project/disarm/> |
| **Rust crate** | <https://crates.io/crates/disarm> |
| **Issue tracker** | <https://github.com/raeq/disarm/issues> |
| **Security policy** | <https://github.com/raeq/disarm/blob/main/SECURITY.md> |
| **Contributing** | <https://github.com/raeq/disarm/blob/main/CONTRIBUTING.md> |
| **Changelog** | <https://github.com/raeq/disarm/blob/main/CHANGELOG.md> |

## License

MIT
