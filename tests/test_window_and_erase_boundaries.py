"""Two boundary defects found by review, gated where a user reaches them (#995).

Both were invisible to the existing suites because each is hidden by a coincidence that
holds for every input anybody had tried.

* `resolve_deletions` erased with `line.truncate(col)`, which is `pop` **only while the
  cursor sits at the end of the line**. That holds for every input without a `CR`, so the
  bug could not appear until `resolve_cr` moved the cursor back — and then a backspace
  discarded the whole rest of the line, or at column 0 the whole line.

* `replace_emoji` matched inside a fixed nine-code-point window sized from
  `max_emoji_seq_len()`, the longest run the CLDR **name** table holds. Naming cannot
  need more; replacing can, because a ZWJ chain has no length limit. A family of four
  with skin tones is eleven code points and RGI.

The second one is the one that matters: splitting a sequence emitted two replacements,
which is wrong but visible, *and* let the joiner at the seam through as ordinary text —
a `U+200D` surviving the function whose job is removing emoji, in a library whose whole
subject is invisible characters.
"""

from __future__ import annotations

import pytest

from disarm import TextPipeline, replace_emoji

ZWJ = "\u200d"

#: 👨🏻‍👩🏻‍👧🏻‍👦🏻 — family of four with skin tones. Eleven code points, RGI, two past the window.
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

    def test_the_behaviour_without_a_return_is_unchanged(self) -> None:
        pipe = TextPipeline(resolve_deletions=True)
        assert pipe("abc\b") == "ab"
        assert pipe("abc\b\b") == "a"
        assert pipe("\babc") == "abc"

    def test_the_paper_construction_still_resolves(self, pipe: TextPipeline) -> None:
        """Boucher et al. §VI-A: one printable character, then BKSP."""
        attack = "".join(c + "X\b" for c in "paypal")
        assert pipe(attack) == "paypal"
