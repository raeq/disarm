"""Every named profile must be a fixed point (#751).

#723 measured this over `PRESETS` and found `strip_obfuscation` was not one. #751 asked
the same question of `get_pipeline`, which #723's sweep never reached, and found three of
seven profiles failing. The profiles were fixed one class at a time — #852 (a cased letter
reaching the table only through its folded form), #853 (the CLDR non-emoji rows) — and this
is the last of them.

The remaining class was the mirror of #852's. That change added a confusable pass *after*
the case fold, so a letter whose folded form is in the table gets folded. But the fold's
**target** can be uppercase, and nothing case-folded after it: ten Cherokee small letters
fold to a capital Latin letter, so `llm_guardrail("\\u13f8")` was `"B"` on the first pass
and `"b"` on the second.

The sweep is over the whole code point range rather than a sample, because that is what
found the ten: they are scattered across three blocks and no hand-written list would have
included `U+ABB7`.
"""

from __future__ import annotations

import pytest

import disarm

#: The ten that failed, with the capital each folds to. Named individually so a
#: regression names a character rather than a count.
CHEROKEE_TO_CAPITAL = [
    ("ᏸ", "b"),
    ("ᏺ", "h"),
    ("ꭸ", "h"),
    ("ꭹ", "y"),
    ("ꮍ", "y"),
    ("ꮏ", "t"),
    ("ꮒ", "h"),
    ("ꮤ", "w"),
    ("ꮥ", "s"),
    ("ꮷ", "d"),
]


@pytest.mark.parametrize("name", disarm.list_profiles())
def test_the_profile_is_a_fixed_point_over_every_code_point(name: str) -> None:
    """One pass and two passes must agree, for every code point that exists.

    A profile that is not a fixed point is a profile whose output depends on how many
    times you called it, which makes it unusable for a key.
    """
    pipeline = disarm.get_pipeline(name)
    moved = []
    for cp in range(0x110000):
        char = chr(cp)
        try:
            once = pipeline(char)
            twice = pipeline(once)
        except Exception:  # noqa: BLE001 - surrogates and the like are not the subject
            continue
        if once != twice:
            moved.append((hex(cp), once, twice))
    assert not moved, f"{name}: {len(moved)} code points move on a second pass; {moved[:5]}"


@pytest.mark.parametrize(("char", "expected"), CHEROKEE_TO_CAPITAL, ids=lambda v: v)
def test_a_confusable_target_that_is_uppercase_is_folded(char: str, expected: str) -> None:
    """The specific class, in one pass.

    Each of these folds to a **capital** Latin letter. Before #751 the guardrail returned
    that capital, so the value it gave you differed from the value it gave itself.
    """
    guardrail = disarm.get_pipeline("llm_guardrail")
    assert guardrail(char) == expected


def test_the_second_case_fold_is_only_added_where_it_can_do_something() -> None:
    """It is gated exactly as #852's second confusable pass is.

    Without `confusables` there is no second fold to close, and a step that cannot act
    would make `explain()` describe a mechanism the pipeline does not run.
    """
    assert [n for n, _ in disarm.TextPipeline(fold_case=True).steps] == ["fold_case"]
    assert [n for n, _ in disarm.TextPipeline(confusables=True).steps] == ["confusables"]
    assert [n for n, _ in disarm.TextPipeline(confusables=True, fold_case=True).steps] == [
        "confusables",
        "fold_case",
        "confusables",
        "fold_case",
    ]
