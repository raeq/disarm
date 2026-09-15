"""The named scanner must not eat, or re-target, a mark that follows an emoji (#992).

`demojize` names an emoji and then sweeps whatever modifiers follow it. Two things were
wrong with that sweep, both the shape #990 was about — a predicate broader than the thing
it claims to test, and two scanners answering the same question differently.

* It swept `U+20E3 COMBINING ENCLOSING KEYCAP`, which makes a keycap sequence only after
  a digit, `#` or `*`. `head_len_at` has no keycap arm and says why, ten lines away; the
  named half did exactly what the unnamed half refuses to, so `demojize("\N{GRINNING FACE}⃣")`
  silently dropped an assigned character.

* What survived the sweep was then emitted with no separator, so it attached to the name:
  `demojize("\N{GRINNING FACE}́")` read `"grinning facé"` — an accent the input put
  on the emoji, landing on a word the input never contained. That is the `"woman's hat"` +
  `"e"` → `"woman's hate"` failure the scanner already guarded against one class narrower,
  and the guard existed at only one of its two emit sites.

Both scanners are checked, because the pyo3 one and the pure-Rust one are separate code
and had drifted: the separator lived in `src/emoji.rs` and not in `src/py/emoji.rs`.
"""

from __future__ import annotations

import pytest

from disarm import TextPipeline, demojize, replace_emoji

KEYCAP = "⃣"
ACUTE = "́"
ZWJ = "\N{ZERO WIDTH JOINER}"


class TestAStrayKeycapIsNotEaten:
    @pytest.mark.parametrize(
        ("text", "must_contain"),
        [
            ("\N{GRINNING FACE}" + KEYCAP, "grinning face"),
            ("☺️" + KEYCAP, "smiling face"),
            ("x\N{GRINNING FACE}" + KEYCAP + "y", "grinning face"),
        ],
    )
    def test_the_keycap_survives(self, text: str, must_contain: str) -> None:
        out = demojize(text)
        assert KEYCAP in out, f"{text!r} lost its keycap: {out!r}"
        assert must_contain in out

    def test_replacing_already_agreed_and_still_does(self) -> None:
        """The unnamed half never ate it; the two halves now give the same answer."""
        assert replace_emoji("\N{GRINNING FACE}" + KEYCAP, "") == KEYCAP


class TestARealKeycapSequenceIsUntouched:
    @pytest.mark.parametrize("text", ["x1️" + KEYCAP + "y", "x1" + KEYCAP + "y"])
    def test_it_is_still_named_as_one_emoji(self, text: str) -> None:
        assert demojize(text) == "x keycap: 1 y"

    def test_it_is_still_replaced_as_one_emoji(self) -> None:
        assert replace_emoji("x1️" + KEYCAP + "y", "") == "xy"
        assert replace_emoji("x1️" + KEYCAP + "y", " ") == "x y"

    @pytest.mark.parametrize("base", ["#", "*", "0", "9"])
    def test_every_keycap_base_still_works(self, base: str) -> None:
        out = demojize(f"x{base}️{KEYCAP}y")
        assert out.startswith("x keycap: ") and out.endswith(" y"), out
        assert KEYCAP not in out


class TestAMarkDoesNotLandOnTheName:
    @pytest.mark.parametrize("mark", [ACUTE, KEYCAP, "̈", "⃝"])
    def test_a_separator_keeps_it_off_the_last_letter(self, mark: str) -> None:
        out = demojize("\N{GRINNING FACE}" + mark)
        assert out == f"grinning face {mark}", out
        # The point of the separator: the mark must not be attached to a letter.
        assert not out.startswith("grinning facé")

    def test_punctuation_still_takes_no_separator(self) -> None:
        """The rule widened to marks, not to everything."""
        assert demojize("\N{GRINNING FACE}.") == "grinning face."
        assert demojize("\N{GRINNING FACE},") == "grinning face,"

    def test_an_alphanumeric_still_takes_one(self) -> None:
        assert demojize("\N{GRINNING FACE}x") == "grinning face x"


class TestTheJoinerSweepIsLoadBearing:
    """#992 proposed dropping ZWJ from the sweep too. It cannot be dropped."""

    @pytest.mark.parametrize("links", [2, 3, 7])
    def test_joiners_between_separately_named_emoji_are_consumed(self, links: int) -> None:
        out = demojize(ZWJ.join(["\N{MAN}"] * links))
        assert ZWJ not in out, f"a joiner reached the prose: {out!r}"
        assert out == " ".join(["man"] * links)

    def test_a_named_sequence_is_still_matched_whole(self) -> None:
        assert (
            demojize("\N{MAN}" + ZWJ + "\N{WOMAN}" + ZWJ + "\N{GIRL}") == "family: man, woman, girl"
        )


class TestBothScannersAgree:
    """The pyo3 scanner and the pure-Rust one are separate code and had drifted."""

    @pytest.mark.parametrize(
        "text",
        [
            "\N{GRINNING FACE}" + KEYCAP,
            "\N{GRINNING FACE}" + ACUTE,
            "x1️" + KEYCAP + "y",
            "\N{MAN}" + ZWJ + "\N{MAN}",
        ],
    )
    def test_demojize_and_the_pipeline_step_give_the_same_answer(self, text: str) -> None:
        assert demojize(text) == TextPipeline(demojize=True)(text)
