"""#815 — the negative enclosed letters fold on no surface; the positive ones do.

`ⓐ` U+24D0 and `🄰` U+1F130 fold, because NFKC decomposes them. `🅐` U+1F150 and `🅰`
U+1F170 do not, because NFKC leaves them alone and nothing else claimed them. Two
neighbouring blocks, opposite outcomes, and a "fancy text" generator offers both side by
side — so one style is neutralised and the other passes through untouched.

54 code points: NEGATIVE CIRCLED (26), NEGATIVE SQUARED (26), CROSSED NEGATIVE SQUARED
and one stray SQUARED. Derived from the UCD name, filtered to what NFKC does not already
handle, so a future block of the same shape is covered without an edit here.
"""

from __future__ import annotations

import functools
import re
import sys
import unicodedata
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "tests" / "fixtures" / "key_stability" / "corpus.txt"

#: The four that are also genuine emoji. A letter shape and a blood-type button at once.
DUAL_PURPOSE = {"\U0001f170": "A", "\U0001f171": "B", "\U0001f17e": "O", "\U0001f17f": "P"}


#: Compiled once. The sweep below runs over the whole code space, so re-compiling per
#: call was measurable on its own.
_NAME = re.compile(r".+\bLATIN (CAPITAL|SMALL) LETTER ([A-Z])")


@functools.lru_cache(maxsize=1)
def _enclosed() -> dict[str, str]:
    """Every code point the generator's rule selects, re-derived here independently.

    Cached: seven tests in this file call it, and each call walked 1.1M code points
    (#920 review). Re-derived rather than imported from `scripts/gen_confusables.py` on
    purpose — a test that reuses the generator's own function cannot catch the generator
    selecting the wrong set.

    The returned dict is shared, so callers must not mutate it. Nothing here does.
    """
    out = {}
    for cp in range(sys.maxunicode + 1):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        ch = chr(cp)
        m = _NAME.fullmatch(unicodedata.name(ch, ""))
        if not m or ch.isascii():
            continue
        if unicodedata.category(ch)[0] not in ("L", "S"):
            continue
        if unicodedata.normalize("NFKC", ch) != ch:
            continue
        out[ch] = m.group(2) if m.group(1) == "CAPITAL" else m.group(2).lower()
    return out


def test_the_set_is_the_fifty_four() -> None:
    """Anti-vacuity, and a check that the UCD has not moved the population."""
    found = _enclosed()
    assert len(found) == 54, f"expected 54, found {len(found)}: {sorted(found)}"


def test_every_one_of_them_folds() -> None:
    missing = [
        f"U+{ord(ch):05X}"
        for ch, letter in _enclosed().items()
        if disarm.canonicalize(ch) != letter
    ]
    assert not missing, f"negative enclosed letters not folding: {missing}"


def test_the_positive_counterparts_still_fold_via_nfkc() -> None:
    """The other half of the asymmetry, so a regression on either side is visible."""
    assert disarm.canonicalize("ⓐ") == "a"  # ⓐ CIRCLED LATIN SMALL LETTER A
    assert disarm.canonicalize("\U0001f130") == "A"  # 🄰 SQUARED LATIN CAPITAL LETTER A
    assert unicodedata.normalize("NFKC", "ⓐ") != "ⓐ"
    assert unicodedata.normalize("NFKC", "\U0001f150") == "\U0001f150"


def test_tags_are_stripped_not_folded() -> None:
    """Excluded from the derivation on purpose: they match the name pattern and are a
    smuggling class (#413), already handled by stripping."""
    tag = "\U000e0041"  # TAG LATIN CAPITAL LETTER A
    assert disarm.canonicalize("a" + tag + "b") == "ab"
    assert disarm.has_anomalies("a" + tag + "b")
    assert tag not in _enclosed()


def test_combining_letters_are_marks_not_substitutes() -> None:
    """Also excluded: category `Mn`, a diacritic over a base, `strip_accents`' business."""
    combining = "ͣ"  # COMBINING LATIN SMALL LETTER A
    assert unicodedata.category(combining) == "Mn"
    assert disarm.strip_accents("a" + combining) == "a"
    assert combining not in _enclosed()


@pytest.mark.parametrize(("glyph", "letter"), sorted(DUAL_PURPOSE.items()))
def test_the_dual_purpose_buttons_fold_under_canonicalize(glyph: str, letter: str) -> None:
    """`🅰` is NEGATIVE SQUARED LATIN CAPITAL LETTER A *and* the blood-type A button.

    `canonicalize` folds it, following #614: inside a comparison preset the fold wins over
    the name, or a spoof and its target stop being equal.

    `llm_guardrail` used to *name* it — demojize ran before the fold and these carry the
    Emoji property — which #918 recorded and #910 removed by turning `demojize` off for
    that profile. So the guardrail folds them too now, and `\U0001f17fAYPAL` reaches
    `paypal` instead of `p buttonaypal`.
    """
    assert disarm.canonicalize(glyph) == letter
    assert disarm.get_pipeline("llm_guardrail")(glyph) == letter.lower()


def test_the_class_is_in_the_key_stability_corpus() -> None:
    """It was not, and `catalog_key` moves for all 54 — the third time this cycle that the
    fixture stayed green through a key change because its corpus lacked the class."""
    text = CORPUS.read_text(encoding="utf-8")
    present = sum(1 for ch in _enclosed() if ch in text)
    assert present == 54, f"only {present}/54 in the corpus"


def test_a_capital_never_folds_to_a_lowercase_letter() -> None:
    """The case bug this set introduced before review caught it.

    These are category `So`, so `fix_case_mismatch` cannot tell a capital from a small
    letter and left every row lowercase — `🅰` reached `a` while its positive counterpart
    `🄰` reaches `A` through NFKC. Case now comes from the UCD name.
    """
    for glyph, letter in _enclosed().items():
        got = disarm.canonicalize(glyph)
        assert got == letter, f"U+{ord(glyph):05X} folded to {got!r}, expected {letter!r}"
        name = unicodedata.name(glyph)
        assert got.isupper() == ("CAPITAL LETTER" in name), (
            f"U+{ord(glyph):05X} is a {'capital' if 'CAPITAL' in name else 'small'} "
            f"letter by name and folded to {got!r}"
        )
