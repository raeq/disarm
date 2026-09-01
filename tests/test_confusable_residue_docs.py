"""#791 — the documented residue must match the table it describes.

`docs/user-guide/confusables.md` presents `target_script` as a menu of two, and what it
did not say is that generation **drops an entire equivalence class** when no member of it
belongs to the target script. The two options are not two views of one table; they are the
only two views that exist, and a class whose members are all Arabic or all CJK survives
into neither.

The counts in that section are the kind that rot: they move whenever the confusable tables
are regenerated, and #821 already moved them once between the issue being filed (4,384)
and this being written (4,331), and #831 moved it again to 4,330 by mapping one of the
17 ICANN LGR sources that had been unmapped. So they are derived here rather than trusted
— the same
discipline `tests/test_doc_table_counts.py` applies to the mapping totals.

That applies to the per-script breakdown too. An earlier version of this file checked
only the *ordering* there while the page went on publishing exact counts beside it —
which is the failure mode the module docstring is about, one table down. Both the order
and the figures are derived below.
"""

from __future__ import annotations

import collections
import re
import unicodedata
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "user-guide" / "confusables.md"
UPSTREAM = ROOT / "data" / "confusables.txt"


def _documented(label: str) -> int:
    """The figure the page states for `label`, from its own table row."""
    for line in PAGE.read_text(encoding="utf-8").splitlines():
        if label in line and "|" in line:
            numbers = re.findall(r"\b([\d,]{3,})\b", line)
            if numbers:
                return int(numbers[-1].replace(",", ""))
    raise AssertionError(f"no row in {PAGE.name} states {label!r}")


def test_the_page_states_the_residue() -> None:
    """A gate over a missing section passes for the wrong reason."""
    text = PAGE.read_text(encoding="utf-8")
    assert "only two views" in text, "the section #791 asked for is gone"
    assert "unmapped_confusables" in text, "the page must name the way to measure it"


def test_the_upstream_source_count_is_right() -> None:
    sources = {
        line.split(";")[0].strip()
        for line in UPSTREAM.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and ";" in line
    }
    assert _documented("TR39 sources in the bundled file") == len(sources)


def test_the_latin_residue_count_is_right() -> None:
    """The number a reader would act on, checked against the function that produces it."""
    actual = len(disarm.unmapped_confusables(target_script="latin"))
    assert _documented('unmapped under `target_script="latin"`') == actual


def test_the_rtl_share_is_right() -> None:
    """948 of the residue being strong-RTL is what makes this worth a section."""
    residue = disarm.unmapped_confusables(target_script="latin")
    rtl = sum(1 for char in residue if unicodedata.bidirectional(char) in {"R", "AL"})
    assert _documented("strong-RTL") == rtl


#: The page's row labels, mapped to the UCD `Name` prefix they stand for. Written out
#: rather than derived because the labels are prose — "Kangxi radicals", not "KANGXI" —
#: and a label the page invents should fail this test rather than silently match nothing.
SCRIPT_LABELS = {
    "CJK": ("CJK",),
    "Arabic": ("ARABIC",),
    "Hangul": ("HANGUL",),
    "Canadian Aboriginal": ("CANADIAN",),
    "Kangxi radicals": ("KANGXI",),
}


def _residue_by_script() -> collections.Counter[str]:
    scripts: collections.Counter[str] = collections.Counter()
    for char in disarm.unmapped_confusables(target_script="latin"):
        try:
            scripts[unicodedata.name(char).split()[0]] += 1
        except ValueError:
            continue
    return scripts


def test_the_per_script_breakdown_is_right() -> None:
    """Every figure in the breakdown table, derived from the same function.

    Review on #845 asked for this: the section explains that these numbers rot, and then
    published five of them that nothing checked. Deriving them is the option that keeps
    the magnitudes — "CJK 1,158 against Kangxi 212" is the shape of the residue, and an
    ordering-only table does not carry it.
    """
    scripts = _residue_by_script()
    for label, prefixes in SCRIPT_LABELS.items():
        actual = sum(scripts[prefix] for prefix in prefixes)
        assert _documented(label) == actual, (
            f"the page says {_documented(label)} for {label}, measured {actual}"
        )


def test_the_per_script_ordering_holds() -> None:
    """The table is also in descending order, which is how the prose reads it."""
    documented = [_documented(label) for label in SCRIPT_LABELS]
    assert documented == sorted(documented, reverse=True), documented
    scripts = _residue_by_script()
    assert scripts.most_common(1)[0][0] == "CJK", scripts.most_common(3)


# ── the half the page must not over-claim ────────────────────────────────────


@pytest.mark.parametrize(
    ("left", "right", "name"),
    [
        ("ک", "ك", "Persian keheh / Arabic kaf"),
        ("ی", "ي", "Farsi yeh / Arabic yeh"),
    ],
    ids=["keheh-kaf", "yeh-yeh"],
)
def test_the_fold_misses_what_the_key_builders_catch(left: str, right: str, name: str) -> None:
    """The gap is in the fold, and it does not follow that the key builders share it.

    They transliterate first, which reaches these pairs. Asserted so the page cannot
    quietly become an over-claim if either side changes.
    """
    assert disarm.normalize_confusables(left) != disarm.normalize_confusables(right), name
    assert disarm.search_key(left) == disarm.search_key(right), name
    assert disarm.catalog_key(left) == disarm.catalog_key(right), name
