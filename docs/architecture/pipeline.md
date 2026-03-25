# Architecture: TextPipeline

How translit composes multiple transforms into a single, fixed-order pipeline.

## Two composition models

translit offers two ways to compose transforms:

1. **`Text` builder** (recommended for interactive use): fluent method chaining where the user controls step ordering. Each method call executes immediately and returns a new `Text` instance.
2. **`TextPipeline`** (recommended for batch/server use): a pre-compiled pipeline configured at construction time, with a fixed execution order optimized for correctness.

The `Text` builder is covered in the [Pipeline user guide](../user-guide/pipeline.md). This page documents `TextPipeline`'s internals.

## Bitflag step selection

Steps are represented as a `u16` bitflag set using the `bitflags` crate:

| Bit | Step |
|---|---|
| 0 | Normalize |
| 1 | Transliterate |
| 2 | Confusables |
| 3 | Strip accents |
| 4 | Fold case |
| 5 | Collapse whitespace |
| 6 | Demojize |
| 7 | Strip control |
| 8 | Strip zero-width |

The constructor accepts boolean keyword arguments (`transliterate=True`, `fold_case=True`, etc.) and ORs the corresponding flags into the step set. Checking whether a step is enabled is a single bitmask test — no branching on string keys or dictionary lookups.

## Fixed execution order

Regardless of the order in which constructor arguments are specified, `process()` always executes enabled steps in this sequence:

1. **Normalize** — establish a canonical Unicode form before any character-level operation.
2. **Confusables** — resolve homoglyphs while characters are still in their original script (confusable mapping operates on Unicode, not ASCII).
3. **Demojize** — expand emoji to text before transliteration would drop them.
4. **Strip accents** — NFD decompose + remove combining marks.
5. **Transliterate** — Unicode → ASCII.
6. **Fold case** — after transliteration so it operates on ASCII/Latin output.
7. **Strip control** — remove control characters (U+0000–U+001F except tab/newline, U+007F–U+009F).
8. **Strip zero-width** — remove zero-width spaces, joiners, and invisible math operators.
9. **Collapse whitespace** — final cleanup of whitespace runs. When combined with strip_control/strip_zero_width, uses an optimized single-pass implementation.

**Why this order matters**: confusable normalization must precede transliteration because the confusable table maps Unicode→Unicode (Cyrillic а → Latin a), and transliteration would destroy the script distinction. Demojize must precede transliteration because transliteration would drop emoji codepoints (they have no ASCII mapping). Case folding comes after transliteration so that language-specific transliterations (e.g., German ü → ue) are folded correctly.

The user cannot reorder steps in `TextPipeline`. If custom ordering is needed, the `Text` builder or direct function composition (`fold_case(transliterate(text))`) should be used instead.

## All-Rust execution

`process()` runs entirely in Rust. Each step calls the Rust implementation directly (`transliterate::transliterate_impl`, `normalize::_normalize`, etc.) without re-entering Python. This eliminates N-1 PyO3 boundary crossings for an N-step pipeline compared to calling the Python functions sequentially.

The `demojize` step uses `emoji::demojize_rust()` — a Python-provider-free variant — to avoid acquiring the GIL for provider lookups during pipeline execution.

## Configuration capture

All configuration is captured at construction time. The `normalize_form`, `lang` (including `"auto"` for script-based detection), and `strict_iso9` are stored as struct fields. When `lang="auto"`, language resolution happens at call time inside `transliterate_impl()` — each input string's dominant script is detected and mapped to a language code. The `strip_control` and `strip_zero_width` options are encoded directly into the bitflag set as `STRIP_CONTROL` and `STRIP_ZERO_WIDTH` flags. The constructor validates the normalization form string eagerly (rejecting invalid values immediately) so that `process()` never encounters bad configuration at call time.

This makes `TextPipeline` safe to share across threads (it implements `Send` via PyO3's `#[pyclass]`) and efficient for repeated calls — there is no per-call configuration parsing.

## Intended use pattern

```python
from translit import TextPipeline

pipe = TextPipeline(
    normalize="NFC",
    transliterate=True,
    fold_case=True,
    collapse_whitespace=True,
    lang="de",
)

# Process thousands of records with one object
results = [pipe(record) for record in dataset]
```

The pipeline object is created once and called many times. For processing lists of strings, the batch APIs (`transliterate_batch`, `slugify_batch`) are even faster because they also amortize the per-item PyO3 boundary crossing.
