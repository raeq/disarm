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

import functools

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

    No `try`/`except`. An earlier draft caught `Exception` and continued, on the theory
    that surrogates need skipping — they do not: every profile accepts a lone surrogate
    without raising, checked. So the catch could only ever have swallowed a genuine
    failure and let the sweep pass for the wrong reason (#880 review).
    """
    pipeline = disarm.get_pipeline(name)
    moved = []
    for cp in range(0x110000):
        char = chr(cp)
        once = pipeline(char)
        twice = pipeline(once)
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


# ---------------------------------------------------------------------------
# #886 — the sweep above walks single code points, and this class needs a pair
# ---------------------------------------------------------------------------

#: Combining marks that compose with a Latin base under NFC.
MARKS = [0x300, 0x301, 0x302, 0x303, 0x304, 0x306, 0x307, 0x308, 0x30A, 0x30C, 0x327, 0x328]


@functools.cache
def _bases_that_can_move_under_a_fold() -> tuple[int, ...]:
    """Bases whose fold, or whose own decomposition, can leave a mark uncomposed.

    The same derivation `tests/test_repeat_created_by_the_fold.py` uses, and for the same
    reason: sweeping every code point against every mark costs seconds per profile and
    finds nothing the derived population misses.
    """
    at_risk = []
    for cp in range(0x110000):
        char = chr(cp)
        if any(disarm.normalize(char, form="NFD")[1:]):
            at_risk.append(cp)
            continue
        folded = disarm.normalize_confusables(char)
        if folded != char:
            at_risk.append(cp)
    return tuple(at_risk)


@pytest.mark.parametrize("name", disarm.list_profiles())
def test_the_profile_is_a_fixed_point_over_base_and_mark_pairs(name: str) -> None:
    """`normalize_web_input` was not, on 6,410 pairs (#886).

    The single-code-point sweep above passed throughout, because the defect needs a base
    *and* a mark: the confusable fold emits a decomposed base, and nothing composed it
    until the next call. That is the same blind spot that let #835's regression reach
    `main` — closed for the key builders in #881, and this closes it for the profiles.
    """
    pipeline = disarm.get_pipeline(name)
    moved = []
    for cp in _bases_that_can_move_under_a_fold():
        for mark in MARKS:
            once = pipeline(chr(cp) + chr(mark))
            if pipeline(once) != once:
                moved.append((hex(cp), hex(mark), once, pipeline(once)))
    assert not moved, f"{name}: {len(moved)} pairs move on a second pass; {moved[:5]}"


def test_the_reported_pairs_are_stable() -> None:
    """The three worked cases from the issue, named so a regression names a character."""
    pipeline = disarm.get_pipeline("normalize_web_input")
    for base, mark in [(0x007C, 0x0301), (0x0430, 0x0301), (0x00E7, 0x0327)]:
        once = pipeline(chr(base) + chr(mark))
        assert pipeline(once) == once, f"U+{base:04X}+U+{mark:04X} moved again: {once!r}"
    # And the shape that motivated it: a spoofed `cafe` built from Cyrillic e.
    spoof = "caf" + chr(0x0435) + chr(0x0301)
    once = pipeline(spoof)
    assert pipeline(once) == once
    assert once == "café"


def test_a_pipeline_without_normalization_still_folds_once() -> None:
    """The fixed point is gated on a form being configured.

    With nothing to normalize toward there is no composed form to converge on, and a
    caller who asked for `confusables` alone gets the single pass they asked for.
    """
    single = disarm.TextPipeline(confusables=True)
    assert [n for n, _ in single.steps] == ["confusables"]
    assert single("\u0430pple") == "apple"
