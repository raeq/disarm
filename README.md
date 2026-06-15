# disarm

[![Documentation](https://img.shields.io/badge/docs-disarm.dev-blue)](https://docs.disarm.dev/) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/raeq/disarm/blob/main/LICENSE)

Unicode canonicalization and TR39 *visual* confusable analysis — building blocks for text-security pipelines (homoglyph/bidi/zalgo/invisible-character handling), plus standards-based *phonetic* transliteration. **One pure-Rust core, with bindings for Python, Ruby, and more.**

**[Documentation](docs/index.md)** | **[API Reference](docs/api/index.md)** | **[PyPI](https://pypi.org/project/disarm/)**

**Get started in your language:** [Python](docs/python/getting-started.md) · [Rust](docs/rust/getting-started.md) · [Ruby](docs/ruby/getting-started.md)

## Demo

**[Try disarm in your browser](https://disarm-web.pages.dev/)**

## Why disarm

The text-cleaning libraries already in most pipelines — `ftfy`, `unidecode`, `anyascii` — were built for encoding repair and ASCII conversion. They map confusables *phonetically* (Cyrillic `р` → Latin `r`), which does not reverse a homoglyph substitution.

disarm's `normalize_confusables()` / `strip_obfuscation()` implement *visual* confusable mapping per [Unicode TR39](https://www.unicode.org/reports/tr39/) (Cyrillic `р` → Latin `p`) — **not** to be confused with `transliterate()`, which romanizes *phonetically* (`р` → `r`) like the tools above. In a controlled benchmark (six attack types, three downstream tasks, two architectures; 435,864 observations), this visual TR39 mapping reached **XMR = 1.000 on the tested TR39 homoglyph pairs** (17 Latin–Cyrillic, 19 Greek), where phonetic transliterators plateaued near half:

| Tool class | Mapping | Homoglyph XMR (tested TR39 pairs) |
|---|---|---|
| `unidecode`, `anyascii`, `cyrtranslit`, `uroman` | phonetic | ~0.49 |
| **disarm** (`strip_obfuscation` / `normalize_confusables`) | **visual (TR39)** | **1.000** |

`ftfy` was statistically equivalent to no preprocessing; `unidecode` *degraded* accuracy on invisible-character attacks. Details: **[Adversarial-Text Defense](docs/security/adversarial-defense.md)** (paper *"Fire Extinguishers Full of Gasoline"*; XMR metric: [Zenodo 10.5281/zenodo.19323513](https://doi.org/10.5281/zenodo.19323513)).

> **Scope.** disarm is a **defense-in-depth layer, not a complete control.** It canonicalizes the confusables it bundles (TR39) and strips the format characters it enumerates; it does not promise to stop any attack class, and the confusable space is far larger than any table. See the **[Threat Model](THREAT_MODEL.md)** for what is and isn't in scope.
>
> **Not an output sanitizer.** disarm normalizes *input*; it does **not** make text safe to emit into HTML, JS, URLs, SQL, or shells. It performs no escaping and does not strip `<`, `>`, `&` — `<script>alert(1)</script>` passes through unchanged, and NFKC normalization can even *surface* ASCII metacharacters from fullwidth lookalikes (`＜script＞` → `<script>`). disarm is **not** an XSS or injection defense and never replaces one: encode at the output sink (framework auto-escaping, DOMPurify, parameterized queries). Run disarm *before* those, as the Unicode layer they don't cover.

### Which function do I want?

The most common confusion is reaching for `transliterate()` to defend against homoglyphs. It does the **opposite** mapping. Two distinct operations, two different tables:

| If you want to… | Use | Mapping | Example |
|---|---|---|---|
| **Defend against homoglyph / look-alike spoofing** | `normalize_confusables()`, `strip_obfuscation()` | **visual** (TR39) | Cyrillic `р` → Latin **`p`** |
| **Romanize text to readable ASCII** | `transliterate()` | **phonetic** (BGN/PCGN, ISO 9, GOST) | Cyrillic `р` → Latin **`r`**; `Москва` → `Moskva` |
| **Flag spoofed hostnames / IDNs** | `is_suspicious_hostname()` | analysis (no rewrite) | `аpple.com` → suspicious |

`transliterate()` is a *romanizer*, not a security control: it maps by sound/standard, so it will turn a Cyrillic `р` into `r` and leave the spoof readable. For homoglyph defense, always use the visual (TR39) functions in row 1.

```python
from disarm import strip_obfuscation, normalize_confusables, is_suspicious_hostname

# Fold Cyrillic look-alikes to their Latin prototypes (TR39 visual mapping)
strip_obfuscation("рroduсt")        # → "product"  (р→p, с→c)
strip_obfuscation("pаypаl 🔥🔥")     # → "paypal fire fire"  (also strips zalgo/bidi/invisible/emoji)

normalize_confusables("раypal")      # → "paypal"   (mixed Cyrillic skeleton → Latin)

# IDN / hostname spoofing check (flags the bad; a False result is not a safety guarantee)
suspicious, analysis = is_suspicious_hostname("аpple.com")   # leading Cyrillic а
# suspicious is True; analysis.has_confusables and analysis.mixed_script flag why
```

## Installation

```bash
pip install disarm
```

Install and import use the same name, `disarm`:

```python
import disarm
```

Requires Python 3.10+. Wheels are available for Linux, macOS, and Windows.

## Use from Rust

`disarm` is also a standalone Rust crate. The **default build is pure Rust** — no
Python, no `pyo3`, no `libpython` — so it drops into any Rust project as an
ordinary dependency:

```bash
cargo add disarm
```

The public surface is the [`disarm::api`](https://docs.rs/disarm/latest/disarm/api/)
module plus the error types (`Error`, `ErrorKind`, `ErrorMode`). The
[`DisarmStr`](https://docs.rs/disarm/latest/disarm/trait.DisarmStr.html) extension
trait gives the same operations method syntax on any string:

```rust
use disarm::{api, DisarmStr};
use disarm::api::{Transliterate, Scheme, OnUnknown, TargetScript};

fn main() {
    // TR39 confusable folding (Cyrillic look-alikes → Latin)
    assert_eq!(api::normalize_confusables("раypal", TargetScript::Latin), "paypal");
    // …or via the extension trait:
    assert_eq!("раypal".normalize_confusables(TargetScript::Latin), "paypal");

    // Transliteration to ASCII — the one-liner, or the builder for full control
    assert_eq!(api::transliterate("Москва"), "Moskva");
    let s = Transliterate::new()
        .scheme(Scheme::StrictIso9)
        .on_unknown(OnUnknown::Replace("?".into()))
        .run("Москва");
    assert!(s.is_ascii());

    // Canonicalization primitives (borrow on the no-op path via Cow)
    assert_eq!(api::strip_accents("café"), "cafe");
    assert_eq!(api::fold_case("ﬁ"), "fi");
    assert_eq!(api::slugify("Héllo Wörld", &api::SlugConfig::default()), "hello-world");

    // IDN / hostname spoofing check
    let (suspicious, _why) = api::is_suspicious_hostname("раypal.com");
    assert!(suspicious);
}
```

Fallible operations (`sanitize_filename`, `decode_to_utf8`, `strip_log_injection`,
the key/clean presets) return `Result<_, disarm::Error>`; inspect
[`Error::kind()`](https://docs.rs/disarm/latest/disarm/struct.Error.html) for a
stable [`ErrorKind`](https://docs.rs/disarm/latest/disarm/enum.ErrorKind.html).

The `extension-module` Cargo feature (which pulls in `pyo3`) is used **only** to
build the Python wheel — Rust consumers never enable it. See the [Rust API &
semver policy](docs/RUST_API.md) and the full reference on
[docs.rs/disarm](https://docs.rs/disarm).

### Logging (opt-in, off by default)

disarm can emit diagnostic records through the binding-neutral
[`log`](https://docs.rs/log) facade behind the **`log`** Cargo feature. It is
**off by default** — the shipped artifact has no logging code in the hot path
unless you turn it on — and records carry only **metadata** (lengths, language,
mode, flags, counts, durations, error codes), **never** the input or output
text. Pick a sink in your application (`env_logger`, `tracing-subscriber`, …):

```toml
disarm = { version = "0.10", features = ["log"] }
```

```rust
env_logger::init();   // your sink, your level filter
// Core transforms (transliterate, the registration/seal config calls, …) then
// emit redacted records — lengths, flags, counts, duration — but never the text.
```

A library must not set `log`'s `release_max_level_*` (those unify across the
whole dependency graph) — that ceiling is the application's call.

## Features

- **[Confusable & homoglyph analysis (TR39)](docs/security/adversarial-defense.md)**: visual [confusable mapping](docs/user-guide/confusables.md), bidi-control / zalgo / zero-width / invisible-character stripping, and the `strip_obfuscation` pipeline (defense-in-depth — see the [Threat Model](THREAT_MODEL.md))
- **[Canonicalization pipelines](docs/api/pipelines.md)**: `security_clean`, `normalize_user_input`, `catalog_key`, `search_key`, `sort_key`, `display_clean`, `ml_normalize` for common workflows
- **[LLM / RAG pipelines](docs/user-guide/llm-pipelines.md)**: guardrail matching (`llm_guardrail`) and ingestion (`rag_ingest`) profiles — deterministic deobfuscation and ASCII-index normalisation for LLM stacks
- **[Hostname / IDN analysis](docs/api/predicates.md#is_suspicious_hostname)**: mixed-script and confusable detection for domains
- **[Standards-based transliteration](docs/user-guide/transliteration.md)**: best-in-class Latin / Cyrillic / Greek with ISO 9-style ASCII (`strict_iso9`), GOST R 7.0.34, and BGN/PCGN, plus [reverse transliteration](docs/user-guide/language-support.md#reverse-transliteration) (Russian, Ukrainian, Greek)
- **[Text normalization](docs/user-guide/normalization.md)**: NFC/NFD/NFKC/NFKD, full Unicode case folding (1,557 CaseFolding.txt mappings via PHF), [whitespace collapse](docs/user-guide/text-cleaning.md)
- **[Slugification](docs/user-guide/slugification.md)** & **[filename sanitization](docs/user-guide/filenames.md)**: URL-safe slugs (python-slugify compatible) and cross-platform safe filenames with path-traversal handling
- **[Grapheme clusters](docs/user-guide/graphemes.md)**: correct user-perceived character counting, splitting, and truncation
- **[Encoding detection](docs/api/encoding.md)**: auto-detect and decode byte sequences to UTF-8 (chardetng)
- **Broad transliteration coverage** for CJK, Indic, and other scripts — a context-free [unidecode-compatible drop-in](#coverage-tiers) (best-effort; see caveats)

All text processing is implemented in Rust with O(1) PHF lookups and exposed to Python via PyO3.

## Quick start

### Defense & canonicalization

```python
from disarm import (
    is_confusable, normalize_confusables, strip_obfuscation,
    security_clean, normalize_user_input,
)

is_confusable("аpple")             # → True  (contains Cyrillic а)
normalize_confusables("раypal")  # → "paypal"

# Maximum deobfuscation: homoglyphs, zalgo, invisible chars, bidi, emoji → clean text
strip_obfuscation("рroduсt")  # → "product"   (does NOT transliterate; chain transliterate() if needed)

# Pipelines
security_clean("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥")            # → "Real text"   (NFKC → confusables → strip bidi → collapse ws → path-safety)
normalize_user_input("pаypal")      # → "paypal"  (NFKC → strip bidi → strip zero-width → strip control → strip zalgo → confusables → collapse ws → path-safety)
```

### Transliteration (standards-based core)

> **Romanization, not homoglyph defense.** `transliterate()` maps *phonetically* (Cyrillic `р` → `r`), **not** by TR39 *visual* confusability (`р` → `p`). It will not reverse a look-alike spoof — for that use [`normalize_confusables()` / `strip_obfuscation()`](#which-function-do-i-want).

```python
from disarm import transliterate, slugify

transliterate("café")                      # → "cafe"
transliterate("Москва")                    # → "Moskva"     (Cyrillic, BGN/PCGN)
transliterate("Αθήνα")                     # → "Athina"     (Greek, BGN/PCGN)

# Named standards (Latin / Cyrillic / Greek)
transliterate("Юрий", strict_iso9=True)    # → "Jurij"      (ISO 9-style ASCII)
transliterate("Москва", gost7034=True)     # → "Moskva"     (GOST R 7.0.34)

# Language profiles (sparse overrides on top of the default table)
transliterate("Ärger", lang="de")          # → "Aerger"
transliterate("Київ", lang="uk")           # → "Kyiv"

# Auto-detect language from script
transliterate("Москва", lang="auto")       # → "Moskva"     (detects Cyrillic → Russian)

# Reverse transliteration (Latin → native script): Russian, Ukrainian, Greek
transliterate("Moskva", target="ru")       # → "Москва"
transliterate("Athina", target="el")       # → "Αθηνα"

# Slugs & filenames
slugify("café au lait")                    # → "cafe-au-lait"
```

### Compatibility coverage (CJK and other scripts)

```python
# Context-free, character-by-character — best-effort, unidecode-parity (see caveats below)
transliterate("北京市")                     # → "bei jing shi"   (Chinese, toneless pinyin)
transliterate("서울")                       # → "seo ul"         (Korean, Revised Romanization)
transliterate("ひらがな")                   # → "hiragana"       (Japanese, Hepburn)
```

## Coverage tiers

disarm transliterates a very wide range of scripts, but the **quality guarantee differs by tier**. Lead with the core; treat the rest as compatibility coverage.

| Tier | Scripts | Policy | Standard |
|---|---|---|---|
| **Core** (best-in-class) | Latin, Cyrillic, Greek | Standards-based romanization + reverse | BGN/PCGN (default), ISO 9-style ASCII (`strict_iso9`), GOST R 7.0.34 (`gost7034`) |
| **Compatibility** (best-effort) | CJK (Chinese / Japanese / Korean), Arabic, Hebrew, Devanagari & 9 other Indic scripts, Thai, Lao | Context-free, character-by-character — same approach as Unidecode/AnyAscii | Unihan `kMandarin`, Revised Romanization, Hepburn, UNGEGN/IAST-derived, RTGS-derived |
| **Best-effort** | Georgian, Armenian, and a long tail of additional scripts | Context-free coverage so input is never silently dropped | see [Language support](docs/user-guide/language-support.md) |

**Compatibility-tier transliteration is context-free and character-by-character** — no linguistic analysis, polyphony handling, or phonological rules. For CJK/Arabic/Indic this is fundamentally lossy and no better than Unidecode; it exists so disarm is a complete drop-in, not because it is best-in-class there. See [docs/limitations.md](docs/limitations.md) for trade-offs and the [full per-script policy table](docs/user-guide/language-support.md).

> **Context-aware abjad (Arabic, Persian, Hebrew):** an optional dictionary-backed mode (`transliterate(text, context=True)`) restores vowels for more readable output. It is a best-effort *readability aid*, not a romanization standard. See [Abjad scripts](docs/user-guide/abjad-transliteration.md).

## Precompiled pipelines

```python
from disarm import security_clean, ml_normalize, catalog_key, normalize_user_input, strip_obfuscation

# Security: NFKC → confusables → strip bidi → collapse whitespace → path-safety
security_clean("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥")  # → "Real text"

# ML/NLP: NFKC → emoji→text → transliterate → strip accents → fold case
ml_normalize("Café ☕ Ünïcödé")  # → "cafe hot beverage unicode"

# Library catalog: NFKC → transliterate → confusables → strip accents → fold case
catalog_key("Москва", lang="ru")  # → "moskva"
catalog_key("ΩMEGA  café")        # → "omega cafe"

# Web input: NFKC → strip bidi → strip zero-width → strip control → strip zalgo → confusables → collapse → path-safety
normalize_user_input("pаypal")  # → "paypal" (Cyrillic а folded to Latin)

# Maximum deobfuscation: homoglyphs, zalgo, invisible chars → clean text
strip_obfuscation("рroduсt")       # → "product" (Cyrillic р→p, с→c via TR39)
strip_obfuscation("pаypаl 🔥🔥")  # → "paypal fire fire"
# Note: does NOT transliterate — chain with transliterate() if needed
```

## Text builder

```python
from disarm import Text

result = (
    Text("Ünïcödé Café ☕")
    .normalize(form="NFKC")
    .demojize()
    .transliterate()
    .strip_accents()
    .fold_case()
    .value
)
# → "unicode cafe hot beverage"
```

## Package structure

The API is organized into domain-specific namespaces. All functions are also available at the top level for convenience.

| Namespace | Purpose | Key functions |
|---|---|---|
| `disarm.security` | Defense & safety analysis | `normalize_confusables`, `is_confusable`, `is_mixed_script`, `is_suspicious_hostname`, `strip_bidi`, `security_clean` |
| `disarm` | Core transforms | `transliterate`, `slugify`, `strip_obfuscation`, `Text`, `TextPipeline` |
| `disarm.normalization` | Unicode normalization | `normalize`, `strip_accents`, `fold_case`, `collapse_whitespace` |
| `disarm.files` | Filename handling | `sanitize_filename` |
| `disarm.codec` | Byte decoding | `decode_to_utf8`, `detect_encoding` |

```python
# Namespace imports
from disarm.security import is_confusable, security_clean
from disarm.codec import decode_to_utf8
from disarm.normalization import fold_case

# Top-level imports also work
from disarm import is_confusable, security_clean, decode_to_utf8, fold_case
```

## Language profiles

Built-in language profiles span the core and compatibility tiers, with scholarly ASCII Cyrillic support (`strict_iso9`; ISO 9-style digraphs, not the diacritic standard). Profiles apply **sparse overrides** on top of the default table (e.g. German maps `ü` → `ue` instead of the default `u`).

```python
from disarm import list_langs, transliterate

print(len(list_langs()))   # 83
print(list_langs())
#  ['am', 'ar', 'as', 'ban', 'bax', 'bg', 'bn', 'bo', 'bug', 'ca', 'chr',
#   'cjm', 'cop', 'cs', 'cy', 'da', 'de', 'dv', 'el', 'es', 'et', 'fa',
#   'fi', 'fr', 'ga', 'gu', 'he', 'hi', 'hr', 'hu', 'hy', 'is', 'it',
#   'ja', 'ja-kunrei', 'jv', 'ka', 'khb', 'km', 'kn', 'ko', 'lis', 'lo',
#   'lt', 'lv', 'ml', 'mn', 'mni', 'mr', 'mt', 'my', 'ne', 'nl', 'no',
#   'nod', 'nqo', 'or', 'pa', 'pl', 'pt', 'ro', 'ru', 'sa', 'sat', 'si',
#   'sk', 'sl', 'sq', 'sr', 'su', 'sv', 'syr', 'ta', 'tdd', 'te', 'th',
#   'tl', 'tr', 'tzm', 'uk', 'vai', 'vi', 'zh']
```

See [Language support](docs/user-guide/language-support.md) for the full registry, per-script policies, and tier classification.

## Performance

disarm is compiled Rust with O(1) compile-time perfect hash tables — no regex, no per-character Python iteration, no runtime data loading. Speed is a supporting benefit, not the headline; correctness and defense come first.

Performance is measured in two regimes, because they stress different things.
**Long text** (documents, batch pipelines) is dominated by per-character cost;
**short strings** (per-record processing — names, titles, slugs, one field at a
time) are dominated by fixed per-call overhead. disarm is fast in both, and
quotes them separately so neither number overstates the other.

**Long text — document-scale throughput:**

| Operation | Throughput | vs. legacy |
|---|---|---|
| Transliterate (Latin) | ~450M chars/sec | **~38×** faster than Unidecode |
| Transliterate (Cyrillic) | ~106M chars/sec | **~15×** faster than Unidecode |
| Slugify | ~712K slugs/sec | **~10–24×** faster than python-slugify |
| Batch transliterate (100 strings) | ~2.8× faster than loop | — |

**Short strings — per-call, ~70–85 character inputs:**

| Input | vs. Unidecode |
|---|---|
| Latin | **~17×** |
| Mixed scripts | **~14×** |
| Cyrillic / Greek | **~13×** |

A `transliterate()` call crosses the Python→Rust boundary exactly once, and
already-ASCII input returns the original `str` object in roughly 65 ns with
zero allocation. disarm also wins all four cells of [Unidecode's own
benchmark](https://github.com/raeq/disarm/blob/main/benchmarks/bench_unidecode_own.py) — a faithful replication of the
original, re-measured continuously in CI — from ~1.3× on Unidecode's strongest
case (ASCII passthrough) to ~25×. That bar is worth clearing precisely because
Unidecode has carried this workload for two decades; it remains the reference
point this library measures itself against.

Throughput figures are from a commodity 4‑vCPU x86‑64 Linux runner (min‑of‑N
`perf_counter`); per-call figures are interleaved ratios against pinned
comparator versions on CI runners, median-of-7, bucketed by CPU
microarchitecture, and measured in the **fresh-string regime** — every timed
call receives a newly constructed `str` object, as production traffic does,
rather than re-running one cached object (which would understate comparators'
real-world parity and overstate ours). All figures are hardware‑dependent and
directional, not guarantees. See [docs/performance.md](docs/performance.md)
for full benchmark methodology and results.

## Drop-in replacement

disarm provides compatibility aliases for painless migration from existing libraries:

```python
from disarm import unidecode, casefold, remove_accents

unidecode("café")        # → "cafe"       (alias for transliterate)
casefold("Straße")       # → "strasse"    (alias for fold_case)
remove_accents("café")   # → "cafe"       (alias for strip_accents)
```

`sanitize_filename()` also accepts `replacement_text` and `max_len` kwargs for pathvalidate compatibility, and `is_confusable()` accepts `greedy` for confusable_homoglyphs compatibility. See [migration guides](docs/migration/index.md) for details.

> **Security note:** the `unidecode` alias is for *coverage* compatibility only. For security/defense use it is the wrong tool (phonetic mapping does not reverse homoglyph attacks and can degrade downstream accuracy). Use `strip_obfuscation` / `normalize_confusables` instead — see [Migration from Unidecode](docs/migration/from-unidecode.md).

## Exhaustive testing

disarm is exhaustively tested with three layers of machine-verifiable assurance beyond conventional unit and property-based tests:

- **Compile-time assertions**: `build.rs` asserts all transliteration table values are ASCII and entry counts match expectations — if any check fails, `cargo build` fails
- **Exhaustive domain coverage**: Every Hangul syllable (11,172), every BMP codepoint (63,488), every CJK ideograph (20,992), and every Indic script block are tested individually — zero sampling gaps
- **Stated invariants**: Seven stated properties (ASCII passthrough, idempotence, determinism, output bounds, etc.) verified by exhaustive enumeration and Hypothesis

See [docs/formal-verification.md](docs/formal-verification.md) for details.

## Architecture

Rust core with compile-time PHF (perfect hash function) tables for O(1) per-character lookup. Exposed to Python via PyO3 with the stable ABI (abi3-py39). The Chinese pinyin table contains 20,924 entries from the Unicode Unihan database; Korean romanization is purely algorithmic (jamo decomposition, ~100 lines of Rust).

## Links

| | |
|---|---|
| **Source code** | <https://github.com/raeq/disarm> |
| **Releases** | <https://github.com/raeq/disarm/releases> |
| **PyPI package** | <https://pypi.org/project/disarm/> |
| **Documentation** | <https://docs.disarm.dev/> |
| **Issue tracker** | <https://github.com/raeq/disarm/issues> |
| **Changelog** | <https://github.com/raeq/disarm/blob/main/CHANGELOG.md> |

## License

MIT
