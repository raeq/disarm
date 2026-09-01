"""#725/#733/#735/#744 — the security and stability pages say what the library does.

Four corrections, one shape: a page stated a property that was true of a *neighbour* of
the thing it described. The CVE matrix answered for a line where the CVE is about a file,
`catalog_key` exempted two scripts that are not exempt, the printable-ASCII rewrites lived
only in a Rust comment, and the stability contract covered three of the eight functions its
own gate watches.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
LIMITATIONS = ROOT / "docs" / "limitations.md"
RUST_API = ROOT / "docs" / "RUST_API.md"

#: Every printable ASCII character any surface rewrites, and what it becomes (#725).
ASCII_REWRITES = {"|": "l", '"': "''", "`": "'"}

#: The surfaces that apply them, and those that do not.
REWRITING = (
    "canonicalize",
    "canonicalize_strict",
    "strip_obfuscation",
    "normalize_confusables",
    "catalog_key",
)
NOT_REWRITING = ("search_key", "sort_key", "ml_normalize")


def test_those_three_are_the_only_printable_ascii_any_surface_rewrites() -> None:
    """#725 — the table's completeness, not just its rows.

    A fourth character joining the set would make the limitations page silently
    incomplete, which is the failure mode a table invites.
    """
    found: dict[str, set[str]] = {}
    for name in REWRITING + NOT_REWRITING:
        fn = getattr(disarm, name)
        for code in range(0x21, 0x7F):
            char = chr(code)
            out = fn(char)
            if out != char and out != char.lower():
                found.setdefault(char, set()).add(name)
    assert set(found) == set(ASCII_REWRITES), (
        f"the set of rewritten printable ASCII moved: {sorted(found)}"
    )


@pytest.mark.parametrize("name", REWRITING)
@pytest.mark.parametrize(("char", "expected"), sorted(ASCII_REWRITES.items()))
def test_the_rewriting_surfaces_rewrite(name: str, char: str, expected: str) -> None:
    assert getattr(disarm, name)(char) == expected


@pytest.mark.parametrize("name", NOT_REWRITING)
@pytest.mark.parametrize("char", sorted(ASCII_REWRITES))
def test_the_others_do_not(name: str, char: str) -> None:
    """These escape it as a side effect of an earlier step, so they are worth pinning."""
    assert getattr(disarm, name)(char) == char


def test_the_limitations_page_names_all_three() -> None:
    page = LIMITATIONS.read_text(encoding="utf-8")
    assert "Five surfaces rewrite printable ASCII" in page, "the #725 section is gone"
    for char in ASCII_REWRITES:
        assert f"`{char}`" in page or f"`` {char} ``" in page or "U+007C" in page


@pytest.mark.parametrize(
    ("spoof", "latin", "keys_as"),
    [("раураl", "paypal", "raural"), ("аррlе", "apple", "arrle")],
)
def test_catalog_key_does_not_collide_cyrillic_with_its_latin_lookalike(
    spoof: str, latin: str, keys_as: str
) -> None:
    """#735 — the docstring claimed these collide. They do not.

    A romanization is a *sound*, not a shape, so a letter that looks like one Latin
    letter routinely keys as a different one.
    """
    assert disarm.catalog_key(spoof) == keys_as
    assert disarm.catalog_key(spoof) != disarm.catalog_key(latin)


def test_the_catalog_key_warning_no_longer_claims_the_exemption() -> None:
    """#735 — the sentence that was wrong, asserted gone rather than assumed fixed."""
    doc = disarm.catalog_key.__doc__ or ""
    assert "Cyrillic and Greek lookalikes do collide" not in doc
    assert "not the exception this warning used to claim" in doc


def test_every_watched_function_carries_a_stability_note() -> None:
    """#733 — the fixture watches eight and the contract covered three.

    Derived from the generator's own list, so a ninth function added there is covered on
    the day it is added rather than whenever someone next reads the page.
    """
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from gen_key_fixture import FUNCTIONS

    documented: dict[str, bool] = {}
    for path in (
        ROOT / "python" / "disarm" / "_presets.py",
        ROOT / "python" / "disarm" / "_api.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                doc = ast.get_docstring(node) or ""
                documented[node.name] = documented.get(node.name, False) or (
                    "**Stability.**" in doc
                )

    missing = [name for name in FUNCTIONS if not documented.get(name)]
    assert not missing, (
        f"watched by tests/test_key_stability.py and carrying no stability note: {missing}. "
        "A reader asking 'may I store this?' gets no answer for these."
    )


def test_the_contract_says_it_covers_all_eight() -> None:
    """#733 — the page, not only the docstrings."""
    page = RUST_API.read_text(encoding="utf-8")
    assert "The contract extends to all eight" in page
    assert "the contract did not cover" in page
