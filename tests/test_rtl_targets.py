"""#792 — `target_script="arabic"` and `"hebrew"`, and the boundary of what they reach.

Generation keeps the members of an equivalence class that belong to the target script and
drops the class entirely when no member does (#791). So a class whose members are all
Arabic survived into neither shipped table, and **948 of TR39's 1,007 strong-RTL sources**
folded to nothing. These two targets give those classes somewhere to land: 373 rows and 261
rows.

The boundary is the important half of this file. #792 was filed believing an Arabic target
would fold Persian keheh onto Arabic kaf. It does not, and cannot: both members are
*already* in the target script, which `filter_direct` skips and `filter_via_classes` has
nothing to map from. Prototyping it before writing any of it is what showed that, and the
four code points in the issue's motivating table are absent from the generated table.

That is #848, and it needs the generator to stop discarding same-script classes rather than
a new target. Asserting the boundary here is what stops someone concluding from the
CHANGELOG that intra-RTL is now covered.
"""

from __future__ import annotations

import pytest

import disarm

RTL_TARGETS = ("arabic", "hebrew")


@pytest.mark.parametrize("target", RTL_TARGETS)
def test_the_target_is_accepted(target: str) -> None:
    assert disarm.normalize_confusables("abc", target_script=target) == "abc"


@pytest.mark.parametrize(
    ("source", "expected", "target"),
    [
        ("⸮", "؟", "arabic"),
        ("⸲", "،", "arabic"),
        ("𞣉", "٣", "arabic"),
        ("ℵ", "א", "hebrew"),
        ("ℶ", "ב", "hebrew"),
        ("∸", "﬩", "hebrew"),
    ],
    ids=["question", "comma", "three", "alef", "bet", "plus"],
)
def test_cross_script_sources_now_fold(source: str, expected: str, target: str) -> None:
    """The rows the residue gets back — punctuation, letterlike symbols, digits."""
    assert disarm.normalize_confusables(source, target_script=target) == expected


@pytest.mark.parametrize("target", RTL_TARGETS)
def test_the_other_targets_are_unmoved(target: str) -> None:
    """Opt-in, like `cyrillic`. No preset consumes a non-Latin target.

    This is what made #792 §1's blocking question resolve: adding a target introduces no
    second answer on any surface a caller is already using.
    """
    assert disarm.normalize_confusables("а") == "a"
    assert disarm.canonicalize("раураl.com") == "paypal.com"


# ── the boundary ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("left", "right", "name"),
    [
        ("ک", "ك", "Persian keheh / Arabic kaf"),
        ("ی", "ي", "Farsi yeh / Arabic yeh"),
    ],
    ids=["keheh-kaf", "yeh-yeh"],
)
def test_intra_script_pairs_are_not_reached(left: str, right: str, name: str) -> None:
    """The premise #792 was filed on, asserted as false so nobody re-assumes it.

    TR39 *does* put these in one class — the data is not the problem. A cross-script table
    cannot express a same-script pair, and that is #848.
    """
    folded_left = disarm.normalize_confusables(left, target_script="arabic")
    folded_right = disarm.normalize_confusables(right, target_script="arabic")
    assert folded_left != folded_right, f"{name}: if this passes, #848 landed — update this"


def test_the_key_builders_still_reach_them() -> None:
    """The gap is in the fold, not in identity comparison.

    A caller comparing identities is not exposed to it, because the key builders
    transliterate first. Pinned so the docs cannot become an over-claim in either
    direction.
    """
    assert disarm.search_key("ک") == disarm.search_key("ك")
    assert disarm.catalog_key("ک") == disarm.catalog_key("ك")


def test_the_hostname_screen_is_unaffected() -> None:
    """`is_suspicious_hostname` computes against Latin with the target hardcoded.

    An Arabic label whose skeleton stays Arabic cannot qualify whatever these tables hold,
    and the docs say so rather than implying the tables fixed it.
    """
    suspicious, analysis = disarm.is_suspicious_hostname("مرحبا.com")
    assert not analysis.whole_script_confusable


def test_an_unknown_target_is_still_rejected() -> None:
    """Adding two targets must not turn the validator into a pass-through."""
    with pytest.raises(disarm.InvalidArgumentError):
        disarm.normalize_confusables("x", target_script="klingon")
