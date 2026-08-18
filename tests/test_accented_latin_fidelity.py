"""#564 — accented-Latin fidelity is a ``strip_obfuscation`` property, not a confusables one.

``normalize_confusables`` preserves accented Latin where ``strip_obfuscation`` destroys
it, at identical homoglyph recovery. The structural reason is that ``strip_accents``
sits in the ``strip_obfuscation`` bundle, not in the confusable primitive — so accent
destruction is a property of the bundle a caller chose, not of confusable mapping.

That distinction is now documented (``docs/security/adversarial-defense.md`` and the
confusables user guide). These tests keep the documented claim true. Without them a
future table or preset change could quietly invert the story the docs tell, and the only
signal would be a benchmark cell nobody re-reads.
"""

from __future__ import annotations

import pytest

import disarm

#: (input, expected) pairs where the two entry points must agree — the attack strings.
#: Cyrillic а is U+0430, Cyrillic С is U+0421.
HOMOGLYPH_ATTACKS = [
    pytest.param("pаypаl", "paypal", id="cyrillic-a-paypal"),
    pytest.param("аpple", "apple", id="cyrillic-a-apple"),
]

#: Legitimate accented Latin. The primitive must preserve it; the bundle must not.
ACCENTED_LEGITIMATE = [
    pytest.param("José Martínez", "Jose Martinez", id="spanish-name"),
    pytest.param("naïve café", "naive cafe", id="french-loanwords"),
    # ß is not an accented letter — `strip_accents` leaves it, so the bundle does too.
    # Only ü is lost. Kept in the set precisely because it shows the step is
    # accent-removal, not a general Latin-to-ASCII fold.
    pytest.param("Müller Straße", "Muller Straße", id="german-umlaut-only"),
]


@pytest.mark.parametrize(("attack", "recovered"), HOMOGLYPH_ATTACKS)
def test_equal_recovery_on_attacks(attack: str, recovered: str) -> None:
    """Both entry points recover the homoglyph. The fidelity difference is not a
    recovery difference — that is the whole point of the comparison."""
    assert disarm.normalize_confusables(attack) == recovered
    assert disarm.strip_obfuscation(attack) == recovered


@pytest.mark.parametrize(("text", "_stripped"), ACCENTED_LEGITIMATE)
def test_confusables_primitive_preserves_accents(text: str, _stripped: str) -> None:
    """Accented Latin is not confusable with anything, so the fold is identity on it."""
    assert disarm.normalize_confusables(text) == text


@pytest.mark.parametrize(("text", "stripped"), ACCENTED_LEGITIMATE)
def test_strip_obfuscation_bundle_destroys_accents(text: str, stripped: str) -> None:
    """Documented, not accidental: the bundle includes ``strip_accents``."""
    assert disarm.strip_obfuscation(text) == stripped


@pytest.mark.parametrize(("text", "stripped"), ACCENTED_LEGITIMATE)
def test_the_destruction_is_attributable_to_strip_accents(text: str, stripped: str) -> None:
    """Names the mechanism the docs name.

    Running ``strip_accents`` alone on the confusable-folded text must reproduce the
    bundle's output. If it ever stops matching, some *other* step in the bundle became
    destructive too, and the documented explanation is no longer the whole story.
    """
    assert disarm.strip_accents(disarm.normalize_confusables(text)) == stripped


def test_ml_normalize_is_not_a_homoglyph_defence() -> None:
    """The related half of the same confusion (#559/#564).

    ``ml_normalize``'s pipeline has no TR39 step, so it recovers nothing at either
    ``fold_case`` setting. A reader who assumes "normalize" implies confusable folding
    is drawing the wrong conclusion; the docs now say so, and this pins it.
    """
    spoof = "fuСk"  # Cyrillic С
    assert disarm.ml_normalize(spoof, fold_case=False) == spoof
    assert disarm.normalize_confusables(spoof) == "fuCk"


def test_the_two_knobs_are_independent() -> None:
    """Case and accents are separate losses with separate switches.

    ``ml_normalize(fold_case=False)`` restores case only; ``normalize_confusables``
    preserves both. Naming the four corners keeps the docs' selection table honest.
    """
    text = "José Martínez"
    assert disarm.ml_normalize(text) == "jose martinez"  # loses case + accents
    assert disarm.ml_normalize(text, fold_case=False) == "Jose Martinez"  # loses accents
    assert disarm.strip_obfuscation(text) == "Jose Martinez"  # loses accents
    assert disarm.normalize_confusables(text) == text  # loses neither
