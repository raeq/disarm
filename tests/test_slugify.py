"""Tests for translit.slugify and Slugifier classes."""

from translit import slugify, Slugifier, UniqueSlugifier


class TestSlugify:
    """Core slugification tests."""

    def test_basic(self) -> None:
        assert slugify("Hello World") == "hello-world"

    def test_empty(self) -> None:
        assert slugify("") == ""

    def test_unicode(self) -> None:
        assert slugify("café latte") == "cafe-latte"

    def test_custom_separator(self) -> None:
        assert slugify("Hello World", separator="_") == "hello_world"

    def test_no_lowercase(self) -> None:
        assert slugify("Hello World", lowercase=False) == "Hello-World"

    def test_max_length(self) -> None:
        result = slugify("This is a very long title", max_length=10)
        assert len(result) <= 10

    def test_max_length_word_boundary(self) -> None:
        result = slugify("This is a very long title", max_length=10, word_boundary=True)
        assert len(result) <= 10
        assert not result.endswith("-")

    def test_stopwords(self) -> None:
        result = slugify("the quick brown fox", stopwords=["the"])
        assert "the" not in result.split("-")

    def test_replacements(self) -> None:
        result = slugify("test & check", replacements=[("&", "and")])
        assert "and" in result

    def test_special_characters(self) -> None:
        assert slugify("hello!@#$%world") == "hello-world"

    def test_consecutive_separators(self) -> None:
        result = slugify("hello   world")
        assert "--" not in result

    def test_entities(self) -> None:
        assert slugify("hello &amp; world") == "hello-world"

    def test_allow_unicode(self) -> None:
        result = slugify("café latte", allow_unicode=True)
        assert "café" in result or "cafe" in result


class TestSlugifier:
    """Tests for the Slugifier class."""

    def test_basic(self) -> None:
        s = Slugifier()
        assert s("Hello World") == "hello-world"

    def test_custom_config(self) -> None:
        s = Slugifier(separator="_", lowercase=False)
        assert s("Hello World") == "Hello_World"

    def test_repr(self) -> None:
        s = Slugifier(separator="_")
        r = repr(s)
        assert "Slugifier" in r
        assert "_" in r


class TestUniqueSlugifier:
    """Tests for the UniqueSlugifier class."""

    def test_unique_slugs(self) -> None:
        s = UniqueSlugifier()
        first = s("Hello World")
        second = s("Hello World")
        third = s("Hello World")
        assert first == "hello-world"
        assert second == "hello-world-1"
        assert third == "hello-world-2"

    def test_reset(self) -> None:
        s = UniqueSlugifier()
        first = s("Hello World")
        s.reset()
        after_reset = s("Hello World")
        assert first == after_reset

    def test_with_check_callback(self) -> None:
        existing = {"hello-world"}

        def check(slug: str) -> bool:
            return slug in existing

        s = UniqueSlugifier(check=check)
        result = s("Hello World")
        assert result == "hello-world-1"
