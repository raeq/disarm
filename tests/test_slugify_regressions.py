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


class TestControlCharEntityDecoding:
    """Regression: fix #2 — entities that decode to control chars must not appear in slugs.

    Before the fix, &#0; decoded to U+0000 (NUL) which passed through the
    slugify pipeline. Now control chars are filtered at the entity decode step.
    """

    def test_nul_entity_decimal_not_in_slug(self) -> None:
        """&#0; must not produce a NUL byte in the slug output."""
        result = slugify("hello&#0;world")
        assert "\x00" not in result

    def test_nul_entity_hex_not_in_slug(self) -> None:
        """&#x0; (hex NUL) must not produce a NUL byte in the slug output."""
        result = slugify("&#x0;")
        assert "\x00" not in result

    def test_backspace_entity_not_in_slug(self) -> None:
        """&#8; (U+0008 backspace) is a control char — must not appear in slug."""
        result = slugify("hello&#8;world")
        assert "\x08" not in result

    def test_tab_entity_not_in_slug(self) -> None:
        """&#9; (U+0009 tab) is a control char — must not appear in slug."""
        result = slugify("hello&#9;world")
        assert "\x09" not in result

    def test_valid_entity_still_decodes(self) -> None:
        """Regression guard: the filter must not break valid entity decoding."""
        assert slugify("caf&#233;") == "cafe"
        assert slugify("caf&#xe9;") == "cafe"
        assert slugify("&#65;BC") == "abc"
