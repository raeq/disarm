"""Prose that quotes a `benchmarks/meta` finding must quote it accurately (#816).

`docs/limitations.md` states the detect-versus-transform gap with numbers — 30 of 37
recovered, 7 of 37 flagged — and attributes them to the `nonstandard-unicode-sets` suite.
That suite is `Availability.MANUAL`: its corpus is not in the tree, so no test can
re-measure it, and the numbers in the page would otherwise be unattached prose that
drifts from the suite it names.

The suite's `Provenance.finding` is the recorded measurement, and by protocol it is
historical and never edited to match a fresh run. That makes it a stable thing to hold
the documentation to: this fails if either side is changed without the other.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))


@pytest.fixture(scope="module")
def nonstandard_finding() -> str:
    from meta.registry import all_suites

    suite = next(s for s in all_suites() if s.name == "nonstandard-unicode-sets")
    finding = suite.provenance.finding
    assert finding, "the suite's recorded finding is what the page cites"
    return finding


def test_the_page_quotes_the_recorded_measurement(nonstandard_finding: str) -> None:
    page = (ROOT / "docs" / "limitations.md").read_text(encoding="utf-8")
    section = page.split("### Rewriting is not reporting", 1)
    assert len(section) == 2, "the section that carries the citation is gone"
    body = section[1].split("\n## ", 1)[0]

    # Both fractions, read out of the finding rather than restated here — a literal
    # would have to be updated in three places and would drift in two of them.
    recovered = re.search(r"(\d+)/(\d+) sets recovered", nonstandard_finding)
    flagged = re.search(r"only (\d+)/(\d+) flagged", nonstandard_finding)
    assert recovered and flagged, nonstandard_finding

    assert f"{recovered.group(1)} of {recovered.group(2)}" in body
    assert f"{flagged.group(1)} of {flagged.group(2)}" in body
    assert "nonstandard-unicode-sets" in body, "the page must name its source"


def test_the_citation_names_the_published_failure_mode(nonstandard_finding: str) -> None:
    """The gap is a named result, not a repo-internal observation.

    Dropping the citation while keeping the numbers would turn a published failure mode
    back into an unsourced claim about disarm.
    """
    page = (ROOT / "docs" / "limitations.md").read_text(encoding="utf-8")
    assert "10.1145/3774904.3792438" in page
    assert "success interval" in page
