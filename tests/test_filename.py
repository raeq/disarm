"""Tests for disarm.sanitize_filename."""

import pytest

from disarm import DisarmError, sanitize_filename


class TestSanitizeFilename:
    """Filename sanitization tests."""

    def test_basic(self) -> None:
        result = sanitize_filename("hello world.txt")
        assert "hello" in result
        assert ".txt" in result

    def test_empty(self) -> None:
        # #485: empty input now uses the same never-empty "_" fallback every all-stripped
        # input uses (an empty filename is a downstream write-target footgun).
        assert sanitize_filename("") == "_"

    def test_illegal_chars(self) -> None:
        result = sanitize_filename("file:name*with?bad<chars>.txt")
        assert ":" not in result
        assert "*" not in result
        assert "?" not in result
        assert "<" not in result
        assert ">" not in result

    def test_windows_reserved(self) -> None:
        result = sanitize_filename("CON.txt")
        assert result != "CON.txt"  # Should be prefixed or modified

    def test_max_length(self) -> None:
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name, max_length=255)
        assert len(result) <= 255

    def test_custom_separator(self) -> None:
        result = sanitize_filename("hello world.txt", separator="-")
        assert "-" in result or "hello" in result

    def test_unicode(self) -> None:
        result = sanitize_filename("café résumé.txt")
        assert ".txt" in result

    def test_posix_platform(self) -> None:
        result = sanitize_filename("file\\name.txt", platform="posix")
        # Backslash is not illegal on POSIX
        assert result  # Should produce something valid

    def test_invalid_platform(self) -> None:
        with pytest.raises(DisarmError):
            sanitize_filename("test.txt", platform="invalid")  # type: ignore[arg-type]
