"""`strip_format` keeps a presentation selector only after a base registered for it (#1135).

#413 asked to keep `U+FE0E` and `U+FE0F` when adjacent to a valid base, and the fix for its
idempotence defined valid as "survives the later strips". So any letter qualified, and a word
spelled in the two selectors, one after each letter, left the preset whole. After `a` the
selector changes no glyph, which is what makes it a free channel.

A valid base is now one Unicode's `emoji-variation-sequences.txt` lists. Its only ASCII members
are the digits, `#` and `*`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import disarm
from disarm import strip_format

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "src" / "tables" / "data" / "variation_sequences.tsv"
TEXT, EMOJI = "\ufe0e", "\ufe0f"


def _rows() -> set[tuple[int, int]]:
    rows = set()
    for line in TABLE.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            base, selector = line.split("\t")
            rows.add((int(base, 16), int(selector, 16)))
    return rows


@pytest.mark.parametrize("selector", [TEXT, EMOJI])
@pytest.mark.parametrize("base", ["a", "A", "\u0430", "\u845b", "!", "\u00e9"])
def test_a_selector_after_a_base_no_sequence_registers_is_removed(base: str, selector: str) -> None:
    assert strip_format(f"{base}{selector}x") == f"{base}x"


@pytest.mark.parametrize(
    "text",
    [
        f"\u2764{EMOJI}",
        f"\u2764{TEXT}",
        f"\u00a9{TEXT}",
        f"\u00a9{EMOJI}",
        f"1{EMOJI}\u20e3",
        f"#{EMOJI}\u20e3",
        f"*{EMOJI}\u20e3",
        f"\U0001f44d{EMOJI}",
    ],
)
def test_a_registered_sequence_is_unchanged(text: str) -> None:
    assert strip_format(text) == text


def test_a_word_spelled_in_selectors_does_not_survive() -> None:
    bits = "".join(format(byte, "08b") for byte in b"hidden")
    cover = "the quick brown fox jumps over the lazy dog and keeps on running"
    text = "".join(
        letter + (EMOJI if bit == "1" else TEXT) for letter, bit in zip(cover, bits, strict=False)
    )
    assert TEXT in text and EMOJI in text
    once = strip_format(text)
    assert TEXT not in once
    assert EMOJI not in once
    assert strip_format(once) == once


def test_every_registered_emoji_base_keeps_both_selectors_and_is_a_fixed_point() -> None:
    """A base a later stage removes would orphan the selector, the D-2 bug in #413."""
    kept = 0
    for base, selector in sorted(_rows()):
        if selector not in (0xFE0E, 0xFE0F):
            continue
        text = chr(base) + chr(selector)
        once = strip_format(text)
        assert strip_format(once) == once, f"U+{base:04X}"
        kept += once == text
    assert kept >= 700


def test_the_table_is_not_empty_and_holds_the_rows_the_issue_names() -> None:
    rows = _rows()
    assert (0x2764, 0xFE0F) in rows
    assert (0x0030, 0xFE00) in rows, "StandardizedVariants, read by #1134"
    assert (ord("a"), 0xFE0F) not in rows
    bases = {base for base, selector in rows if selector == 0xFE0F}
    assert {base for base in bases if base < 0x80} == {*map(ord, "0123456789#*")}


def test_only_ordinary_selectors_are_in_the_table() -> None:
    assert {selector for _, selector in _rows()} <= set(range(0xFE00, 0xFE10))


def test_the_other_two_comparison_surfaces_still_remove_all_of_them() -> None:
    text = f"\u2764{EMOJI}"
    assert disarm.canonicalize(text) == "\u2764"


def test_provenance_records_the_table_and_its_version() -> None:
    """Consumers pin against that page for the byte-stable behaviour of a preset."""
    page = (ROOT / "docs" / "provenance.md").read_text(encoding="utf-8")
    row = next((line for line in page.splitlines() if "variation_sequences.tsv" in line), "")
    assert "18.0.0" in row
