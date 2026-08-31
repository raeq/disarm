"""Drift gates for `src/tables/data/word_joiners.tsv` (#750).

The table is a Unicode snapshot, so it carries the same obligations as every other bundled
table: it must say which version it is, it must match that version, and it must not be
silently edited. `scripts/gen_word_joiners.py` derives it from the general category rather
than curating it, so a Unicode release that adds a dash cannot leave a hole — these
assertions are what make that claim checkable.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pytest

TABLE = Path(__file__).resolve().parent.parent / "src" / "tables" / "data" / "word_joiners.tsv"

#: `Pd` is dash punctuation, `Pc` is connector punctuation.
JOINER_CATEGORIES = frozenset({"Pd", "Pc"})

#: `U+002E FULL STOP` is `Po`, and is in the table by hand: it is the separator the branch
#: was built for, and widening the category test to `Po` would pull in `?`, `!` and `@`.
EXTRA = frozenset({0x002E})


def _rows() -> list[int]:
    return [
        int(line, 16)
        for line in TABLE.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]


def _declared_version() -> str:
    header = TABLE.read_text(encoding="utf-8")
    match = re.search(r"^# Unicode (\d+\.\d+\.\d+),", header, re.M)
    assert match, "the table must name the Unicode version it was generated from"
    return match.group(1)


ROWS = _rows()


def test_the_table_is_not_empty_or_truncated() -> None:
    """A gate over an empty set passes for the wrong reason."""
    assert len(ROWS) > 30, len(ROWS)


def test_every_row_is_a_joiner_or_the_documented_exception() -> None:
    """Nothing may be hand-added except `U+002E`, which the header names.

    A row the running interpreter reports as `Cn` is **version skew**, not a bad row:
    `U+10D6E` is `Pd` in UCD 17.0 and unassigned in 16.0, so a host on the older Unicode
    sees a code point the table legitimately contains. Skipped rather than failed — the
    same distinction `tests/test_assigned_ranges.py` draws — and the count of skips is
    asserted to stay small so this cannot quietly become a no-op.
    """
    skew = []
    for cp in ROWS:
        if cp in EXTRA:
            continue
        category = unicodedata.category(chr(cp))
        if category == "Cn":
            skew.append(cp)
            continue
        assert category in JOINER_CATEGORIES, f"U+{cp:04X} is {category}, not a within-word joiner"
    assert len(skew) < 5, (
        f"{len(skew)} rows are unassigned on this interpreter (UCD "
        f"{unicodedata.unidata_version}) against a table declaring "
        f"{_declared_version()}. That is more than version skew explains: "
        f"{[f'U+{cp:04X}' for cp in skew]}"
    )


def test_the_table_is_sorted_and_has_no_duplicates() -> None:
    assert ROWS == sorted(set(ROWS))


def test_the_header_declares_a_unicode_version() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", _declared_version())


@pytest.mark.skipif(
    unicodedata.unidata_version != "17.0.0",
    reason="only the interpreter matching the declared version can check completeness",
)
def test_the_table_is_complete_for_its_declared_version() -> None:
    """Derived, not curated: every `Pd`/`Pc` code point must be present.

    Skipped unless the running interpreter carries the declared UCD, because a host on an
    older Unicode would report a hole that is really version skew — the failure mode
    `tests/test_assigned_ranges.py` already guards against.
    """
    assert _declared_version() == unicodedata.unidata_version
    expected = {
        cp
        for cp in range(0x110000)
        if not (0xD800 <= cp < 0xE000) and unicodedata.category(chr(cp)) in JOINER_CATEGORIES
    } | set(EXTRA)
    assert set(ROWS) == expected, {
        "missing": sorted(f"U+{cp:04X}" for cp in expected - set(ROWS)),
        "extra": sorted(f"U+{cp:04X}" for cp in set(ROWS) - expected),
    }


def test_the_visually_identical_pair_is_both_present() -> None:
    """`U+2010 HYPHEN` and `U+002D HYPHEN-MINUS` render the same and used to disagree."""
    assert 0x2010 in ROWS
    assert 0x002D in ROWS


def test_the_two_that_canonicalize_rewrites_are_present() -> None:
    """`canonicalize` folds `U+2E40` and `U+30A0` to `=`, which is not a joiner either.

    The fold moved the attack from one unrecognised separator to another, which is why
    #750 calls these the sharp ones.
    """
    assert 0x2E40 in ROWS
    assert 0x30A0 in ROWS
