"""Detection and reduction answer different questions, and neither is complete (#882).

`find_confusables` reports what *looks like* something else. The key reducers report what
two strings *collapse to*. Each interface looks complete on its own, which is what makes
the mistake easy: two deliberate measurement attempts in two days scored one of them and
published the result as disarm's answer.

Measured over `confusable-bench.v1` — 120 malicious identifiers, 20 benign controls — the
six reducers together catch 72 and `find_confusables` catches 66, but **either one firing
catches 108**, at 0 false positives for each alone and for the pair.

These tests do not fetch that corpus. They pin the *structural* claim instead, which is
what the documentation rests on and what a regression would break: there are cases each
surface catches and the other cannot, so recommending one is recommending a partial
answer. The corpus scoring lives in `benchmarks/meta`, where a network dependency belongs.
"""

from __future__ import annotations

import pytest

import disarm

REDUCERS = {
    "canonicalize": disarm.canonicalize,
    "canonicalize_strict": disarm.canonicalize_strict,
    "search_key": lambda s: disarm.search_key(s),
    "catalog_key": lambda s: disarm.catalog_key(s),
    "sort_key": lambda s: disarm.sort_key(s),
    "strip_obfuscation": disarm.strip_obfuscation,
}


def _any_reducer_collides(identifier: str, target: str) -> bool:
    """Score as a registry would: does it reduce to the same non-empty form as the name?"""
    for reduce in REDUCERS.values():
        reduced = reduce(identifier)
        if reduced and reduced == reduce(target):
            return True
    return False


#: Cases the reducers catch and `find_confusables` cannot — the evasion class. The
#: attacker's character has no fold target; the attack is in what survives, and only a
#: reduction that strips it makes the two strings equal.
#:
#: Escapes, not literals: each renders as nothing, so a literal would be
#: indistinguishable from a typo on the line meant to explain it (#802).
ONLY_THE_REDUCERS = [
    ("pay\u200bpal", "paypal"),  # zero-width space
    ("pay\u00adpal", "paypal"),  # soft hyphen
    ("pay\ufeffpal", "paypal"),  # BOM
]

#: Cases `find_confusables` catches and the reducers cannot — the composability class.
#: The two strings are already equal by the time the divergence matters, so no reduction
#: separates them, but the identifier still carries a character imitating another.
ONLY_THE_DETECTOR = [
    "аpple",  # Cyrillic а
    "ԁoinbase",  # Cyrillic ԁ
    "gоnfig",  # Cyrillic о
]

#: Benign controls. Neither surface may fire.
BENIGN = ["stripe", "vercel", "openai", "github", "admin"]


@pytest.mark.parametrize(("identifier", "target"), ONLY_THE_REDUCERS, ids=lambda v: repr(v))
def test_the_reducers_catch_what_the_detector_cannot(identifier: str, target: str) -> None:
    assert _any_reducer_collides(identifier, target)
    assert not disarm.find_confusables(identifier), (
        "if the detector reaches this, the two surfaces are no longer complementary "
        "in this direction and the documented split needs re-measuring"
    )


@pytest.mark.parametrize("identifier", ONLY_THE_DETECTOR, ids=lambda v: repr(v))
def test_the_detector_catches_what_the_reducers_cannot(identifier: str) -> None:
    assert disarm.find_confusables(identifier)


@pytest.mark.parametrize("identifier", BENIGN)
def test_neither_fires_on_a_benign_name(identifier: str) -> None:
    """The pairing costs nothing in false positives, which is why it is a recommendation."""
    assert not disarm.find_confusables(identifier)
    assert not any(reduce(identifier) != identifier for reduce in (disarm.canonicalize,))


def test_the_union_is_strictly_larger_than_either_side() -> None:
    """The claim in one assertion: neither surface is a superset of the other."""
    reducer_only = {i for i, t in ONLY_THE_REDUCERS if _any_reducer_collides(i, t)}
    detector_only = {i for i in ONLY_THE_DETECTOR if disarm.find_confusables(i)}
    assert reducer_only, "no case is reducer-only; the split has changed"
    assert detector_only, "no case is detector-only; the split has changed"
    assert not any(disarm.find_confusables(i) for i in reducer_only)
