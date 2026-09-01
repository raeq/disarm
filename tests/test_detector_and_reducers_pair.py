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
    for reducer in REDUCERS.values():
        reduced = reducer(identifier)
        if reduced and reduced == reducer(target):
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

#: Cases `find_confusables` catches and no reducer can — the composability class.
#:
#: These are the rows where TR39 and NFKC disagree about what the character is (#834), so
#: the reducer takes the NFKC answer and never collides with the TR39 target a registry is
#: protecting. `U+017F` is `f` to TR39 and `s` to NFKC; `U+2110` is `l` and `i`.
#:
#: A first draft of this list used Cyrillic lookalikes — `аpple`, `gоnfig`. Those are the
#: *impersonation* class, and the reducers catch 30 of 35 of them, so `аpple` was not a
#: detector-only case at all and the comment above it overclaimed (#892 review). Each row
#: below is asserted in both directions rather than described.
ONLY_THE_DETECTOR = [
    ("ſ", "f"),  # U+017F LATIN SMALL LETTER LONG S
    ("ℐ", "l"),  # U+2110 SCRIPT CAPITAL I
    ("Ⅰ", "l"),  # U+2160 ROMAN NUMERAL ONE
    ("Ｉ", "l"),  # U+FF29 FULLWIDTH LATIN CAPITAL LETTER I
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


@pytest.mark.parametrize(("identifier", "target"), ONLY_THE_DETECTOR, ids=lambda v: repr(v))
def test_the_detector_catches_what_the_reducers_cannot(identifier: str, target: str) -> None:
    assert disarm.find_confusables(identifier)
    assert not _any_reducer_collides(identifier, target), (
        "if a reducer reaches this, it is not a detector-only case and the documented "
        "0/31 on composability needs re-measuring"
    )


@pytest.mark.parametrize("identifier", BENIGN)
def test_neither_fires_on_a_benign_name(identifier: str) -> None:
    """The pairing costs nothing in false positives, which is why it is a recommendation.

    Across every reducer, not just `canonicalize`: the documented 0/20 is the union's
    figure, so checking one of the six would understate what is being claimed.
    """
    assert not disarm.find_confusables(identifier)
    for name, reducer in REDUCERS.items():
        assert reducer(identifier) == identifier, f"{name} altered the benign {identifier!r}"


def test_the_union_is_strictly_larger_than_either_side() -> None:
    """The claim in one assertion: neither surface is a superset of the other."""
    reducer_only = {i for i, t in ONLY_THE_REDUCERS if _any_reducer_collides(i, t)}
    detector_only = {i for i, t in ONLY_THE_DETECTOR if not _any_reducer_collides(i, t)}
    assert reducer_only, "no case is reducer-only; the split has changed"
    assert detector_only, "no case is detector-only; the split has changed"
    assert not any(disarm.find_confusables(i) for i in reducer_only)
