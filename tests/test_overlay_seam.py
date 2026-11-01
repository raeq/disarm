"""A filler between a letter and its strike must not hide the strike (#1209).

#1199 made a non-letter close a letter, so a mark after a symbol counts for no letter. A format
or private-use character draws nothing, so the strike after it still belongs to the letter, and
`canonicalize` deletes the filler and hands back a word `has_anomalies` reports. The seam is the
promise that what the detector calls clean stays clean through `canonicalize`, so the overlay rule
also reads the canonical form of a text holding an overlay mark.
"""

from __future__ import annotations

import pytest

import disarm

STRIKE = chr(0x336)
SLASH = chr(0x338)
SHY, ZWNJ, ZWJ = chr(0xAD), chr(0x200C), chr(0x200D)
ACUTE, CIRCUMFLEX, TILDE = chr(0x301), chr(0x302), chr(0x303)
ENCLOSING_CIRCLE = chr(0x20DD)


def _word(*code_points: int) -> str:
    return "".join(map(chr, code_points))


ARABIC = _word(0x633, 0x644, 0x627, 0x645)
PERSIAN = _word(0x645, 0x6CC, 0x62E, 0x648, 0x627, 0x647, 0x645)
DEVANAGARI = _word(0x928, 0x92E, 0x938, 0x924)
CYRILLIC = _word(0x43F, 0x440, 0x438, 0x432, 0x435, 0x442)
HAN = _word(0x4E00, 0x4E8C, 0x4E09, 0x56DB)

#: Every format character Unicode 15.1 has, written out, since a sweep by the host's own
#: `unicodedata` would move with the host (#1209).
EVERY_FORMAT_CHARACTER = [
    0xAD,
    *range(0x600, 0x606),
    0x61C,
    0x6DD,
    0x70F,
    0x890,
    0x891,
    0x8E2,
    0x180E,
    *range(0x200B, 0x2010),
    *range(0x202A, 0x202F),
    *range(0x2060, 0x2065),
    *range(0x2066, 0x2070),
    0xFEFF,
    *range(0xFFF9, 0xFFFC),
    0x110BD,
    0x110CD,
    *range(0x13430, 0x13440),
    *range(0x1BCA0, 0x1BCA4),
    *range(0x1D173, 0x1D17B),
    0xE0001,
    *range(0xE0020, 0xE0080),
]
PRIVATE_USE_ENDS = [0xE000, 0xF8FF, 0xF0000, 0xFFFFD, 0x100000, 0x10FFFD]


def _fill(word: str, filler: str) -> str:
    return "".join(letter + filler + STRIKE for letter in word)


def _kinds(text: str) -> set[str]:
    return set(disarm.inspect_anomalies(text).kinds)


REPORTS = {
    "soft hyphen": _fill("password", SHY),
    "U+E000": _fill("password", chr(0xE000)),
    "U+F0000": _fill("password", chr(0xF0000)),
    "U+100000": _fill("password", chr(0x100000)),
    "arabic ZWNJ": _fill(ARABIC, ZWNJ),
    "arabic ZWJ": _fill(ARABIC, ZWJ),
    "devanagari ZWNJ": _fill(DEVANAGARI, ZWNJ),
    "devanagari ZWJ": _fill(DEVANAGARI, ZWJ),
    "persian ZWNJ": _fill(PERSIAN, ZWNJ),
    "cyrillic soft hyphen": _fill(CYRILLIC, SHY),
    "han soft hyphen": _fill(HAN, SHY),
    "every other letter": "".join(
        letter + (SHY + STRIKE if i % 2 == 0 else "") for i, letter in enumerate("password")
    ),
    "pipe": _fill("password", "|"),
    "degree celsius": _fill("password", chr(0x2103)),
    "kangxi one": _fill("password", chr(0x2F00)),
    "circled ideograph": _fill("password", chr(0x3280)),
}

STAYS_CLEAN = {
    "digit": _fill("password", "1"),
    "star": _fill("password", chr(0x2605)),
    "equals": _fill("password", "="),
    "unassigned": _fill("password", chr(0x378)),
    "two negations": "x=" + SLASH + "y=" + SLASH + "z",
    "one negation": "a=" + SLASH + "b",
    "parallel negations": "a|" + SLASH + "b|" + SLASH + "c",
    "two struck temperatures": "20" + chr(0x2103) + STRIKE + " and 30" + chr(0x2103) + STRIKE,
    "one struck letter": "p" + STRIKE + "assword",
    "soft hyphen, no mark": "pass" + SHY + "word",
    "persian ZWNJ, no mark": _word(0x645, 0x6CC, 0x200C, 0x62E, 0x648, 0x627, 0x647, 0x645),
    "devanagari ZWJ, no mark": _word(0x915, 0x94D, 0x200D, 0x937),
}


@pytest.mark.parametrize("text", REPORTS.values(), ids=REPORTS.keys())
def test_reports(text: str) -> None:
    assert disarm.has_anomalies(text)
    assert "zalgo" in _kinds(text)


@pytest.mark.parametrize("text", REPORTS.values(), ids=REPORTS.keys())
def test_the_output_reports_nothing_the_input_did_not(text: str) -> None:
    assert _kinds(disarm.canonicalize(text)) - _kinds(text) == set()


@pytest.mark.parametrize("text", STAYS_CLEAN.values(), ids=STAYS_CLEAN.keys())
def test_stays_clean(text: str) -> None:
    assert not disarm.has_anomalies(text)
    assert disarm.inspect_anomalies(text).kinds == []


@pytest.mark.parametrize("code_point", EVERY_FORMAT_CHARACTER, ids=lambda c: f"U+{c:04X}")
def test_no_format_character_hides_a_strike(code_point: int) -> None:
    assert disarm.has_anomalies(_fill("password", chr(code_point)))


@pytest.mark.parametrize("code_point", PRIVATE_USE_ENDS, ids=lambda c: f"U+{c:04X}")
def test_no_private_use_character_hides_a_strike(code_point: int) -> None:
    assert disarm.has_anomalies(_fill("password", chr(code_point)))


@pytest.mark.parametrize("filler", [SHY, chr(0xE000)], ids=["soft hyphen", "private use"])
def test_the_other_mark_rules_hold_on_the_same_fillers(filler: str) -> None:
    stacked = "".join(c + filler + ACUTE + CIRCUMFLEX + TILDE for c in "password")
    assert "zalgo" in _kinds(stacked)
    enclosed = "".join(c + filler + ENCLOSING_CIRCLE for c in "password")
    assert "enclosing_mark" in _kinds(enclosed)


def test_a_finding_from_the_canonical_form_points_at_the_first_mark_in_the_input() -> None:
    text = _fill("password", "|")
    zalgo = [f for f in disarm.inspect_anomalies(text).findings if f.kind == "zalgo"]
    assert len(zalgo) == 1
    assert zalgo[0].token == STRIKE
    assert zalgo[0].start == text.encode().index(STRIKE.encode())


def test_an_input_that_already_reports_gets_one_finding() -> None:
    zalgo = [
        f for f in disarm.inspect_anomalies(_fill("password", SHY)).findings if f.kind == "zalgo"
    ]
    assert len(zalgo) == 1


def test_the_rule_reads_the_bars_as_decided() -> None:
    """The canonical form answers to #1213's bars and not to a lower one."""
    assert not disarm.has_anomalies("s" + SHY + chr(0x332) + "h" + SHY + chr(0x332))
    assert disarm.has_anomalies("".join(c + SHY + chr(0x332) for c in "the"))
    # `|` folds to a letter, so three of six in the output, and an underline needs every letter.
    assert not disarm.has_anomalies("".join(c + "|" + chr(0x332) for c in "the"))


@pytest.mark.slow
def test_no_scalar_value_opens_the_seam() -> None:
    """The input reads clean and its canonical form reports: 137,978 fillers on 0.19.0."""
    open_on = []
    for code_point in range(0x110000):
        if 0xD800 <= code_point <= 0xDFFF:
            continue
        text = _fill("password", chr(code_point))
        if not disarm.has_anomalies(text) and "zalgo" in _kinds(disarm.canonicalize(text)):
            open_on.append(f"U+{code_point:04X}")
    assert open_on == []
