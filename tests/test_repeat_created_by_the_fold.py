"""A confusable fold can *create* a repeated mark, after the step that drops them ran.

#835 added `Step::DropRepeatedMarks` to the key builders. In `canonicalize` it sits
before the confusable fold — deliberately, so the zalgo cap counts marks a reader can
distinguish. But the fold is not order-neutral with respect to it: `U+1EF3` (y with
grave) folds to `U+00FD` (y with acute), whose NFD is `y` + acute. Put a combining acute
after it and the fold *manufactures* a duplicate that nothing downstream removes.

    canonicalize("\\u1ef3\\u0301")  ->  "\\u00fd\\u0301"   (first pass)
    canonicalize("\\u00fd\\u0301")  ->  "\\u00fd"          (second pass)

So `canonicalize` stopped being idempotent on 16 (base, mark) pairs. Before #835 it was
idempotent on all of them, because nothing dropped the repeat on either pass — the
regression is the new step running too early, not the fold.

Every existing idempotence sweep in this repository walks **single code points**. This
defect needs a base *and* a mark, so none of them could see it, which is why it reached
`main` green.
"""

from __future__ import annotations

import functools

import pytest

import disarm

#: Combining marks that compose with a Latin base in NFC. Enough to reach the class
#: without sweeping every mark in Unicode.
MARKS = [0x300, 0x301, 0x302, 0x303, 0x304, 0x306, 0x307, 0x308, 0x30A, 0x30C, 0x327, 0x328]

#: Every (base, mark) pair `canonicalize` answered differently on a second pass, measured
#: over the whole code point range. Listed rather than counted so a regression names a
#: character.
REGRESSED = [
    (0x0101, 0x0303),  # LATIN SMALL LETTER A WITH MACRON
    (0x010B, 0x0301),  # LATIN SMALL LETTER C WITH DOT ABOVE
    (0x0121, 0x0327),  # LATIN SMALL LETTER G WITH DOT ABOVE
    (0x0123, 0x0307),  # LATIN SMALL LETTER G WITH CEDILLA
    (0x012B, 0x0303),  # LATIN SMALL LETTER I WITH MACRON
    (0x014D, 0x0303),  # LATIN SMALL LETTER O WITH MACRON
    (0x016B, 0x0303),  # LATIN SMALL LETTER U WITH MACRON
    (0x017C, 0x0301),  # LATIN SMALL LETTER Z WITH DOT ABOVE
    (0x01E7, 0x0306),  # LATIN SMALL LETTER G WITH CARON
    (0x1E45, 0x0301),  # LATIN SMALL LETTER N WITH DOT ABOVE
    (0x1EA3, 0x0300),  # LATIN SMALL LETTER A WITH HOOK ABOVE
    (0x1EBD, 0x0304),  # LATIN SMALL LETTER E WITH TILDE
    (0x1ECF, 0x0300),  # LATIN SMALL LETTER O WITH HOOK ABOVE
    (0x1EE7, 0x0300),  # LATIN SMALL LETTER U WITH HOOK ABOVE
    (0x1EF3, 0x0301),  # LATIN SMALL LETTER Y WITH GRAVE
    (0x1EF7, 0x0301),  # LATIN SMALL LETTER Y WITH HOOK ABOVE
]

BUILDERS = {
    "canonicalize": disarm.canonicalize,
    "canonicalize_strict": disarm.canonicalize_strict,
    "strip_obfuscation": disarm.strip_obfuscation,
    "sort_key": lambda s: disarm.sort_key(s),
    "search_key": lambda s: disarm.search_key(s),
    "catalog_key": lambda s: disarm.catalog_key(s),
}


def test_the_reported_case() -> None:
    """The one the sweep was run from."""
    once = disarm.canonicalize("ỳ́")
    assert disarm.canonicalize(once) == once, f"canonicalize moved again: {once!r}"


@pytest.mark.parametrize(("base", "mark"), REGRESSED, ids=lambda v: f"U+{v:04X}")
def test_every_regressed_pair_is_idempotent(base: int, mark: int) -> None:
    once = disarm.canonicalize(chr(base) + chr(mark))
    assert disarm.canonicalize(once) == once


@functools.cache
def _bases_that_can_end_up_carrying_a_duplicated_mark() -> tuple[int, ...]:
    """The population that can produce this defect, derived rather than listed.

    Two routes, and the second is why the obvious derivation is not enough:

    1. The base's **confusable target** carries a mark. `U+1EF3` folds to `U+00FD`,
       whose NFD is `y` + acute, so a following acute becomes a duplicate.
    2. The **base itself** decomposes to base + mark. It can then reorder and recompose
       with the following mark into a *different* character, which folds and reintroduces
       the mark it started with. `U+0121` (g with dot above) does not fold at all — but
       `U+0121` + cedilla reorders by combining class to `g` + cedilla + dot, recomposes
       to `U+0123`, and *that* folds to `ġ` = `g` + dot. Two dots.

    A first draft of this function had only route 1. It covered 15 of the 16 pairs that
    actually regressed and would have shipped believing itself exhaustive — the property
    is about the (base, mark) *pair* after normalization, not about the base alone.

    12,469 code points. Cached: the scan walks the whole code point space and every test
    in this module wants the same answer.
    """
    at_risk = []
    for cp in range(0x110000):
        char = chr(cp)
        if any(disarm.normalize(char, form="NFD")[1:]):
            at_risk.append(cp)
            continue
        folded = disarm.normalize_confusables(char)
        if folded != char and any(disarm.normalize(folded, form="NFD")[1:]):
            at_risk.append(cp)
    return tuple(at_risk)


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_no_builder_moves_on_a_second_pass_over_the_at_risk_bases(name: str) -> None:
    """The sweep that would have caught this, over the population that can produce it.

    Deliberately not a full sweep: an exhaustive BMP version costs ~5s of a ~12s suite
    and finds exactly the same thing, because a base whose fold carries no mark cannot
    manufacture a repeat. The exhaustive version is below, marked `formal`.

    No `try`/`except` here. Nothing in `BUILDERS` raises — not even on a lone surrogate,
    checked — so a broad catch would swallow only genuine failures, which is how a sweep
    passes for the wrong reason (#751 measured that mistake first-hand).
    """
    build = BUILDERS[name]
    moved = []
    for cp in _bases_that_can_end_up_carrying_a_duplicated_mark():
        for mark in MARKS:
            text = chr(cp) + chr(mark)
            once = build(text)
            if build(once) != once:
                moved.append((hex(cp), hex(mark), once, build(once)))
    assert not moved, f"{name}: {len(moved)} pairs move on a second pass; {moved[:5]}"


def test_the_at_risk_population_covers_every_pair_that_regressed() -> None:
    """Non-vacuity, and the check the first draft of the derivation would have failed.

    A derived sweep that derives the wrong set passes for the wrong reason. Route 1 alone
    covered 15 of these 16.
    """
    at_risk = set(_bases_that_can_end_up_carrying_a_duplicated_mark())
    assert len(at_risk) > 1000, f"only {len(at_risk)} at-risk bases — has the fold changed?"
    uncovered = [(hex(b), hex(m)) for b, m in REGRESSED if b not in at_risk]
    assert not uncovered, f"the sweep cannot reach these known-bad pairs: {uncovered}"


@pytest.mark.formal
@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_no_builder_moves_on_a_second_pass_over_every_code_point(name: str) -> None:
    """The exhaustive version. Tier 3 (see CLAUDE.md), because it is slow, not optional.

    The default-tier sweep above is over the *derived* at-risk population, which is
    faster and, on the argument in that function, complete. This one assumes nothing
    about the derivation and is what would catch a third route into the class.

    No `try`/`except`: nothing in `BUILDERS` raises, not even on a lone surrogate, so a
    catch here would swallow only genuine failures (#881 review).
    """
    build = BUILDERS[name]
    moved = []
    for cp in range(0x110000):
        for mark in MARKS:
            text = chr(cp) + chr(mark)
            once = build(text)
            if build(once) != once:
                moved.append((hex(cp), hex(mark), once, build(once)))
    assert not moved, f"{name}: {len(moved)} pairs move on a second pass; {moved[:5]}"
