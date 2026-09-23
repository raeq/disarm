"""Emoji scanner defects found by the Lean model in `formal/lean/Emoji`.

The model mirrors `src/emoji.rs` and `src/py/emoji.rs` branch by branch, agrees
with the library on 680,172 differential inputs, and checks the documented
properties exhaustively over short strings. Each class below is one property it
refuted, with the shortest witness it found.
"""

from __future__ import annotations

import pytest

from disarm import TextPipeline, demojize, ml_normalize, replace_emoji

VS15, VS16, ZWJ, KEYCAP = "\ufe0e", "\ufe0f", "\u200d", "\u20e3"
GRIN, LONE_RI, ACUTE = "\U0001f600", "\U0001f1e6", "\u0301"


class TestAFullyQualifiedSequenceIsNamedWhole:
    """CLDR keys a ZWJ sequence without its presentation selectors; people type them.

    The trie walk stopped at the first U+FE0F, so a fully qualified sequence was
    named piece by piece: 306 of the 1,021 such sequences were misnamed.
    """

    @pytest.mark.parametrize(
        ("fully_qualified", "name"),
        [
            ("\u2764" + VS16 + ZWJ + "\U0001f525", "heart on fire"),
            ("\U0001f3f3" + VS16 + ZWJ + "\U0001f308", "rainbow flag"),
            ("\U0001f468" + ZWJ + "\u2764" + VS16 + ZWJ + "\U0001f468", None),
        ],
    )
    def test_it_takes_the_name_of_the_unqualified_key(
        self, fully_qualified: str, name: str | None
    ) -> None:
        bare = fully_qualified.replace(VS16, "")
        assert demojize(fully_qualified) == demojize(bare)
        assert TextPipeline(demojize=True)(fully_qualified) == demojize(bare)
        if name is not None:
            assert demojize(fully_qualified) == name

    def test_the_longest_rgi_form_fits_the_window(self) -> None:
        kiss = (
            "\U0001f468\U0001f3fb"
            + ZWJ
            + "\u2764"
            + VS16
            + ZWJ
            + "\U0001f48b"
            + ZWJ
            + "\U0001f468\U0001f3fb"
        )
        assert len(kiss) == 10
        assert demojize(kiss) == demojize(kiss.replace(VS16, ""))


class TestADroppedEmojiDoesNotGlueTheNextWordToTheLastName:
    """Dropping an emoji that writes nothing reset the separator flag (#200, #996)."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            (GRIN + LONE_RI + "x", "grinning face x"),
            (GRIN + LONE_RI + ACUTE, "grinning face " + ACUTE),
        ],
    )
    def test_ignore_and_the_pipeline(self, text: str, expected: str) -> None:
        assert demojize(text, errors="ignore") == expected
        assert demojize(text, errors="replace", replace_with="") == expected
        assert TextPipeline(demojize=True)(text) == expected

    def test_a_stored_key_keeps_its_words_apart(self) -> None:
        assert ml_normalize("I " + GRIN + LONE_RI + "x ok") == "i grinning face x ok"


class TestARemovalBuildsNoKeycap:
    """A keycap is three code points; the seam looked back at one."""

    def test_replace_with_nothing(self) -> None:
        once = replace_emoji("1" + VS16 + GRIN + KEYCAP, "")
        assert replace_emoji(once, "") == once
        assert "1" in once

    @pytest.mark.parametrize("skipped", [VS15, ZWJ, VS15 + VS16])
    def test_demojize_skipping_a_selector_or_joiner(self, skipped: str) -> None:
        once = demojize("1" + skipped + KEYCAP)
        assert demojize(once) == once
        assert TextPipeline(demojize=True)(once) == TextPipeline(demojize=True)(
            "1" + skipped + KEYCAP
        )
