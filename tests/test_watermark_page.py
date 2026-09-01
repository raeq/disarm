"""#706 — the watermark page's numbers, derived rather than typed.

The page exists because "does disarm remove AI watermarks?" is a question its audience
arrives with and no document answered. Most of the page is a boundary statement and has
nothing to run. The one table that is a measurement is measured here, because a table of
counts is exactly the thing that goes quietly stale.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import disarm

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "security" / "watermarks.md"

#: `Default_Ignorable_Code_Point` as ranges — `unicodedata` exposes no predicate for it.
DEFAULT_IGNORABLE_RANGES = (
    (0x00AD, 0x00AD),
    (0x034F, 0x034F),
    (0x061C, 0x061C),
    (0x115F, 0x1160),
    (0x17B4, 0x17B5),
    (0x180B, 0x180F),
    (0x200B, 0x200F),
    (0x202A, 0x202E),
    (0x2060, 0x206F),
    (0x3164, 0x3164),
    (0xFE00, 0xFE0F),
    (0xFEFF, 0xFEFF),
    (0xFFA0, 0xFFA0),
    (0xFFF0, 0xFFF8),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
    (0xE0000, 0xE0FFF),
)


def carriers() -> list[str]:
    return [
        chr(cp)
        for start, end in DEFAULT_IGNORABLE_RANGES
        for cp in range(start, end + 1)
        if unicodedata.category(chr(cp)) != "Cn"
    ]


def measured() -> dict[str, int]:
    """The page's four buckets, over the same probe shape the page describes."""
    removed, reported = set(), set()
    for char in carriers():
        probe = f"a{char}b"
        if disarm.canonicalize(probe) == "ab":
            removed.add(char)
        if disarm.inspect_anomalies(probe).anomalous:
            reported.add(char)
    everything = set(carriers())
    return {
        "both": len(removed & reported),
        "removed_only": len(removed - reported),
        "reported_only": len(reported - removed),
        "neither": len(everything - removed - reported),
    }


def published() -> list[int]:
    """The counts in the page's table, in order."""
    page = PAGE.read_text(encoding="utf-8")
    table = page[page.index("| | count |") :]
    return [int(n) for n in re.findall(r"\|\s+(\d+)\s+\|", table[: table.index("\n\n")])]


def test_the_four_buckets_match_the_page() -> None:
    counts = measured()
    assert published() == [
        counts["both"],
        counts["removed_only"],
        counts["reported_only"],
        counts["neither"],
    ], f"the page's table is stale; measured {counts}"


def test_removed_and_reported_are_genuinely_different_sets() -> None:
    """The claim the table exists to support, independent of the exact counts.

    If these ever coincide, the page's advice — run both, because transforming and
    reporting see different things — stops being true and the section needs rewriting
    rather than renumbering.
    """
    counts = measured()
    assert counts["removed_only"] > 100, (
        "the page's central point is that most carriers are stripped without a finding"
    )
    assert counts["reported_only"] > 0, (
        "the page states some carriers are reported and deliberately not removed"
    )


def test_the_page_says_the_three_things_it_exists_to_say() -> None:
    """A boundary page that loses its boundary is worse than no page."""
    page = PAGE.read_text(encoding="utf-8")
    for claim in (
        "stripping invisible characters is not the same as removing a watermark",
        "makes no claim about the provenance",
        "out of scope by choice",
    ):
        assert claim in page, f"the page no longer says: {claim!r}"


def test_the_terms_a_reader_searches_for_are_present() -> None:
    """#706's measurement was that these appeared nowhere in the documentation."""
    page = PAGE.read_text(encoding="utf-8").lower()
    for term in ("watermark", "synthid", "c2pa"):
        assert term in page
