# Text Processing

translit offers two ways to compose multiple transforms: the fluent `Text` builder for readability and one-off processing, and `TextPipeline` for high-throughput batch use.

## Text builder (recommended)

Wrap a string in `Text`, chain methods, extract with `.value` or `str()`. Each method returns a new `Text` — immutable, like Python `str`.

```python
from translit import Text

result = (Text("  Héllo   Straße  ")
    .normalize(form="NFC")
    .transliterate(lang="de")
    .fold_case()
    .collapse_whitespace()
    .value)
# => "hello strasse"
```

### Ordering is explicit

Steps execute in the order you chain them. This gives full control — there is no hidden reordering.

```python
# Strip accents first, then transliterate the remainder
Text("café").strip_accents().transliterate().value  # => "cafe"

# Transliterate first (accents handled by the transliteration table)
Text("café").transliterate().value                  # => "cafe"
```

### Branching

Because each step returns a new `Text`, you can branch from a common base:

```python
base = Text("Héllo Wörld").normalize(form="NFC")

ascii_version = base.transliterate().value          # => "Hello World"
lowered = base.fold_case().value                    # => "héllo wörld"
slug = base.transliterate().slugify().value         # => "hello-world"
```

### Available transforms

All 8 standalone transform functions are available as chainable methods:

| Method | Description |
|---|---|
| `.normalize(form)` | Unicode normalization (NFC, NFD, NFKC, NFKD) |
| `.normalize_confusables()` | Replace homoglyphs with Latin equivalents |
| `.strip_accents()` | Remove combining diacritical marks |
| `.transliterate(lang=...)` | Unicode → ASCII transliteration |
| `.fold_case()` | Unicode case folding (ß→ss, İ→i̇, etc.) |
| `.collapse_whitespace()` | Normalize whitespace, strip control chars |
| `.slugify(separator=...)` | URL-safe slug generation |
| `.sanitize_filename()` | OS-safe filename sanitization |

### Predicates

Predicates return their native type and do not chain:

```python
t = Text("hello мир")
t.is_mixed_script()   # => True
t.detect_scripts()    # => [Script.LATIN, Script.CYRILLIC]
t.is_ascii()          # => False

Text("café").transliterate().is_ascii()  # => True (check the transformed text)
```

### Extracting the result

```python
t = Text("café").transliterate()

t.value       # "cafe" — property access
str(t)        # "cafe" — str() conversion
len(t)        # 4
t == "cafe"   # True — compares with str directly
```

## TextPipeline (batch processing)

`TextPipeline` is a pre-compiled, reusable processor. Configure once at construction, call repeatedly. Operations execute in a fixed optimal order regardless of how you specify them.

Use this when processing large datasets where the same transform chain applies to every item.

```python
from translit import TextPipeline

pipe = TextPipeline(
    normalize="NFC",
    confusables=True,
    strip_accents=True,
    fold_case=True,
    collapse_whitespace=True,
)

# Call repeatedly — construction cost amortized
for text in large_dataset:
    cleaned = pipe(text)
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `normalize` | `str \| None` | `None` | Normalization form: `"NFC"`, `"NFD"`, `"NFKC"`, `"NFKD"` |
| `transliterate` | `bool` | `False` | Convert to ASCII via transliteration tables |
| `lang` | `str \| None` | `None` | Language profile for transliteration. Use `"auto"` to detect from script. |
| `confusables` | `bool` | `False` | Normalize confusable homoglyphs to Latin |
| `strip_accents` | `bool` | `False` | Remove diacritical marks |
| `fold_case` | `bool` | `False` | Unicode case folding |
| `collapse_whitespace` | `bool` | `False` | Normalize whitespace to single spaces |
| `strip_control` | `bool \| None` | `None` | Strip control characters. Defaults to `True` when `collapse_whitespace=True`, `False` otherwise. Can be used independently. |
| `strip_zero_width` | `bool \| None` | `None` | Strip zero-width characters. Defaults to `True` when `collapse_whitespace=True`, `False` otherwise. Can be used independently. |

### Fixed execution order

Operations always execute in this order, regardless of how you specify them:

1. **Normalize** — Unicode normalization
2. **Confusables** — Replace homoglyphs
3. **Demojize** — Expand emoji to text
4. **Strip accents** — Remove combining marks
5. **Transliterate** — Convert to ASCII
6. **Fold case** — Case folding
7. **Strip control** — Remove control characters
8. **Strip zero-width** — Remove zero-width/invisible characters
9. **Collapse whitespace** — Whitespace normalization

## When to use which

| Scenario | Use |
|---|---|
| One-off text processing | `Text` builder |
| Ad-hoc chains with varying steps | `Text` builder |
| Processing a large dataset uniformly | `TextPipeline` |
| Need explicit control over step ordering | `Text` builder |
| Batch ETL / search index normalization | `TextPipeline` |
