"""#831 — ICANN's Latin second-level LGR blocks same-script pairs disarm did not fold.

The LGR defines 25 variant sets over a 231-element repertoire, expanding to 51 blocked or
fallback variant pairs. 23 carry the variant comment *"Glyphs either homoglyph or nearly
identical"* — the Latin Generation Panel's own visual judgement. `canonicalize` collided 2
of those 23.

That was not a defect in the fold. These are **same-script Latin-to-Latin** pairs and
disarm's confusable data is cross-script; most of the code points are not TR39 sources at
all. The two sets never met.

Both directions are asserted, and the second half is the one that matters more. The LGR's
other 23 pairs are commented *"Required for use with Common LGR"* — transitivity artefacts
of running this ruleset concurrently with the Greek and Cyrillic ones (`u`/`ü`, `a`/`á`,
`o`/`ó`, `n`/`ń`) — and its own Variants section says they "can be removed if the LGR is
used strictly as standalone". Importing them would strip legitimate diacritics from every
language that uses them. Asserting they stay distinct is what stops a later well-meaning
import of the whole variant set.

Two rows are deliberately absent: `n̄`/`ñ` and `g̃`/`ḡ`, whose source is base + combining
mark with no precomposed form. The file format cannot express a multi-code-point source,
and the contraction table that can is unreachable from `normalize_confusables`. Filed as
#836 with the whole class — six Latin bases where tilde and macron disagree on
precomposition.
"""

from __future__ import annotations

import pytest

import disarm

#: The 19 single-code-point pairs whose LGR comment reads "homoglyph or nearly identical".
#: Written as escapes: several are indistinguishable from each other on the page, which is
#: the entire reason they are in this file.
HOMOGLYPH_PAIRS = [
    ("\u00f2", "\u1ecf", "o-grave / o-hook"),
    ("i", "\u1ec9", "i / i-hook"),
    ("\u00f5", "\u014d", "o-tilde / o-macron"),
    ("\u0131", "\u1ec9", "dotless i / i-hook"),
    ("\u00f9", "\u1ee7", "u-grave / u-hook"),
    ("\u0269", "\u1ec9", "iota / i-hook"),
    ("\u00fd", "\u1ef7", "y-acute / y-hook"),
    ("\u0144", "\u1e45", "n-acute / n-dot"),
    ("\u1ef3", "\u1ef7", "y-grave / y-hook"),
    ("\u0107", "\u010b", "c-acute / c-dot"),
    ("\u00e0", "\u1ea3", "a-grave / a-hook"),
    ("\u0113", "\u1ebd", "e-macron / e-tilde"),
    ("\u00e3", "\u0101", "a-tilde / a-macron"),
    ("\u011f", "\u01e7", "g-breve / g-caron"),
    ("\u0121", "\u0123", "g-dot / g-cedilla"),
    ("\u0129", "\u012b", "i-tilde / i-macron"),
    ("\u0169", "\u016b", "u-tilde / u-macron"),
    ("\u017a", "\u017c", "z-acute / z-dot"),
    ("\u01dd", "\u0259", "turned e / schwa"),
]

#: Pairs the LGR blocks only for Common-LGR transitivity, which must NOT collide.
COMMON_LGR_ONLY = [
    ("u", "\u00fc", "u / u-diaeresis"),
    ("a", "\u00e1", "a / a-acute"),
    ("o", "\u00f3", "o / o-acute"),
    ("n", "\u0144", "n / n-acute"),
    ("e", "\u00e9", "e / e-acute"),
]


@pytest.mark.parametrize(("left", "right", "name"), HOMOGLYPH_PAIRS, ids=lambda v: v)
def test_the_homoglyph_pairs_collide(left: str, right: str, name: str) -> None:
    """The half #831 is about: 2 of 23 collided before."""
    assert disarm.canonicalize(left) == disarm.canonicalize(right), name


@pytest.mark.parametrize(("left", "right", "name"), COMMON_LGR_ONLY, ids=lambda v: v)
def test_the_transitivity_pairs_stay_distinct(left: str, right: str, name: str) -> None:
    """The half that stops the next import going too far.

    These are blocked by the LGR only because it is meant to run beside the Greek and
    Cyrillic rulesets. Folding them would merge every accented letter with its bare form —
    the over-collapse `search_key` already commits, at 1,534 non-LGR merges.
    """
    assert disarm.canonicalize(left) != disarm.canonicalize(right), name


@pytest.mark.parametrize(
    ("host_a", "host_b"),
    [
        ("ważne.pl", "waźne.pl"),
        ("gmaġl.com", "gmaģl.com"),
        ("lýs.com", "lỳs.com"),
        ("gǝnc.com", "gənc.com"),
    ],
    ids=["zz", "gg", "yy", "ee"],
)
def test_the_hostname_rows_from_the_issue(host_a: str, host_b: str) -> None:
    """The surface the LGR is about: two registrable names that render the same."""
    assert disarm.canonicalize(host_a) == disarm.canonicalize(host_b)


def test_the_schwa_inconsistency_is_repaired() -> None:
    """#831 flags this as an inconsistency rather than a gap, and it is fixed both ways.

    TR39 folds `ə` to `e` and does not know `ǝ`, so disarm cleared one member of a
    mutually blocked pair and flagged the other. The class representative is chosen as the
    existing ASCII target where one exists, so both now reach `e` — a pairwise "fold to the
    lower code point" rule would have made `ə` the *source* and undone its fold.
    """
    assert disarm.canonicalize("ǝ") == "e"
    assert disarm.canonicalize("ə") == "e"


def test_the_targets_are_one_step() -> None:
    """No LGR target is itself a source, so the fold does not chain.

    `build.rs` asserts this at compile time; asserting it here too states the property in
    the place a reader looks for behaviour rather than for build wiring.
    """
    for left, right, name in HOMOGLYPH_PAIRS:
        for text in (left, right):
            once = disarm.normalize_confusables(text)
            assert disarm.normalize_confusables(once) == once, f"{name}: not a fixed point"


def test_accented_latin_is_not_collapsed_to_ascii() -> None:
    """The reason the targets are not ASCII.

    Folding `ż` to `z` would merge it with the bare letter, which the LGR does not
    block. The pair collides with each other and with nothing else.
    """
    assert disarm.canonicalize("ż") == disarm.canonicalize("ź")
    assert disarm.canonicalize("ż") != disarm.canonicalize("z")
