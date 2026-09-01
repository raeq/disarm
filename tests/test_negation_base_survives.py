"""A negation overlay may only outlive a base that itself survives (#749 follow-up).

`is_negation_of` kept `U+0338` / `U+20D2` whenever the base was `!is_alphanumeric()`,
because the 45 composed negations all sit on `Sm`/`So` and std exposes no category API.
That also admitted every base the pipeline *deletes*: the overlay was kept because it had
a base, the base was then stripped by a later step, and the orphan was removed on the next
pass.

    ml_normalize("\\u0000\\u0338")  ->  "\\u0338"  ->  ""

Found by `exhaustive_preset_idempotency` while cutting v0.15.0 — in the publish workflow,
after the same suite had passed locally on the same commit with a different draw.

141 (base, overlay) pairs were affected, and they do not share a general category:
`U+0000` (Cc), `U+0020` (Zs), `U+00A8` (Sk, which NFKC-decomposes to space + diaeresis),
`U+2017` (Po, likewise), `U+2800` (So, removed as a blank render). What they share is that
none of them survives, which is why the fix asks about survival rather than category.

Escapes, not literals: most of these bases render as nothing or as whitespace (#802).
"""

from __future__ import annotations

import unicodedata

import pytest

import disarm

OVERLAYS = ["\u0338", "\u20d2"]

#: One base per failing category from the original sweep, with why it does not survive.
NON_SURVIVING_BASES = [
    ("\u0000", "Cc", "stripped as a control"),
    ("\u0020", "Zs", "collapsed as whitespace"),
    ("\u180e", "Cf", "stripped as zero-width (Mongolian vowel separator)"),
    ("\u00a8", "Sk", "NFKC-decomposes to space + combining diaeresis"),
    ("\u2017", "Po", "NFKC-decomposes to space + combining double low line"),
    ("\u2028", "Zl", "line separator"),
    ("\u2029", "Zp", "paragraph separator"),
    ("\u2800", "So", "removed as a blank render (#643)"),
]

PRESETS = {
    "ml_normalize": disarm.ml_normalize,
    "strip_obfuscation": disarm.strip_obfuscation,
    "canonicalize": disarm.canonicalize,
    "canonicalize_strict": disarm.canonicalize_strict,
    "strip_format": disarm.strip_format,
}


@pytest.mark.parametrize(("base", "category", "why"), NON_SURVIVING_BASES, ids=lambda v: v)
@pytest.mark.parametrize("overlay", OVERLAYS, ids=lambda v: f"U+{ord(v):04X}")
def test_an_overlay_on_a_disappearing_base_is_idempotent(
    base: str, category: str, why: str, overlay: str
) -> None:
    assert unicodedata.category(base) == category
    for name, preset in PRESETS.items():
        once = preset(base + overlay)
        assert preset(once) == once, f"{name} moved again on U+{ord(base):04X} ({why}): {once!r}"


def test_the_input_the_proptest_shrank_to() -> None:
    assert disarm.ml_normalize("\u0000\u0338") == ""


@pytest.mark.parametrize("text", ["\u2260", "a \u2260 b", "\u2204", "\u2209"])
def test_a_real_negation_is_still_preserved(text: str) -> None:
    """#749's point: stripping the overlay inverts the meaning, so it must stay."""
    assert disarm.canonicalize(text) == text
    assert disarm.strip_obfuscation(text) == text


def test_a_negation_on_a_surviving_base_keeps_its_overlay() -> None:
    """The property, stated as retention rather than identity.

    `U+2ADC FORKING` canonically decomposes to `U+2ADD` + `U+0338`, so writing it with a
    second solidus is one mark repeated and #835 collapses it — correctly. Asserting the
    string is *unchanged* would therefore fail for a reason that has nothing to do with
    negation. What must hold is that the overlay is still there.
    """
    folded = disarm.canonicalize("\u2adc\u0338")
    assert "\u0338" in disarm.normalize(folded, form="NFD")
    assert disarm.canonicalize(folded) == folded


def test_strikethrough_obfuscation_is_still_removed() -> None:
    """#749's other half: on a letter the same overlay is a moderation bypass."""
    assert disarm.strip_obfuscation("H\u0338a\u0338t\u0338e\u0338") == "Hate"


def test_no_base_at_all_leaves_nothing_behind() -> None:
    for overlay in OVERLAYS:
        assert disarm.ml_normalize(overlay) == ""
