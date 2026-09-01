"""#777 — UTS #39 §5.3 Mixed Numbers.

An identifier should not carry digits from more than one decimal numbering system.
`1٢۳４५` reads as `12345` and is five of them.

Nothing detected this, and the reason is worth stating: **digits carry the script of
nothing**, so `is_mixed_script` sees one script for a token that is mostly ASCII with one
substituted digit. `1٢۳４५` was caught only by accident — five systems happen to be five
scripts — while `12٣`, the shape an attacker would actually use, was clean at every
surface.
"""

from __future__ import annotations

import pytest

import disarm

#: `(text, system count)`. A single system is never a finding however unusual it looks.
ONE_SYSTEM = ["2024", "٢٠٢٤", "٢٠٢٤", "२०२४", "๒๐๒๔", "hello", "", "no digits here"]

MANY_SYSTEMS = [
    ("12٣", 2),  # ASCII + Arabic-Indic — the common shape
    ("١" + "23", 2),  # the other way round
    ("1٢۳４२", 5),  # ASCII, Arabic-Indic, Extended, fullwidth, Devanagari
    ("٠۰", 2),  # two zeros, no ASCII at all
]


@pytest.mark.parametrize("text", ONE_SYSTEM)
def test_one_system_is_never_a_finding(text: str) -> None:
    """`٢٠٢٤` is a year. The check is about mixing, not about which digits."""
    assert "mixed_numbers" not in disarm.inspect_anomalies(text).kinds


@pytest.mark.parametrize(("text", "systems"), MANY_SYSTEMS)
def test_more_than_one_system_is_reported(text: str, systems: int) -> None:
    result = disarm.inspect_anomalies(text)
    assert "mixed_numbers" in result.kinds, f"{text!r} draws on {systems} systems"
    assert result.anomalous


def test_the_reason_says_how_many() -> None:
    """The detail is the count, because two and five are different situations."""
    reason = disarm.inspect_anomalies("1٢۳４२").reason
    assert "5 decimal numbering systems" in reason
    assert "Mixed Numbers" in reason


def test_the_shape_that_was_clean_everywhere() -> None:
    """#777's actual complaint, as a regression test.

    `12٣` is two systems and reads as `123`. Before this it was `anomalous=False` with no
    kinds, and `is_mixed_script` was `False` too — which is still true and still correct,
    since digits belong to no script. That is precisely why this needed its own check.
    """
    text = "12٣"
    assert disarm.inspect_anomalies(text).kinds == ["mixed_numbers"]
    assert not disarm.is_mixed_script(text), (
        "digits carry no script, so is_mixed_script should still say False — if it now "
        "says True, something else changed and this test is no longer about #777"
    )


def test_a_digit_run_inside_a_word_is_still_seen() -> None:
    """Tokenisation must not hide it: the digits need not be the whole token."""
    assert "mixed_numbers" in disarm.inspect_anomalies("user12٣").kinds


def test_every_system_in_the_table_is_a_complete_run() -> None:
    """The model the lookup assumes: a system spans exactly ten code points.

    Asserted through the public surface — one digit from each system paired with an ASCII
    digit must report mixing. If a run were incomplete, some member would not resolve to
    its system and the pair would read as clean.

    Uses the interpreter's `unicodedata`, which is an older UCD than the bundled tables.
    That skew is safe in this direction: numbering systems are only ever added, so every
    system this interpreter knows is one the table has. It is a floor, not a census.
    """
    import unicodedata

    zeros = []
    for cp in range(0x30, 0x110000):
        try:
            if unicodedata.decimal(chr(cp)) == 0:
                zeros.append(cp)
        except ValueError:
            continue
    assert len(zeros) > 50, f"only {len(zeros)} numbering systems found; table too small"

    missed = []
    for zero in zeros:
        if zero == 0x30:  # ASCII itself is the control
            continue
        for offset in (0, 5, 9):
            probe = "1" + chr(zero + offset)
            if "mixed_numbers" not in disarm.inspect_anomalies(probe).kinds:
                missed.append(f"U+{zero + offset:04X}")
    assert not missed, f"digits not recognised as their own system: {missed[:8]}"
