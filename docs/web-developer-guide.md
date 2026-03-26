# translit for Web Developers

A guide to translit's URL slug generation, filename sanitization, and
Unicode text handling for web applications.

translit is a Rust+PyO3 library that handles the Unicode edge cases web
developers routinely encounter: generating URL-safe slugs from
international text, sanitizing user-uploaded filenames, and cleaning up
the messy Unicode that arrives via form submissions and API payloads.

---

## URL Slug Generation

`slugify()` converts arbitrary Unicode text into a URL-safe, SEO-friendly
slug. It is parameter-compatible with `python-slugify`, so it can serve as
a drop-in replacement with significantly better performance.

### Basic Usage

```python
from translit import slugify

slugify("Hello World!")               # → "hello-world"
slugify("café au lait")               # → "cafe-au-lait"
slugify("Привет мир")                 # → "privet-mir"
slugify("日本語テスト")                 # → "ri-ben-yu-tesuto"
```

The pipeline: decode HTML entities → transliterate Unicode to ASCII →
lowercase → strip non-alphanumeric characters → collapse repeated
separators → apply stopwords and length constraints.

### Customizing the Separator

```python
slugify("My Blog Post: A Journey!", separator="_")
# → "my_blog_post_a_journey"

slugify("My Blog Post: A Journey!", separator=".")
# → "my.blog.post.a.journey"
```

### Preserving Case

```python
slugify("Hello World", lowercase=False)
# → "Hello-World"
```

### Length Limits

```python
slugify("Hello World", max_length=5)
# → "hello"

# word_boundary=True avoids cutting words in half
slugify("Hello Beautiful World", word_boundary=True, max_length=15)
# → "hello"
```

### Stopword Removal

```python
slugify("Hello World", stopwords=("hello",))
# → "world"
```

### Custom Replacements

```python
slugify("Rock & Roll", replacements=[("&", "and")])
# → "rock-and-roll"
```

### HTML Entity Handling

By default, slugify decodes HTML entities before processing. This is the
behavior you want when processing content from CMS editors or API payloads
that HTML-encode special characters:

```python
slugify("Tom &amp; Jerry", entities=True)    # → "tom-jerry"    (default)
slugify("Tom &amp; Jerry", entities=False)   # → "tom-amp-jerry"
```

### Language-Specific Transliteration

Pass `lang` to use language-appropriate romanization rules during the
transliteration step:

```python
slugify("Ünïcödé Ärticlé", lang="de")       # → "uenicoede-aerticle"
slugify("Ünïcödé Ärticlé")                   # → "unicode-article"
```

German `lang="de"` maps ü→ue and ä→ae (Duden standard), while the
default simply strips the diacritic.

When you don't know the source language (e.g., user-generated content in
any script), use `lang="auto"` to auto-detect:

```python
slugify("Москва", lang="auto")           # → "moskva" (Cyrillic → Russian)
slugify("ภาษาไทย", lang="auto")           # → Thai slug
```

### Preserving Unicode Characters

For sites that support Unicode URLs (common in internationalized domains),
`allow_unicode=True` skips transliteration and keeps non-ASCII letters:

```python
slugify("café au lait", allow_unicode=True)  # → "café-au-lait"
slugify("日本語", allow_unicode=True)          # → "日本語"
```

### Emoji in Slugs

Emoji are transliterated to their ASCII text forms and included in the
slug:

```python
slugify("🔥 Hot Takes")    # → "hot-takes"
```

If you want emoji descriptions in the slug, use the `Text` builder to
demojize first:

```python
from translit import Text

Text("🔥 Hot Takes").demojize().slugify().value
# → "fire-hot-takes"
```

---

## Filename Sanitization

`sanitize_filename()` converts arbitrary text into a safe filename that
works across operating systems. It handles the edge cases that cause
real bugs: path separators in user input, Windows reserved names, null
bytes, trailing dots, and length limits.

The function applies NFC normalization as its first step, which prevents
the cross-platform filename mismatch bug where macOS (APFS uses NFD
internally) and Linux/Windows (NFC) disagree on the byte representation
of the same accented filename.

### Basic Usage

```python
from translit import sanitize_filename

sanitize_filename("My Document (Final).pdf")
# → "My_Document_(Final).pdf"

sanitize_filename("résumé — draft #2.docx")
# → "resume_-_draft_#2.docx"

# Path separators and colons are stripped
sanitize_filename("photo/image:2024.jpg")
# → "photo_image_2024.jpg"
```

### Separator Choice

```python
sanitize_filename("my file.txt", separator="-")
# → "my-file.txt"
```

### Platform-Specific Rules

```python
sanitize_filename("CON.txt", platform="universal")
# → "_CON"  (CON is reserved on Windows; extension absorbed into stem sanitization)
```

### Length Limits

```python
sanitize_filename("a" * 300 + ".pdf", max_length=255)
# Truncates the stem, preserves the .pdf extension
```

### Extension Handling

The extension is preserved by default and excluded from the length limit.
Disable this if you don't want extension-aware truncation:

```python
sanitize_filename("report.final.pdf", preserve_extension=True)   # default
sanitize_filename("report.final.pdf", preserve_extension=False)
```

---

## Checking for ASCII Safety

Before deciding whether to transliterate or slugify, you may want to
check whether text is already ASCII-safe:

```python
from translit import is_ascii

is_ascii("hello world")    # True
is_ascii("café")           # False
is_ascii("100% pure")      # True  (% is ASCII)
```

---

## The Text Builder

For multi-step processing — for example, demojize emoji, then
transliterate, then slugify — use the `Text` builder's chainable API:

```python
from translit import Text

# Blog post title → URL slug
result = (
    Text("  🇫🇷 Les Éléments du Style  ")
    .normalize(form="NFC")
    .demojize()
    .transliterate()
    .slugify()
    .value
)
# → "flag-france-les-elements-du-style"
```

Each method returns a new `Text` instance, so the chain is immutable
and can be broken across lines for readability.

### Available Methods

| Method                  | Effect                                          |
|-------------------------|-------------------------------------------------|
| `.normalize(form)`      | Unicode normalization (NFC, NFD, NFKC, NFKD)    |
| `.transliterate()`      | Unicode → ASCII transliteration                  |
| `.demojize()`           | Emoji → descriptive text                         |
| `.slugify()`            | Generate URL-safe slug                           |
| `.fold_case()`          | Unicode case folding                             |
| `.strip_accents()`      | Remove diacritical marks                         |
| `.collapse_whitespace()`| Normalize whitespace variants                    |
| `.normalize_confusables()`| Replace homoglyphs                             |
| `.value`                | Extract the final string                         |

---

## Handling International Content

### CJK Text

Chinese, Japanese, and Korean text is automatically transliterated during
slug generation:

```python
slugify("東京タワー")                 # → "tawa" (Katakana portion)
slugify("東京タワー", lang="ja")      # → "tawa"
```

For Japanese text with kanji, transliteration coverage depends on the
character. Kana (hiragana and katakana) have full Hepburn romanization;
kanji falls through to the error mode (default: replace with empty).

### Cyrillic Text

Russian, Ukrainian, Serbian, and Bulgarian text is transliterated using
language-appropriate romanization:

```python
slugify("Привет мир")                # → "privet-mir"
slugify("Привет мир", lang="ru")     # → "privet-mir"
slugify("Київ", lang="uk")           # → "kyiv"
```

### Arabic and Right-to-Left Text

Arabic text is transliterated to ASCII. The slug output is always
left-to-right:

```python
slugify("مرحبا بالعالم")             # → "mrhb-bl-lm"
```

---

## Sanitizing User-Submitted Text: `sanitize_user_input()`

For form submissions, comments, bios, and API payloads, use
`sanitize_user_input()` — a single-call pipeline that neutralizes
common attack vectors while preserving the original script:

```python
from translit import sanitize_user_input

sanitize_user_input("Hello, world!")        # → "Hello, world!"
sanitize_user_input("p\u0430ypal")          # → "paypal"  (Cyrillic а → Latin a)
sanitize_user_input("admin\u202Euser")      # → "adminuser"  (bidi override stripped)
sanitize_user_input("hello\u200Bworld")     # → "helloworld"  (ZWSP stripped)
```

Pipeline: `NFKC → strip_zalgo → confusables → strip_bidi → collapse_whitespace`

This handles:

- **Zalgo text** — caps combining marks at 2 per base character
- **Homoglyph spoofing** — neutralizes cross-script lookalikes
- **Bidi overrides** — prevents text reordering attacks
- **Zero-width injections** — strips invisible characters
- **Control characters** — removes null bytes and control sequences
- **Encoding tricks** — NFKC collapses fullwidth bypasses and ligatures

No transliteration is applied — multilingual input keeps its original script.

### Zalgo Detection

To check whether input contains zalgo-style combining mark abuse before
processing:

```python
from translit import is_zalgo, strip_zalgo

is_zalgo("café")               # False (1 combining mark — normal)
is_zalgo("Việt Nam")           # False (2 marks — normal)

# Strip zalgo while preserving legitimate diacritics
strip_zalgo(zalgo_text)         # caps at 2 marks per base char
strip_zalgo(text, max_marks=0)  # strips ALL combining marks
```

### Lightweight Display Cleaning: `display_clean()`

For rendering-only cleanup without homoglyph or zalgo protection,
use the lighter `display_clean()`:

```python
from translit import display_clean

display_clean("hello   world")        # → "hello world"
display_clean("hello\x00world")       # → "helloworld"  (null byte stripped)
display_clean("hello\u200Bworld")     # → "helloworld"  (ZWSP stripped)
display_clean("\uFEFFhello")          # → "hello"        (BOM stripped)
display_clean("  hello  ")            # → "hello"        (trimmed)
```

`display_clean()` strips bidi overrides, control characters, and
zero-width injections, then collapses whitespace. It does **not** handle
homoglyphs or zalgo — use `sanitize_user_input()` for that.

For security-critical contexts (e.g., domain validation, username checks),
use `security_clean()` instead.

---

## Grapheme-Safe Truncation

When truncating text for display (e.g., preview cards, form fields),
byte-level or `text[:n]` truncation can split emoji, combining accents,
or flag sequences mid-character. Use `grapheme_truncate()`:

```python
from translit import grapheme_len, grapheme_truncate

grapheme_len("cafe\u0301")              # → 4 (not 5 — accent is part of the 'e')
grapheme_truncate("cafe\u0301s", 4)     # → "café" (accent stays with the e)

# Emoji are never split
grapheme_truncate("Hi 👩‍👩‍👧‍👦!", 4)            # → "Hi 👩‍👩‍👧‍👦" (family emoji = 1 grapheme)

# Flag emoji
grapheme_len("🇬🇧")                     # → 1 (two regional indicators = 1 grapheme)
```

---

## Performance

translit is compiled Rust with O(1) perfect-hash-function table lookups.
For web applications generating slugs in request handlers or batch-
processing CMS exports, translit is 7–13× faster than python-slugify and
up to 34× faster than Unidecode for Latin transliteration at document
scale. See [performance benchmarks](performance.md) for full measured
results.

If you are generating the same kind of slug repeatedly (e.g., in a
migration script), use `TextPipeline` for pre-compiled transforms:

```python
from translit import TextPipeline

pipe = TextPipeline(
    normalize="NFC",
    transliterate=True,
    fold_case=True,
    collapse_whitespace=True,
)

# Apply to thousands of titles
slugs = [pipe(title) for title in titles]
```

---

## Drop-in Replacement for python-slugify

`translit.slugify()` accepts the same parameters as `python-slugify`:
`separator`, `lowercase`, `max_length`, `word_boundary`, `save_order`,
`stopwords`, `regex_pattern`, `replacements`, `allow_unicode`, `entities`,
`decimal`, `hexadecimal`. Existing code that calls `slugify()` from
`python-slugify` can switch to `translit.slugify()` with no argument
changes.

```python
# Before
from slugify import slugify

# After
from translit import slugify
```

---

## Installation

```bash
pip install translit-rs
```

Single wheel per platform. No Rust toolchain required for installation.
