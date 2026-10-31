"""Selectors or `U+034F` spread one per letter report, as a run of them does (#1134).

The run rule needs two touching selectors, or eight `U+034F`, so marks spread out with none
touching read clean, while `canonicalize` removes them all. What separates such a carrier
from ordinary text is the base, and Unicode publishes that: no letter takes any of them.

A selector after a base no sequence registers counts, and so does `U+034F` before a non-mark.
Eight in one text report, the floor the zero-width run rule uses: enough to spell one byte,
and more than any ordinary text holds by accident. Ideographs answer differently. The IVD
registers tens of thousands of sequences and is not shipped, so a selector in the ideographic
range after an ideograph counts only when a text uses eight different ones, because registered
variants of a word repeat and a message's bytes do not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import disarm
from disarm import decode_smuggled, has_anomalies, inspect_anomalies

COVER = "the quick brown fox jumps over the lazy dog while seventy zebras quietly watch the sunset"
GE = "\u845b"


def spread(mark: str, count: int = 22, every: int = 3) -> str:
    """One `mark` after every `every`th letter, `count` of them."""
    out = []
    placed = 0
    letters = 0
    for ch in COVER * 3:
        out.append(ch)
        if ch.isalpha():
            letters += 1
            if letters % every == 0 and placed < count:
                out.append(mark)
                placed += 1
    assert placed == count
    return "".join(out)


@pytest.mark.parametrize(
    "mark",
    ["\ufe00", "\ufe01", "\ufe0e", "\ufe0f", "\U000e0100", "\u034f"],
    ids=lambda m: f"U+{ord(m):04X}",
)
def test_marks_spread_one_per_letter_report(mark: str) -> None:
    text = spread(mark)
    assert has_anomalies(text)
    assert inspect_anomalies(text).kinds == ["invisible"]


@pytest.mark.parametrize("every", [1, 2, 3, 5])
def test_spacing_does_not_defeat_it(every: int) -> None:
    assert has_anomalies(spread("\ufe01", count=40, every=every))


def test_seven_are_under_the_floor_and_eight_are_not() -> None:
    assert not has_anomalies(spread("\ufe0f", count=7))
    assert has_anomalies(spread("\ufe0f", count=8))


@pytest.mark.parametrize(
    "text",
    [
        "\u2764\ufe0f" * 50,
        "1\ufe0f\u20e3" * 20,
        f"{GE}\U000e0100" * 40,
        "0\ufe00" * 20,
        "A\ufe0e",
        "\u05d0\u034f\u05b8",
        "\u05d0\u034f\u05b8 " * 20,
    ],
    ids=[
        "registered emoji",
        "keycaps",
        "one registered ideographic sequence",
        "standardized variant",
        "one selector",
        "cgj before a hebrew point",
        "cgj before a hebrew point, repeated",
    ],
)
def test_registered_and_ordinary_uses_stay_clean(text: str) -> None:
    assert not has_anomalies(text)
    assert not inspect_anomalies(text).kinds


def _ideographic_carrier(bases: int, selectors: int, count: int = 32) -> str:
    return "".join(f"{chr(0x4E00 + i % bases)}{chr(0xE0100 + i % selectors)}" for i in range(count))


def test_a_message_spelled_across_ideographs_reports() -> None:
    """ghostchars' carrier: 32 ideographs on 8 bases, with 15 distinct selectors."""
    assert has_anomalies(_ideographic_carrier(bases=8, selectors=15))


def test_one_base_cycling_every_selector_reports() -> None:
    assert has_anomalies("".join(f"{GE}{chr(0xE0100 + i % 16)}" for i in range(32)))


def test_a_japanese_text_with_a_few_variants_on_many_bases_stays_clean() -> None:
    assert not has_anomalies(_ideographic_carrier(bases=30, selectors=4, count=60))


def test_decode_smuggled_still_reads_nothing_from_a_spread_pattern() -> None:
    """A bit pattern across letters is not one of its schemes."""
    assert decode_smuggled(spread("\ufe01")) == []


def test_every_surface_that_removed_them_still_does() -> None:
    text = spread("\ufe01")
    assert "\ufe01" not in disarm.canonicalize(text)
    assert "\ufe01" not in disarm.get_pipeline("llm_guardrail")(text)


def test_the_finding_says_how_many_and_where_the_first_is() -> None:
    text = spread("\ufe01")
    found = inspect_anomalies(text).findings
    assert len(found) == 1
    assert found[0].kind == "invisible"
    assert "22" in found[0].detail
    assert text.encode("utf-8")[found[0].start : found[0].end].decode("utf-8") == "\ufe01"


def test_has_anomalies_and_inspect_anomalies_agree() -> None:
    for text in (spread("\u034f"), spread("\ufe0f", count=7), _ideographic_carrier(8, 15)):
        assert has_anomalies(text) == bool(inspect_anomalies(text).kinds), ascii(text[:20])


def test_the_pages_describe_the_spread_shape() -> None:
    root = Path(__file__).resolve().parent.parent
    for page in ("docs/limitations.md", "docs/user-guide/llm-pipelines.md"):
        flat = " ".join((root / page).read_text(encoding="utf-8").split())
        assert "spread" in flat, page
