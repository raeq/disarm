"""The detect-versus-transform gap keeps its citation (#816).

`docs/limitations.md` states that disarm's transforms reach more than its detectors
report, and attributes the shape of that failure to a published result rather than
presenting it as an observation about this library. The citation is the part that rots:
prose gets tightened, a DOI looks like decoration, and what remains is an unsourced claim
about a competitor-free field.

The gate is deliberately narrow. It does not check numbers — the section deliberately
carries none — only that the section exists, names the phenomenon, and keeps the
reference that makes it checkable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "limitations.md"
HEADING = "### Rewriting is not reporting"


@pytest.fixture(scope="module")
def section() -> str:
    page = PAGE.read_text(encoding="utf-8")
    assert HEADING in page, f"{HEADING} is gone from {PAGE.name}"
    return page.split(HEADING, 1)[1].split("\n## ", 1)[0]


def test_the_section_keeps_its_citation(section: str) -> None:
    assert "10.1145/3774904.3792438" in section, "the DOI is what makes the claim checkable"
    assert "success interval" in section, "the named phenomenon is the point of citing it"


def test_the_section_reaches_the_recommendation(section: str) -> None:
    """A limitation with no consequence attached is a fact nobody acts on."""
    assert "clean unconditionally" in section
    assert "#601" in section, "the decision that recommendation comes from"


def test_the_section_states_the_direction_of_the_gap(section: str) -> None:
    """Which side is wider is the whole claim; a reader who loses it gets it backwards."""
    lowered = section.lower()
    assert "strictly less" in lowered or "less than" in lowered
