"""Every character UTS #46 deletes as ignorable is reported by the hostname screen.

UTS #46 maps each `Default_Ignorable_Code_Point` to nothing, so `ev<c>il.com` resolves to
`evil.com`. The screen runs before that mapping for exactly this reason (#605, #610), but
it checked a hand-written list, and 28 of the property's code points were not on it: the
soft hyphen, U+034F, the Hangul fillers, the Mongolian free variation selectors, U+17B4
and U+17B5, U+206A-U+206F, the shorthand format controls and the musical-symbol formats.
Each of those screened clean and resolved to the blocked name. Found by the Lean model of
the detectors (`formal/lean/Detection`, finding 8).
"""

from __future__ import annotations

import pytest

from disarm import is_suspicious_hostname

#: `Default_Ignorable_Code_Point=Yes` in `DerivedCoreProperties.txt`, Unicode 15.1-17.0.
DEFAULT_IGNORABLE = (
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

#: UAX #9 controls, reported through `bidi_control` rather than `has_invisible` (#603).
BIDI = {0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}

CODE_POINTS = [cp for lo, hi in DEFAULT_IGNORABLE for cp in range(lo, hi + 1)]


def test_the_property_is_the_documented_size() -> None:
    assert len(CODE_POINTS) == 4174


@pytest.mark.parametrize("cp", CODE_POINTS[:600], ids=lambda cp: f"U+{cp:04X}")
def test_a_default_ignorable_in_a_label_is_reported(cp: int) -> None:
    _check(cp)


def test_every_default_ignorable_in_a_label_is_reported() -> None:
    """The tag and unassigned tail, in one test rather than 3,574 parameters."""
    for cp in CODE_POINTS[600:]:
        _check(cp)


def _check(cp: int) -> None:
    host = f"ev{chr(cp)}il.com"
    suspicious, analysis = is_suspicious_hostname(host)
    assert suspicious, f"U+{cp:04X} screened clean"
    if cp in BIDI:
        assert analysis.bidi_control and not analysis.has_invisible, f"U+{cp:04X}"
    else:
        assert analysis.has_invisible, f"U+{cp:04X} not reported as invisible"
