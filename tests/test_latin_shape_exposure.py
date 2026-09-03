"""#815 items 4, 5 and 7 — the census, as a fixture that cannot drift.

The number in the issue was 401, and it was wrong in both directions. Its selector matched
names *starting with* `LATIN `, `MODIFIER LETTER ` or `TURNED `, or containing
`SMALL CAPITAL`, so `NEGATIVE CIRCLED LATIN CAPITAL LETTER A` and 51 siblings were outside
it entirely; and it counted combining marks and TAG characters, which are handled by
`strip_accents` and by stripping respectively.

The corrected census is 299 across 8 blocks, published as `latin_shape_exposure.tsv`. It
is an exposure set rather than a bug list — Latin Extended-D's medievalist letters have no
sensible ASCII fold — so what matters is that the list is reviewed and that it cannot grow
without someone noticing.

Asserted per block, not only in total, because a table refresh that gained rows in one
block and lost them in another would pass a total-only check while changing what a
deployment is exposed to.
"""

from __future__ import annotations

import collections
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "latin_shape_exposure.tsv"

_spec = importlib.util.spec_from_file_location(
    "gen_latin_shape_exposure", ROOT / "scripts" / "gen_latin_shape_exposure.py"
)
assert _spec and _spec.loader
gen = importlib.util.module_from_spec(_spec)
sys.modules["gen_latin_shape_exposure"] = gen
_spec.loader.exec_module(gen)


def _fixture_rows() -> list[tuple[int, str, str]]:
    rows = []
    for line in FIXTURE.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or line.startswith("codepoint\t"):
            continue
        cp, block, name = line.split("\t")
        rows.append((int(cp, 16), block, name))
    return rows


def test_the_fixture_matches_the_library() -> None:
    """The gate #815 item 5 asks for. Regenerate with the script, never by hand."""
    assert _fixture_rows() == gen.census(), (
        "latin_shape_exposure.tsv is stale — run scripts/gen_latin_shape_exposure.py. "
        "A code point LEAVING the file is a fix; one JOINING it needs a reason."
    )


@pytest.mark.parametrize(
    ("block", "count"),
    sorted(collections.Counter(b for _, b, _ in _fixture_rows()).items()),
)
def test_each_block_holds_its_count(block: str, count: int) -> None:
    """Per block, so a refresh cannot trade rows between blocks and stay green."""
    live = collections.Counter(b for _, b, _ in gen.census())
    assert live[block] == count, f"{block}: {live[block]} now, {count} in the fixture"


def test_the_total_is_what_the_issue_records() -> None:
    assert len(_fixture_rows()) == 299


def test_the_selector_excludes_combining_marks() -> None:
    """53 of them, and #815's original sweep counted them.

    `COMBINING LATIN SMALL LETTER A` is a diacritic written above a base, not a letter
    standing in for one. It is `strip_accents`' business.
    """
    assert not gen.depicts_a_latin_letter(0x0363)  # COMBINING LATIN SMALL LETTER A
    assert not gen.depicts_a_latin_letter(0x1DD3)  # COMBINING LATIN SMALL LETTER FLATTENED OPEN A


def test_the_selector_excludes_tag_characters() -> None:
    """52 of them, stripped rather than folded (#413), which a naive test reads as a gap."""
    assert not gen.depicts_a_latin_letter(0xE0041)  # TAG LATIN CAPITAL LETTER A


def test_the_selector_excludes_names_that_merely_contain_latin() -> None:
    """`LATIN CROSS` is a symbol; `LATINATE MYSLITE` is Glagolitic. Neither is a letter."""
    assert not gen.depicts_a_latin_letter(0x271E)  # SHADOWED WHITE LATIN CROSS
    assert not gen.depicts_a_latin_letter(0x2C2E)  # GLAGOLITIC CAPITAL LETTER LATINATE MYSLITE


def test_the_selector_includes_what_the_old_one_missed() -> None:
    """The blocks #815's name-prefix sweep could not see, now folded but selectable."""
    for cp in (0x1F150, 0x1F170, 0x1D00, 0xA730):
        assert gen.depicts_a_latin_letter(cp), f"U+{cp:04X} is outside the selector"


def test_what_915_and_920_fixed_is_absent() -> None:
    """Both halves: the classes that were closed must not be in the exposure set."""
    exposed = {cp for cp, _, _ in _fixture_rows()}
    for cp in (0x1D00, 0x1D05, 0x1D18, 0x1D1B, 0xA730):  # single-letter small capitals
        assert cp not in exposed, f"U+{cp:04X} folds since #915 and should not be listed"
    for cp in (0x1F150, 0x1F170, 0x1F17F):  # negative enclosed
        assert cp not in exposed, f"U+{cp:04X} folds since #920 and should not be listed"


def test_the_census_is_pointed_at_something() -> None:
    """A selector that matched nothing would make every assertion above vacuous."""
    selected = sum(
        1
        for cp in range(0x80, 0x30000)
        if not (0xD800 <= cp <= 0xDFFF) and gen.depicts_a_latin_letter(cp)
    )
    assert selected >= 1000, f"only {selected} code points selected; the pattern may have changed"
