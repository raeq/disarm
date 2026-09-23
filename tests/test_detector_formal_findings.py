"""Findings of the Lean model of the anomaly detector, in ``formal/lean/Detection``.

Each class below is one finding, reproduced on the library before it was fixed:

* **Finding 1**: ``canonicalize``, ``strip_bidi`` and ``strip_format`` deleted the
  deprecated format controls ``U+206A``-``U+206F`` and the interlinear annotation
  characters ``U+FFF9``-``U+FFFB`` from inside a word while the detector reported clean.
  The set lived only in the bidi strip. Its secondary finding is the 66 noncharacters,
  which ``canonicalize`` deletes and nothing reported.

Every assertion marked as a regression fails on the ``main`` these fixes were written
against. Escapes throughout, per #802: most of these characters render as nothing.
"""

from __future__ import annotations

import unicodedata

import pytest

import disarm

DEPRECATED_OR_ANNOTATION = [chr(c) for c in [*range(0x206A, 0x2070), *range(0xFFF9, 0xFFFC)]]

NONCHARACTERS = [
    chr(c)
    for c in [
        *range(0xFDD0, 0xFDF0),
        *(plane << 16 | low for plane in range(17) for low in (0xFFFE, 0xFFFF)),
    ]
]


def _cp(ch: str) -> str:
    return f"U+{ord(ch):04X}"


class TestFinding1DeprecatedFormatControls:
    @pytest.mark.parametrize("ch", DEPRECATED_OR_ANNOTATION, ids=_cp)
    def test_it_is_deleted_by_the_strips(self, ch: str) -> None:
        split = f"pay{ch}pal"
        assert disarm.strip_bidi(split) == "paypal"
        assert disarm.strip_format(split) == "paypal"
        assert disarm.canonicalize(split) == "paypal"

    @pytest.mark.parametrize("ch", DEPRECATED_OR_ANNOTATION, ids=_cp)
    def test_it_is_reported_inside_a_word(self, ch: str) -> None:
        """Regression: clean on ``main``."""
        report = disarm.inspect_anomalies(f"pay{ch}pal")
        assert report.kinds == ["invisible"]
        assert report.findings[0].detail == _cp(ch)

    def test_it_is_not_a_bidi_control(self) -> None:
        """They are format characters, not UAX #9 controls: the census stays twelve."""
        assert not any(disarm.has_bidi_control(ch) for ch in DEPRECATED_OR_ANNOTATION)


class TestFinding1Noncharacters:
    def test_there_are_66(self) -> None:
        assert len(NONCHARACTERS) == 66
        assert all(unicodedata.category(ch) == "Cn" for ch in NONCHARACTERS)

    @pytest.mark.parametrize("ch", NONCHARACTERS, ids=_cp)
    def test_canonicalize_deletes_it_and_the_detector_reports_it(self, ch: str) -> None:
        """Regression: clean on ``main``. One is enough, as for a tag character."""
        assert disarm.canonicalize(f"pay{ch}pal") == "paypal"
        for text in (f"pay{ch}pal", ch, f"12{ch}34"):
            report = disarm.inspect_anomalies(text)
            assert report.kinds == ["invisible"], text.encode("unicode_escape")
            assert report.findings[0].detail == f"{_cp(ch)} \u00d71"

    def test_the_replacement_character_is_not_one(self) -> None:
        assert not disarm.has_anomalies("pay\ufffdpal")


def test_what_canonicalize_deletes_from_a_word_is_reported_or_a_documented_spare() -> None:
    """Finding 1 as the property rather than the list, over every scalar.

    Regression: on ``main`` this also lists ``U+206A``-``U+206F``, ``U+FFF9``-``U+FFFB``
    and the 66 noncharacters. What remains is what the guide documents as spared: the
    soft hyphen and CGJ (legitimate between letters), ``LRM``/``RLM`` (ordinary in
    right-to-left text), a lone variation selector (emoji presentation) and a single
    Private Use Area code point (an icon-font glyph).
    """

    def spared(cp: int) -> bool:
        return (
            cp in (0x00AD, 0x034F, 0x200E, 0x200F)
            or 0xFE00 <= cp <= 0xFE0F
            or 0xE0100 <= cp <= 0xE01EF
            or 0xE000 <= cp <= 0xF8FF
            or 0xF0000 <= cp <= 0xFFFFD
            or 0x100000 <= cp <= 0x10FFFD
        )

    canonicalize, has_anomalies = disarm.canonicalize, disarm.has_anomalies
    missed = [
        _cp(chr(cp))
        for cp in range(0x110000)
        if not 0xD800 <= cp <= 0xDFFF
        and not spared(cp)
        and canonicalize(f"pay{chr(cp)}pal") == "paypal"
        and not has_anomalies(f"pay{chr(cp)}pal")
    ]
    assert missed == []
