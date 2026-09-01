"""The confusable fold is not order-independent, and the docs must say the true number.

#834. `normalize_confusables` folds the TR39 table against the input as written. Every
preset and profile that folds confusables normalizes to NFKC first, so the fold there
sees a decomposed image — and the two paths disagree on 68 code points for the Latin
target and 8 for Cyrillic.

Both verdicts are defensible and disarm ships both. What it was missing is anyone saying
so, which is why these tests are about *documentation* as much as behaviour: the counts
and the worked examples are pinned to the pages that state them, so the prose cannot go
stale the way it did.
"""

from __future__ import annotations

import functools
import re
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "docs" / "user-guide" / "confusables.md"
LIMITATIONS = ROOT / "docs" / "limitations.md"


@functools.cache
def _divergent(target: str) -> tuple[int, ...]:
    """Code points the standalone fold and the NFKC-first fold answer differently.

    Uses `disarm.normalize` rather than `unicodedata.normalize`: the runtime's Unicode
    version trails the library's, and a census that normalizes with the wrong one gets a
    different count for a reason that has nothing to do with the question.

    Cached: the scan walks the whole code point space and four tests in this module want
    the same two answers (#879 review).

    No surrogate skip and no `try`/`except`. Neither `normalize_confusables` nor
    `normalize` raises on a lone surrogate — checked, both accept one and return it — so
    a guard here would be guarding against nothing, and a broad catch would swallow a
    genuine failure instead.
    """
    out = []
    for cp in range(0x110000):
        ch = chr(cp)
        alone = disarm.normalize_confusables(ch, target_script=target)
        if alone == ch:
            continue
        if alone != disarm.normalize_confusables(
            disarm.normalize(ch, form="NFKC"), target_script=target
        ):
            out.append(cp)
    return tuple(out)


@pytest.mark.parametrize(("target", "expected"), [("latin", 68), ("cyrillic", 8)])
def test_the_documented_count_is_the_measured_count(target: str, expected: int) -> None:
    assert len(_divergent(target)) == expected


@pytest.mark.parametrize(
    ("char", "standalone", "after_nfkc"),
    [
        ("ſ", "f", "s"),  # LATIN SMALL LETTER LONG S — TR39 says f, NFKC says s
        ("⑴", "(l)", "(1)"),  # PARENTHESIZED DIGIT ONE
        ("⒈", "l.", "1."),  # DIGIT ONE FULL STOP
        ("ⅿ", "rn", "m"),  # SMALL ROMAN NUMERAL ONE THOUSAND
    ],
)
def test_the_worked_examples_still_diverge(char: str, standalone: str, after_nfkc: str) -> None:
    assert disarm.normalize_confusables(char) == standalone
    assert disarm.normalize_confusables(disarm.normalize(char, form="NFKC")) == after_nfkc
    assert disarm.canonicalize(char) == after_nfkc


def test_the_standalone_fold_is_not_a_canonical_skeleton() -> None:
    """The consequence a caller building keys actually meets.

    The table has only three ASCII sources (#725), so ASCII `(1)` passes through while
    `⑴` folds to `(l)`. Two strings a reader cannot tell apart get *different* keys from
    the standalone call and the *same* key from any preset.
    """
    assert disarm.normalize_confusables("⑴") != disarm.normalize_confusables("(1)")
    assert disarm.canonicalize("⑴") == disarm.canonicalize("(1)")


@pytest.mark.parametrize("page", [GUIDE, LIMITATIONS], ids=lambda p: p.name)
def test_the_pages_state_the_measured_count(page: Path) -> None:
    """Anchored to the count, not to the phrasing (#806).

    A gate keyed on a sentence passes as soon as someone rewrites the sentence. This asks
    only that the number the page commits to is the number the library produces.
    """
    text = page.read_text(encoding="utf-8")
    counts = {int(n) for n in re.findall(r"\b(\d{2,3})\b", text)}
    assert len(_divergent("latin")) in counts, f"{page.name} does not state the Latin count"


def test_the_buckets_add_up() -> None:
    """The four-class table on both pages: 30 + 14 + 15 + 9.

    Split by what NFKC does to the source, not by Unicode block, because that is the
    distinction the tables are making: whether decomposing first helps or hurts.
    """
    assert 30 + 14 + 15 + 9 == len(_divergent("latin"))
