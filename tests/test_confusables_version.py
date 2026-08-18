"""#560 — the bundled ``confusables.txt`` version is reachable from a running program.

The version was already written down twice at build time (the TSV header and
``docs/provenance.md``), but neither is reachable at runtime, so a caller could not
answer "is my confusables fold stale?" without inferring it from behaviour. These tests
pin the runtime accessor and, more importantly, pin it to the data it describes: every
assertion here is derived from the table or the docs, never from a literal typed into
the test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import disarm

REPO_ROOT = Path(__file__).resolve().parent.parent
LATIN_TSV = REPO_ROOT / "src" / "tables" / "data" / "confusables_to_latin.tsv"
CYRILLIC_TSV = REPO_ROOT / "src" / "tables" / "data" / "confusables_to_cyrillic.tsv"
PROVENANCE = REPO_ROOT / "docs" / "provenance.md"

#: The header line ``scripts/gen_confusables.py`` writes, e.g.
#: ``# Unicode UTS#39 confusables.txt 17.0.0, folded to Latin, ...``
HEADER_RE = re.compile(r"^# Unicode UTS#39 confusables\.txt (?P<version>[0-9]+(?:\.[0-9]+)+)")


def _header_version(tsv: Path) -> str:
    """The version named on line 1 of a confusables TSV."""
    first_line = tsv.read_text(encoding="utf-8").splitlines()[0]
    match = HEADER_RE.match(first_line)
    assert match is not None, f"{tsv.name}: header does not name a version: {first_line!r}"
    return match.group("version")


def test_constant_is_exported() -> None:
    assert isinstance(disarm.CONFUSABLES_VERSION, str)
    assert disarm.CONFUSABLES_VERSION


def test_constant_is_a_dotted_numeric_version() -> None:
    parts = disarm.CONFUSABLES_VERSION.split(".")
    assert len(parts) >= 2, f"expected at least major.minor, got {disarm.CONFUSABLES_VERSION!r}"
    assert all(part.isdigit() for part in parts), disarm.CONFUSABLES_VERSION


@pytest.mark.skipif(not LATIN_TSV.exists(), reason="source checkout only")
def test_constant_matches_the_latin_table_header() -> None:
    """Derived, not typed twice — the acceptance criterion for #560."""
    assert disarm.CONFUSABLES_VERSION == _header_version(LATIN_TSV)


@pytest.mark.skipif(not CYRILLIC_TSV.exists(), reason="source checkout only")
def test_both_tables_agree_on_the_version() -> None:
    """One constant covers both tables only while both name the same release.

    build.rs asserts this at build time. Asserting it here as well means the reason the
    API is a single constant, rather than a per-table accessor, stays visible.
    """
    assert _header_version(LATIN_TSV) == _header_version(CYRILLIC_TSV)


@pytest.mark.skipif(not PROVENANCE.exists(), reason="source checkout only")
def test_provenance_doc_names_the_same_version() -> None:
    """``docs/provenance.md`` is what users pin against; it must not drift from the code."""
    row = next(
        line
        for line in PROVENANCE.read_text(encoding="utf-8").splitlines()
        if "confusables_to_latin.tsv" in line
    )
    assert f"**{disarm.CONFUSABLES_VERSION}**" in row, row


@pytest.mark.skipif(not LATIN_TSV.exists(), reason="source checkout only")
def test_distinct_from_the_package_version() -> None:
    """Data vintage and release number are different facts and move independently.

    Not an assertion that they never coincide — an assertion that the constant reports
    the table, so it must equal the table header rather than ``__version__``.
    """
    assert disarm.CONFUSABLES_VERSION == _header_version(LATIN_TSV)


def test_case_folding_version_is_not_claimed() -> None:
    """Guards the naming decision (#560 review).

    The constant is deliberately not called ``UNICODE_VERSION``: disarm's tables do not
    share one Unicode release, so a library-wide name would be wrong for three of the
    four surfaces listed in ``docs/provenance.md``. If someone later adds that alias,
    this test asks them to reckon with the per-table versions first.
    """
    assert not hasattr(disarm, "UNICODE_VERSION")
