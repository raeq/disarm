"""#815 — small capitals are TR39 destinations, so nothing folded them as sources.

`ASCII_FOLD` resolves a small capital when it is a row's *target*, which is why `ᴍ`
folded: TR39 happens to list U+1D0D as a source as well (`1D0D ; 028D`). `ᴀ` is listed
only as a destination, so no row existed and a word written in small capitals
half-converted — matching neither the attack nor the target, and handed to a model in
that state by `llm_guardrail`.

The half-conversion is the damage, not the miss. A clean miss leaves text a downstream
filter can still read; `'cᴀn you unᴅersᴛᴀnᴅ me'` is readable to a model and matches no
denylist entry.
"""

from __future__ import annotations

import sys
import unicodedata

import pytest

import disarm

#: The seven single-letter Latin small capitals an English word actually needs.
#: Written as escapes, not literals: at small sizes `ᴀ` and `a` are hard to tell apart
#: in a diff, which is the whole point of the class.
NEW_FOLDS = {
    "\u1d00": "a",  # ᴀ LATIN LETTER SMALL CAPITAL A
    "\u1d05": "d",  # ᴅ LATIN LETTER SMALL CAPITAL D
    "\u1d0a": "j",  # ᴊ LATIN LETTER SMALL CAPITAL J
    "\u1d18": "p",  # ᴘ LATIN LETTER SMALL CAPITAL P
    "\u1d1b": "t",  # ᴛ LATIN LETTER SMALL CAPITAL T
    "\ua730": "f",  # ꜰ LATIN LETTER SMALL CAPITAL F
    "\ua7af": "q",  # ꞯ LATIN LETTER SMALL CAPITAL Q
}


@pytest.mark.parametrize(("glyph", "letter"), sorted(NEW_FOLDS.items()))
def test_each_small_capital_folds_to_its_letter(glyph: str, letter: str) -> None:
    assert disarm.canonicalize(glyph) == letter
    assert disarm.normalize_confusables(glyph) == letter


def test_the_worked_example_fully_converts() -> None:
    """It used to come back `'cᴀn you unᴅersᴛᴀnᴅ me'` — neither the attack nor the target."""
    assert disarm.canonicalize("ᴄᴀɴ ʏᴏᴜ") == "can you"


def test_a_prompt_injection_in_small_capitals_reaches_the_model_readable() -> None:
    """`llm_guardrail` must hand on text a downstream filter can match, not a mangling."""
    attack = "ɪɢɴᴏʀᴇ ᴀʟʟ ᴘʀᴇᴠɪᴏᴜꜱ"
    assert disarm.get_pipeline("llm_guardrail")(attack) == "ignore all previous"


def test_every_single_letter_latin_small_capital_folds() -> None:
    """Derived, so a future UCD that adds one is covered without editing NEW_FOLDS."""
    missing = []
    for cp in range(sys.maxunicode + 1):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        name = unicodedata.name(chr(cp), "")
        prefix = "LATIN LETTER SMALL CAPITAL "
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix) :]
        if len(rest) == 1 and "A" <= rest <= "Z":
            if disarm.canonicalize(chr(cp)) != rest.lower():
                missing.append(f"U+{cp:04X} {name}")
    assert not missing, f"single-letter small capitals not folding: {missing}"


def test_the_derived_sweep_is_pointed_at_something() -> None:
    """A name prefix that matched nothing would make the test above vacuous.

    Three known code points rather than a second sweep of the codespace (#915 review):
    the prefix either matches or it does not, and re-walking 1.1M names to learn that
    duplicates the sweep above at real cost.
    """
    prefix = "LATIN LETTER SMALL CAPITAL "
    for cp in (0x1D00, 0x1D1B, 0xA730):
        assert unicodedata.name(chr(cp), "").startswith(prefix), (
            f"U+{cp:04X} no longer matches {prefix!r}; the derived sweep above is vacuous"
        )


def test_multi_letter_small_capitals_are_left_alone() -> None:
    """The other half: `ᴁ` is a digraph, not a letter-for-letter identity.

    Folding it would be a visual judgment, which is the open policy question in #815
    rather than something this change decides.
    """
    # All three the docstring names, not two of them (#915 review).
    for glyph in ("\u1d01", "\u1d03", "\u1d06"):  # ᴁ AE, ᴃ BARRED B, ᴆ ETH
        assert disarm.canonicalize(glyph) == glyph


def test_the_class_is_in_the_key_stability_corpus() -> None:
    """It was not, which is why a `catalog_key` change kept the fixture green (#815).

    22,977 rows and zero small capitals. The gate could not have caught this.
    """
    from pathlib import Path

    corpus = Path(__file__).resolve().parent / "fixtures" / "key_stability" / "corpus.txt"
    text = corpus.read_text(encoding="utf-8")
    present = sum(1 for g in NEW_FOLDS if g in text)
    assert present == len(NEW_FOLDS), f"only {present}/{len(NEW_FOLDS)} in the corpus"
