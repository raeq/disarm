# Contributing

Contributions to translit are welcome. This guide covers the development setup, testing, and common contribution tasks.

## Development setup

### Prerequisites

- **Rust** 1.70+ (install via [rustup](https://rustup.rs/))
- **Python** 3.9+ with pip
- **maturin** (Rust/Python build tool)

### Clone and build

```bash
git clone https://github.com/raeq/translit.git
cd translit

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install maturin
pip install maturin

# Build and install in development mode
maturin develop

# Verify
python -c "import translit; print(translit.transliterate('café'))"
```

## Running tests

### Python tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test module
pytest tests/test_transliterate.py -v

# Run with coverage
pytest tests/ --cov=translit --cov-report=term-missing
```

### Rust tests

```bash
cargo test
```

### Type checking

```bash
# mypy
mypy python/translit/ --strict

# pyright
pyright python/translit/
```

## Project structure

```
translit/
├── src/                    # Rust source code
│   ├── lib.rs              # PyO3 module registration
│   ├── transliterate.rs    # Transliteration engine
│   ├── slugify.rs          # Slug generation
│   ├── normalize.rs        # Unicode normalization
│   ├── confusables.rs      # Homoglyph detection
│   ├── filename.rs         # Filename sanitization
│   ├── case_fold.rs        # Full Unicode case folding (CaseFolding.txt PHF)
│   ├── whitespace.rs       # Whitespace normalization
│   ├── scripts.rs          # Script detection
│   ├── pipeline.rs         # TextPipeline
│   └── tables/             # Transliteration & confusable data
│       ├── mod.rs           # Language routing
│       ├── transliteration.rs   # Include + lookup logic
│       ├── confusables_data.rs  # Include + lookup (TR39)
│       ├── case_folding_data.rs # Include + PHF lookup (CaseFolding.txt)
│       ├── hanzi_pinyin.rs      # Include + lookup (Unihan)
│       ├── emoji_data.rs        # Include + constants (CLDR)
│       └── data/              # TSV data files (build.rs input)
│           ├── translit_default.tsv
│           ├── translit_lang_*.tsv  # 20 language tables
│           ├── confusables.tsv
│           ├── case_folding.tsv     # 1,557 Unicode case folding entries
│           ├── hanzi_pinyin.tsv
│           └── emoji_*.tsv          # 3 emoji tables
├── python/translit/         # Python public API
│   ├── __init__.py          # Public functions & classes (Google-style docstrings + doctests)
│   ├── __init__.pyi         # Type stubs (one-line docstrings for IDE hover)
│   ├── _text.py             # Text fluent builder class
│   ├── _text.pyi            # Text builder type stubs
│   ├── _enums.py            # Script, NF enums
│   ├── _enums.pyi           # Enum type stubs
│   ├── _types.py            # Type aliases
│   ├── _compat.py           # Compatibility aliases (unidecode, awesome-slugify)
│   └── py.typed             # PEP 561 marker
├── tests/                  # Python test suite
├── benchmarks/             # Performance benchmarks
├── docs/                   # MkDocs documentation
├── Cargo.toml              # Rust dependencies
├── pyproject.toml          # Python packaging
└── mkdocs.yml              # Documentation config
```

## Common contributions

### Adding a transliteration table

Language-specific transliteration data lives in TSV files under `src/tables/data/`. Each file maps hex codepoints to replacement strings (tab-separated: `HEXCODEPOINT\tvalue`).

To add a new language table:

1. Create `src/tables/data/translit_lang_xx.tsv` with your mappings
2. Add the table to `build.rs` in the `lang_tables` array: `("lang_xx", "LANG_XX")`
3. Add a `lookup_lang` match arm in `src/tables/transliteration.rs`: `"xx" => LANG_XX.get(&c).copied()`
4. Register the language constant in:
   - `python/translit/_enums.py` — `LANG_XX = "xx"`
   - `python/translit/_enums.pyi` — `LANG_XX: str`
   - `python/translit/__init__.py` — add to imports and `__all__`
   - `python/translit/__init__.pyi` — add to imports
   - `tests/test_transliterate.py` — add test methods

### Updating confusable mappings

Confusable data lives in `src/tables/data/confusables.tsv`, derived from Unicode TR39's [confusables.txt](https://www.unicode.org/Public/security/latest/confusables.txt). The extraction script `scripts/extract_phf_data.py` can regenerate all TSV data files from the Rust source, and `scripts/gen_confusables.py` can regenerate the confusables from upstream TR39 data.

The TSV file uses the format `HEXCODEPOINT\tvalue` and is read by `build.rs` at compile time to produce a PHF map of ~1,900 non-Latin→Latin mappings.

### Fixing a transliteration mapping

If a character maps incorrectly, edit the relevant TSV file in `src/tables/data/`. For the default table, edit `translit_default.tsv`; for a language-specific override, edit the corresponding `translit_lang_xx.tsv`.

### How PHF generation works

All PHF (perfect hash function) tables are generated by `build.rs` using `phf_codegen`. The workflow:

1. Data files in `src/tables/data/` store mappings as simple TSV
2. `build.rs` reads the TSV files and computes PHF maps using `phf_codegen`
3. Generated Rust code is written to `$OUT_DIR`
4. Source files in `src/tables/` pull in the generated maps via `include!()`

Cargo caches `build.rs` output, so incremental rebuilds that only change Rust source skip PHF generation entirely.

## Code style

### Rust

- Follow standard `rustfmt` formatting
- Run `cargo clippy` before submitting
- Every `#[pyfunction]` must have a `///` doc comment above it (before the `#[pyfunction]` attribute). These appear in `cargo doc` output and help Rust maintainers understand each function's purpose without reading the Python layer.

### Python

- Follow PEP 8 (enforced via `ruff check` and `ruff format`)
- Type annotations on all functions
- Run `mypy python/translit/ --ignore-missing-imports` before submitting

## Code documentation

The project maintains four parallel documentation surfaces. All four must be kept in sync when adding or modifying a public function.

### 1. Google-style docstrings in `__init__.py`

mkdocstrings is configured with `docstring_style: google` (see `mkdocs.yml`). Every public function and class must have a docstring with these sections:

- **Summary line** — one-line description ending with a period.
- **Extended description** (optional) — pipeline steps, algorithm notes, caveats.
- **Args:** — one entry per parameter, with name, type context, and description. Even single-parameter functions like `strip_accents(text)` include an `Args:` section for mkdocstrings rendering consistency.
- **Returns:** — what the function returns, including tuple unpacking where relevant (e.g. `Tuple of (encoding_name, confidence) where confidence is 0.0–1.0.`).
- **Examples:** — at least one `>>>` doctest per function. These serve triple duty: (a) `python -m doctest` / `doctest.testmod()` verification, (b) mkdocstrings autodoc output, (c) IDE hover tooltips and AI agent comprehension.

Example of a correctly documented function:

```python
def strip_accents(text: str) -> str:
    """Remove diacritical marks while preserving base characters.

    NFD decompose → strip combining marks → NFC recompose.
    café → cafe, naïve → naive.

    Args:
        text: Input Unicode string.

    Returns:
        String with diacritical marks removed.

    Examples:
        >>> strip_accents("café résumé naïve")
        'cafe resume naive'
    """
```

### 2. Doctest examples

Every public function has `>>>` examples inside its docstring. Run doctests with:

```bash
python3 -c "import doctest; import translit; print(doctest.testmod(translit))"
```

When adding a doctest, always verify the expected output matches the actual Rust implementation. Common pitfalls: transliteration output varies by language table (check `lang=` parameter), case folding for Cherokee is reversed relative to intuition, ligature folding can shrink byte length.

### 3. Stub docstrings in `.pyi` files

PyCharm and other IDEs that read `.pyi` stubs instead of `.py` source files display stub docstrings in hover tooltips and autocomplete. Every function in `__init__.pyi` and `_text.pyi` must have a one-line docstring matching the summary line from its `.py` counterpart.

Example stub entry:

```python
def strip_accents(text: str) -> str:
    """Remove diacritical marks while preserving base characters."""
    ...
```

The PEP 561 `py.typed` marker is already present, so tools discover the stubs automatically.

### 4. Rust `///` doc comments on `#[pyfunction]`

Every `#[pyfunction]` in Rust source must have `///` doc comments placed above the `#[pyfunction]` attribute. These appear in `cargo doc` output and provide context for Rust maintainers.

Example:

```rust
/// Remove diacritical marks while preserving base characters.
///
/// NFD decompose → strip combining marks → NFC recompose.
#[pyfunction]
#[pyo3(name = "_strip_accents")]
pub fn _strip_accents(text: &str) -> String {
```

### Adding a new public function — documentation checklist

When adding a new public function, update all four surfaces:

1. `python/translit/__init__.py` — full Google-style docstring with Args, Returns, and at least one `>>>` doctest example
2. `python/translit/__init__.pyi` — one-line stub docstring
3. `src/*.rs` — `///` doc comment above `#[pyfunction]`
4. If the function is a `Text` builder method, also update `python/translit/_text.py` (full docstring) and `python/translit/_text.pyi` (stub docstring)

## Documentation site

Documentation is built with MkDocs:

```bash
# Install doc dependencies
pip install -r docs/requirements.txt

# Serve locally
mkdocs serve

# Build
mkdocs build
```

## Pull requests

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest tests/ -v && cargo test`)
6. Submit a PR with a clear description
