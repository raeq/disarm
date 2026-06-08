"""Tests for translit.slugify and Slugifier classes."""

import pytest

from translit import Slugifier, Text, UniqueSlugifier, slugify


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


class TestSlugifyDefault:
    """#97: opt-in `default` fallback when the input has no sluggable characters."""

    def test_default_for_empty_result(self) -> None:
        # Emoji / punctuation / zero-width otherwise slug to "" (routing hazard).
        assert slugify("🔥🔥🔥") == ""
        assert slugify("🔥🔥🔥", default="n-a") == "n-a"
        assert slugify("...", default="n-a") == "n-a"
        assert slugify("​", default="n-a") == "n-a"

    def test_default_not_applied_when_nonempty(self) -> None:
        assert slugify("Hello World", default="n-a") == "hello-world"

    def test_default_none_preserves_empty_string(self) -> None:
        assert slugify("🔥", default=None) == ""
        assert slugify("🔥") == ""

    def test_default_applies_per_element_in_batch(self) -> None:
        out = slugify(["Hello World", "🔥", "café"], default="n-a")
        assert out == ["hello-world", "n-a", "cafe"]


class TestSlugifyDefaultSanitized:
    """#193: the `default` fallback is itself sanitized through the slug pipeline.

    slugify() output is documented as URL-safe; a caller-derived default
    (username, filename) must not smuggle path-traversal or `?#/` into a value
    assumed sanitized. The default is run through the same pipeline, so it is
    both sanitized and subject to `max_length`.
    """

    def test_default_is_sanitized_not_returned_raw(self) -> None:
        # Was returned verbatim before #193 — now sanitized like real output.
        assert slugify("...", default="Not Slugged!") == "not-slugged"

    def test_default_neutralizes_path_traversal(self) -> None:
        assert slugify("🔥🔥", default="../../etc/passwd") == "etc-passwd"
        assert "/" not in slugify("🔥🔥", default="../../etc/passwd")

    def test_default_neutralizes_url_metachars(self) -> None:
        out = slugify("🔥🔥", default="a/b?c#d")
        assert out == "a-b-c-d"
        assert not (set("/?#") & set(out))

    def test_default_obeys_max_length(self) -> None:
        # #193 part 4: the length guarantee must hold for the fallback too.
        assert slugify("🔥", default="this-is-a-long-fallback", max_length=5) == "this"

    def test_default_with_no_sluggable_chars_yields_empty(self) -> None:
        # A default that is itself unsluggable sanitizes to "" (documented).
        assert slugify("🔥", default="💧💧") == ""

    def test_default_honors_separator_and_lang(self) -> None:
        assert slugify("🔥", default="N A", separator="_") == "n_a"
        assert slugify("🔥", default="Ärger", lang="de") == "aerger"


class TestSlugifyBatchMaxLengthGuard:
    """#193 part 3: a negative max_length raises a catchable ValueError on both
    the scalar and the batch path (the batch path previously fell through to the
    Rust uint conversion and raised an uncatchable OverflowError)."""

    def test_scalar_negative_max_length_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="max_length must be non-negative"):
            slugify("hello", max_length=-1)

    def test_batch_negative_max_length_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="max_length must be non-negative"):
            slugify(["hello"], max_length=-1)


class TestStatefulDefault:
    """#193 part 2 / #169: `default` threads through the class/stateful forms,
    where the empty-slug routing hazard #97 fixed was otherwise still present."""

    def test_slugifier_default(self) -> None:
        assert Slugifier(default="n-a")("🔥") == "n-a"
        assert Slugifier(default="N/A")("🔥") == "n-a"  # sanitized
        assert Slugifier(default="n-a")("Hello World") == "hello-world"
        assert Slugifier()("🔥") == ""  # no default -> unchanged

    def test_unique_slugifier_default_is_made_unique(self) -> None:
        # Each unsluggable input must get a *unique* default, not collide on one.
        u = UniqueSlugifier(default="n-a")
        assert [u("🔥") for _ in range(3)] == ["n-a", "n-a-1", "n-a-2"]

    def test_unique_slugifier_default_is_sanitized(self) -> None:
        assert UniqueSlugifier(default="N/A")("🔥") == "n-a"

    def test_unique_slugifier_mixes_real_and_default(self) -> None:
        u = UniqueSlugifier(default="n-a")
        assert u("My Post") == "my-post"
        assert u("My Post") == "my-post-1"
        assert u("🔥") == "n-a"
        assert u("🔥") == "n-a-1"

    def test_unique_slugifier_no_default_unchanged(self) -> None:
        u = UniqueSlugifier()
        assert u("🔥") == ""
        assert u("🔥") == "-1"  # legacy empty-uniquify behavior preserved

    def test_text_slugify_default(self) -> None:
        assert Text("🔥").slugify(default="N/A").value == "n-a"
        assert Text("Hello World").slugify(default="n-a").value == "hello-world"
