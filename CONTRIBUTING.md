# Contributing to translit

Thank you for your interest in contributing!

## Prerequisites

- Rust stable toolchain (`rustup update stable`)
- Python 3.9+
- `maturin` for building the Python extension: `pip install maturin[patchelf]`

## Development setup

```bash
git clone https://github.com/raeq/translit.git
cd translit
maturin develop          # build Rust extension in-place
pip install -e ".[test,dev]"
```

## Running tests

```bash
# Python tests
pytest tests/ -v

# Including type checks (requires Python 3.10+)
pytest tests/test_typing.py -v

# Rust tests
cargo test

# Doctests
pytest --doctest-modules python/translit/__init__.py python/translit/_compat.py
```

## Linting and formatting

```bash
# Rust
cargo fmt
cargo clippy --all-targets -- -D warnings

# Python
ruff check python/ tests/
mypy python/translit/__init__.py --ignore-missing-imports
```

## Submitting changes

1. Fork the repository and create a branch from `main`.
2. Make your changes with tests.
3. Ensure all CI checks pass locally.
4. Open a pull request with a clear description of what changed and why.

## Reporting bugs

Please open an issue at https://github.com/raeq/translit/issues with:
- A minimal reproducing example
- Expected vs actual output
- Python and OS version
