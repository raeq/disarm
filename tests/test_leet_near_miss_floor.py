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


@pytest.mark.parametrize("token", ["k8s", "b2b", "es6", "go2", "id3", "mp3", "x86", "3pm"])
def test_short_technical_tokens_do_not_fire_through_the_near_miss_path(token: str) -> None:
    """The floor is doing real work and the issue's argument for removing it was too strong.

    At floor 3 these decode into a one-edit neighbourhood dense enough to match: `k8s` →
    `kos`, `b2b` → `bab`, `es6` → `es`. Measured, removing the floor takes false
    positives from 5 to 22 per 65 tokens.
    """
    # One edit from each decode, never the decode itself — a lexicon holding the decode
    # would make these *exact*-path hits and the test would be measuring the wrong path.
    # `k8s` decodes to `kos`, `b2b` to `bab`, `es6` to `esg`, `id3` to `ide`, `mp3` to `mpe`.
    neighbours = {"kot", "bat", "esq", "gob", "ida", "mpg", "xbg", "opm", "epm"}
    report = disarm.inspect_anomalies(token, lexicon=neighbours | BRANDS)
    assert "leet" not in report.kinds, f"{token}: {report.reason}"


def test_the_exact_path_keeps_its_own_lower_floor() -> None:
    """Three, unchanged. The two paths have different floors on purpose."""
    assert "leet" in disarm.inspect_anomalies("fr33", lexicon={"free"}).kinds
