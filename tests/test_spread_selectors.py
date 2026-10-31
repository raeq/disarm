"""Selectors or `U+034F` spread one per letter report, as a run of them does (#1134).

The run rule needs two touching selectors, or eight `U+034F`, so marks spread out with none
touching read clean, while `canonicalize` removes them all. What separates such a carrier
from ordinary text is the base, and Unicode publishes that: no letter takes any of them.

A selector after a base no sequence registers counts, and so does `U+034F` before a non-mark.
Eight in one text report, the floor the zero-width run rule uses: enough to spell one byte,
and more than any ordinary text holds by accident. Ideographs answer to the IVD the same way
(#1196): an unregistered sequence counts, and a registered one does not, unless a text uses eight
different selectors after ideographs. A carrier that keeps to registered sequences has no table
that can tell it apart, and that is pinned below as the limit it is.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

import disarm
from disarm import decode_smuggled, has_anomalies, inspect_anomalies

IVD_TABLE = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "tables"
    / "data"
    / "ideographic_variation_sequences.tsv"
)
COVER = "the quick brown fox jumps over the lazy dog while seventy zebras quietly watch the sunset"
GE = "\u845b"


def _load_generator() -> ModuleType:
    path = Path(__file__).resolve().parent.parent / "scripts" / "gen_ivd_sequences.py"
    spec = importlib.util.spec_from_file_location("gen_ivd_sequences", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def _ivd_rows() -> set[tuple[int, int]]:
    rows = set()
    for line in IVD_TABLE.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            base, selector = line.split("\t")
            rows.add((int(base, 16), int(selector, 16)))
    return rows


def _registered_text(bases: int = 30, per_base: int = 2) -> str:
    """Sequences the IVD registers: `per_base` on each of `bases` bases, four selectors in all."""
    by_base: dict[int, list[int]] = {}
    for base, selector in sorted(_ivd_rows()):
        if 0x4E00 <= base <= 0x9FFF and selector <= 0xE0103:
            by_base.setdefault(base, []).append(selector)
    chosen = [base for base, selectors in sorted(by_base.items()) if len(selectors) >= per_base]
    return "".join(
        f"{chr(base)}{chr(selector)}"
        for base in chosen[:bases]
        for selector in by_base[base][:per_base]
    )


def _bits(word: str) -> list[int]:
    return [int(bit) for byte in word.encode() for bit in f"{byte:08b}"]


def _kanji(count: int) -> list[str]:
    return [chr(0x4E00 + i) for i in range(count)]


def _bit_carrier() -> str:
    bits = _bits("hidden")
    return "".join(f"{k}{chr(0xE0100 + b)}" for k, b in zip(_kanji(48), bits, strict=True))


def _presence_carrier() -> str:
    bits = _bits("hidden")
    return "".join(k + ("\U000e0100" if b else "") for k, b in zip(_kanji(48), bits, strict=True))


def _cycling(selectors: int, count: int = 64) -> str:
    return "".join(f"{k}{chr(0xE0100 + i % selectors)}" for i, k in enumerate(_kanji(count)))


def _registered_bit_carrier() -> str:
    """48 bases that register both selectors, so every sequence here is valid."""
    rows = _ivd_rows()
    bases = [b for b in sorted({b for b, _ in rows}) if 0x4E00 <= b <= 0x9FFF]
    both = [b for b in bases if (b, 0xE0100) in rows and (b, 0xE0101) in rows][:48]
    bits = _bits("hidden")
    return "".join(f"{chr(b)}{chr(0xE0100 + bit)}" for b, bit in zip(both, bits, strict=True))


def test_the_clean_text_holds_what_its_name_says() -> None:
    """It held 23 registered of 60, which no table of registered sequences would have passed."""
    text = _registered_text()
    pairs = list(zip(text[::2], text[1::2], strict=True))
    assert len(pairs) == 60
    assert all((ord(b), ord(s)) in _ivd_rows() for b, s in pairs)
    assert len({s for _, s in pairs}) <= 4


def test_a_japanese_text_with_a_few_variants_on_many_bases_stays_clean() -> None:
    assert not has_anomalies(_registered_text())


def test_one_registered_sequence_repeated_stays_clean() -> None:
    assert not has_anomalies(f"{GE}\U000e0100" * 40)


@pytest.mark.parametrize(
    "text",
    [_bit_carrier(), _cycling(1), _cycling(2), _cycling(4), _cycling(7), _cycling(8), _cycling(16)],
    ids=["bits", "1-selector", "2-selectors", "4-selectors", "7-selectors", "8", "16"],
)
def test_unregistered_sequences_on_ideographs_count_as_any_others_do(text: str) -> None:
    """48 bits on `U+E0100` and `U+E0101` used two selectors and read clean (#1196).

    Each of these holds at least eight sequences the IVD does not register.
    """
    assert "invisible" in inspect_anomalies(text).kinds, ascii(text[:16])
    assert has_anomalies(text), ascii(text[:16])


def test_a_presence_carrier_with_five_unregistered_stays_under_the_floor() -> None:
    assert not has_anomalies(_presence_carrier())


@pytest.mark.parametrize(
    ("text", "unregistered"),
    [
        (_bit_carrier(), 23),
        (_presence_carrier(), 5),
        (_cycling(1), 13),
        (_cycling(2), 31),
        (_cycling(4), 39),
        (_cycling(7), 47),
        (_cycling(8), 52),
        (_cycling(16), 59),
        (_registered_bit_carrier(), 0),
    ],
    ids=["bits", "presence", "1", "2", "4", "7", "8", "16", "registered"],
)
def test_the_finding_counts_what_the_release_does_not_register(
    text: str, unregistered: int
) -> None:
    """The counts the decision weighed, against IVD 2026-08-03."""
    pairs = re.findall("(.)([\U000e0100-\U000e01ef])", text)
    rows = _ivd_rows()
    assert sum((ord(b), ord(s)) not in rows for b, s in pairs) == unregistered


def test_a_registered_sequence_outside_the_bmp_stays_clean() -> None:
    """Asked of the table, not of whether the block table resolves the base to Han."""
    base, selector = max(_ivd_rows())
    assert base > 0xFFFF
    assert not has_anomalies(f"{chr(base)}{chr(selector)}" * 40)


def test_a_carrier_that_keeps_to_registered_sequences_stays_clean() -> None:
    """The limit: every sequence is valid, so no table can tell it apart. The sanitizers can."""
    text = _registered_bit_carrier()
    assert len(_bits("hidden")) == 48
    assert not has_anomalies(text)


def test_the_same_bits_on_hiragana_report() -> None:
    hiragana = "".join(chr(0x3042 + i) for i in range(48))
    bits = _bits("hidden")
    text = "".join(f"{k}{chr(0xE0100 + b)}" for k, b in zip(hiragana, bits, strict=True))
    assert has_anomalies(text)


def test_registered_sequences_cycling_eight_selectors_still_report() -> None:
    """72 bases register eight or more, and variety is still not what a word does."""
    rows = _ivd_rows()
    counts: dict[int, list[int]] = {}
    for base, selector in sorted(rows):
        counts.setdefault(base, []).append(selector)
    base = next(b for b, selectors in sorted(counts.items()) if len(selectors) >= 8)
    assert has_anomalies("".join(f"{chr(base)}{chr(s)}" for s in counts[base][:8]))


@pytest.mark.parametrize(
    "text",
    [
        _bit_carrier(),
        _presence_carrier(),
        _cycling(1),
        _cycling(7),
        _cycling(8),
        _registered_bit_carrier(),
        _registered_text(),
    ],
    ids=["bits", "presence", "one", "seven", "eight", "registered-bits", "registered-text"],
)
def test_all_three_sanitizers_remove_every_ideographic_selector(text: str) -> None:
    def selectors(out: str) -> int:
        return sum(0xE0100 <= ord(c) <= 0xE01EF for c in out)

    assert selectors(disarm.canonicalize(text)) == 0
    assert selectors(disarm.get_pipeline("llm_guardrail")(text)) == 0
    assert selectors(disarm.strip_format(text)) == 0


@pytest.mark.parametrize("text", [_bit_carrier(), _registered_bit_carrier()], ids=["any", "valid"])
def test_decode_smuggled_reads_nothing_from_a_bit_carrier(text: str) -> None:
    """These bits are not one of its schemes."""
    assert decode_smuggled(text) == []


# --- The table itself -------------------------------------------------------------


def test_the_table_is_the_pinned_release() -> None:
    rows = _ivd_rows()
    assert len(rows) == 29_642
    assert len({b for b, _ in rows}) == 15_304
    assert len({s for _, s in rows}) == 32
    assert {s for _, s in rows} == set(range(0xE0100, 0xE0120))
    assert IVD_TABLE.read_text(encoding="utf-8").startswith(
        "# Generated by scripts/gen_ivd_sequences.py from IVD 2026-08-03."
    )


def test_the_table_is_sorted_so_the_build_can_search_it() -> None:
    lines = [ln for ln in IVD_TABLE.read_text(encoding="utf-8").splitlines() if ln[0] != "#"]
    pairs = [tuple(int(part, 16) for part in line.split("\t")) for line in lines]
    assert pairs == sorted(set(pairs))


def test_the_generator_refuses_a_file_that_is_not_the_pinned_release() -> None:
    generator = _load_generator()
    with pytest.raises(ValueError, match="sha256"):
        generator.rows_from(b"4E00 E0100; Adobe-Japan1; CID+1200\n")


def test_the_generator_keeps_each_base_and_selector_once() -> None:
    generator = _load_generator()
    text = "# a comment\n4E00 E0100; Adobe-Japan1; CID+1200\n4E00 E0100; Moji_Joho; MJ000001\n"
    assert generator.parse(text) == {(0x4E00, 0xE0100)}


def test_the_generator_refuses_a_selector_outside_the_ideographic_range() -> None:
    generator = _load_generator()
    with pytest.raises(ValueError, match="selector"):
        generator.parse("4E00 FE00; Adobe-Japan1; CID+1200\n")


def test_provenance_records_the_release_and_its_digest() -> None:
    root = Path(__file__).resolve().parent.parent
    page = (root / "docs" / "provenance.md").read_text(encoding="utf-8")
    row = next(line for line in page.splitlines() if "ideographic_variation_sequences.tsv" in line)
    assert "2026-08-03" in row
    generator = _load_generator()
    assert generator.RELEASE == "2026-08-03"
    assert generator.SHA256 in row
    assert generator.SHA256 == "2b466659c2bfde1c52e60bd9fc883ab14dfa5c583df024b80352420265d2cd87"


def test_the_limit_page_says_what_a_carrier_can_still_do() -> None:
    root = Path(__file__).resolve().parent.parent
    page = (root / "docs" / "limitations.md").read_text(encoding="utf-8")
    assert "the IVD is\nnot shipped" not in page
    assert "registers both" in page


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
