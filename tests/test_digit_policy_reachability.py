"""`digit_policy` is reachable from the key builders, and `numeric` stays the default.

#885 measured that `digit_policy="tr39"` is worth 27 of `confusable-bench.v1`'s 120
malicious rows and reported it at "zero false-positive cost". The first half is right —
over the six key builders the union goes from 72 to 92 — and the second half is an
artifact of the corpus.

TR39's digit mappings are not the styled Latin variants. They cover **every non-Latin
numeral system**: Arabic-Indic zero folds to ``.``, one to ``l``, five to ``o``. The 20
benign controls that measured the cost contain no non-Latin digits at all, so the
population that pays for `tr39` was never sampled.

So the parameter is added and the default is not moved. `"numeric"` is a genuine no-op —
these tests pin that byte-for-byte, because a default that quietly moved would be a
reindex event for every stored key.
"""

from __future__ import annotations

import pytest

import disarm

KEY_BUILDERS = [
    "canonicalize",
    "canonicalize_strict",
    "search_key",
    "catalog_key",
    "sort_key",
    "strip_obfuscation",
]

#: Digits whose TR39 target is a Latin letter or punctuation, with what each becomes.
#: These are the cost of `tr39`, and none of them is a styled Latin variant.
NON_LATIN_DIGITS = [
    ("٠", "0", "."),  # ARABIC-INDIC DIGIT ZERO
    ("١", "1", "l"),  # ARABIC-INDIC DIGIT ONE
    ("٥", "5", "o"),  # ARABIC-INDIC DIGIT FIVE
    ("۰", "0", "."),  # EXTENDED ARABIC-INDIC DIGIT ZERO
]


@pytest.mark.parametrize("name", KEY_BUILDERS)
def test_numeric_is_a_genuine_no_op(name: str) -> None:
    """Passing the default must be byte-identical to not passing it.

    Not a formality. A pre-fold under `"numeric"` would still change output — 78 of the
    120 rows collide instead of 72, because folding both sides before reducing is a
    different operation from reducing alone. If the default ever stopped being a no-op,
    every stored key would move without anyone asking for it.
    """
    build = getattr(disarm, name)
    for cp in range(0x10000):
        char = chr(cp)
        assert build(char) == build(char, digit_policy="numeric"), f"{name} moved on U+{cp:04X}"


@pytest.mark.parametrize("name", KEY_BUILDERS)
def test_the_parameter_is_accepted_and_validated(name: str) -> None:
    build = getattr(disarm, name)
    for policy in ("numeric", "tr39", "preserve"):
        assert isinstance(build("a", digit_policy=policy), str)
    with pytest.raises(disarm.InvalidArgumentError):
        build("a", digit_policy="bogus")


@pytest.mark.parametrize(("digit", "numeric", "tr39"), NON_LATIN_DIGITS, ids=lambda v: repr(v))
def test_tr39_destroys_the_numeric_reading_of_non_latin_digits(
    digit: str, numeric: str, tr39: str
) -> None:
    """The cost, asserted rather than described — this is why the default did not move."""
    assert disarm.canonicalize(digit) == numeric
    assert disarm.canonicalize(digit, digit_policy="tr39") == tr39


def test_a_real_year_survives_the_default_and_does_not_survive_tr39() -> None:
    assert disarm.canonicalize("٢٠٢٤") == "٢0٢٤"
    assert disarm.canonicalize("٢٠٢٤", digit_policy="tr39") == "٢.٢٤"


def test_tr39_reaches_a_spoof_the_default_cannot() -> None:
    """The gain, on the class the parameter exists for: a styled digit used as a letter.

    Through `search_key` rather than `canonicalize`, and #885's own table says why: the
    digit-zero variants fold to a capital `O`, so they need the policy **and** a case
    fold. `canonicalize` does not case-fold, so it reaches `paypO1` and stops one step
    short of the collision.
    """
    spoof = "payp\U0001d7ce1"  # MATHEMATICAL BOLD DIGIT ZERO used as an `o`
    assert disarm.search_key(spoof) != disarm.search_key("paypo1")
    assert disarm.search_key(spoof, digit_policy="tr39") == disarm.search_key(
        "paypo1", digit_policy="tr39"
    )
    # And the half-step, pinned so the distinction is not lost: the fold reaches the
    # letter, the case fold is what closes it.
    assert disarm.canonicalize(spoof, digit_policy="tr39") == "paypO1"
