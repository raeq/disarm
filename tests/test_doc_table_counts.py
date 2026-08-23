"""Anti-rot guard: documented table sizes must match the tables (#563/#558 follow-up).

``docs/architecture/data-tables.md`` and ``docs/limitations.md`` quote row counts for the
bundled confusable tables. Those numbers move whenever the tables are regenerated — a
table refresh, or a generator change like the one that added 16 rows in #558 — and
nothing was checking them, so they silently went stale within a day of being written.

``scripts/check_doc_claims.py`` catches decorative ``# =>`` output claims but not prose
numbers. This closes that gap for the counts that are cheapest to get wrong: parse the
figure out of the doc, count the TSV, compare.

The comparison is **exact**, despite the prose writing the figures as "~2,181". A
tolerance was the first instinct, and it was wrong: #558 moved the Latin table by 16 rows,
a 0.7% drift, so any tolerance loose enough to absorb "routine churn" would have missed
the very staleness this guard exists to catch. The `~` tells a reader the number is
approximate; it does not license the number being wrong. Regenerating a table is a
deliberate act, and updating one figure in two files in the same change is the cost of
that.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "src" / "tables" / "data"


def _rows(tsv: Path) -> int:
    """Data rows in a TSV — comments and blanks excluded, as build.rs counts them."""
    return sum(
        1
        for line in tsv.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _documented(path: Path, pattern: str) -> int:
    """The first number matched by *pattern* in *path*, with separators stripped."""
    match = re.search(pattern, path.read_text(encoding="utf-8"))
    assert match is not None, f"{path.name}: no figure matched {pattern!r}"
    return int(match.group(1).replace(",", ""))


CASES = [
    pytest.param(
        Path("docs/architecture/data-tables.md"),
        r"Confusables \(Latin\)[^|]*\|[^|]*\|\s*~?([\d,]+)",
        "confusables_to_latin.tsv",
        id="data-tables-latin",
    ),
    pytest.param(
        Path("docs/architecture/data-tables.md"),
        r"Confusables \(Cyrillic\)[^|]*\|[^|]*\|\s*~?([\d,]+)",
        "confusables_to_cyrillic.tsv",
        id="data-tables-cyrillic",
    ),
    pytest.param(
        Path("docs/architecture/data-tables.md"),
        r"Upstream confusable sources[^|]*\|[^|]*\|\s*~?([\d,]+)",
        "confusables_upstream_sources.tsv",
        id="data-tables-upstream",
    ),
    pytest.param(
        Path("docs/limitations.md"),
        r"([\d,]+) sources upstream",
        "confusables_upstream_sources.tsv",
        id="limitations-upstream",
    ),
    pytest.param(
        Path("docs/limitations.md"),
        r"~?([\d,]+) rows bundled",
        "confusables_to_latin.tsv",
        id="limitations-latin",
    ),
    # #590: the two files above were gated and stayed accurate. Three other surfaces
    # quote the same Latin figure and were not, so they drifted to ~2,063 — 118 rows
    # stale — without anything noticing. Gate them at the same source of truth.
    pytest.param(
        Path("src/tables/confusables_data.rs"),
        r"Contains ~?([\d,]+) non-Latin",
        "confusables_to_latin.tsv",
        id="crate-docs-latin",
    ),
    pytest.param(
        Path("src/tables/confusables_data.rs"),
        r"and ~?([\d,]+) non-Cyrillic",
        "confusables_to_cyrillic.tsv",
        id="crate-docs-cyrillic",
    ),
    pytest.param(
        Path("python/disarm/_api.py"),
        r"default, ~?([\d,]+) mappings",
        "confusables_to_latin.tsv",
        id="python-docstring-latin",
    ),
    pytest.param(
        Path("python/disarm/_api.py"),
        r"\(~?([\d,]+) mappings\)",
        "confusables_to_cyrillic.tsv",
        id="python-docstring-cyrillic",
    ),
    pytest.param(
        Path("docs/user-guide/confusables.md"),
        r"`\"latin\"` \(default\) \| ~?([\d,]+)",
        "confusables_to_latin.tsv",
        id="user-guide-latin",
    ),
    pytest.param(
        Path("docs/user-guide/confusables.md"),
        r"`\"cyrillic\"` \| ~?([\d,]+)",
        "confusables_to_cyrillic.tsv",
        id="user-guide-cyrillic",
    ),
]


@pytest.mark.parametrize(("doc", "pattern", "tsv"), CASES)
def test_documented_count_matches_the_table(doc: Path, pattern: str, tsv: str) -> None:
    doc_path, tsv_path = ROOT / doc, DATA / tsv
    if not doc_path.exists() or not tsv_path.exists():  # pragma: no cover
        pytest.skip("source checkout only")

    claimed, actual = _documented(doc_path, pattern), _rows(tsv_path)
    assert claimed == actual, (
        f"{doc.name} claims {claimed:,} for {tsv} but it has {actual:,} rows. "
        f"Regenerating the tables moves these figures — update the prose in the same "
        f"change."
    )
