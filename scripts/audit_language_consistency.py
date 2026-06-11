#!/usr/bin/env python3
"""Audit language/script registration consistency across the disarm codebase.

Checks that every language in BUILTIN_LANGS is fully registered in all required
files: Rust source, Python enums/stubs/exports, docs, and tests.

Exit 0 if all checks pass, exit 1 if any gaps found.

Usage:
    python scripts/audit_language_consistency.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Loaders: extract data from each file
# ---------------------------------------------------------------------------


def load_builtin_langs() -> set[str]:
    """Parse BUILTIN_LANGS from src/tables/mod.rs."""
    text = (ROOT / "src" / "tables" / "mod.rs").read_text()
    m = re.search(r"const BUILTIN_LANGS:.*?=.*?\[(.+?)\];", text, re.DOTALL)
    if not m:
        sys.exit("ERROR: Could not find BUILTIN_LANGS in src/tables/mod.rs")
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def load_script_to_lang() -> dict[str, str]:
    """Parse script_to_lang() match arms from src/scripts.rs."""
    text = (ROOT / "src" / "scripts.rs").read_text()
    m = re.search(r"fn script_to_lang.*?\{(.+?)\n\}", text, re.DOTALL)
    if not m:
        sys.exit("ERROR: Could not find script_to_lang in src/scripts.rs")
    mapping = {}
    for script, lang in re.findall(r'"(\w+)".*?Some\("([^"]+)"\)', m.group(1)):
        mapping[script] = lang
    return mapping


def load_script_ranges() -> set[str]:
    """Parse SCRIPT_RANGES script names from src/scripts.rs."""
    text = (ROOT / "src" / "scripts.rs").read_text()
    m = re.search(r"static SCRIPT_RANGES:.*?=.*?\[(.+?)\];", text, re.DOTALL)
    if not m:
        sys.exit("ERROR: Could not find SCRIPT_RANGES in src/scripts.rs")
    return set(re.findall(r'"(\w+)"', m.group(1)))


def load_enum_constants(path: Path) -> set[str]:
    """Extract LANG_XX constant names from a Python file."""
    text = path.read_text()
    return {m for m in re.findall(r"^(LANG_\w+)\s*[=:]", text, re.MULTILINE)}


def load_init_imports() -> set[str]:
    """Extract LANG_XX names from __init__.py imports."""
    text = (ROOT / "python" / "disarm" / "__init__.py").read_text()
    return {m for m in re.findall(r"^\s+(LANG_\w+),?$", text, re.MULTILINE)}


def load_init_all() -> set[str]:
    """Extract LANG_XX names from __all__ in __init__.py."""
    text = (ROOT / "python" / "disarm" / "__init__.py").read_text()
    m = re.search(r"__all__\s*=\s*\[(.+?)\]", text, re.DOTALL)
    if not m:
        sys.exit("ERROR: Could not find __all__ in __init__.py")
    return {x for x in re.findall(r'"(LANG_\w+)"', m.group(1))}


def load_reference_texts() -> set[str]:
    """Extract lang codes from reference text table in docs/reference.md."""
    text = (ROOT / "docs" / "reference.md").read_text()
    # Find the Reference Texts table section
    idx = text.find("## Reference Texts")
    if idx < 0:
        return set()
    section = text[idx:]
    return set(re.findall(r"\|\s*`(\w[\w-]*)`\s*\|", section))


def load_lang_samples(path: Path, dict_name: str) -> set[str]:
    """Extract lang codes from a dict literal in a test file."""
    text = path.read_text()
    m = re.search(rf"{dict_name}\s*[=:].+?\{{(.+?)\n\}}", text, re.DOTALL)
    if not m:
        return set()
    return set(re.findall(r'"([^"]+)"(?:\s*:|\s*\))', m.group(1)))


def load_auto_test_langs() -> set[str]:
    """Extract expected_lang values from test_lang_auto.py parametrize."""
    path = ROOT / "tests" / "test_lang_auto.py"
    text = path.read_text()
    # Find the first parametrize list (test_auto_matches_explicit_lang)
    m = re.search(r'parametrize\(\s*"text,expected_lang".*?\[(.+?)\]', text, re.DOTALL)
    if not m:
        return set()
    return set(re.findall(r'"(\w[\w-]*)"(?:\s*\))', m.group(1)))


def load_lang_support_auto_table() -> set[str]:
    """Extract lang codes from the auto-detection table in language-support.md."""
    text = (ROOT / "docs" / "user-guide" / "language-support.md").read_text()
    idx = text.find("### Script-to-language mapping")
    if idx < 0:
        return set()
    # Scan until next ### or end
    section = text[idx:]
    next_h3 = section.find("\n### ", 5)
    if next_h3 > 0:
        section = section[:next_h3]
    return set(re.findall(r"`(\w[\w-]*)`", section))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    langs = load_builtin_langs()
    script_to_lang = load_script_to_lang()
    script_ranges = load_script_ranges()
    enum_constants = load_enum_constants(ROOT / "python" / "disarm" / "_enums.py")
    stub_constants = load_enum_constants(ROOT / "python" / "disarm" / "_enums.pyi")
    init_imports = load_init_imports()
    init_all = load_init_all()
    ref_texts = load_reference_texts()
    dyn_samples = load_lang_samples(ROOT / "tests" / "test_dynamic_coverage.py", "LANG_SAMPLES")
    ascii_samples = load_lang_samples(
        ROOT / "tests" / "test_transliterate.py", "_ALL_LANG_ASCII_SAMPLES"
    )
    auto_test_langs = load_auto_test_langs()
    auto_doc_langs = load_lang_support_auto_table()

    # Langs that map 1:1 from a script (should have auto-detection)
    langs_with_script = set(script_to_lang.values())
    # Scripts that should be in SCRIPT_RANGES for auto-detection to work
    scripts_needing_ranges = set(script_to_lang.keys())

    errors = 0

    def check(description: str, expected: set[str], actual: set[str], label: str):
        nonlocal errors
        missing = expected - actual
        if missing:
            errors += 1
            print(f"FAIL: {description}")
            print(f"  Missing from {label}: {sorted(missing)}")

    # --- Rust checks ---
    check(
        "script_to_lang() scripts have SCRIPT_RANGES entries",
        scripts_needing_ranges,
        script_ranges,
        "SCRIPT_RANGES",
    )

    # --- Python checks ---
    expected_consts = {f"LANG_{code.upper().replace('-', '_')}" for code in langs}
    # Exclude some edge cases: LANG_AUTO is special, ja-kunrei has no constant
    expected_consts.discard("LANG_JA_KUNREI")  # uses LANG_JA
    check("Python _enums.py constants", expected_consts, enum_constants, "_enums.py")
    check("Python _enums.pyi stubs", expected_consts, stub_constants, "_enums.pyi")
    check("__init__.py imports", expected_consts, init_imports, "imports")
    check("__init__.py __all__", expected_consts, init_all, "__all__")

    # --- Docs checks ---
    # ja-kunrei is a variant mode, not a separate script — exclude from ref text check
    langs_needing_ref = langs - {"ja-kunrei"}
    check("Reference text entries", langs_needing_ref, ref_texts, "docs/reference.md")
    # The doc table uses "respective language" groupings for many scripts.
    # Check only that explicitly-listed new scripts appear, not the grouped ones.
    # Grouped scripts: Bengali, Tamil, Telugu, Kannada, Malayalam, Gujarati,
    # Gurmukhi, Odia, Sinhala, Ethiopic, Tibetan, Lao, Myanmar, Khmer,
    # Mongolian, Javanese, Hebrew + CJK (Han, Hiragana, Katakana, Hangul)
    grouped_doc_langs = {
        "bn",
        "ta",
        "te",
        "kn",
        "ml",
        "gu",
        "pa",
        "or",
        "si",
        "am",
        "bo",
        "lo",
        "my",
        "km",
        "mn",
        "jv",
        "he",
        "ru",
        "zh",
        "hi",
        "ar",  # multi-lang scripts with defaults
    }
    doc_check_langs = langs_with_script - grouped_doc_langs
    check(
        "Auto-detection doc table (langs with script mapping)",
        doc_check_langs,
        auto_doc_langs,
        "language-support.md script-to-language table",
    )

    # --- Test checks ---
    check("LANG_SAMPLES in test_dynamic_coverage.py", langs, dyn_samples, "LANG_SAMPLES")
    check(
        "_ALL_LANG_ASCII_SAMPLES in test_transliterate.py",
        langs,
        ascii_samples,
        "_ALL_LANG_ASCII_SAMPLES",
    )
    check(
        "Auto-detection tests for script-mapped langs",
        langs_with_script,
        auto_test_langs,
        "test_lang_auto.py parametrize",
    )

    if errors:
        print(f"\n{errors} check(s) failed.")
        return 1
    else:
        print("All consistency checks passed.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
