"""#852 — `llm_guardrail` folded case after the confusable fold.

A cased letter whose *folded* form is in the confusable table and whose original is not
folded only on a second call: `Þ` has no entry, case-folds to `þ`, and only then folds to
`p`. Measured over the BMP, **126** code points behaved that way.

The fix is a second confusable pass after the case fold, not a fold before it. Folding
first would also close the class and is the wrong trade — see
`test_pre_folding_would_lose_the_uppercase_mapping` below.
"""

from __future__ import annotations

import pytest

import disarm

BMP = [chr(cp) for cp in range(0x20, 0x10000) if not 0xD800 <= cp <= 0xDFFF]


def guardrail():
    return disarm.get_pipeline("llm_guardrail")


@pytest.mark.parametrize(
    ("text", "expected", "why"),
    [
        ("Þ", "p", "THORN: no entry, folds to þ, which folds to p"),
        ("Ŋ", "n", "ENG"),
        ("Ɓ", "b", "B WITH HOOK"),
    ],
)
def test_a_cased_letter_folds_in_one_pass(text: str, expected: str, why: str) -> None:
    assert guardrail()(text) == expected, why


def test_the_profile_is_far_closer_to_a_fixed_point() -> None:
    """126 before, a small documented residue after.

    A ceiling rather than zero: the residue is a real and separate problem, and pinning
    it at zero would fail the day someone fixes something adjacent. What must not happen
    is a return to the old order.
    """
    pipe = guardrail()
    unstable = [c for c in BMP if pipe(c) != pipe(pipe(c))]
    assert len(unstable) <= 12, (
        f"{len(unstable)} code points still need a second call; it was 126 before #852 "
        f"and 10 after. First few: {[hex(ord(c)) for c in unstable[:5]]}"
    )


def test_the_residue_is_the_cherokee_class_and_needs_iteration() -> None:
    """What is left, named so it is a known quantity rather than an unexplained number.

    Cherokee small letters fold to an *uppercase* Latin letter, so the pair
    (confusables, fold_case) has to run more than twice. Two more passes converge, which
    means the structure this needs is a fixed-point loop — what the presets use — rather
    than another fixed pass.
    """
    pipe = guardrail()
    unstable = [c for c in BMP if pipe(c) != pipe(pipe(c))]
    import unicodedata

    non_cherokee = [
        f"U+{ord(c):04X} {unicodedata.name(c, '?')}"
        for c in unstable
        if "CHEROKEE" not in unicodedata.name(c, "")
    ]
    assert not non_cherokee, f"the residue has grown beyond the known class: {non_cherokee}"

    for char in unstable[:3]:
        current = char
        for _ in range(6):
            nxt = disarm.fold_case(disarm.normalize_confusables(current))
            if nxt == current:
                break
            current = nxt
        else:
            pytest.fail(f"U+{ord(char):04X} does not converge, so a loop would not close it")


def test_pre_folding_would_lose_the_uppercase_mapping() -> None:
    """Why the fix is a second fold pass and not a fold placed first.

    73 cased code points fold to a *different* target than their case pair. Case folding
    before the confusable fold would reach the lowercase entry and lose the uppercase one
    outright, where the current order reaches it one pass later.
    """
    divergent = []
    for cp in range(0x20, 0x10000):
        upper = chr(cp)
        lower = upper.lower()
        if lower == upper:
            continue
        folded_upper = disarm.normalize_confusables(upper)
        folded_lower = disarm.normalize_confusables(lower)
        if folded_upper != upper and folded_upper.lower() != folded_lower.lower():
            divergent.append(upper)

    assert len(divergent) > 50, (
        f"only {len(divergent)} case pairs fold differently; if this collapsed, "
        "pre-folding may now be the simpler fix and this reasoning needs revisiting"
    )
    # The clearest example, and the one a lock caught: uppercase eta looks like `H`,
    # lowercase eta looks like `n`.
    assert disarm.normalize_confusables("Η") == "H"
    assert disarm.normalize_confusables("η") == "n"
    assert disarm.TextPipeline(confusables=True, fold_case=True)("Ηello") == "hello"


def test_only_the_profile_with_both_steps_changed() -> None:
    """The second pass is added only where a case fold precedes a confusable fold.

    A pipeline without `confusables` must not gain a step, or `explain()` would describe
    a mechanism it does not run.
    """
    assert [name for name, _ in disarm.TextPipeline(fold_case=True).steps] == ["fold_case"]
    assert [name for name, _ in disarm.TextPipeline(confusables=True).steps] == ["confusables"]
    assert [name for name, _ in disarm.TextPipeline(confusables=True, fold_case=True).steps] == [
        "confusables",
        "fold_case",
        "confusables",
    ]
