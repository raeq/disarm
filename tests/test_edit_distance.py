"""The ASCII-substitution class, and the defence disarm had but did not expose (#883).

Twelve of the 120 malicious rows in ``confusable-bench.v1`` are ASCII substitutions:

    paypa1  paypaI  paypa-l  g1thub  githu8  0penai  opena1
    verce1  adm1n   5upport  supp0rt str1pe

Every key reducer misses all twelve. `find_confusables` misses all twelve. **That is
correct**: no confusable table should fold ASCII ``1`` onto ``l``, because doing so would
wreck ordinary text. These are not Unicode attacks and disarm's Unicode machinery should
not reach them.

Edit distance is the defence, and `utils::edit_distance` has been compiled into the wheel
all along without a Python caller being able to reach it. So the one class disarm does not
model in Unicode was also the one where its existing answer was unreachable from the
binding most callers use.

All twelve are **distance 1** from the name they imitate.
"""

from __future__ import annotations

import pytest

import disarm

#: The twelve, with the name each imitates. Taken from `confusable-bench.v1`; every one is
#: ASCII on both sides, which is what puts them outside the confusable table by design.
ASCII_SUBSTITUTIONS = [
    ("paypa1", "paypal"),
    ("paypaI", "paypal"),
    ("paypa-l", "paypal"),
    ("g1thub", "github"),
    ("githu8", "github"),
    ("0penai", "openai"),
    ("opena1", "openai"),
    ("verce1", "vercel"),
    ("adm1n", "admin"),
    ("5upport", "support"),
    ("supp0rt", "support"),
    ("str1pe", "stripe"),
]

RESERVED = sorted({target for _, target in ASCII_SUBSTITUTIONS})


@pytest.mark.parametrize(("spoof", "target"), ASCII_SUBSTITUTIONS, ids=lambda v: v)
def test_every_ascii_substitution_is_one_edit_away(spoof: str, target: str) -> None:
    assert disarm.edit_distance(spoof, target) == 1


@pytest.mark.parametrize(("spoof", "target"), ASCII_SUBSTITUTIONS, ids=lambda v: v)
def test_a_reserved_list_catches_all_twelve(spoof: str, target: str) -> None:
    """The whole point: `max_distance=1` against a reserved list reaches the class."""
    hit = disarm.nearest_match(spoof, RESERVED, max_distance=1)
    assert hit is not None
    assert (hit.value, hit.distance) == (target, 1)


@pytest.mark.parametrize(("spoof", "target"), ASCII_SUBSTITUTIONS, ids=lambda v: v)
def test_the_unicode_surfaces_correctly_miss_them(spoof: str, target: str) -> None:
    """Asserted rather than assumed, and it is not a defect.

    If a confusable table ever folded ASCII `1` onto `l` this would fail — and it should,
    because that fold would rewrite ordinary text. The two defences are complementary in
    the same way `find_confusables` and the reducers are (#882); this pins the boundary.
    """
    assert not disarm.find_confusables(spoof)
    assert disarm.canonicalize(spoof) != disarm.canonicalize(target)


def test_an_exact_match_is_reported() -> None:
    """The behaviour that made exposing the internal helper wrong.

    `utils::closest_match` skips distance 0, because it exists for a *"did you mean …?"*
    hint after the caller already rejected the input. A registry asking about a name it
    protects verbatim would have been told `None`.
    """
    hit = disarm.nearest_match("admin", RESERVED, max_distance=1)
    assert hit is not None
    assert (hit.value, hit.distance) == ("admin", 0)


def test_nothing_beyond_the_threshold_the_caller_set() -> None:
    """The threshold is the caller's, not a fixed heuristic tuned for language codes."""
    assert disarm.nearest_match("something-entirely-else", RESERVED) is None
    assert disarm.nearest_match("payment", RESERVED, max_distance=1) is None
    # ...but the caller may widen it, and gets told how far away the answer was.
    #
    # `payment` is 4 from BOTH `admin` and `paypal`, so this also shows the tie rule
    # doing real work: `RESERVED` is sorted, `admin` comes first, and it wins. Widening
    # a threshold does not just add answers, it changes which answer you get.
    assert disarm.edit_distance("payment", "admin") == 4
    assert disarm.edit_distance("payment", "paypal") == 4
    widened = disarm.nearest_match("payment", RESERVED, max_distance=4)
    assert widened is not None
    assert (widened.value, widened.distance) == ("admin", 4)


def test_ties_go_to_the_first_candidate() -> None:
    """Documented, so a caller who cares knows to sort."""
    assert disarm.nearest_match("ax", ["ab", "ac"], max_distance=1).value == "ab"
    assert disarm.nearest_match("ax", ["ac", "ab"], max_distance=1).value == "ac"


def test_distance_counts_characters_not_bytes() -> None:
    """So a composed and a decomposed accent are not silently three edits apart."""
    assert disarm.edit_distance("é", "e") == 1
    assert disarm.edit_distance("café", "cafe") == 1
    # And the documented composition: reduce first when that difference should vanish.
    assert disarm.edit_distance(disarm.canonicalize("café"), disarm.canonicalize("café")) == 0
