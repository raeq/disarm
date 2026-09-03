"""#728 — every preset and key builder maps non-empty input to `""`.

A value that was entirely stripped is indistinguishable from a value that was never there.
`sanitize_filename` is the only surface that guards it, with the `_` sentinel from #485.

    find_key_collisions(["admin", "", ZWSP, STACKED_MARKS, SHY, "bob"], key="search_key")
    -> one group, key "", holding absence and three stripped values

This is not the homoglyph collision the key builders exist to produce. Those are
deliberate: `аdmin` and `admin` *should* meet. This one collapses **absence** onto **a
value**, which arXiv:2608.06508v1 §2.2 calls code-side semantic collapse and §7.5 says is
fixed by redefining the mapping so the sentinel sits outside the value range — not by
normalizing harder.

The census is frozen here, per #728 item 4: a future strip class taking more code points
to `""` becomes a diff somebody reads rather than a silent widening.
"""

from __future__ import annotations

import sys
import unicodedata
from collections.abc import Callable

import pytest

import disarm
from disarm._presets import _EMPTY_KEY_CENSUS

KEY_BUILDERS = ["search_key", "catalog_key", "sort_key", "skeleton_key"]

#: Escapes, never literals: an invisible in a source file is unreviewable (#802).
ZWSP = "\u200b"
SHY = "\u00ad"
STACKED_MARKS = "\u0301\u0302"
#: A sentinel no builder can produce: it is stripped by all of them.
SENTINEL = "␀"  # SYMBOL FOR NULL


@pytest.fixture(scope="module")
def assigned() -> list[str]:
    return [
        chr(cp)
        for cp in range(sys.maxunicode + 1)
        if unicodedata.category(chr(cp)) not in ("Cn", "Cs")
    ]


def _surface(name: str) -> Callable[[str], str]:
    return getattr(disarm, name)


@pytest.mark.parametrize("name", sorted(_EMPTY_KEY_CENSUS))
def test_the_census_is_what_the_docstrings_claim(name: str, assigned: list[str]) -> None:
    """Item 4. The numbers are in nine docstrings; this is what keeps them true.

    A count is asserted rather than proof-read, because a docstring number nobody
    re-measures is a number that stops being right the first time a strip class widens.
    """
    total_want, nonpua_want = _EMPTY_KEY_CENSUS[name]
    fn = _surface(name)
    total = nonpua = 0
    for ch in assigned:
        try:
            if fn(ch) == "":
                total += 1
                if unicodedata.category(ch) != "Co":
                    nonpua += 1
        except disarm.DisarmError:
            pass  # a surface that refuses is not an empty key
    assert (total, nonpua) == (total_want, nonpua_want), (
        f"{name}: measured {total:,}/{nonpua:,}, docstring and census say "
        f"{total_want:,}/{nonpua_want:,}. If this is a deliberate change, update "
        "_EMPTY_KEY_CENSUS and the docstring in the same commit."
    )


def test_sanitize_filename_is_still_the_one_surface_that_reserves_a_sentinel() -> None:
    """The precedent the rest of #728 is measured against (#485)."""
    assert _EMPTY_KEY_CENSUS["sanitize_filename"] == (0, 0)
    assert disarm.sanitize_filename(ZWSP) == "_"


def test_the_collision_the_issue_reports() -> None:
    """Absence and three stripped values in one group, under the default."""
    values = ["admin", "", ZWSP, STACKED_MARKS, SHY, "bob"]
    groups = disarm.find_key_collisions(values, key="search_key")
    empty = [g for g in groups if g.key == ""]
    assert len(empty) == 1, groups
    assert set(empty[0].values) == {"", ZWSP, STACKED_MARKS, SHY}


class TestOnEmpty:
    @pytest.mark.parametrize("name", KEY_BUILDERS)
    def test_a_stripped_value_takes_the_sentinel(self, name: str) -> None:
        fn = _surface(name)
        assert fn(ZWSP) == ""
        assert fn(ZWSP, on_empty=SENTINEL) == SENTINEL

    @pytest.mark.parametrize("name", KEY_BUILDERS)
    def test_absence_keeps_its_own_key(self, name: str) -> None:
        """The whole point, and the thing the first implementation got wrong.

        Substituting the sentinel for an empty *input* too would put absence and a
        stripped value back in one slot — the collision this exists to break.
        """
        fn = _surface(name)
        assert fn("", on_empty=SENTINEL) == ""
        assert fn("", on_empty=SENTINEL) != fn(ZWSP, on_empty=SENTINEL)

    @pytest.mark.parametrize("name", KEY_BUILDERS)
    def test_the_default_is_unchanged(self, name: str) -> None:
        fn = _surface(name)
        for probe in ["admin", "", ZWSP, "Москва", "café"]:
            assert fn(probe) == fn(probe, on_empty=None), repr(probe)

    @pytest.mark.parametrize("name", KEY_BUILDERS)
    def test_it_never_touches_a_non_empty_key(self, name: str) -> None:
        fn = _surface(name)
        for probe in ["admin", "Москва", "café", "a b c"]:
            assert fn(probe, on_empty=SENTINEL) == fn(probe), repr(probe)

    def test_the_reported_collision_is_broken(self) -> None:
        """The issue's own group, with a sentinel: absence leaves it."""
        values = ["admin", "", ZWSP, STACKED_MARKS, SHY, "bob"]
        keys = [disarm.search_key(v, on_empty=SENTINEL) for v in values]
        assert keys[1] == "", "absence"
        assert keys[2] == keys[3] == keys[4] == SENTINEL, "the three stripped values"
        assert keys[1] != keys[2], "which is the separation #728 asks for"

    def test_the_stripped_values_still_share_a_key_and_that_is_correct(self) -> None:
        """They are all "input that reduced to nothing", which is one fact, not three."""
        assert disarm.search_key(ZWSP, on_empty=SENTINEL) == disarm.search_key(
            SHY, on_empty=SENTINEL
        )

    def test_a_sentinel_the_builder_can_produce_reintroduces_the_collision(self) -> None:
        """Documented rather than prevented: disarm cannot check the caller's choice."""
        assert disarm.search_key("admin") == "admin"
        assert disarm.search_key(ZWSP, on_empty="admin") == disarm.search_key("admin")
