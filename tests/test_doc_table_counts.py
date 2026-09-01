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

The second guard here (#708) is a different shape for the same rot. Prose figures are
parsed out and compared against a data file; a **comparison table** is parsed out and
compared against the library itself, one row at a time. It exists because
``docs/user-guide/graphemes.md`` said ``नमस्ते`` was 4 grapheme clusters three screens
below four executed blocks asserting 3, and every doc gate in the repo reads fenced code
blocks while none reads a markdown table.

The published table is the input, deliberately. ``tests/test_performance_claims.py``
hand-writes assertions mirroring its table, which creates a second list that can drift
from the first — someone fixes the test, not the page, and the gate goes green over
documentation that is still wrong. Parsing the page cannot do that.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pytest

import disarm

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
    # #792: the RTL targets. Anchored on the script name rather than on position,
    # because the ordinal patterns above already broke once when a fifth "(N mappings)"
    # was added between them.
    pytest.param(
        Path("python/disarm/_api.py"),
        r"``\"arabic\"`` \(~?([\d,]+) mappings\)",
        "confusables_to_arabic.tsv",
        id="python-docstring-arabic",
    ),
    pytest.param(
        Path("python/disarm/_api.py"),
        r"``\"hebrew\"`` \(~?([\d,]+) mappings\)",
        "confusables_to_hebrew.tsv",
        id="python-docstring-hebrew",
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


# ── Comparison tables: assert the published row, not a copy of it (#708) ──────

GRAPHEMES = Path("docs/user-guide/graphemes.md")
GRAPHEME_TABLE_HEADER = "| Text | `len(b)` bytes | `len(s)` codepoints | `grapheme_len(s)` |"

#: A parenthetical in the Text cell is a **normalization instruction**, not a label.
#: The two ``café`` rows hold byte-identical cell text (both NFC in the source, because
#: an editor will normalize the file), and so do the two ``한`` rows. Only the
#: parenthetical separates them. A parser that ignores it scores the NFD and jamo rows
#: against the precomposed string and passes — wrongly — on two of the nine rows.
NORMALIZATION = {"NFC": "NFC", "precomposed": "NFC", "NFD": "NFD", "jamo": "NFD"}

_TABLE_ROW = re.compile(
    r'^\|\s*`"(?P<text>.*)"`\s*(?:\((?P<note>[^)]*)\))?\s*\|'
    r"\s*(?P<byte_len>\d+)\s*\|\s*(?P<codepoints>\d+)\s*\|\s*(?P<graphemes>\d+)\s*\|\s*$"
)


def _grapheme_rows() -> list:
    """Every row of the graphemes comparison table, as the page publishes it.

    Anchored to the header line rather than to a line number or a bare regex sweep, so
    the table can move within the page but cannot be silently swapped for a different
    one, and a second table elsewhere in the file cannot leak in.
    """
    lines = (ROOT / GRAPHEMES).read_text(encoding="utf-8").splitlines()
    # A bare `.index()` here raises `ValueError: not in list`, which names neither the
    # file nor what it was looking for — the least useful failure a drift gate can give.
    assert GRAPHEME_TABLE_HEADER in lines, (
        f"{GRAPHEMES}: the comparison-table header line is gone. This guard anchors to "
        f"it exactly, including spacing, and expected:\n"
        f"    {GRAPHEME_TABLE_HEADER}\n"
        f"If the table was reworded or moved, update GRAPHEME_TABLE_HEADER in the same "
        f"change — otherwise the rows below it stop being checked."
    )
    start = lines.index(GRAPHEME_TABLE_HEADER) + 2  # header + separator

    rows = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        match = _TABLE_ROW.match(line)
        assert match is not None, f"{GRAPHEMES}: unparsable table row: {line!r}"

        note = (match["note"] or "").strip()
        # Fail on an unrecognised parenthetical rather than treating it as prose. A new
        # form silently read as plain text is exactly the pass this guard exists to deny.
        assert note in NORMALIZATION or not note, (
            f"{GRAPHEMES}: unknown parenthetical {note!r}. It reads as a normalization "
            f"instruction, so add it to NORMALIZATION or the row is scored against the "
            f"wrong string."
        )
        form = NORMALIZATION.get(note)
        text = unicodedata.normalize(form, match["text"]) if form else match["text"]
        rows.append(
            pytest.param(
                text,
                (int(match["byte_len"]), int(match["codepoints"]), int(match["graphemes"])),
                id=f"{match['text']}-{note or 'as-written'}",
            )
        )

    assert len(rows) == 9, (
        f"{GRAPHEMES}: parsed {len(rows)} rows, expected 9. A gate that matches nothing "
        f"passes vacuously — if the table genuinely gained or lost a row, update this "
        f"count in the same change."
    )
    return rows


@pytest.mark.parametrize(("text", "published"), _grapheme_rows())
def test_grapheme_table_row_matches_the_library(text: str, published: tuple) -> None:
    measured = (len(text.encode("utf-8")), len(text), disarm.grapheme_len(text))
    assert measured == published, (
        f"{GRAPHEMES} publishes {published} for {text!r} but the library measures "
        f"{measured}. The table is the input to this test, so correct the page."
    )
