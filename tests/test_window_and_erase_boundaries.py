"""Two boundary defects found by review, gated where a user reaches them (#995).

Both were invisible to the existing suites because each is hidden by a coincidence that
holds for every input anybody had tried.

* `resolve_deletions` erased with `line.truncate(col)`, which is `pop` **only while the
  cursor sits at the end of the line**. That holds for every input without a `CR`, so the
  bug could not appear until `resolve_cr` moved the cursor back — and then a backspace
  discarded the whole rest of the line, or at column 0 the whole line.

* `replace_emoji` matched inside a fixed nine-code-point window sized from
  `max_emoji_seq_len()`, the longest run the CLDR **name** table holds. Naming cannot
  need more; replacing can, because a ZWJ chain has no length limit. The RGI kiss with
  skin tones is ten code points; a family of four with skin tones is eleven, a valid ZWJ
  sequence though not an RGI one.

The second one is the one that matters: splitting a sequence emitted two replacements,
which is wrong but visible, *and* let the joiner at the seam through as ordinary text —
a `U+200D` surviving the function whose job is removing emoji, in a library whose whole
subject is invisible characters.
"""

from __future__ import annotations

import pytest

from disarm import TextPipeline, replace_emoji

ZWJ = "\u200d"

#: Family of four with skin tones. Eleven code points, two past the window; a valid ZWJ
#: sequence, though not RGI — CLDR has no skin-toned family.
FAMILY = (
    "\U0001f468\U0001f3fb"
    + ZWJ
    + "\U0001f469\U0001f3fb"
    + ZWJ
    + "\U0001f467\U0001f3fb"
    + ZWJ
    + "\U0001f466\U0001f3fb"
)

#: 👨🏻‍❤️‍💋‍👨🏻 — kiss. Ten code points, RGI, one past the window.
KISS = "\U0001f468\U0001f3fb" + ZWJ + "❤️" + ZWJ + "\U0001f48b" + ZWJ + "\U0001f468\U0001f3fb"


class TestLongEmojiSequences:
    """One sequence is one emoji however long it is."""

    @pytest.mark.parametrize(
        ("name", "seq", "count"),
        [("family", FAMILY, 11), ("kiss", KISS, 10)],
    )
    def test_an_rgi_sequence_past_the_window_takes_one_replacement(
        self, name: str, seq: str, count: int
    ) -> None:
        assert len(seq) == count, f"{name} is not {count} code points"
        assert replace_emoji(seq, " ") == " "
        assert replace_emoji(f"a{seq}b", " ") == "a b"

    @pytest.mark.parametrize("links", range(1, 13))
    def test_no_joiner_survives_a_chain_of_any_length(self, links: int) -> None:
        """The invisible-character leak. `links` 6 and up crossed the old window."""
        chain = ZWJ.join(["\U0001f468"] * links)
        out = replace_emoji(chain, "")
        assert ZWJ not in out, f"{links} links leaked a joiner: {out!r}"
        assert out == ""

    def test_a_long_sequence_still_reaches_a_fixed_point(self) -> None:
        once = replace_emoji(f"aa{FAMILY}bb", "")
        assert replace_emoji(once, "") == once == "aabb"

    def test_a_dangling_joiner_is_still_left_alone(self) -> None:
        """Growing the window must not start eating characters nobody asked about."""
        assert replace_emoji("\U0001f525" + ZWJ, "") == ZWJ
        assert replace_emoji("a" + ZWJ + "b", "") == "a" + ZWJ + "b"
        assert replace_emoji(FAMILY + ZWJ, "") == ZWJ

    def test_text_after_a_long_sequence_survives(self) -> None:
        """The window pulls past its edge to measure; what it does not use comes back."""
        assert replace_emoji(f"{FAMILY}tail", "") == "tail"
        assert replace_emoji(f"{FAMILY}{KISS}tail", "|") == "||tail"
        assert replace_emoji(f"x{FAMILY}y{KISS}z", "") == "xyz"


class TestARemovalManufacturesNoEmoji:
    """What is left either side of a removed emoji must not join into a new one.

    A keycap or a presentation selector after an emoji is not part of it (#996), so a
    removal leaves it behind; if the character before the emoji can take it, the two are
    now an emoji the input never had, and a second pass removes it — with the character
    the caller wrote. The output of a step whose job is removing emoji contained one.
    """

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1\U0001f600\u20e3", "1"),  # the digit would take the keycap
            ("\u263a1\u20e3\ufe0f", "\u263a"),  # ☺ would take the selector
            ("\u00a9\U0001f1ec\U0001f1e7\ufe0f", "\u00a9"),  # © would take it
            ("1\U0001f1ec\U0001f1e7\ufe0f\u20e3", "1"),  # both, in the keycap order
        ],
    )
    def test_the_seam_is_left_as_text(self, text: str, expected: str) -> None:
        once = replace_emoji(text, "")
        assert once == expected, once
        assert replace_emoji(once, "") == once

    def test_a_replacement_that_can_take_the_mark_is_checked_too(self) -> None:
        assert replace_emoji("a\U0001f600\u20e3", "#") == "a#"

    def test_a_mark_that_joins_nothing_is_still_kept(self) -> None:
        """#996's rule stands: a stray keycap is not the emoji's to take."""
        assert replace_emoji("1\U0001f600\u20e3", " ") == "1 \u20e3"
        assert replace_emoji("a\U0001f600\u20e3", "") == "a\u20e3"


class TestEraseAfterCarriageReturn:
    """An erase removes the cell before the cursor, not everything after it."""

    @pytest.fixture
    def pipe(self) -> TextPipeline:
        return TextPipeline(resolve_deletions=True, resolve_cr=True)

    def test_a_backspace_after_a_return_removes_one_cell(self, pipe: TextPipeline) -> None:
        assert pipe("abc\rX\b") == "bc"
        assert pipe("abc\rXY\b") == "Xc"

    def test_a_backspace_at_column_zero_removes_nothing(self, pipe: TextPipeline) -> None:
        assert pipe("abc\r\b") == "abc"
        assert pipe("abc\r\x7f") == "abc"

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("abc\r\u200bY", "\u200bYbc"),
            ("abc\r\u0301Y", "\u0301Ybc"),
            ("abc\rX\b\u200bY", "\u200bYbc"),
        ],
    )
    def test_a_zero_width_at_column_zero_takes_no_cell(
        self, pipe: TextPipeline, text: str, expected: str
    ) -> None:
        """A character that occupies no cell does not move the cursor either.

        At column 0 after a `CR` there is no cell to its left to join, and it fell
        through to the overwrite branch: it took cell 0 and advanced the cursor, so the
        next letter overwrote `b`, which the reader can still see. A terminal shows
        `Ybc`. It is kept, ahead of the line, rather than dropped: it is text the caller
        passed, and deciding what to do with it is `strip_zero_width`'s job.
        """
        assert pipe(text) == expected

    def test_blank_cells_to_the_right_are_not_a_line_to_keep(self) -> None:
        """Only visible text to the right sends a no-cell character ahead of the line.

        Erases blank cells rather than removing them, so a backspace can also bring
        the cursor to column 0 with cells to its right — blank ones. Treating that
        like the post-`CR` case changed output with no `CR` in it at all:
        `"ab\\b\\b\u200b\\b"` gave `"\u200b"` where `"\u200b\\b"` gives `""`
        (Copilot on #1005).
        """
        pipe = TextPipeline(resolve_deletions=True)
        assert pipe("ab\b\b\u200b\b") == pipe("\u200b\b") == ""
        assert pipe("ab\b\b\u200bY") == "\u200bY"

    def test_the_behaviour_without_a_return_is_unchanged(self) -> None:
        pipe = TextPipeline(resolve_deletions=True)
        assert pipe("abc\b") == "ab"
        assert pipe("abc\b\b") == "a"
        assert pipe("\babc") == "abc"

    def test_the_paper_construction_still_resolves(self, pipe: TextPipeline) -> None:
        """Boucher et al. §VI-A: one printable character, then BKSP."""
        attack = "".join(c + "X\b" for c in "paypal")
        assert pipe(attack) == "paypal"
