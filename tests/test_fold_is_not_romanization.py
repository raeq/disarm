"""#907 — the confusable fold is not a romanization, and `target_script` is not a shield.

Two claims the docstrings now make, both of which are only true because of how the
step lists are ordered, and neither of which any other test pins:

1. `canonicalize` and its siblings fold Cyrillic through the *confusable* table
   without transliterating first, so `Москва` becomes `Mockba` — a shape-for-shape
   substitution — while the key builders romanize it to `moskva`. Three surfaces,
   three different answers, and callers pick by which one they need.
2. `target_script` sends confusables *toward* a script. It does not protect text
   written in one, and pointing it at a third script injects that script's letters.

The docstring examples are the thing most likely to rot: nothing in this repo runs
Python docstrings as doctests, so a quoted value can go stale silently. The literal
in `normalize_confusables`' docstring was wrong when first written — pasted from a
terminal that rendered the RTL result in visual order — which is what
`test_the_arabic_target_docstring_literal_is_the_real_output` exists to catch.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "python" / "disarm" / "_api.py"

#: Moscow, in Cyrillic. The running example throughout #907.
MOSCOW = "Москва"

#: What the confusable fold makes of it: Latin letters chosen by shape, not by sound.
FOLDED = "Mockba"

#: What a transliterating surface makes of it.
ROMANIZED = "moskva"

#: The surfaces that fold without transliterating first.
FOLDING = ("canonicalize", "canonicalize_strict", "strip_obfuscation", "normalize_confusables")

#: The surfaces that transliterate first, and so produce a real romanization.
ROMANIZING = ("search_key", "catalog_key", "sort_key", "slugify")

#: The surfaces that leave the *script* alone. Not identity functions — see
#: `test_normalize_preserves_the_script_without_being_an_identity_function`.
PRESERVING = ("normalize",)


@pytest.mark.parametrize("name", FOLDING)
def test_folding_surfaces_produce_the_homoglyph_reading(name: str) -> None:
    assert getattr(disarm, name)(MOSCOW) == FOLDED


@pytest.mark.parametrize("name", ROMANIZING)
def test_romanizing_surfaces_produce_the_transliteration(name: str) -> None:
    assert getattr(disarm, name)(MOSCOW) == ROMANIZED


@pytest.mark.parametrize("name", PRESERVING)
def test_preserving_surfaces_return_the_input(name: str) -> None:
    assert getattr(disarm, name)(MOSCOW) == MOSCOW


def test_normalize_preserves_the_script_without_being_an_identity_function() -> None:
    """#908 review — "keeps the text unchanged" was wrong, and this pins why.

    `normalize` runs no fold and no transliteration, so a Cyrillic word survives as
    Cyrillic. It is still Unicode normalization: under the default NFC it recomposes,
    so a caller reaching for it to leave a string alone will be surprised. Both halves
    matter — the script claim is what the docstring rests on, the non-identity claim is
    what the review caught.
    """
    assert disarm.normalize(MOSCOW) == MOSCOW  # script survives
    decomposed = "cafe\u0301"
    assert disarm.normalize(decomposed) != decomposed  # …but not an identity
    assert disarm.normalize(decomposed) == "caf\u00e9"

    doc = disarm.canonicalize.__doc__ or ""
    assert "keeps the text unchanged" not in doc
    assert "not an identity function" in doc


def test_the_three_groups_really_do_disagree() -> None:
    """Guards the parametrized tests above against all collapsing to one answer.

    If a future change made every surface romanize, the three tests above would still
    need editing — but a reviewer could "fix" them by moving names between the tuples
    and never notice the distinction had gone.
    """
    assert FOLDED != ROMANIZED != MOSCOW
    assert len({FOLDED, ROMANIZED, MOSCOW}) == 3


def test_the_collapse_is_why_the_fold_does_not_transliterate() -> None:
    """Both halves: the folding surface collides the pair, the romanizing one does not.

    This is the trade the `canonicalize` docstring describes. Asserting only that
    `search_key` misses the spoof would leave "and `canonicalize` catches it" untested,
    which is the half that justifies the ordering.
    """
    assert disarm.canonicalize(MOSCOW) == disarm.canonicalize(FOLDED)
    assert not disarm.find_key_collisions([MOSCOW, FOLDED], key="search_key")
    # …and the control: the romanization does not meet the spoof either, so the miss
    # is not an artifact of one spelling.
    assert not disarm.find_key_collisions([ROMANIZED.capitalize(), FOLDED], key="search_key")


def test_target_script_folds_toward_rather_than_protecting() -> None:
    """A third script's letter lands inside the word (#907)."""
    out = disarm.normalize_confusables(MOSCOW, target_script="arabic")
    assert out != MOSCOW
    assert "ه" in out, "expected ARABIC LETTER HEH to replace the Cyrillic о"
    # Same-script text survives because its characters are not sources in that table.
    assert disarm.normalize_confusables(MOSCOW, target_script="cyrillic") == MOSCOW


def test_the_arabic_target_docstring_literal_is_the_real_output() -> None:
    """The docstring quotes a value; it must be the one the function returns.

    Nothing runs these docstrings as doctests, so this is the only thing standing
    between the quoted string and silent rot. It caught a wrong literal once already.
    """
    line = next(
        line for line in API.read_text(encoding="utf-8").splitlines() if "ARABIC LETTER HEH" in line
    )
    quoted = re.search(r"'([^']*)'", line)
    assert quoted, f"no quoted literal found in: {line!r}"
    assert quoted.group(1) == disarm.normalize_confusables(MOSCOW, target_script="arabic")


def test_there_is_no_greek_target() -> None:
    """Ask #1 rests on this: Greek text has no value that preserves it by design."""
    with pytest.raises(disarm.DisarmError) as excinfo:
        disarm.normalize_confusables("Ελλάδα", target_script="greek")
    message = str(excinfo.value)
    for accepted in ("latin", "cyrillic", "arabic", "hebrew"):
        assert accepted in message
    assert "greek" not in message.replace("got 'greek'", "")


@pytest.mark.parametrize(
    ("text", "expected"),
    [("Ελληνικά", "Eλλnvikά"), ("ا", "l"), ("י", "'")],
)
def test_the_624_docstring_examples_still_hold(text: str, expected: str) -> None:
    """`canonicalize`'s "Scoped to identifiers" block quotes these three.

    They were correct when written and are still correct; 0.15.0's case-pair closure
    moved twelve neighbouring code points without touching them.
    """
    assert disarm.canonicalize(text) == expected


@pytest.mark.parametrize("name", ["canonicalize", "canonicalize_strict", "strip_obfuscation"])
def test_the_asymmetry_is_stated_in_the_docstring(name: str) -> None:
    """#907 ask 2. The paragraph is the deliverable, so its absence is a regression."""
    doc = getattr(disarm, name).__doc__ or ""
    assert "not a romanization" in doc
    assert FOLDED in doc and ROMANIZED in doc


def test_normalize_confusables_states_the_fold_toward_semantics() -> None:
    """#907 ask 1. The one configurable surface carried no warning at all before."""
    doc = disarm.normalize_confusables.__doc__ or ""
    assert "does not protect" in doc
    assert "#900" in doc, "the allowed_scripts alternative must stay linked"


def test_canonicalize_strict_does_not_claim_to_preserve_the_script() -> None:
    """It said "preserves the original script (no transliteration)" and did not.

    The parenthesis was the true half. Folding `Москва` to `Mockba` is a script
    change, so the claim was false for every non-Latin input that has a Latin
    lookalike — which is the whole population the sentence was about.
    """
    doc = disarm.canonicalize_strict.__doc__ or ""
    assert "Preserves the original script" not in doc
    assert disarm.canonicalize_strict(MOSCOW) != MOSCOW
    # The half that was true: no romanization step, so it does not reach `moskva`.
    assert disarm.canonicalize_strict(MOSCOW) != ROMANIZED
