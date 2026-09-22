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
        # The point of the separator: the mark must not be attached to a letter.
        assert out == f"grinning face {mark}", out

    def test_punctuation_still_takes_no_separator(self) -> None:
        """The rule widened to marks, not to everything."""
        assert demojize("\N{GRINNING FACE}.") == "grinning face."
        assert demojize("\N{GRINNING FACE},") == "grinning face,"

    def test_an_alphanumeric_still_takes_one(self) -> None:
        assert demojize("\N{GRINNING FACE}x") == "grinning face x"


class TestTheJoinerSweepIsLoadBearing:
    """#992 proposed dropping ZWJ from the sweep too. What that would change is narrow.

    Both scanners drop every VS15, VS16 and ZWJ at the top of their loop, wherever it
    stands, so a joiner between two named emoji never reaches the prose either way —
    the test that used to stand here passed with the arm removed (#996 review). What
    the arm does is let the sweep carry on *past* a joiner to a modifier the match did
    not take; without it the modifier is named on its own.
    """

    def test_the_sweep_continues_past_a_joiner_to_a_modifier(self) -> None:
        text = "\N{MAN}" + ZWJ + "\N{EMOJI MODIFIER FITZPATRICK TYPE-1-2}"
        assert demojize(text) == "man"
        assert TextPipeline(demojize=True)(text) == "man"

    @pytest.mark.parametrize("links", [2, 3, 7])
    def test_joiners_between_separately_named_emoji_never_reach_the_prose(self, links: int) -> None:
        """A guard, not a test of the arm: the top-of-loop skip holds this."""
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


class TestAPreservedEmojiKeepsItsMark:
    """`errors="preserve"` writes the emoji back, not a name, so a mark stays on it.

    #996 widened the separator from alphanumerics to marks for the character after a
    *name*, and the pyo3 scanner flags a preserved emoji the same way, so a preserved
    emoji and its own mark were pulled apart: `🇦́` came back as `🇦 ́` (#996 review).
    An alphanumeric after it is still separated, as #200 asks.
    """

    @pytest.mark.parametrize(
        "text",
        ["\U0001f1e6" + ACUTE, "\U0001f1e6" + KEYCAP, "\U000e0041" + ACUTE],
    )
    def test_the_mark_stays_on_the_emoji(self, text: str) -> None:
        assert demojize(text, errors="preserve") == text

    def test_an_alphanumeric_is_still_separated(self) -> None:
        assert demojize("x\U0001f1e6y", errors="preserve") == "x\U0001f1e6 y"


class TestAProviderDoesNotSplitAKeycap:
    """A provider asked first can claim a keycap's base alone.

    The sweep no longer takes `U+20E3` (#996), on the ground that `match_emoji_at` has
    already matched a keycap whole — but a provider is asked before it, and one that
    names the digit left the keycap behind as an orphan mark (#996 review).
    """

    class _Digits:
        def lookup(self, sequence: list[int]) -> str | None:
            return "ONE" if sequence == [0x31] else None

    @pytest.mark.parametrize("keycap", ["1\ufe0f" + KEYCAP, "1" + KEYCAP])
    def test_the_keycap_goes_with_its_base(self, keycap: str) -> None:
        assert demojize(f"x{keycap}y", provider=self._Digits()) == "x ONE y"

    def test_a_digit_on_its_own_is_still_the_providers(self) -> None:
        # Non-ASCII on purpose: ASCII text takes the fast path and no provider is asked.
        assert demojize("\u00e91y", provider=self._Digits()) == "\u00e9 ONE y"


class TestADroppedEmojiLeavesNoEmojiBehind:
    """The drop path has the seam `replace_emoji("", ...)` has (#995 follow-up).

    `errors="ignore"` and the pipeline remove an emoji they cannot name, and a keycap
    after it then bound to the digit before: `x9<tag>⃣` became `x9⃣`, a keycap, which
    a second pass named (#996 review).
    """

    TEXT = "x9\U000e0041" + KEYCAP

    def test_ignore(self) -> None:
        once = demojize(self.TEXT, errors="ignore")
        assert once == "x9"
        assert demojize(once, errors="ignore") == once

    def test_the_pipeline(self) -> None:
        pipe = TextPipeline(demojize=True)
        assert pipe(self.TEXT) == "x9"
        assert pipe(pipe(self.TEXT)) == "x9"
