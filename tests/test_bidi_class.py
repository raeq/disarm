"""`strong_dir` resolves direction from `Bidi_Class`, not a script-name list (#773).

It used to look a character's *script name* up in a five-element list:

    RTL_SCRIPTS = ["Hebrew", "Arabic", "Syriac", "Thaana", "NKo"]

UAX #9 resolves direction from `Bidi_Class`, and the two answer different questions.
1,786 of the 3,018 assigned code points with `Bidi_Class` in {R, AL} resolved to no script
at all — two entire Arabic blocks among them — so they were bidi-neutral to disarm while
reordering normally on screen.
"""

from __future__ import annotations

import unicodedata

import pytest

import disarm

DATA_UNICODE_VERSION = "17.0.0"


def _assigned_rtl() -> list[int]:
    return [
        cp
        for cp in range(0x110000)
        if not (0xD800 <= cp <= 0xDFFF)
        and unicodedata.category(chr(cp)) != "Cn"
        and unicodedata.bidirectional(chr(cp)) in ("R", "AL")
    ]


@pytest.mark.formal
def test_every_strong_rtl_code_point_is_visible() -> None:
    """Tier 3: the whole point of the change, over the whole code point space.

    Paired with a Latin letter, every strong-RTL character must make a conflict. This is
    the gate #773 §3 asks for and the one that would have caught the original defect.
    """
    if unicodedata.unidata_version != DATA_UNICODE_VERSION:
        pytest.skip(
            f"host UCD {unicodedata.unidata_version} != table {DATA_UNICODE_VERSION}; "
            f"every code point reclassified between them would read as an error — "
            f"U+1171E is NSM under 15.1 and L under 17.0, and 9,077 more are simply "
            f"unassigned here. The parametrised cases below are version-stable and are "
            f"what holds on CI."
        )
    blind = [cp for cp in _assigned_rtl() if not disarm.has_bidi_conflict("a" + chr(cp))]
    assert not blind, (
        f"{len(blind)} code points with Bidi_Class R/AL are invisible to "
        f"has_bidi_conflict, first " + ", ".join(f"U+{cp:04X}" for cp in blind[:8])
    )


@pytest.mark.formal
def test_no_code_point_is_strong_that_should_not_be() -> None:
    """The other direction: nothing outside {L, R, AL} may create a conflict on its own.

    Without this the test above would pass on an implementation that called everything
    strong-RTL.
    """
    if unicodedata.unidata_version != DATA_UNICODE_VERSION:
        pytest.skip(
            f"host UCD {unicodedata.unidata_version} != table {DATA_UNICODE_VERSION}; "
            f"every code point reclassified between them would read as an error — "
            f"U+1171E is NSM under 15.1 and L under 17.0, and 9,077 more are simply "
            f"unassigned here. The parametrised cases below are version-stable and are "
            f"what holds on CI."
        )
    wrong = [
        cp
        for cp in range(0x110000)
        if not (0xD800 <= cp <= 0xDFFF)
        and unicodedata.bidirectional(chr(cp)) not in ("L", "R", "AL")
        and (disarm.has_bidi_conflict("a" + chr(cp)) or disarm.has_bidi_conflict("א" + chr(cp)))
    ]
    assert not wrong, (
        f"{len(wrong)} code points with no strong Bidi_Class create a conflict: "
        + ", ".join(f"U+{cp:04X}" for cp in wrong[:8])
    )


@pytest.mark.parametrize(
    ("cp", "name"),
    [
        (0x10800, "CYPRIOT SYLLABLE A"),
        (0x10900, "PHOENICIAN LETTER ALF"),
        (0x10A00, "KHAROSHTHI LETTER A"),
        (0x1E800, "MENDE KIKAKUI SYLLABLE M001 KI"),
        (0x10C00, "OLD TURKIC LETTER ORKHON A"),
    ],
)
def test_astral_rtl_scripts_are_seen(cp: int, name: str) -> None:
    """Tier 1 regression. Every one of these was bidi-neutral before #773 because its
    script has no entry in the block table at all."""
    assert disarm.has_bidi_conflict("a" + chr(cp)), f"U+{cp:04X} {name} is still invisible"


def test_a_combining_mark_is_not_strong() -> None:
    """U+0651 ARABIC SHADDA is `Bidi_Class` NSM, and UAX #9 rule W1 gives it the direction
    of the preceding character — after Latin `a` that is L, so there is no conflict.

    It used to report one, because it sits in the Arabic block and direction came from the
    block. That is why `has_bidi_conflict` left CVE-2017-7833's detector list; the row is
    still covered by the three detectors that answer its actual question.
    """
    assert not disarm.has_bidi_conflict("exaّmple.com")
    assert disarm.has_anomalies("exaّmple.com")
    assert disarm.is_mixed_script("exaّmple.com")


def test_arabic_indic_digits_do_not_make_a_conflict() -> None:
    """`AN` is not a strong class, so they are neutral — which the old implementation
    achieved with an explicit `is_numeric()` guard that is no longer needed."""
    assert not disarm.has_bidi_conflict("hello ٥٦٧")


def test_devanagari_digits_are_strong_ltr() -> None:
    """And the guard was too broad: Devanagari digits are `Bidi_Class` L, so beside RTL
    text they genuinely are a conflict. The old `is_numeric()` check excluded them."""
    assert unicodedata.bidirectional("०") == "L"
    assert disarm.has_bidi_conflict("०" + "א")
