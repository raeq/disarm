# Text Processing

disarm offers two ways to compose multiple transforms: the fluent `Text` builder for readability and one-off processing, and `TextPipeline` for high-throughput batch use.

## Text builder (recommended)

Wrap a string in `Text`, chain methods, extract with `.value` or `str()`. Each method returns a new `Text` — immutable, like a Python `str`.

=== "Python"

    ```python
    from disarm import Text

    result = (Text("  Héllo   Straße  ")
        .normalize(form="NFC")
        .transliterate(lang="de")
        .fold_case()
        .collapse_whitespace()
        .value)
    assert result == 'hello strasse'
    ```

=== "Rust"

    Rust has no `Text` builder — chain the standalone operations (here via the
    `DisarmStr` extension trait and the `Transliterate` builder) instead.

    ```rust
    use disarm::api::{self, NormalizationForm, Transliterate};
    use disarm::DisarmStr;

    let normalized = "  Héllo   Straße  ".normalize(NormalizationForm::Nfc);
    let romanized = Transliterate::new().lang("de").run(&normalized);
    let folded = romanized.fold_case();
    let result = api::collapse_whitespace(&folded, true, true);
    assert_eq!(result, "hello strasse"); // => "hello strasse"
    ```

### Ordering is explicit

Steps execute in the order you chain them. This gives full control — there is no hidden reordering.

=== "Python"

    ```python
    # Strip accents first, then transliterate the remainder
    assert Text("café").strip_accents().transliterate().value == 'cafe'

    # Transliterate first (accents handled by the transliteration table)
    assert Text("café").transliterate().value == 'cafe'
    ```

=== "Rust"

    ```rust
    use disarm::DisarmStr;

    // Strip accents first, then transliterate the remainder
    assert_eq!("café".strip_accents().transliterate(), "cafe"); // => "cafe"

    // Transliterate first (accents handled by the transliteration table)
    assert_eq!("café".transliterate(), "cafe"); // => "cafe"
    ```

### Branching

Because each step returns a new `Text`, you can branch from a common base:

=== "Python"

    ```python
    base = Text("Héllo Wörld").normalize(form="NFC")

    ascii_version = base.transliterate().value
    assert ascii_version == 'Hello World'
    lowered = base.fold_case().value
    assert lowered == 'héllo wörld'
    slug = base.transliterate().slugify().value
    assert slug == 'hello-world'
    ```

=== "Rust"

    With no builder to hold the intermediate state, bind the common base to a
    variable and branch from it:

    ```rust
    use disarm::api::{self, NormalizationForm, SlugConfig};
    use disarm::DisarmStr;

    let base = "Héllo Wörld".normalize(NormalizationForm::Nfc);

    let ascii_version = base.transliterate();
    assert_eq!(ascii_version, "Hello World"); // => "Hello World"
    let lowered = base.fold_case();
    assert_eq!(lowered, "héllo wörld"); // => "héllo wörld"
    let slug = api::slugify(&base.transliterate(), &SlugConfig::new());
    assert_eq!(slug, "hello-world"); // => "hello-world"
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

=== "Python"

    ```python
    from disarm import Script

    t = Text("hello мир")
    assert t.is_mixed_script() == True
    assert t.detect_scripts() == [Script.LATIN, Script.CYRILLIC]
    assert t.is_ascii() == False

    assert Text("café").transliterate().is_ascii() == True
    ```

=== "Rust"

    ```rust
    use disarm::api;
    use disarm::DisarmStr;

    assert!("hello мир".is_mixed_script()); // => true
    assert_eq!("hello мир".detect_scripts(), vec!["Latin", "Cyrillic"]); // => ["Latin", "Cyrillic"]
    assert!(!api::is_ascii("hello мир")); // => false

    assert!(api::is_ascii(&"café".transliterate())); // => true
    ```

### Extracting the result

=== "Python"

    ```python
    t = Text("café").transliterate()

    assert t.value == 'cafe'       # property access
    assert str(t) == 'cafe'        # str() conversion
    assert len(t) == 4
    assert t == "cafe"             # compares with str directly
    ```

=== "Rust"

    There is no wrapper to unwrap — each operation returns the string (a
    `Cow<str>` or `String`) directly.

    ```rust
    use disarm::DisarmStr;

    let t = "café".transliterate();

    assert_eq!(t, "cafe");   // => "cafe"
    assert_eq!(t.len(), 4);  // => 4 (bytes)
    ```

## TextPipeline (batch processing)

`TextPipeline` is a pre-compiled, reusable processor. Configure once at construction, call repeatedly. Operations execute in a fixed optimal order regardless of how you specify them.

Use this when processing large datasets where the same transform chain applies to every item.

<!--- skip: next -->
```python
from disarm import TextPipeline

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
