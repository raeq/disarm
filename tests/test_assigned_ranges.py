"""`assigned_ranges.tsv` gates the block-range script table (#774).

`detect_char_script` resolves a script by binary-searching a curated table of **block**
ranges. Blocks have holes: `U+05EB` is unassigned inside the Hebrew block, `U+FDD0` is a
noncharacter inside Arabic Presentation Forms-A. Both inherited the surrounding block's
script, so a code point that does not exist reported as Hebrew or Arabic — and
`"hello" + U+FDD0` came back as `bidi_mixed`, because a phantom Arabic character is
strong-RTL to `strong_dir`.

The table is a snapshot of a Unicode version, so it can rot. Two guards, shaped for where
they run: the structural one holds on any interpreter, and the exact one verifies every
span but only where the interpreter's UCD matches the data.
"""

from __future__ import annotations

import pathlib
import unicodedata

import pytest

import disarm

TSV = (
    pathlib.Path(__file__).resolve().parent.parent
    / "src"
    / "tables"
    / "data"
    / "assigned_ranges.tsv"
)
DATA_UNICODE_VERSION = "17.0.0"


def _spans() -> list[tuple[int, int]]:
    assert TSV.is_file(), (
        f"{TSV} is missing. `detect_char_script` needs it to tell an unassigned code "
        f"point from an assigned one; regenerate with "
        f"`uv run --python 3.15 python scripts/gen_assigned_ranges.py`."
    )
    out = []
    for line in TSV.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        start, end = line.split("\t")
        out.append((int(start, 16), int(end, 16)))
    return out


def test_spans_are_sorted_disjoint_and_non_adjacent() -> None:
    """Structural, so it holds on every interpreter.

    Adjacent spans would mean the generator emitted `A..B` and `B+1..C` separately, which
    is a merge bug rather than data — and the binary search assumes disjointness.
    """
    spans = _spans()
    assert spans, "no spans parsed"
    for (a_start, a_end), (b_start, b_end) in zip(spans, spans[1:], strict=False):
        assert a_start <= a_end, f"U+{a_start:04X}..U+{a_end:04X} is inverted"
        assert b_start > a_end + 1, (
            f"U+{a_start:04X}..U+{a_end:04X} and U+{b_start:04X}..U+{b_end:04X} are "
            f"adjacent or overlapping; they should have been one span"
        )


def test_surrogates_are_absent() -> None:
    """Rust `char` cannot hold a surrogate, so it can never reach the lookup. Listing one
    would describe a case that cannot occur."""
    for start, end in _spans():
        assert not (start <= 0xD800 <= end or start <= 0xDFFF <= end), (
            f"U+{start:04X}..U+{end:04X} covers surrogates"
        )


def test_the_holes_774_found_have_no_script() -> None:
    """Tier 1 regression for the instances."""
    for cp in (0xFDD0, 0x05EB, 0x0530):
        assert disarm.detect_scripts(chr(cp)) == [], (
            f"U+{cp:04X} is unassigned and was given a script"
        )
    # ...and the gate did not cost the assigned neighbours their own.
    assert [s.value for s in disarm.detect_scripts("א")] == ["Hebrew"]
    assert [s.value for s in disarm.detect_scripts("ا")] == ["Arabic"]


def test_a_noncharacter_is_not_a_bidi_conflict() -> None:
    """The consequence #774 leads with. A phantom Arabic character is strong-RTL, so a
    noncharacter beside Latin text made a bidi conflict out of nothing."""
    assert disarm.inspect_anomalies("hello" + chr(0xFDD0)).kinds == []
    # The real signal still fires.
    assert disarm.has_bidi_conflict("hello שלום")


def test_table_matches_this_interpreter_where_it_can() -> None:
    """Exact, and therefore only meaningful on a matching UCD.

    On an older interpreter every code point assigned since would look like a table error,
    so this skips rather than reporting a wall of false differences. The structural checks
    above are what hold on CI.
    """
    if unicodedata.unidata_version != DATA_UNICODE_VERSION:
        pytest.skip(
            f"host UCD {unicodedata.unidata_version} != data {DATA_UNICODE_VERSION}; "
            f"every code point assigned between them would read as a table error"
        )
    covered = set()
    for start, end in _spans():
        covered.update(range(start, end + 1))
    for cp in range(0x110000):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        assigned = unicodedata.category(chr(cp)) != "Cn"
        assert (cp in covered) == assigned, f"U+{cp:04X}: table says {cp in covered}"
