r"""#698 — the four properties that make `strip_format` un-composable, as assertions.

Prose in six binding doc comments claimed `strip_format` *removes* the private-use area
and the presentation variation selectors and *leaves* TAB/LF alone. Every one of those is
backwards. It was written from a summary rather than from `src/presets.rs`, it read
plausibly, and nothing checked it, because the claim had no executable referent anywhere
in the suite — the docs asserted a behaviour and the tests asserted a different one.

That is what this file is: the referent. `RENDERING_STRIP` sets `strip_pua: false` and
`keep_presentation_vs: true`, and the step list ends in `CollapseWs`, so the preset is
*less* destructive than a naive chain of the universal primitives where rendering matters
and *more* destructive with whitespace. The contrast against the chain is asserted
alongside, because "not composable" is the actual claim and a property that only holds for
one of the two is not evidence for it.
"""

from __future__ import annotations

import pytest

import disarm

PUA = ""  # PRIVATE USE AREA — an icon-font glyph
VS16 = "️"  # VARIATION SELECTOR-16, emoji presentation
VS15 = "︎"  # VARIATION SELECTOR-15, text presentation


def test_the_private_use_area_survives() -> None:
    """Icon fonts live here (#413). The naive chain deletes them; the preset does not."""
    assert disarm.strip_format(f"a{PUA}b") == f"a{PUA}b"
    assert disarm.strip_pua(f"a{PUA}b") == "ab"


def test_the_presentation_selectors_survive_after_a_base() -> None:
    """`strip_variation_selectors` removes them unconditionally; the preset keeps them."""
    for selector in (VS16, VS15):
        assert disarm.strip_format(f"❤{selector}") == f"❤{selector}"
    assert disarm.strip_variation_selectors(f"❤{VS16}") == "❤"


@pytest.mark.parametrize(("raw", "want"), [("a\tb", "a b"), ("a\nb", "a b"), ("a  b", "a b")])
def test_whitespace_is_collapsed(raw: str, want: str) -> None:
    """The step list ends in `CollapseWs` (#433) — this is the direction where the
    preset is the *more* destructive of the two, and the one the docs had inverted."""
    assert disarm.strip_format(raw) == want
    assert disarm.collapse_whitespace(raw) == want


def test_the_chain_and_the_preset_disagree_in_both_directions() -> None:
    """The whole claim in one assertion: neither is a subset of the other.

    A caller cannot reach `strip_format` by chaining primitives, and cannot reach the
    chain's output by calling `strip_format`.
    """
    text = f"a{PUA}b❤{VS16}\tx"
    preset = disarm.strip_format(text)
    chain = disarm.strip_pua(disarm.strip_variation_selectors(text))
    assert preset != chain
    assert PUA in preset and PUA not in chain, "preset keeps what the chain deletes"
    assert "\t" in chain and "\t" not in preset, "chain keeps what the preset collapses"


def test_the_script_is_not_folded() -> None:
    """The property that separates it from `canonicalize` — no confusable fold."""
    cyrillic = "ар‍р"
    assert disarm.strip_format(cyrillic) == "арр"
    assert disarm.canonicalize(cyrillic) == "app"


def test_it_is_a_fixed_point() -> None:
    """No NFC pass, so a decomposed base+mark stays decomposed (`src/presets.rs`)."""
    for text in (f"a{PUA}b❤{VS16}\tx", "é", "ар‍р"):
        once = disarm.strip_format(text)
        assert disarm.strip_format(once) == once, text
