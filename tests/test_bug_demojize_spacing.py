"""Bug: demojize() concatenates adjacent emoji text without spaces.

Multiple consecutive emoji produce garbled text like "pile of poopile of poo"
because no separator is inserted between adjacent emoji-to-text replacements.
"""

from __future__ import annotations

from disarm import demojize, ml_normalize


class TestAdjacentEmojiSpacing:
    """Adjacent emoji replacements must be separated by spaces."""

    def test_two_identical_emoji(self):
        result = demojize("\U0001f4a9\U0001f4a9")
        # Must NOT concatenate into one word
        assert "poopile" not in result.lower()
        # Must have a space between the two replacements
        parts = result.strip().split()
        assert len(parts) >= 4  # "pile of poo pile of poo" or similar

    def test_three_identical_emoji(self):
        result = demojize("\U0001f525\U0001f525\U0001f525")
        assert "firefire" not in result.lower()
        parts = result.strip().split()
        # "fire fire fire" = 3 tokens
        assert parts.count("fire") == 3

    def test_two_different_emoji(self):
        result = demojize("\u2764\ufe0f\U0001f1fa\U0001f1f8")
        # "red heart" and "flag: United States" should be separated
        assert "heartflag" not in result.lower()
        assert " " in result

    def test_emoji_between_text(self):
        result = demojize("hello\U0001f525world")
        # "fire" should be separated from "hello" and "world"
        assert "hellofire" not in result.lower()
        assert "fireworld" not in result.lower()

    def test_ml_normalize_adjacent_emoji(self):
        result = ml_normalize("I \u2764\ufe0f\U0001f525")
        assert "heartfire" not in result.lower()


class TestSingleEmojiUnchanged:
    """Single emoji (no adjacency) must still work correctly."""

    def test_single_emoji(self):
        result = demojize("\U0001f525")
        assert "fire" in result.lower()

    def test_emoji_with_surrounding_spaces(self):
        result = demojize("hello \U0001f525 world")
        assert "fire" in result.lower()
        # Should not double-space
        assert "  " not in result

    def test_no_emoji(self):
        result = demojize("hello world")
        assert result == "hello world"


class TestEmojiAfterWhitespace:
    """When the preceding char is already whitespace, no extra space is added."""

    def test_no_double_space_after_tab(self):
        # A tab already separates; the emoji name must not get an extra leading space.
        assert demojize("hello\t\U0001f600") == "hello\tgrinning face"

    def test_no_double_space_after_newline(self):
        assert demojize("hello\n\U0001f600") == "hello\ngrinning face"

    def test_single_space_preserved(self):
        assert demojize("hello \U0001f600") == "hello grinning face"

    def test_space_inserted_after_non_whitespace(self):
        assert demojize("hi\U0001f600") == "hi grinning face"
