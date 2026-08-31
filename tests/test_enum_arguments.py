"""Every surface that documents an enum must accept that enum (#767).

`NF`, `Script` and `Component` are plain `enum.Enum`, not `str` subclasses, so passing a
member to a PyO3-backed function raised `TypeError: 'NF' object is not an instance of
'str'`. Two of the twelve surfaces coerced the member to its `.value` with a one-liner;
the other ten did not, and those two were exactly the two that worked.

`Script` needed more than the one-liner. It has two spellings in this API and they are
not interchangeable: `script_info` takes `"Latin"` and rejects `"latin"`, while the
confusable surfaces take `"latin"` and reject `"Latin"`. Coercing to `.value` alone still
fails at six of them.
"""

from __future__ import annotations

import pytest

import disarm
from disarm import NF, Component, Script

#: (label, callable taking one value, the enum member, its accepted string spelling).
#: The string column is what the surface accepted *before* this change and must keep
#: accepting — the fix adds a spelling, it does not move one.
SURFACES = [
    ("normalize", lambda v: disarm.normalize("ﬁ", form=v), NF.KC, "NFKC"),
    ("is_normalized", lambda v: disarm.is_normalized("fi", form=v), NF.KC, "NFKC"),
    ("Text.normalize", lambda v: disarm.Text("ﬁ").normalize(form=v), NF.KC, "NFKC"),
    ("is_confusable", lambda v: disarm.is_confusable("a", target_script=v), Script.LATIN, "latin"),
    (
        "normalize_confusables",
        lambda v: disarm.normalize_confusables("a", target_script=v),
        Script.LATIN,
        "latin",
    ),
    (
        "Text.normalize_confusables",
        lambda v: disarm.Text("a").normalize_confusables(target_script=v),
        Script.LATIN,
        "latin",
    ),
    (
        "Text.is_confusable",
        lambda v: disarm.Text("a").is_confusable(target_script=v),
        Script.LATIN,
        "latin",
    ),
    (
        "unmapped_confusables",
        lambda v: disarm.unmapped_confusables(target_script=v),
        Script.CYRILLIC,
        "cyrillic",
    ),
    (
        "find_unmapped_confusables",
        lambda v: disarm.find_unmapped_confusables("a", target_script=v),
        Script.LATIN,
        "latin",
    ),
    ("script_info", lambda v: disarm.script_info(v), Script.LATIN, "Latin"),
    (
        "percent_encode",
        lambda v: disarm.percent_encode("a", component=v),
        Component.QUERY,
        "query",
    ),
]


@pytest.mark.parametrize(("label", "call", "member", "_text"), SURFACES, ids=lambda x: x)
def test_surface_accepts_its_own_enum(label, call, member, _text) -> None:
    call(member)  # raised TypeError at ten of these before #767


@pytest.mark.parametrize(("label", "call", "member", "text"), SURFACES, ids=lambda x: x)
def test_member_and_string_agree(label, call, member, text) -> None:
    """Same answer either way. A coercion that silently changed the result would be a
    worse defect than the rejection it replaced."""
    assert call(member) == call(text)


def test_the_two_script_spellings_stay_distinct() -> None:
    """The fix adds a spelling; it must not repair a wrong one.

    `"Latin"` is invalid at the confusable surfaces and `"latin"` is invalid at
    `script_info`. Only an enum *member* is translated, so a caller who hard-coded the
    wrong string still finds out.
    """
    with pytest.raises(disarm.InvalidArgumentError):
        disarm.is_confusable("a", target_script="Latin")
    with pytest.raises(KeyError):
        disarm.script_info("latin")


def test_enums_are_not_str_subclasses() -> None:
    """Subclassing `str` was the rejected fix. It would make `Script.LATIN == "Latin"`
    true and silently change the meaning of equality and `in` tests callers have written.
    """
    for member in (NF.KC, Script.LATIN, Component.QUERY):
        assert not isinstance(member, str)
        assert member != member.value
