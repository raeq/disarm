"""Tests for awesome-slugify compatibility aliases.

Verifies that translit's Slugify/UniqueSlugify classes and preconfigured
instances can serve as drop-in replacements for awesome-slugify.
"""

import warnings

from translit import (
    Slugify,
    UniqueSlugify,
    slugify_de,
    slugify_el,
    slugify_filename,
    slugify_ru,
    slugify_unicode,
    slugify_url,
)

# ---------------------------------------------------------------------------
# Slugify class
# ---------------------------------------------------------------------------


class TestSlugifyClass:
    """awesome-slugify Slugify drop-in."""

    def test_default_no_lowercase(self) -> None:
        """awesome-slugify defaults to to_lower=False."""
        s = Slugify()
        assert s("Hello World") == "Hello-World"

    def test_to_lower(self) -> None:
        s = Slugify(to_lower=True)
        assert s("Hello World") == "hello-world"

    def test_lowercase_param_also_works(self) -> None:
        s = Slugify(lowercase=True)
        assert s("Hello World") == "hello-world"

    def test_separator(self) -> None:
        s = Slugify(separator=".")
        assert s("one two three") == "one.two.three"

    def test_max_length(self) -> None:
        s = Slugify(to_lower=True, max_length=5)
        result = s("Hello World")
        assert len(result) <= 5

    def test_capitalize(self) -> None:
        s = Slugify(to_lower=True, capitalize=True)
        result = s("hello world")
        assert result[0].isupper()

    def test_stop_words(self) -> None:
        s = Slugify(to_lower=True, stop_words=("the", "a"))
        assert s("the big fox") == "big-fox"

    def test_pretranslate_dict(self) -> None:
        s = Slugify(to_lower=True, pretranslate={"©": "c", "®": "r"})
        result = s("© 2024")
        assert "c" in result

    def test_pretranslate_callable_raises(self) -> None:
        import pytest

        from translit import TranslitError, UnsupportedError

        # #183: an unsupported compat feature is now a translit-owned error
        # (UnsupportedError), catchable via TranslitError, not a bare
        # NotImplementedError.
        with pytest.raises(UnsupportedError, match="callable pretranslate"):
            Slugify(pretranslate=lambda x: x)
        assert issubclass(UnsupportedError, TranslitError)

    def test_translate_ignored_warns(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Slugify(translate=lambda x: x)
            assert len(w) == 1
            assert "translate parameter is ignored" in str(w[0].message)

    def test_fold_abbrs_warns(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Slugify(fold_abbrs=True)
            assert len(w) == 1
            assert "fold_abbrs" in str(w[0].message)

    def test_call_with_kwargs_override(self) -> None:
        s = Slugify()
        result = s("Hello World", to_lower=True)
        assert result == "hello-world"

    def test_repr(self) -> None:
        s = Slugify(separator="_")
        r = repr(s)
        assert "Slugify" in r
        assert "_" in r


# ---------------------------------------------------------------------------
# Slugify attribute-style configuration
# ---------------------------------------------------------------------------


class TestSlugifyAttributes:
    """awesome-slugify allows setting properties after construction."""

    def test_set_to_lower(self) -> None:
        s = Slugify()
        assert s("Hello") == "Hello"
        s.to_lower = True
        assert s("Hello") == "hello"

    def test_set_stop_words(self) -> None:
        s = Slugify(to_lower=True)
        s.stop_words = ("the",)
        assert s("the big fox") == "big-fox"

    def test_set_max_length(self) -> None:
        s = Slugify(to_lower=True)
        s.max_length = 5
        result = s("Hello World")
        assert len(result) <= 5

    def test_set_separator(self) -> None:
        s = Slugify(to_lower=True)
        s.separator = "_"
        assert s("hello world") == "hello_world"

    def test_set_pretranslate(self) -> None:
        s = Slugify(to_lower=True)
        s.pretranslate = {"©": "copyright"}
        result = s("©")
        assert "copyright" in result

    def test_set_pretranslate_none(self) -> None:
        s = Slugify(to_lower=True, pretranslate={"©": "c"})
        s.pretranslate = None
        # Should not crash
        s("test")


# ---------------------------------------------------------------------------
# UniqueSlugify class
# ---------------------------------------------------------------------------


class TestUniqueSlugifyClass:
    """awesome-slugify UniqueSlugify drop-in."""

    def test_uniqueness(self) -> None:
        u = UniqueSlugify(to_lower=True)
        first = u("My Post")
        second = u("My Post")
        assert first == "my-post"
        assert second == "my-post-1"

    def test_default_no_lowercase(self) -> None:
        u = UniqueSlugify()
        assert u("Hello") == "Hello"

    def test_reset(self) -> None:
        u = UniqueSlugify(to_lower=True)
        u("My Post")
        u("My Post")
        u.reset()
        assert u("My Post") == "my-post"

    def test_capitalize(self) -> None:
        u = UniqueSlugify(to_lower=True, capitalize=True)
        result = u("hello world")
        assert result[0].isupper()

    def test_repr(self) -> None:
        assert "UniqueSlugify" in repr(UniqueSlugify())


# ---------------------------------------------------------------------------
# Preconfigured instances
# ---------------------------------------------------------------------------


class TestPreconfiguredInstances:
    """awesome-slugify preconfigured slugifier instances."""

    def test_slugify_url_lowercase(self) -> None:
        result = slugify_url("Hello World")
        assert result == "hello-world"

    def test_slugify_url_strips_articles(self) -> None:
        result = slugify_url("the big a fox an end")
        assert "the" not in result.split("-")
        assert "a" not in result.split("-")
        assert "an" not in result.split("-")

    def test_slugify_url_max_length(self) -> None:
        long_text = "a very long title " * 20
        result = slugify_url(long_text)
        assert len(result) <= 200

    def test_slugify_filename_underscore(self) -> None:
        result = slugify_filename("Hello World")
        assert "_" in result or result == "Hello_World"

    def test_slugify_filename_max_length(self) -> None:
        long_text = "x" * 300
        result = slugify_filename(long_text)
        assert len(result) <= 255

    def test_slugify_unicode_preserves(self) -> None:
        result = slugify_unicode("café latte")
        assert "café" in result or "cafe" in result  # allow_unicode=True

    def test_slugify_ru_cyrillic(self) -> None:
        result = slugify_ru("Москва")
        assert result.isascii() or "moskva" in result.lower()

    def test_slugify_de_umlauts(self) -> None:
        result = slugify_de("Ärger")
        assert "ae" in result.lower()

    def test_slugify_el_greek(self) -> None:
        result = slugify_el("Αθήνα")
        assert result.isascii() or len(result) > 0


# ---------------------------------------------------------------------------
# Import compatibility
# ---------------------------------------------------------------------------


class TestImportCompat:
    """Verify the import path mirrors awesome-slugify."""

    def test_import_slugify_class(self) -> None:
        from translit import Slugify as S

        assert S is Slugify

    def test_import_unique_slugify(self) -> None:
        from translit import UniqueSlugify as U

        assert U is UniqueSlugify

    def test_instances_are_callable(self) -> None:
        assert callable(slugify_url)
        assert callable(slugify_filename)
        assert callable(slugify_unicode)
        assert callable(slugify_ru)
        assert callable(slugify_de)
        assert callable(slugify_el)
