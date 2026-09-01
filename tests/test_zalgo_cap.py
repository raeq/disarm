"""#788 — `strip_zalgo` stripped from text `is_zalgo` had just called ordinary.

`is_zalgo` fires above a threshold of 3; `strip_zalgo` capped at 2. Neither figure was
wrong on its own terms, and together they meant the library removed a mark from text it
declined to call suspicious:

    is_zalgo("\\u05d0\\u05b8\\u05c1\\u0591")   -> False
    strip_zalgo(...)                          -> the etnahta is gone

Pointed and cantillated Hebrew routinely puts a vowel, a dot and an accent on one
consonant — Torah text, siddurim, learner materials — and three marks is the normal case
there, not the pathological one. The same shape appears in Arabic with shadda + a short
vowel + sukun.

The direction of the fix is forced. Lowering the threshold to 2 would make `is_zalgo` call
ordinary Torah text zalgo. Raising the cap to 3 makes the transform act only on what the
predicate flags, and serves #429's stated goal — the cap exists to *preserve legitimate
diacritics*, and 3-mark Hebrew is legitimate.

The invariant this file holds is deliberately about **marks lost**, not about the string
being unchanged: `strip_zalgo` recomposes to NFC, so a decomposed input legitimately comes
back spelled differently. An earlier draft asserted byte equality and reported 750
"violations" that were all NFC recomposition.
"""

from __future__ import annotations

import itertools
import unicodedata

import pytest

import disarm


def marks(text: str) -> int:
    """Combining marks in NFD — the quantity both the cap and the threshold count."""
    return sum(1 for char in unicodedata.normalize("NFD", text) if unicodedata.combining(char))


#: The four rows #788 measured. Left as literals: these are Hebrew and Arabic letters
#: with their points, which render as themselves — #802's convention is about
#: characters that render as *nothing*, and applying it here would make the vectors
#: unreadable to anyone who can read the scripts they are about.
ORDINARY_THREE_MARK = [
    ("Hebrew alef + qamats + shin dot + etnahta", "אָׁ֑"),
    ("Hebrew bet + dagesh + qamats + tipeha", "בָּ֖"),
    ("Hebrew shin + shin dot + dagesh + segol", "שֶּׁ"),
    ("Arabic beh + shadda + fatha + sukun", "بَّْ"),
]


@pytest.mark.parametrize(
    ("name", "text"), ORDINARY_THREE_MARK, ids=[name for name, _ in ORDINARY_THREE_MARK]
)
def test_the_predicate_calls_it_ordinary(name: str, text: str) -> None:
    """Establish the premise before asserting the consequence.

    If `is_zalgo` ever starts flagging these, the invariant below becomes vacuous — it
    would hold by the text no longer being ordinary rather than by the transform leaving
    it alone.
    """
    assert not disarm.is_zalgo(text), f"{name} is ordinary text and must not read as zalgo"
    assert marks(text) == 3, name


@pytest.mark.parametrize(
    ("name", "text"), ORDINARY_THREE_MARK, ids=[name for name, _ in ORDINARY_THREE_MARK]
)
def test_the_transform_leaves_it_alone(name: str, text: str) -> None:
    """The defect: one mark was removed from each of these."""
    assert marks(disarm.strip_zalgo(text)) == marks(text), f"{name} lost a mark"


@pytest.mark.parametrize(
    ("name", "text"), ORDINARY_THREE_MARK, ids=[name for name, _ in ORDINARY_THREE_MARK]
)
def test_canonicalize_leaves_it_alone_too(name: str, text: str) -> None:
    """The cap reaches further than `strip_zalgo`.

    `canonicalize` and `canonicalize_strict` both run the step, so the same mark was lost
    from a key. Both now take the cap from the constant rather than repeating the figure.
    """
    assert marks(disarm.canonicalize(text)) == marks(text), f"{name} lost a mark in a key"


def test_the_cap_and_the_threshold_agree() -> None:
    """The invariant, swept: nothing `is_zalgo` calls ordinary loses a mark.

    Stated as marks lost rather than string equality, because `strip_zalgo` recomposes to
    NFC and a decomposed input legitimately comes back spelled differently.
    """
    combining = "़ָَ́̈̇"
    violations = []
    for base in "aZאبकก":
        for combo in itertools.product(combining, repeat=3):
            text = base + "".join(combo)
            if disarm.is_zalgo(text):
                continue
            if marks(disarm.strip_zalgo(text)) < marks(text):
                violations.append(text)
    assert not violations, (
        f"{len(violations)} strings lose a mark despite is_zalgo saying they are ordinary; "
        f"first: {violations[:3]!r}"
    )


def test_real_zalgo_is_still_stripped() -> None:
    """Raising the cap must not stop the transform doing its job."""
    zalgo = "Z" + "́" * 8
    assert disarm.is_zalgo(zalgo)
    assert marks(disarm.strip_zalgo(zalgo)) == 3
    assert marks(disarm.canonicalize(zalgo)) == 3


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("Devanagari conjunct", "क्ष्ण"),
        ("Thai", "กั้"),
        ("Vietnamese NFD", "ệ"),
        ("cafe with acute", "café"),
    ],
    ids=["devanagari", "thai", "vietnamese", "cafe"],
)
def test_the_controls_are_unmoved(name: str, text: str) -> None:
    """#788 checked these and so does this: the change is narrow.

    The Vietnamese row is the one worth keeping. `e` + dot-below + circumflex looks like a
    3-to-1 truncation from the length alone and is not — NFC composes it to `ệ`, and no
    mark is lost either before or after this change.
    """
    assert marks(disarm.strip_zalgo(text)) == marks(text), name


def test_ml_normalize_still_strips_every_mark() -> None:
    """Its cap is 0 and deliberately not the default — this change must not reach it."""
    assert marks(disarm.ml_normalize("café")) == 0


def test_the_explicit_argument_still_works() -> None:
    """A caller who passes a cap gets it, including the old default."""
    text = "אָׁ֑"
    assert marks(disarm.strip_zalgo(text, max_marks=2)) == 2
    assert marks(disarm.strip_zalgo(text, max_marks=0)) == 0
