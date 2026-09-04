"""Two spellings of a script, and the member that bridges them (#884, #767).

`list_scripts()` returns `"Arabic"`; the confusable surfaces take `"arabic"`; `script_info`
takes `"Arabic"`. #884 reads that as a defect — the obvious loop over `list_scripts()`
raises on every script, including the four that are supported.

It is half a defect. #767 decided the bridge deliberately: an enum **member** is translated
at every surface, so `unmapped_confusables(target_script=Script.ARABIC)` works and
`script_info(Script.LATIN)` works, while a raw string stays strict at each so a caller who
hard-codes the wrong one finds out. `Script("Arabic")` converts a name from
`list_scripts()`, which is the loop written correctly.

What remains of #884 is not a spelling problem at all: four target tables against 61
identifiable scripts. That is #963.
"""

from __future__ import annotations

import pytest

import disarm
from disarm import Script

#: The four disarm ships a fold table for, as `list_scripts()` spells them.
SUPPORTED = ["Latin", "Cyrillic", "Arabic", "Hebrew"]


def _accepts(value: object) -> bool:
    """Whether the census takes this target script.

    Only `InvalidArgumentError` counts as a rejection: that is the documented contract for
    an unsupported `target_script`, and catching more would let an unrelated failure read
    as a normal refusal.
    """
    try:
        disarm.unmapped_confusables(target_script=value)
    except disarm.InvalidArgumentError:
        return False
    return True


@pytest.mark.parametrize("name", SUPPORTED)
def test_the_member_bridges_both_spellings(name: str) -> None:
    """The loop, written the way #767 intended it."""
    member = Script(name)
    assert _accepts(member)
    assert disarm.script_info(member)["name"] == name


@pytest.mark.parametrize("name", SUPPORTED)
def test_the_member_and_the_lowercase_token_agree(name: str) -> None:
    """A bridge that changed the answer would be worse than the rejection it replaced."""
    assert disarm.unmapped_confusables(target_script=Script(name)) == disarm.unmapped_confusables(
        target_script=name.lower()
    )


def test_a_raw_string_stays_strict_at_each_surface() -> None:
    """#767's decision, pinned here too: the member is translated, a wrong string is not."""
    with pytest.raises(disarm.InvalidArgumentError):
        disarm.is_confusable("a", target_script="Latin")
    with pytest.raises(KeyError):
        disarm.script_info("latin")


def test_the_documented_loop_reaches_every_supported_script() -> None:
    reached = [s for s in disarm.list_scripts() if _accepts(Script(s))]
    assert sorted(reached) == sorted(SUPPORTED), reached


def test_a_script_with_no_table_is_refused_even_as_a_member() -> None:
    """The bridge is about spelling, not about tables disarm does not have."""
    assert not _accepts(Script("Greek"))
    with pytest.raises(disarm.InvalidArgumentError, match="greek"):
        disarm.unmapped_confusables(target_script="greek")


def test_four_tables_against_the_scripts_disarm_knows() -> None:
    """What is left of #884 once the spelling question is answered — see #963."""
    assert len(SUPPORTED) == 4
    assert len(disarm.list_scripts()) > 50
