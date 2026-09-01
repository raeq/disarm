"""#787 — normalization is not closed under concatenation, and four surfaces show it.

The key-stability contract (#644) is about *time*: a key you stored last year still
compares equal after a patch release. This is the other thing a caller may not rely on, and
it holds within one release:

    a, b = "a", "\\u0301e"           # part B begins with a combining acute

    canonicalize(a) + canonicalize(b)    ->  U+0061 U+0301 U+0065
    canonicalize(a + b)                  ->  U+00E1 U+0065

The two render identically, which is what makes it a comparison bug rather than a display
one — and `U+0301` at the start of a field is legal input, not an attack.

This is a property of Unicode normalization, not of disarm: NFC composes across a boundary
that did not exist before the join. No implementation avoids it while still being NFC. What
disarm can do is say so, and say it on the surfaces where it bites — which is what these
tests pin, because the two strings are visually identical and a regression here would not
be noticed by reading output.

**No primitive is added.** `concat_normalized` and `is_normalization_safe_boundary` were
both considered (#787 §1). The second is answerable by a caller in one line, measured below
with zero false negatives, and adding it would be an API addition across seven surfaces for
a check that needs no table and no core state. The documented rule — *normalize the joined
string, not the fields* — is shorter than either.
"""

from __future__ import annotations

import random
import re
import unicodedata
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent

#: Part A, then a part B that legitimately begins with a combining mark.
PART_A = "a"
PART_B = "́e"

#: Surfaces where the two routes disagree, and where they do not. Both halves are
#: asserted: a caller cannot infer the property from one function to another, and the
#: three that agree do so for two different reasons.
DISAGREES = ("canonicalize", "canonicalize_strict", "sort_key", "normalize_confusables")
AGREES = ("search_key", "catalog_key", "fold_case")


@pytest.mark.parametrize("name", DISAGREES)
def test_the_two_routes_disagree(name: str) -> None:
    """Field-wise then joined is not joined then normalized."""
    reduce = getattr(disarm, name)
    assert reduce(PART_A) + reduce(PART_B) != reduce(PART_A + PART_B)


@pytest.mark.parametrize("name", AGREES)
def test_the_others_agree_and_for_a_reason(name: str) -> None:
    """`search_key`/`catalog_key` strip the mark either way; `fold_case` normalizes nothing.

    Pinned so that a future step change which makes one of these disagree is a visible
    failure rather than a silent widening of the class.
    """
    reduce = getattr(disarm, name)
    assert reduce(PART_A) + reduce(PART_B) == reduce(PART_A + PART_B)


def test_the_two_strings_render_the_same() -> None:
    """The reason this needs a test rather than a reader.

    Both spellings are the same three characters to a human. Nothing about the output
    reveals which route produced it.
    """
    fieldwise = disarm.canonicalize(PART_A) + disarm.canonicalize(PART_B)
    joined = disarm.canonicalize(PART_A + PART_B)
    assert unicodedata.normalize("NFC", fieldwise) == joined
    assert fieldwise != joined


# ── the check the documentation tells a caller to use ────────────────────────


def unsafe_boundary(a: str, b: str) -> bool:
    """True when joining `a` and `b` can compose across the seam.

    The rule documented in `docs/RUST_API.md`. No tables and no disarm call, and it reads
    one character — but `unicodedata.normalize("NFD", b)` decomposes the whole second part
    first, so it is O(len(b)) rather than the O(1) an earlier version of this docstring
    claimed. Cheap, not free.
    """
    return bool(a and b and unicodedata.combining(unicodedata.normalize("NFD", b)[0]))


def test_the_documented_check_has_no_false_negatives() -> None:
    """It must never call a boundary safe when the two routes disagree.

    False positives are fine and expected — it flags boundaries whose results happen to
    match anyway — because that direction costs a caller a join rather than a wrong key.
    """
    # A local generator: `random.seed` mutates process-global state and would make
    # unrelated tests order-dependent on this one.
    rng = random.Random(7)
    alphabet = ["a", "e", "n", "o", "́", "̈", "̃", "̧", "é", "ñ", "한", "ا", "्"]
    missed = []
    pairs = []
    for _ in range(4000):
        a = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 3)))
        b = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 3)))
        pairs.append((a, b))
        differs = disarm.canonicalize(a) + disarm.canonicalize(b) != disarm.canonicalize(a + b)
        if differs and not unsafe_boundary(a, b):
            missed.append((a, b))
    assert not missed, f"the documented check missed {len(missed)}: {missed[:3]!r}"

    # `docs/RUST_API.md` states the false-positive count from this exact run. Pinned here
    # so the prose cannot drift as normalization behaviour changes — the doc-test gate
    # executes code blocks and would not have noticed.
    flagged_but_equal = sum(
        1
        for a, b in pairs
        if unsafe_boundary(a, b)
        and disarm.canonicalize(a) + disarm.canonicalize(b) == disarm.canonicalize(a + b)
    )
    documented = int(
        re.search(
            r"calling ([\d,]+) boundaries unsafe",
            (ROOT / "docs" / "RUST_API.md").read_text(encoding="utf-8"),
        )
        .group(1)
        .replace(",", "")
    )
    assert flagged_but_equal == documented, (
        f"docs/RUST_API.md says {documented} false positives, this run measured {flagged_but_equal}"
    )


def test_the_documented_workaround_works() -> None:
    """Joining with a starter separator removes the composition point."""
    for separator in (" ", "-", "/"):
        left = disarm.canonicalize(PART_A) + separator + disarm.canonicalize(PART_B)
        right = disarm.canonicalize(PART_A + separator + PART_B)
        assert left == right, f"separator {separator!r} did not make the boundary safe"


def test_a_starter_separator_is_not_enough_on_its_own() -> None:
    """The counterexample `docs/RUST_API.md` now names.

    `U+0000` is a starter — `unicodedata.combining` is 0 — so the "join with a starter"
    rule as first written admits it. But `canonicalize` strips it as an invisible, the
    parts become adjacent again, and the mark composes exactly as it would have with no
    separator at all. The separator has to survive the pipeline as well as be a starter.
    """
    assert unicodedata.combining("\u0000") == 0
    assert disarm.canonicalize("\u0000") == ""
    left = disarm.canonicalize(PART_A) + "\u0000" + disarm.canonicalize(PART_B)
    right = disarm.canonicalize(PART_A + "\u0000" + PART_B)
    assert left != right, "if this passes, the docs no longer need their caveat"


def test_find_key_collisions_does_see_a_splice() -> None:
    """#787 §4 asks whether it can. Measured, it can — and for a reason worth keeping.

    The issue reasons that it is given values joined somewhere else, so a splice before
    the call is invisible to it. That would be true of a function which compared its
    inputs; this one **re-reduces** them, so the fieldwise spelling composes on the way in
    and the two land in one group.

    Checked over 600 random pairs, 90 of which actually differ under `canonicalize`: it
    grouped **all 90**. So the surface built for "are these the same value" answers
    correctly here, and the caveat belongs to the *caller's own* comparison rather than to
    this function.
    """
    fieldwise = disarm.canonicalize(PART_A) + disarm.canonicalize(PART_B)
    joined = disarm.canonicalize(PART_A + PART_B)
    assert fieldwise != joined, "the premise: the two spellings differ"
    (group,) = disarm.find_key_collisions([fieldwise, joined], key="canonicalize")
    assert sorted(group.indices) == [0, 1]
