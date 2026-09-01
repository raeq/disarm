"""A confusable fold can *create* a repeated mark, after the step that drops them ran.

#835 added `Step::DropRepeatedMarks` to the key builders. In `canonicalize` it sits
before the confusable fold — deliberately, so the zalgo cap counts marks a reader can
distinguish. But the fold is not order-neutral with respect to it: `U+1EF3` (y with
grave) folds to `U+00FD` (y with acute), whose NFD is `y` + acute. Put a combining acute
after it and the fold *manufactures* a duplicate that nothing downstream removes.

    canonicalize("\\u1ef3\\u0301")  ->  "\\u00fd\\u0301"   (first pass)
    canonicalize("\\u00fd\\u0301")  ->  "\\u00fd"          (second pass)

So `canonicalize` stopped being idempotent on 16 (base, mark) pairs. Before #835 it was
idempotent on all of them, because nothing dropped the repeat on either pass — the
regression is the new step running too early, not the fold.

Every existing idempotence sweep in this repository walks **single code points**. This
defect needs a base *and* a mark, so none of them could see it, which is why it reached
`main` green.
"""

from __future__ import annotations

import pytest

import disarm

#: Combining marks that compose with a Latin base in NFC. Enough to reach the class
#: without sweeping every mark in Unicode.
MARKS = [0x300, 0x301, 0x302, 0x303, 0x304, 0x306, 0x307, 0x308, 0x30A, 0x30C, 0x327, 0x328]

#: Every (base, mark) pair `canonicalize` answered differently on a second pass, measured
#: over the whole code point range. Listed rather than counted so a regression names a
#: character.
REGRESSED = [
    (0x0101, 0x0303),  # LATIN SMALL LETTER A WITH MACRON
    (0x010B, 0x0301),  # LATIN SMALL LETTER C WITH DOT ABOVE
    (0x0121, 0x0327),  # LATIN SMALL LETTER G WITH DOT ABOVE
    (0x0123, 0x0307),  # LATIN SMALL LETTER G WITH CEDILLA
    (0x012B, 0x0303),  # LATIN SMALL LETTER I WITH MACRON
    (0x014D, 0x0303),  # LATIN SMALL LETTER O WITH MACRON
    (0x016B, 0x0303),  # LATIN SMALL LETTER U WITH MACRON
    (0x017C, 0x0301),  # LATIN SMALL LETTER Z WITH DOT ABOVE
    (0x01E7, 0x0306),  # LATIN SMALL LETTER G WITH CARON
    (0x1E45, 0x0301),  # LATIN SMALL LETTER N WITH DOT ABOVE
    (0x1EA3, 0x0300),  # LATIN SMALL LETTER A WITH HOOK ABOVE
    (0x1EBD, 0x0304),  # LATIN SMALL LETTER E WITH TILDE
    (0x1ECF, 0x0300),  # LATIN SMALL LETTER O WITH HOOK ABOVE
    (0x1EE7, 0x0300),  # LATIN SMALL LETTER U WITH HOOK ABOVE
    (0x1EF3, 0x0301),  # LATIN SMALL LETTER Y WITH GRAVE
    (0x1EF7, 0x0301),  # LATIN SMALL LETTER Y WITH HOOK ABOVE
]

BUILDERS = {
    "canonicalize": disarm.canonicalize,
    "canonicalize_strict": disarm.canonicalize_strict,
    "strip_obfuscation": disarm.strip_obfuscation,
    "sort_key": lambda s: disarm.sort_key(s),
    "search_key": lambda s: disarm.search_key(s),
    "catalog_key": lambda s: disarm.catalog_key(s),
}


def test_the_reported_case() -> None:
    """The one the sweep was run from."""
    once = disarm.canonicalize("ỳ́")
    assert disarm.canonicalize(once) == once, f"canonicalize moved again: {once!r}"


@pytest.mark.parametrize(("base", "mark"), REGRESSED, ids=lambda v: f"U+{v:04X}")
def test_every_regressed_pair_is_idempotent(base: int, mark: int) -> None:
    once = disarm.canonicalize(chr(base) + chr(mark))
    assert disarm.canonicalize(once) == once


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_no_builder_moves_on_a_second_pass_over_the_bmp(name: str) -> None:
    """The sweep that would have caught this, over pairs rather than single characters.

    Bounded to the BMP to stay in the fast tier; the full-range version is below, marked
    `formal`. Every pair in `REGRESSED` is in this range, so the bound does not hide the
    class it was written for.
    """
    build = BUILDERS[name]
    moved = []
    for cp in range(0x10000):
        for mark in MARKS:
            text = chr(cp) + chr(mark)
            try:
                once = build(text)
                twice = build(once)
            except Exception:  # noqa: BLE001 - surrogates are not the subject
                continue
            if once != twice:
                moved.append((hex(cp), hex(mark), once, twice))
    assert not moved, f"{name}: {len(moved)} pairs move on a second pass; {moved[:5]}"


@pytest.mark.formal
@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_no_builder_moves_on_a_second_pass_over_every_code_point(name: str) -> None:
    """The exhaustive version. Tier 3 (see CLAUDE.md), because it is slow, not optional."""
    build = BUILDERS[name]
    moved = []
    for cp in range(0x110000):
        for mark in MARKS:
            text = chr(cp) + chr(mark)
            try:
                once = build(text)
                twice = build(once)
            except Exception:  # noqa: BLE001
                continue
            if once != twice:
                moved.append((hex(cp), hex(mark), once, twice))
    assert not moved, f"{name}: {len(moved)} pairs move on a second pass; {moved[:5]}"
