"""Tests for compatibility aliases (drop-in replacement)."""

from translit import unidecode, ascii_fold


class TestUnidecode:
    """Drop-in replacement for Unidecode."""

    def test_basic(self) -> None:
        assert unidecode("café") == "cafe"

    def test_empty(self) -> None:
        assert unidecode("") == ""

    def test_ascii(self) -> None:
        assert unidecode("hello") == "hello"

    def test_cyrillic(self) -> None:
        result = unidecode("Москва")
        assert result == "Moskva"

    def test_unknown_chars_dropped(self) -> None:
        # unidecode drops unknown chars (errors="replace", replace_with="")
        result = unidecode("hello")
        assert result == "hello"


class TestAsciiFold:
    """Elasticsearch/Solr ascii_fold alias."""

    def test_basic(self) -> None:
        assert ascii_fold("café") == "cafe"

    def test_no_accents(self) -> None:
        assert ascii_fold("hello") == "hello"
