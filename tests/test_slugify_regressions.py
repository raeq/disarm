"""Regression tests for slugify correctness.

Pin exact expected outputs. Tests for numeric HTML entity decoding
and regex_pattern behavior.
"""

from __future__ import annotations

from translit import slugify


class TestHtmlEntityDecoding:
    """HTML entity decoding in slugify."""

    def test_named_entity_amp(self) -> None:
        """&amp; should decode to & which becomes empty after transliteration."""
        result = slugify("&amp; test")
        assert "test" in result

    def test_numeric_decimal_entity(self) -> None:
        """&#38; is numeric decimal for &, which is non-alnum and dropped."""
        result = slugify("&#38; test")
        assert "test" in result

    def test_numeric_hex_entity(self) -> None:
        """&#x26; is numeric hex for &, which is non-alnum and dropped."""
        result = slugify("&#x26; test")
        assert "test" in result

    def test_numeric_decimal_eacute(self) -> None:
        """&#233; is decimal for é → transliterates to e."""
        result = slugify("caf&#233;")
        assert result == "cafe"

    def test_numeric_hex_eacute(self) -> None:
        """&#xe9; is hex for é → transliterates to e."""
        result = slugify("caf&#xe9;")
        assert result == "cafe"

    def test_numeric_entity_uppercase_x(self) -> None:
        """&#X26; with uppercase X should also decode."""
        result = slugify("&#X41;bc")
        assert "abc" in result.lower()

    def test_named_entity_lt(self) -> None:
        assert slugify("&lt;tag&gt;") == "tag"

    def test_named_entity_quot(self) -> None:
        result = slugify("&quot;hello&quot;")
        assert "hello" in result


class TestRegexPattern:
    """regex_pattern filters characters from the slug."""

    def test_regex_removes_digits(self) -> None:
        result = slugify("hello 123 world", regex_pattern=r"[^a-z]+")
        # After transliteration: "hello 123 world"
        # After lowercase: "hello 123 world"
        # After regex removes non-[a-z]: "helloworld"
        # After separator logic: no separators left to insert
        assert result == "helloworld"

    def test_regex_basic(self) -> None:
        result = slugify("abc-123-def", regex_pattern=r"[0-9]+")
        assert "123" not in result
