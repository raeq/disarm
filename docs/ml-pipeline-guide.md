# translit for ML and LLM Pipelines

A guide to using translit for text normalization, cleaning, and
preprocessing in machine learning and large language model workflows.

Real-world text is messy. User inputs, web scrapes, and document extracts
arrive with inconsistent Unicode normalization, mixed scripts, invisible
characters, emoji, typographic variants, and homoglyph attacks. translit
provides a compiled Rust pipeline that resolves these issues before text
reaches your tokenizer or embedding model.

---

## The Core Problem

Consider text that looks identical to a human but differs at the codepoint
level:

```python
from translit import normalize, is_normalized

# These look the same but are different byte sequences
a = "café"           # é as precomposed U+00E9
b = "café"           # e + combining acute U+0301

a == b               # False (different codepoints!)
normalize(a, form="NFC") == normalize(b, form="NFC")  # True
```

Without normalization, your model treats these as different tokens,
fragmenting its vocabulary and diluting signal. translit handles this and
a dozen other text hygiene problems in a single pass.

---

## Quick Start: `ml_normalize()`

For the most common NLP preprocessing scenario — accent-free, lowercased,
whitespace-clean text — translit provides a precompiled pipeline:

```python
from translit import ml_normalize

ml_normalize("Café Résumé")                   # → "cafe resume"
ml_normalize("Straße")                         # → "strasse"
ml_normalize("Über cool", lang="de")           # → "ueber cool"
ml_normalize("\ufb01lter")                      # → "filter"
```

`ml_normalize()` executes a fixed Rust pipeline:
NFKC → emoji→text → [transliterate if lang] → strip_accents → fold_case → collapse_whitespace.

Pass `lang=` for language-specific transliteration (e.g., German ü→ue) or
`emoji="none"` to leave emoji as-is (useful if your tokenizer handles them).

For more control over which steps run, use `TextPipeline` directly.

---

## TextPipeline: The Batch Preprocessing Tool

`TextPipeline` pre-compiles a sequence of transforms at construction time
and applies them in a fixed optimal order. Use this when `ml_normalize()`
doesn't match your exact requirements — for example, when you want
confusable normalization, or need to keep accents.

```python
from translit import TextPipeline

pipe = TextPipeline(
    normalize="NFKC",          # 1. Canonical normalization
    confusables=True,          # 2. Homoglyph → Latin normalization
    demojize=True,             # 3. Emoji → descriptive text
    strip_accents=True,        # 4. Remove diacritical marks
    transliterate=True,        # 5. Non-Latin → ASCII
    fold_case=True,            # 6. Unicode case folding
    collapse_whitespace=True,  # 7. Normalize whitespace
)

pipe("  Hello 🌍 World!  Ü  ")
# → "hello globe showing europe-africa world! u"
```

### Execution Order

The pipeline always executes in this order regardless of how you specify
the flags. The order is designed so each step's output is in the form
the next step expects:

1. **Normalize** — resolve encoding variants (NFC/NFD/NFKC/NFKD)
2. **Confusables** — replace cross-script homoglyphs with Latin equivalents
3. **Demojize** — expand emoji to descriptive text
4. **Strip accents** — remove combining diacritical marks
5. **Transliterate** — convert remaining non-ASCII to ASCII
6. **Fold case** — Unicode-aware lowercasing (ß→ss, İ→i̇)
7. **Strip control** — remove control characters (auto-enabled with collapse_whitespace)
8. **Strip zero-width** — remove invisible characters (auto-enabled with collapse_whitespace)
9. **Collapse whitespace** — merge runs of whitespace to single spaces

### Choosing Your Pipeline

Not every task needs every step. Here are recommended configurations for
common ML tasks:

**Embedding model input (multilingual):**
```python
pipe = TextPipeline(
    normalize="NFC",
    collapse_whitespace=True,
)
```
Keep diacritics and non-Latin scripts — the embedding model was trained
on multilingual data. Just normalize encoding and clean whitespace.

**Bag-of-words / TF-IDF (English-centric):**
```python
pipe = TextPipeline(
    normalize="NFKC",
    demojize=True,
    transliterate=True,
    fold_case=True,
    collapse_whitespace=True,
)
```
Flatten everything to lowercase ASCII. Emoji become word tokens.
Compatibility variants collapse (ﬁ→fi, ²→2).

**Sentiment analysis on social media:**
```python
pipe = TextPipeline(
    normalize="NFKC",
    demojize=True,              # Emoji carry sentiment signal
    confusables=True,           # Normalize intentional misspellings
    fold_case=True,
    collapse_whitespace=True,
)
```
Preserve non-Latin scripts (don't transliterate) but expand emoji to text
so the model can use their semantic content.

**Deduplication / near-duplicate detection:**
```python
pipe = TextPipeline(
    normalize="NFKC",
    confusables=True,
    strip_accents=True,
    transliterate=True,
    fold_case=True,
    collapse_whitespace=True,
)
```
Maximum normalization — two strings that a human would consider identical
should produce the same output.

---

## NFKC: The ML Normalization Standard

NFKC (Normalization Form Compatibility Composition) is the recommended
normalization for most ML pipelines. It resolves compatibility variants
that would otherwise pollute your vocabulary:

```python
from translit import normalize

# Typographic variants → standard forms
normalize("ﬁnancial", form="NFKC")     # → "financial"  (fi ligature)
normalize("𝗕𝗼𝗹𝗱 𝘁𝗲𝘅𝘁", form="NFKC")  # → "Bold text"  (math bold)
normalize("𝒜ℬ𝒞", form="NFKC")         # → "ABC"        (script letters)

# Width variants → standard forms
normalize("Ｈｅｌｌｏ", form="NFKC")     # → "Hello"  (full-width Latin)
normalize("ﾊﾞﾅﾅ", form="NFKC")        # → "バナナ"  (half-width Katakana)

# Numeric variants → digits
normalize("①②③", form="NFKC")         # → "123"    (circled digits)

# Superscripts/subscripts → base digits
normalize("H₂O", form="NFKC")          # → "H2O"
normalize("x²", form="NFKC")           # → "x2"
```

Use NFC instead of NFKC when you need to preserve the distinction between
compatibility variants (e.g., if ² and 2 carry different meaning in your
domain).

---

## Emoji Handling for NLP

Emoji are the single largest source of OOV (out-of-vocabulary) tokens in
social media text. Most tokenizers either drop them or emit their raw
codepoints, both of which lose semantic information. translit's `demojize()`
converts emoji to their Unicode CLDR short-name descriptions.

### Why This Matters

A sentiment classifier seeing `"I love 🍕"` needs to know that 🍕 means
"pizza." Without expansion, the emoji is either dropped (losing the object
of the sentiment) or kept as a codepoint the model has never seen.

```python
from translit import demojize

demojize("I love 🍕")                    # → "I love pizza"
demojize("Great job! 👍🏽")               # → "Great job! thumbs up: medium skin tone"
demojize("👨‍👩‍👧‍👦 movie night")       # → "family: man, woman, girl, boy movie night"
```

### Reducing Feature Sparsity with strip_modifiers

Skin tone and hair style modifiers create dozens of variants of the same
base emoji (👋, 👋🏻, 👋🏼, 👋🏽, 👋🏾, 👋🏿 are six different codepoint
sequences). For most ML tasks, these variants carry the same semantic
content. `strip_modifiers=True` collapses them to the base form:

```python
demojize("👋🏽", strip_modifiers=False)   # → "waving hand: medium skin tone"
demojize("👋🏽", strip_modifiers=True)    # → "waving hand"
```

This reduces vocabulary size and prevents the model from learning spurious
distinctions between skin tone variants.

### Comparison with NLTK and Other Tools

**NLTK's TweetTokenizer** preserves emoji as tokens but does not expand
their meaning. Downstream bag-of-words or TF-IDF models cannot use a raw
emoji codepoint. translit converts emoji to descriptive text that existing
pipelines can tokenize and embed directly.

**The `emoji` package** offers `demojize()` but outputs `:colon_delimited:`
format strings with underscores. These require post-processing to be
useful as natural language tokens. translit outputs bare CLDR short names
as plain text — no colons, no underscores, no format artifacts.

**The `demoji` package** replaces emoji with empty string by default,
losing semantic content entirely. It also downloads data at runtime,
creating reproducibility issues. translit compiles CLDR data into the
binary at build time.

### ZWJ Sequence Handling

Modern emoji use Zero Width Joiner (ZWJ) sequences to compose complex
glyphs: 👩‍💻 is three codepoints (woman + ZWJ + laptop). translit's
matching engine uses longest-match-first scanning to correctly identify
these as single semantic units:

```python
demojize("👩‍💻")          # → "woman technologist"  (not "woman [?] laptop")
demojize("🏳️‍🌈")         # → "rainbow flag"         (not three separate tokens)
demojize("🇫🇷")           # → "flag: France"         (regional indicator pair)
```

Orphaned ZWJ characters and variation selectors that remain after partial
matches are automatically consumed, preventing invisible garbage in your
feature vectors.

---

## Homoglyph and Confusable Normalization

Cross-script homoglyphs are a significant noise source in web-scraped
corpora. Cyrillic а (U+0430) is visually identical to Latin a (U+0061)
but is a different codepoint. Without normalization, "pаypal" (with
Cyrillic а) and "paypal" (all Latin) are different tokens.

```python
from translit import normalize_confusables, is_confusable, is_mixed_script

# Detect the problem
is_confusable("раypal")               # True  (contains Cyrillic lookalikes)
is_mixed_script("раypal")             # True  (Cyrillic + Latin)

# Fix it
normalize_confusables("раypal")       # → "paypal"
```

For ML pipelines, enable the `confusables=True` flag in `TextPipeline` to
automatically normalize homoglyphs during preprocessing.

---

## Script Detection

Identify which Unicode scripts are present in a text sample. Useful for
corpus analysis, language identification preprocessing, and filtering:

```python
from translit import detect_scripts

detect_scripts("Hello World")           # [Script.LATIN]
detect_scripts("Привет мир")            # [Script.CYRILLIC]
detect_scripts("Привет Hello")          # [Script.CYRILLIC, Script.LATIN]
detect_scripts("こんにちは世界")          # [Script.HIRAGANA, Script.HAN]
```

Scripts are returned in order of first appearance. translit recognizes
39 Unicode scripts.

---

## Case Folding vs .lower()

Python's `str.lower()` does not handle all Unicode case mappings correctly.
translit's `fold_case()` implements the full Unicode CaseFolding.txt
specification (Unicode 16.0, all 1,557 status-C and status-F mappings),
backed by a compile-time PHF table:

```python
from translit import fold_case

# Latin
fold_case("Straße")      # → "strasse"   (ß→ss)
fold_case("İstanbul")    # → "i̇stanbul"  (Turkish İ→i̇, not just "istanbul")
fold_case("ﬁle")         # → "file"      (fi ligature → f + i)

# Characters where .lower() gives the wrong answer
fold_case("\u00B5")       # → "μ"  (micro sign → Greek mu)
fold_case("\u017F")       # → "s"  (long s → s)
fold_case("ϐ")           # → "β"  (variant beta → standard beta)
fold_case("ς")           # → "σ"  (final sigma → standard sigma)
```

The table covers Latin, Greek (including 6 variant forms), Cyrillic,
Armenian, Georgian Mtavruli, Cherokee, Adlam, Deseret, Osage, Warang Citi,
fullwidth Latin, and all Latin ligature expansions. This matters for
multilingual ML datasets where `str.lower()` silently leaves 175
characters incorrectly folded.

For ML preprocessing, always use `fold_case=True` in `TextPipeline`
rather than calling `.lower()` on the output. Pure-ASCII strings take
a branchless fast path with no table lookup.

---

## Accent Stripping

Strip diacritical marks while preserving base characters. This is
implemented as NFD decomposition followed by removal of combining marks:

```python
from translit import strip_accents

strip_accents("café")      # → "cafe"
strip_accents("naïve")     # → "naive"
strip_accents("résumé")    # → "resume"
```

Use this instead of transliteration when you want to keep Latin characters
but remove diacritics (e.g., for search normalization where "cafe" should
match "café").

---

## Whitespace Normalization

Unicode defines 13 whitespace variants beyond ASCII space. Web-scraped
text commonly contains non-breaking spaces (U+00A0), em spaces (U+2003),
ideographic spaces (U+3000), and zero-width characters that are invisible
but affect tokenization:

```python
from translit import collapse_whitespace

collapse_whitespace("hello\u00A0\u2003world")  # → "hello world"
```

The `collapse_whitespace` step in `TextPipeline` also strips control
characters and zero-width joiners/non-joiners that can silently corrupt
token boundaries.

---

## ASCII Check

Quick predicate to determine whether text needs any processing at all.
Useful for short-circuiting in hot paths:

```python
from translit import is_ascii

if not is_ascii(text):
    text = pipe(text)
```

---

## Transliteration for Cross-Lingual Tasks

When you need all text in a single script (e.g., for cross-lingual
information retrieval or monolingual model input), `transliterate()`
converts Unicode to ASCII using language-appropriate romanization:

```python
from translit import transliterate

transliterate("Привет мир")           # → "Privet mir"
transliterate("すし")                  # → "sushi"
transliterate("café")                  # → "cafe"

# Language-specific romanization
transliterate("Київ", lang="uk")       # → "Kyiv"  (Ukrainian KMU 2010)
transliterate("Київ")                  # → "Kiiv"  (default pan-Cyrillic)
```

60 language profiles are available. See `list_langs()` for the full set.

When the source language is unknown (common in multi-lingual corpora), use
`lang="auto"` to detect the dominant script and apply the appropriate profile:

```python
transliterate("Москва", lang="auto")          # → "Moskva" (Cyrillic → Russian)
transliterate("ภาษาไทย", lang="auto")          # → Thai romanization
transliterate("Hello Москва", lang="auto")     # → "Hello Moskva" (first non-Latin script wins)
```

This is especially useful for multi-lingual datasets where different records
are in different scripts.

---

## Batch Processing Pattern

For processing large corpora, construct the pipeline once and apply it
in a loop or with multiprocessing:

```python
from translit import TextPipeline

pipe = TextPipeline(
    normalize="NFKC",
    demojize=True,
    transliterate=True,
    fold_case=True,
    collapse_whitespace=True,
)

# Single-threaded
cleaned = [pipe(doc) for doc in corpus]

# With multiprocessing (pipe is picklable — it's just a config object)
from multiprocessing import Pool
with Pool() as pool:
    cleaned = pool.map(pipe, corpus)
```

---

## Encoding Detection for Messy Corpora

Real-world corpora often contain files in mixed encodings (UTF-8,
ISO-8859-1, Shift-JIS, Big5). translit provides encoding detection and
conversion using Firefox's chardetng algorithm:

```python
from translit import detect_encoding, decode_to_utf8

# Detect encoding with confidence score
encoding, confidence = detect_encoding(raw_bytes)
# e.g. ('Shift_JIS', 0.95)

# Decode to UTF-8 (explicit encoding)
text, had_errors = decode_to_utf8(raw_bytes, encoding="Shift_JIS")

# Decode to UTF-8 (auto-detect)
text, had_errors = decode_to_utf8(raw_bytes)
if had_errors:
    log.warning(f"Lossy conversion for {filename}")
```

**Important**: automatic encoding detection is inherently probabilistic.
A high confidence score does NOT guarantee correctness. For critical
pipelines, always prefer explicit encoding metadata (HTTP headers, BOM,
file format specs) over detection. The `had_errors` flag indicates whether
replacement characters were inserted during decoding.

---

## Grapheme-Aware Character Counts

When tokenizer alignment or character-level models require accurate
"character" counts, use `grapheme_len()` instead of `len()`:

```python
from translit import grapheme_len, grapheme_split

# len() counts codepoints; grapheme_len() counts user-perceived characters
grapheme_len("cafe\u0301")              # → 4 (not 5)
grapheme_len("\U0001F1EC\U0001F1E7")    # → 1 (flag emoji: 2 codepoints)

# Split into grapheme clusters for character-level tokenization
grapheme_split("cafe\u0301")            # → ['c', 'a', 'f', 'é']
```

This is especially relevant for models trained with character-level
tokenizers, where an NFD-decomposed accent or a multi-codepoint emoji
must count as one unit.

---

## Performance

translit is compiled Rust with PyO3 bindings. All table lookups are O(1)
compile-time perfect hash functions. There is no regex compilation, no
Python-level per-character iteration, and no runtime data loading.

The `TextPipeline` executes all enabled steps in a single Rust-side pass
per step, minimizing Python↔Rust boundary crossings. For batch workloads
this reduces per-step overhead — see [performance benchmarks](performance.md)
for measured numbers.

---

## Installation

```bash
pip install translit-rs
```

Single wheel per platform (abi3). No Rust toolchain required. No runtime
data downloads. No network calls during import.
