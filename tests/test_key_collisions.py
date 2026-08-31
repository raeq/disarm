"""Tests for find_key_collisions: which values in a set are the same name (#620).

The set-shaped question. Every other disarm detector is a single-string
predicate, and a collision is not a property of a single string — ``groß.txt`` is
an ordinary German filename, ``аdmin`` is only a problem next to ``admin``.

Two things are worth pinning beyond the mechanics. First, **the reducer is the
policy**: each of the six draws a different line, which is why there is no
default. Second, **the report cannot disagree with the collapse it describes**,
because both come from one pass over one reducer — that is the property the issue
asks for and the one a caller re-implementing the loop has to get right.
"""

from __future__ import annotations

import re

import pytest

import disarm
from disarm import KeyCollision, find_key_collisions, fold_case


def _accepted_key_forms() -> tuple[str, ...]:
    """The reducers the function accepts, read out of its own rejection message.

    Derived rather than transcribed (review on #635, which caught this comment
    claiming a derivation the code did not do): a seventh key added to the enum
    updates the message, and every parametrized test below follows it. A
    hand-written copy here would quietly stop covering the new one.
    """
    try:
        find_key_collisions(["x"], key="")
    except disarm.InvalidArgumentError as exc:
        offered = str(exc).split(", got ")[0]
        return tuple(re.findall(r"'([a-z_]+)'", offered))
    raise AssertionError("an empty key must be rejected")


#: Every reducer the function accepts.
KEY_FORMS = _accepted_key_forms()


def test_the_derived_key_form_list_is_not_vacuous() -> None:
    """Guard the derivation itself: a message reword that stops matching would
    silently empty every parametrized test in this file."""
    assert len(KEY_FORMS) == 6, KEY_FORMS
    assert "fold_case" in KEY_FORMS


class TestTheNodeTarCase:
    """CVE-2026-23950 — the collision `PathReservations` failed to notice."""

    def test_the_pair_is_reported(self) -> None:
        found = find_key_collisions(["groß.txt", "gross.txt", "other.txt"], key="fold_case")
        assert len(found) == 1
        assert found[0].key == "gross.txt"
        assert found[0].values == ["groß.txt", "gross.txt"]
        assert found[0].indices == [0, 1]

    def test_a_clean_set_reports_nothing(self) -> None:
        assert find_key_collisions(["a.txt", "b.txt", "c.txt"], key="fold_case") == []
        assert find_key_collisions([], key="fold_case") == []

    def test_the_report_is_what_the_extractor_needs(self) -> None:
        """Both halves of the result are load-bearing, for different callers.

        A registry refusing a registration wants the *names*. An extractor
        deciding which archive entries to skip wants the *positions*. Building
        either from the other means re-running the reducer, which is the step this
        function exists to stop the caller getting wrong.
        """
        entries = ["a.txt", "groß.txt", "b.txt", "gross.txt", "GROSS.TXT"]
        (group,) = find_key_collisions(entries, key="fold_case")
        assert group.values == ["groß.txt", "gross.txt", "GROSS.TXT"]
        assert group.indices == [1, 3, 4]
        assert [entries[i] for i in group.indices] == group.values


class TestWhatCountsAsACollision:
    def test_one_name_twice_is_not_a_collision(self) -> None:
        """A reservation table already handles the same name twice. The hazard is
        two names that *differ* and land in one slot."""
        assert find_key_collisions(["a.txt", "a.txt"], key="fold_case") == []

    def test_a_repeat_inside_a_real_collision_keeps_every_index(self) -> None:
        (group,) = find_key_collisions(["groß.txt", "gross.txt", "gross.txt"], key="fold_case")
        assert group.values == ["groß.txt", "gross.txt"]  # distinct
        assert group.indices == [0, 1, 2]  # every position

    def test_groups_come_back_in_first_appearance_order(self) -> None:
        """Asserted rather than observed: the grouping is hash-backed, so a
        deterministic order has to be a choice, not a coincidence."""
        found = find_key_collisions(["zetaß", "alphaß", "zetass", "alphass"], key="fold_case")
        assert [g.key for g in found] == ["zetass", "alphass"]


class TestTheReducerIsThePolicy:
    """The measured table behind the docstrings, derived here rather than trusted.

    A stronger reducer finds more collisions. That is the whole trade, and it is
    why the caller chooses: ``fold_case`` sees the eszett and no homoglyph;
    ``canonicalize`` sees the reverse; ``search_key`` sees both and also collides
    ordinary names nobody attacked.
    """

    #: (genuine, spoof) for the four published collision CVEs.
    CVE_PAIRS = {
        "CVE-2026-23950": ("gross.txt", "groß.txt"),
        "CVE-2019-19844": ("admin@example.com", "admın@example.com"),
        "CVE-2013-7236": ("admin", "аdmin"),
        "CVE-2020-12063": ("boss@example.com", "bοss@example.com"),
    }

    #: Which key catches which row. This is the table the Rust `KeyForm` docs and
    #: the Python docstring publish, so it is measured here and nowhere else.
    EXPECTED = {
        "fold_case": {"CVE-2026-23950"},
        "search_key": set(CVE_PAIRS),
        "catalog_key": set(CVE_PAIRS),
        "canonicalize": {"CVE-2019-19844", "CVE-2013-7236", "CVE-2020-12063"},
        "canonicalize_strict": {"CVE-2019-19844", "CVE-2013-7236", "CVE-2020-12063"},
        "normalize_confusables": {"CVE-2019-19844", "CVE-2013-7236", "CVE-2020-12063"},
    }

    @pytest.mark.parametrize("key", KEY_FORMS)
    def test_each_key_catches_exactly_the_rows_claimed(self, key: str) -> None:
        caught = {
            cve for cve, pair in self.CVE_PAIRS.items() if find_key_collisions(list(pair), key=key)
        }
        assert caught == self.EXPECTED[key]

    def test_no_key_catches_everything_for_free(self) -> None:
        """The cost side of the same table, and the reason this is not a detector.

        ``search_key`` collides ``Muller`` with ``Müller`` and ``Ivan`` with
        ``Иван``. Neither is an attack, and neither is a false positive: they
        really are one key. The caller who picked that key asked for it.
        """
        ordinary = ["Muller", "Müller", "Ivan", "Иван"]
        merged = find_key_collisions(ordinary, key="search_key")
        assert [g.values for g in merged] == [["Muller", "Müller"], ["Ivan", "Иван"]]
        # The narrow keys leave them alone.
        assert find_key_collisions(ordinary, key="fold_case") == []
        assert find_key_collisions(ordinary, key="canonicalize") == []

    def test_there_is_no_default_key(self) -> None:
        """Choosing for the caller would be choosing their threat model."""
        with pytest.raises(TypeError):
            find_key_collisions(["a"])  # type: ignore[call-arg]


class TestTheGuarantee:
    """Reporting and collapsing use one reducer, so they cannot disagree."""

    NAMES = ["groß.txt", "gross.txt", "GROSS.TXT", "other.txt", "andere", "admin", "аdmin"]

    #: The public function behind each token, so the guarantee is checked against
    #: the reducer itself rather than against the function's own bookkeeping.
    REDUCERS = {
        "fold_case": disarm.fold_case,
        "search_key": disarm.search_key,
        "catalog_key": disarm.catalog_key,
        "canonicalize": disarm.canonicalize,
        "canonicalize_strict": disarm.canonicalize_strict,
        "normalize_confusables": disarm.normalize_confusables,
    }

    @pytest.mark.parametrize("key", KEY_FORMS)
    def test_every_reported_group_really_shares_a_key(self, key: str) -> None:
        reducer = self.REDUCERS[key]
        found = find_key_collisions(self.NAMES, key=key)
        for group in found:
            assert {reducer(v) for v in group.values} == {group.key}

    @pytest.mark.parametrize("key", KEY_FORMS)
    def test_nothing_that_should_have_been_grouped_was_left_out(self, key: str) -> None:
        """The other half: no value outside a reported group shares its key."""
        reducer = self.REDUCERS[key]
        found = find_key_collisions(self.NAMES, key=key)
        reported = {v for g in found for v in g.values}
        keys = {g.key for g in found}
        for name in self.NAMES:
            if name not in reported:
                assert reducer(name) not in keys, name


class TestLanguageHint:
    def test_lang_reaches_the_keys_that_take_one(self) -> None:
        """German transliteration turns ö into oe, so the pair is one key under
        ``de`` and two under the default."""
        names = ["Müller", "Mueller"]
        assert len(find_key_collisions(names, key="search_key", lang="de")) == 1
        assert find_key_collisions(names, key="search_key") == []

    def test_lang_is_ignored_by_the_keys_that_do_not(self) -> None:
        names = ["Müller", "Mueller"]
        assert find_key_collisions(names, key="fold_case", lang="de") == []


class TestErrors:
    def test_an_unknown_key_is_refused_rather_than_defaulted(self) -> None:
        with pytest.raises(disarm.InvalidArgumentError, match="key must be"):
            find_key_collisions(["a"], key="lower")

    def test_the_error_names_every_accepted_key(self) -> None:
        """So the message is the documentation, and cannot drift from the set."""
        with pytest.raises(disarm.InvalidArgumentError) as exc:
            find_key_collisions(["a"], key="nope")
        for form in KEY_FORMS:
            assert form in str(exc.value)

    def test_a_batch_over_the_cap_is_refused(self) -> None:
        """Same cap and the same exception class as every other batch entry
        point: a size limit is a resource limit, not a bad argument."""
        from disarm._core import _MAX_BATCH_SIZE

        with pytest.raises(disarm.ResourceLimitError, match="batch too large"):
            find_key_collisions(["a"] * (_MAX_BATCH_SIZE + 1), key="fold_case")

    @pytest.mark.parametrize("bad", ["notalist", 42, None])
    def test_a_non_list_is_a_type_error(self, bad: object) -> None:
        with pytest.raises(TypeError, match="expects list"):
            find_key_collisions(bad, key="fold_case")  # type: ignore[arg-type]

    def test_a_non_str_member_is_a_type_error(self) -> None:
        with pytest.raises(TypeError, match="expects list"):
            find_key_collisions(["a", 42], key="fold_case")  # type: ignore[list-item]


class TestResultObject:
    def test_fields_and_repr(self) -> None:
        (group,) = find_key_collisions(["groß", "gross"], key="fold_case")
        assert isinstance(group, KeyCollision)
        assert (group.key, group.values, group.indices) == ("gross", ["groß", "gross"], [0, 1])
        assert "KeyCollision(" in repr(group)
        assert "gross" in repr(group)

    def test_it_is_return_only(self) -> None:
        """Constructed by disarm, never by the caller — the same contract
        ``AnomalyReport`` and ``HostnameAnalysis`` have."""
        with pytest.raises(TypeError):
            KeyCollision()  # type: ignore[call-arg]


class TestSurrogateContract:
    def test_a_lone_surrogate_answers_for_its_scrubbed_form(self) -> None:
        """#469, applied to a list argument.

        A lone surrogate has no UTF-8 encoding, so it never reaches Rust: the
        boundary replaces it with U+FFFD. Two inputs that differ only by that
        substitution therefore arrive as **one name**, and one name twice is not a
        collision. Pinned because it is the one place the contract changes an
        answer rather than just avoiding an exception.
        """
        assert find_key_collisions(["a\ud800b", "a�b"], key="fold_case") == []
        # And a genuine collision alongside a surrogate still reports.
        found = find_key_collisions(["a\ud800b", "groß", "gross"], key="fold_case")
        assert [g.values for g in found] == [["groß", "gross"]]


class TestTheReducedSetCount:
    """#763 — the return is a filtered list, not a partition, and the two counts do not add.

    A name that collides with nothing never appears in the result, so a caller who wants
    "how many distinct identities does this batch hold" has to derive it. Four spellings
    of that derivation are plausible and three are wrong, but all four agree on any
    duplicate-free input — and every worked example in the repository was duplicate-free.
    That is the whole trap: a caller checking their arithmetic against the documentation
    got agreement from a wrong formula.

    Pinned to ASCII case folding on purpose (R13). `admin` / `Admin` reduce the same way
    before and after the confusable regeneration in #715/#801 and the `strip_accents`
    change in #749, so unrelated data work cannot move this fixture.
    """

    #: The one correct spelling: distinct inputs, minus the distinct inputs the groups
    #: account for, plus one slot per group.
    @staticmethod
    def reduced(names: list[str], groups: list) -> int:
        return len(set(names)) - sum(len(g.values) for g in groups) + len(groups)

    def test_the_documented_derivation(self) -> None:
        names = ["admin", "admin", "Admin"]
        groups = find_key_collisions(names, key="fold_case")
        assert len(groups) == 1
        assert groups[0].values == ["admin", "Admin"]  # distinct: two
        assert groups[0].indices == [0, 1, 2]  # occurrences: three
        assert self.reduced(names, groups) == 1, "three names, one identity"

    def test_the_three_near_misses_are_wrong_on_this_input(self) -> None:
        """Asserted, not described. Each is a real substitution somebody would make."""
        names = ["admin", "admin", "Admin"]
        groups = find_key_collisions(names, key="fold_case")
        raw = len(names)
        distinct = len(set(names))
        by_values = sum(len(g.values) for g in groups)
        by_indices = sum(len(g.indices) for g in groups)
        assert raw - by_values + len(groups) == 2, "counts a repeat as a second identity"
        assert distinct - by_indices + len(groups) == 0, "mixes the two denominators"
        assert raw - by_indices + len(groups) == 1, "right here, by cancellation"

    def test_the_derivation_agrees_with_the_direct_form(self) -> None:
        """The two routes to the same number, pinned to each other.

        `len({fold_case(n) for n in names})` is the quantity by definition; the
        derivation is the quantity from the report. They must not diverge.
        """
        for names in (
            ["admin", "admin", "Admin"],
            ["admin", "Admin", "ADMIN"],
            ["a.txt", "b.txt"],
            ["a.txt", "a.txt"],
            ["groß.txt", "gross.txt", "gross.txt", "other.txt"],
            [],
        ):
            groups = find_key_collisions(names, key="fold_case")
            direct = len({fold_case(n) for n in names})
            assert self.reduced(names, groups) == direct, names

    def test_a_duplicate_free_batch_cannot_tell_the_four_apart(self) -> None:
        """Why no existing test caught it: the trap is invisible without a repeat."""
        names = ["groß.txt", "gross.txt", "other.txt"]
        groups = find_key_collisions(names, key="fold_case")
        by_values = sum(len(g.values) for g in groups)
        by_indices = sum(len(g.indices) for g in groups)
        assert by_values == by_indices, "no repeat, so the denominators coincide"
        assert len(set(names)) == len(names)
        assert self.reduced(names, groups) == 2

    def test_one_reduced_slot_can_hold_unrelated_values(self) -> None:
        """#728, noted rather than solved: the count is slots, not meanings.

        Every key builder maps some non-empty input to the empty string, so one of the
        two identities below is the empty key holding three strings with nothing in
        common.
        """
        names = ["", "\u200b", "\u0301\u0302", "bob"]
        groups = find_key_collisions(names, key="search_key")
        assert len(groups) == 1
        assert groups[0].key == ""
        assert groups[0].values == ["", "\u200b", "\u0301\u0302"]
        assert self.reduced(names, groups) == 2
