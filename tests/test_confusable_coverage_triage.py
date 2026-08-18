"""#558 — the established-core coverage gap, triaged and closed.

The issue asks for the upstream miss list to be split three ways — genuine table gap,
deliberate divergence, out of scope — with bucket 1 closed by regenerating and buckets
2 and 3 written down rather than inferred.

The triage was computable locally once #563 landed: for every upstream confusable source
the Latin table does not fold, look at what upstream folds it to. That is what these
tests pin, so the buckets stay honest as the tables move.
"""

from __future__ import annotations

import unicodedata

import pytest

import disarm

#: Bucket 1, now closed. Latin-script letters whose TR39 prototype is a single ASCII
#: DIGIT or PUNCTUATION mark. `filter_latin_homoglyphs` required the prototype to be an
#: ASCII *letter*, so every one of these was dropped by the generator — a table gap, not
#: a policy decision. Nothing distinguished Ʒ→3 from the þ→p rows that were already in.
CLOSED_GAP = {
    "Ƨ": "2",  # U+01A7 LATIN CAPITAL LETTER TONE TWO
    "Ʒ": "3",  # U+01B7 LATIN CAPITAL LETTER EZH
    "ƻ": "2",  # U+01BB LATIN LETTER TWO WITH STROKE
    "Ƽ": "5",  # U+01BC LATIN CAPITAL LETTER TONE FIVE
    "ǃ": "!",  # U+01C3 LATIN LETTER RETROFLEX CLICK
    "Ȝ": "3",  # U+021C LATIN CAPITAL LETTER YOGH
    "Ȣ": "8",  # U+0222 LATIN CAPITAL LETTER OU
    "ȣ": "8",  # U+0223 LATIN SMALL LETTER OU
    "Ɂ": "?",  # U+0241 LATIN CAPITAL LETTER GLOTTAL STOP
    "Ꝛ": "2",  # U+A75A LATIN CAPITAL LETTER R ROTUNDA
    "Ꝫ": "3",  # U+A76A LATIN CAPITAL LETTER ET
    "Ꝯ": "9",  # U+A76E LATIN CAPITAL LETTER CON
    "ꝸ": "&",  # U+A778 LATIN SMALL LETTER UM
    "꞉": ":",  # U+A789 MODIFIER LETTER COLON
    "ꞌ": "'",  # U+A78C LATIN SMALL LETTER SALTILLO
    "Ɜ": "3",  # U+A7AB LATIN CAPITAL LETTER REVERSED OPEN E
}

#: Bucket 2 — deliberate divergence. TR39 is a skeleton transform, so these ASCII
#: characters are upstream sources. disarm does not apply those rows: folding a
#: legitimate `m` to `rn` or a `0` to the letter `O` corrupts prose. The digit half is
#: the subject of the digit-policy issue; the contraction half of the contraction issue.
DELIBERATE_ASCII = ["%", "0", "1", "I", "m"]


@pytest.fixture(scope="module")
def exposure() -> frozenset[str]:
    return disarm.unmapped_confusables()


# ── bucket 1: closed ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(("source", "target"), sorted(CLOSED_GAP.items()))
def test_closed_gap_now_folds(source: str, target: str) -> None:
    assert disarm.normalize_confusables(source) == target


@pytest.mark.parametrize("source", sorted(CLOSED_GAP))
def test_closed_gap_no_longer_reported_as_exposure(source: str, exposure: frozenset[str]) -> None:
    """The #563 coverage API and the table must agree that the gap is closed."""
    assert source not in exposure


@pytest.mark.parametrize("source", sorted(CLOSED_GAP))
def test_closed_gap_is_idempotent(source: str) -> None:
    """A new row must not break the preset fixed point.

    None of the 16 targets is itself a confusable source, so no chain exists — but
    asserting it here means a future row whose target *does* fold gets caught.
    """
    once = disarm.normalize_confusables(source)
    assert disarm.normalize_confusables(once) == once


def test_every_closed_row_is_a_latin_letter_impersonating_a_non_letter() -> None:
    """Pins the shape of the fix, not just its output.

    The widened predicate accepts an ASCII digit/punctuation prototype. If someone later
    widens it further — to whitespace, or to non-ASCII — this fails and asks why.
    """
    for source, target in CLOSED_GAP.items():
        assert unicodedata.category(source).startswith(("L", "S")), source
        assert target.isascii() and target.isprintable() and not target.isspace()
        assert not target.isalpha(), f"{target!r} is a letter; that case was already in"


def test_the_fix_is_a_letter_to_digit_direction_only() -> None:
    """Guards against colliding with the digit-policy issue.

    That issue is about a DIGIT source folding to a look-alike letter (Devanagari zero →
    `o`). This change is the opposite direction: a letter source folding to a digit. A
    digit must still fold to a digit.
    """
    assert disarm.normalize_confusables("०") == "0"  # Devanagari zero stays numeric
    assert disarm.normalize_confusables("Ʒ") == "3"  # letter → digit is the new case


# ── bucket 2: deliberate divergence, recorded ────────────────────────────────


def test_deliberate_divergence_is_still_reported(exposure: frozenset[str]) -> None:
    """These stay unfolded on purpose, and stay visible in the exposure set.

    Not filtered out: the coverage API reports what the table does not fold, and hiding
    a deliberate divergence would make the report read as coverage.
    """
    assert sorted(c for c in exposure if c.isascii()) == DELIBERATE_ASCII


def test_deliberate_divergence_does_not_corrupt_prose() -> None:
    """Why bucket 2 is not closed: applying the skeleton rows would break real words."""
    for word in ("amazon", "earnings", "turnip", "born"):
        assert disarm.normalize_confusables(word) == word
    assert disarm.normalize_confusables("2026") == "2026"


# ── bucket 3: out of scope ───────────────────────────────────────────────────


def test_whitespace_rows_are_out_of_scope_and_handled_elsewhere(
    exposure: frozenset[str],
) -> None:
    """TR39 folds the whole space family to U+0020; `collapse_whitespace` owns that.

    Duplicating those rows in the confusables table would put a second, divergent copy of
    the whitespace policy in the tree. They stay in the exposure set — honestly reported
    as unfolded *by the confusables table* — and the pipeline handles them.
    """
    for space in (" ", " ", " ", " ", " "):
        assert space in exposure, f"U+{ord(space):04X} should be reported"
        assert disarm.normalize_confusables(space) == space
        assert disarm.collapse_whitespace(f"a{space}b") == "a b"


def test_non_latin_targets_dominate_the_residue(exposure: frozenset[str]) -> None:
    """The bulk of the remaining set is out of scope, not missing.

    A source folding to a non-Latin target has no business in a to-Latin table. The
    residue is thousands of CJK / Arabic / Hangul sources, which is why the raw count is
    not a defect count.
    """
    assert len(exposure) > 4_000
    non_ascii = [c for c in exposure if not c.isascii()]
    assert len(non_ascii) / len(exposure) > 0.99


# ── the regression the whole exercise buys ───────────────────────────────────


def test_closing_the_gap_measurably_shrank_the_exposure_set(
    exposure: frozenset[str],
) -> None:
    """The 16 rows moved the number, and the coverage API is what proves it.

    Bounds rather than an exact count: the figure legitimately moves with a table
    refresh, and pinning it exactly would make every upstream bump a test failure.
    """
    assert 4_300 < len(exposure) < 4_400
    assert not (set(CLOSED_GAP) & exposure)
