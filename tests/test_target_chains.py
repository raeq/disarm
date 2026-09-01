"""#723 — a fold target must not itself be a source.

`044B` ы mapped to `ƅi`, and `ƅ` (`U+0185`) is a source folding to `b`. So the entry
points that iterate — `normalize_confusables`, `canonicalize` — reached `bi`, while the
single-pass ones — `strip_obfuscation`, and the `confusables` step inside `get_pipeline`
— stopped at `ƅi`.

The issue's title names why it survived: *the exhaustive idempotence gate tests the one
function that iterates*. A gate aimed at the forgiving caller cannot see a defect that
only the strict one meets.

Fixed in the **data**: the generator resolves every target through the map until it is a
fixed point, and `build.rs` asserts no target contains a source — an assert that can only
hold because the data already satisfies it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "src" / "tables" / "data" / "confusables_to_latin.tsv"


def table_rows() -> dict[int, str]:
    rows: dict[int, str] = {}
    for line in TABLE.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "\t" not in stripped:
            continue
        source, value = stripped.split("\t", 1)
        value = re.sub(r"\\u\{([0-9A-Fa-f]+)\}", lambda m: chr(int(m.group(1), 16)), value)
        rows[int(source, 16)] = value
    return rows


def test_no_target_contains_a_source() -> None:
    """The property `build.rs` asserts, checked here too so a failure names the row.

    A build-script panic is a wall of cargo output; this says which row and why.
    """
    rows = table_rows()
    chained = [
        f"U+{source:04X} -> {value!r} (U+{ord(ch):04X} is itself a source)"
        for source, value in rows.items()
        for ch in value
        if ord(ch) in rows
    ]
    assert not chained, "targets that chain the fold:\n  " + "\n  ".join(chained)


@pytest.mark.parametrize("char", ["ы", "ᴔ"])
def test_the_single_pass_callers_reach_the_fixed_point(char: str) -> None:
    """The defect, from the caller's side.

    `strip_obfuscation` does one pass. Before the data was resolved it stopped one step
    short of what `canonicalize` returned for the same input — `ƅi` against `bi`.

    `ӹ` is deliberately not here even though it is the other row #723 names. The two
    functions differ on it for an unrelated and correct reason: it carries a diaeresis,
    which `strip_obfuscation` removes and `canonicalize` preserves. Comparing them there
    would be asserting that accent preservation is a bug.
    """
    assert disarm.strip_obfuscation(char) == disarm.canonicalize(char)


def test_the_other_row_is_a_fixed_point_even_though_the_two_differ() -> None:
    """`ӹ` — what is actually claimed about it.

    `strip_obfuscation` and `canonicalize` give different answers because one strips
    accents. What #723 is about is that the single-pass answer is *stable*, which it now
    is: `bi`, not `ƅi` needing another call.
    """
    once = disarm.strip_obfuscation("ӹ")
    assert once == "bi"
    assert disarm.strip_obfuscation(once) == once


def test_strip_obfuscation_is_a_fixed_point_over_the_bmp() -> None:
    """The exhaustive form, on the function the original gate did not cover."""
    unstable = [
        chr(cp)
        for cp in range(0x20, 0x10000)
        if not 0xD800 <= cp <= 0xDFFF
        and disarm.strip_obfuscation(chr(cp))
        != disarm.strip_obfuscation(disarm.strip_obfuscation(chr(cp)))
    ]
    assert not unstable, (
        f"{len(unstable)} code points where strip_obfuscation is not a fixed point: "
        f"{[hex(ord(c)) for c in unstable[:6]]}"
    )


def test_the_generator_resolves_chains_rather_than_the_consumer() -> None:
    """Where the fix lives is the durable part.

    Resolving in a consumer would leave the data able to reintroduce the class for the
    next consumer. Resolving at generation makes `build.rs`'s assert satisfiable, and the
    assert is what keeps it true.
    """
    generator = (ROOT / "scripts" / "gen_confusables.py").read_text(encoding="utf-8")
    assert "_resolve_target_chains" in generator
    build = (ROOT / "build.rs").read_text(encoding="utf-8")
    assert "is itself a source" in build
    # Every character, not just a single-character target — the hole #723 fell through.
    assert "target.iter().enumerate()" in build
