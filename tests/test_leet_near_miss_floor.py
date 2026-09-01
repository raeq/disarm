"""The leet near-miss floor, in both directions (#825).

The `leet` branch has two sub-paths: the decode is a lexicon word, or the decode is one
edit from one. `leet_sub` maps `'1'` to `'i'` rather than `'l'` — correct, since `1`
looks like `i` in most faces — but the consequence is that a `1`-for-`l` substitution
**never decodes exactly** and can only ever be caught by the second path.

That path carried an uncommented `>= 6` from #393, so the whole substitution class went
unreported on short targets: `l0gin` was caught and `1ogin` was not.

The floor is now five. These tests pin both sides of it, so moving it again is a visible
change rather than a silent one.
"""

from __future__ import annotations

import pytest

import disarm

BRANDS = {
    "apple",
    "slack",
    "email",
    "login",
    "lyft",
    "google",
    "paypal",
    "netflix",
    "linkedin",
    "cloudflare",
    "gitlab",
    "outlook",
}


@pytest.mark.parametrize("token", ["app1e", "s1ack", "emai1", "1ogin"])
def test_a_five_letter_one_for_l_spoof_is_caught(token: str) -> None:
    """All four were clean before #825. The exact path cannot reach them at all."""
    assert "leet" in disarm.inspect_anomalies(token, lexicon=BRANDS).kinds


@pytest.mark.parametrize(
    "token", ["goog1e", "paypa1", "netf1ix", "1inkedin", "c1oudflare", "g1tlab", "out1ook"]
)
def test_the_six_and_over_cases_still_fire(token: str) -> None:
    """The floor moved down, so nothing above the old one may have been lost."""
    assert "leet" in disarm.inspect_anomalies(token, lexicon=BRANDS).kinds


def test_four_letters_is_still_below_the_floor() -> None:
    """`1yft` is the deliberate cost, not an oversight.

    Dropping to four would catch it and add eight false positives per 65 ordinary
    technical tokens; five costs exactly one. Pinned so the trade is visible if anyone
    lowers it further.
    """
    assert "leet" not in disarm.inspect_anomalies("1yft", lexicon=BRANDS).kinds


# (token, its actual `leet_sub` decode, a word one edit from that decode).
#
# Spelled out per row because an earlier version of this test described `k8s` as decoding
# to `kos` and `b2b` to `bab` — those are the words `nearest()` *matched*, not the
# decodes, which are `kbs` and `bzb` (#877 review). The decode is stated here so the
# one-edit relationship is checkable rather than asserted in a comment, and the decode
# itself is never in the lexicon: seeding it would make these exact-path hits and the
# test would be measuring the wrong path.
SHORT_TECHNICAL = [
    ("k8s", "kbs", "abs"),
    ("b2b", "bzb", "bob"),
    ("es6", "esg", "egg"),
    ("go2", "goz", "got"),
    ("id3", "ide", "ida"),
    ("mp3", "mpe", "ape"),
    ("l10n", "lion", "lions"),
    ("a11y", "aiiy", "airy"),
]


@pytest.mark.parametrize(("token", "decode", "neighbour"), SHORT_TECHNICAL, ids=lambda v: v)
def test_short_technical_tokens_do_not_fire_through_the_near_miss_path(
    token: str, decode: str, neighbour: str
) -> None:
    """The floor is doing real work, and the issue's case for removing it was too strong.

    Every decode here is three or four characters, which is short enough that a one-edit
    neighbourhood catches ordinary technical tokens. Measured, removing the floor takes
    false positives from 5 to 22 per 65 such tokens.
    """
    assert decode not in {neighbour}, "the neighbour must not be the decode itself"
    report = disarm.inspect_anomalies(token, lexicon={neighbour} | BRANDS)
    assert "leet" not in report.kinds, f"{token} -> {decode}: {report.reason}"


@pytest.mark.parametrize(("token", "decode", "neighbour"), SHORT_TECHNICAL, ids=lambda v: v)
def test_those_tokens_do_reach_the_branch(token: str, decode: str, neighbour: str) -> None:
    """Non-vacuity, and the reason the test above is worth anything.

    A token that never enters the leet branch at all — too short a base, a literal number
    — would pass the test above for a reason that has nothing to do with the floor. Put
    the decode itself in the lexicon and the *exact* path fires, which has no floor beyond
    three. So the branch is reachable for every row, and the near-miss floor is the only
    thing declining them.
    """
    assert neighbour  # the row is well-formed
    report = disarm.inspect_anomalies(token, lexicon={decode} | BRANDS)
    assert "leet" in report.kinds, f"{token} never reaches the leet branch at all"
    assert report.findings[0].detail == decode


def test_the_exact_path_keeps_its_own_lower_floor() -> None:
    """Three, unchanged. The two paths have different floors on purpose."""
    assert "leet" in disarm.inspect_anomalies("fr33", lexicon={"free"}).kinds
