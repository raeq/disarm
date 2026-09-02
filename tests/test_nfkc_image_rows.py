"""#833 — a row whose NFKC image has no row is unreachable from every preset.

`STEP_ORDER` runs `normalize` at position 1 and `confusables` at position 7, so every
confusable-bearing preset folds the NFKC *image* of the input, never the input. When the
image has no row of its own, the row that exists for the source can never fire:

    U+03F2 GREEK LUNATE SIGMA  -> `c` in the table
    NFKC(U+03F2)               -> U+03C2 GREEK SMALL FINAL SIGMA, no row
    llm_guardrail("ϲecure")    -> "oecure"

#245 diagnosed exactly this for U+2502 and fixed it with one literal in
`CUSTOM_LATIN_OVERRIDES`, which is why it stayed closed for the Latin target and open for
Cyrillic for six months. The generator derives the rows now, so the next class that routes
through an unmapped image is covered without an edit.
"""

from __future__ import annotations

import pytest

import disarm

#: source, name, latin target, cyrillic target. Every row #833 measured.
ROWS = [
    ("ϲ", "GREEK LUNATE SIGMA SYMBOL", "c", "с"),
    ("ℇ", "EULER CONSTANT", "E", None),
    ("\U0001d6a5", "MATHEMATICAL ITALIC SMALL DOTLESS J", "j", None),
    ("Ϲ", "GREEK CAPITAL LUNATE SIGMA SYMBOL", None, "С"),
    ("￨", "HALFWIDTH FORMS LIGHT VERTICAL", "l", "ӏ"),
]


def _nfkc(text: str) -> str:
    """disarm's NFKC, not `unicodedata`'s.

    The presets normalize with disarm's tables, and the host UCD drifts — #833 measured
    7 Cyrillic rows instead of 8 that way.
    """
    return disarm.normalize(text, form="NFKC")


@pytest.mark.parametrize(("source", "name", "latin", "_cyr"), ROWS, ids=[r[1] for r in ROWS])
def test_the_image_reaches_the_same_answer_as_the_source(
    source: str, name: str, latin: str | None, _cyr: str | None
) -> None:
    """Scope item 5: the preset result and the standalone result must agree."""
    if latin is None:
        pytest.skip(f"{name} has no Latin target")
    assert disarm.normalize_confusables(source) == latin
    assert disarm.normalize_confusables(_nfkc(source)) == latin


@pytest.mark.parametrize(("source", "name", "_lat", "cyrillic"), ROWS, ids=[r[1] for r in ROWS])
def test_the_image_reaches_the_same_answer_for_cyrillic(
    source: str, name: str, _lat: str | None, cyrillic: str | None
) -> None:
    if cyrillic is None:
        pytest.skip(f"{name} has no Cyrillic target")
    assert disarm.normalize_confusables(source, target_script="cyrillic") == cyrillic
    assert disarm.normalize_confusables(_nfkc(source), target_script="cyrillic") == cyrillic


def test_the_spoof_the_issue_opens_with() -> None:
    """`llm_guardrail("ϲecure")` returned `"oecure"`: NFKC to ς, case fold to σ, fold to o."""
    assert disarm.get_pipeline("llm_guardrail")("ϲecure") == "cecure"
    assert disarm.canonicalize("ϲecure") == "cecure"
    # The final sigma reaches the same place, which is the row that was missing.
    assert disarm.canonicalize("ςecure") == "cecure"


def test_no_row_is_left_unreachable_behind_nfkc() -> None:
    """The measurement, not a sample: #833's actionable set must be empty.

    A source whose fold answer changes under NFKC *and* whose image is left as a non-ASCII
    letter is a row no preset can reach. Sweeping rather than listing, so a future table
    refresh that reopens the class fails here.
    """
    for target in ("latin", "cyrillic"):
        unreachable = []
        for cp in range(0x110000):
            ch = chr(cp)
            alone = disarm.normalize_confusables(ch, target_script=target)
            if alone == ch:
                continue
            # Normalize once: this sweeps the whole code space twice over, and #919's
            # review measured the duplicate call as roughly doubling the cost.
            image = _nfkc(ch)
            after = disarm.normalize_confusables(image, target_script=target)
            if alone == after:
                continue
            if after == image and any(c.isalpha() and not c.isascii() for c in after):
                unreachable.append(f"U+{cp:04X}")
        assert not unreachable, f"[{target}] rows unreachable behind NFKC: {unreachable}"


def test_the_sweep_still_finds_the_defensible_divergences() -> None:
    """Guards the sweep above against passing because the fold stopped diverging at all.

    65 Latin rows still answer differently before and after NFKC. Those are the two
    defensible readings #834 documents, and they must survive — if this went to zero the
    test above would be vacuous.
    """
    divergent = sum(
        1
        for cp in range(0x110000)
        for ch in [chr(cp)]
        for alone in [disarm.normalize_confusables(ch)]
        if alone != ch and alone != disarm.normalize_confusables(_nfkc(ch))
    )
    assert divergent == 65


def test_the_cyrillic_half_of_245_is_closed() -> None:
    """#245 shipped `CUSTOM_LATIN_OVERRIDES = {0x2502: "l"}` — Latin only, by its name.

    A dict whose name says LATIN closed half a gap and no gate noticed the other half.
    """
    assert disarm.normalize_confusables("│", target_script="cyrillic") == "ӏ"
    assert disarm.normalize_confusables("￨", target_script="cyrillic") == "ӏ"


def test_the_rtl_targets_are_deliberately_untouched() -> None:
    """The derivation is Latin and Cyrillic only, and that is a decision (#848).

    For the RTL tables a source is often an Arabic *mathematical* variant whose NFKC image
    is the ordinary letter, so propagating the row would fold the base letter: `ث` would
    become `ى`, corrupting every Arabic word containing it. Asserting the base letters are
    untouched keeps that decision from being quietly reversed.
    """
    for base in ("ث", "ش", "ي"):  # THEH, SHEEN, YEH
        assert disarm.normalize_confusables(base, target_script="arabic") == base
