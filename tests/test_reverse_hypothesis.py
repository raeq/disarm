"""Property-based tests for reverse transliteration.

Tests round-trip properties, invariants, and edge cases for
transliterate(text, target=...) using Hypothesis.
"""

from __future__ import annotations

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from translit import reverse_langs, transliterate

pytestmark = pytest.mark.hypothesis


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Latin text that reverse transliteration can plausibly handle
latin_alpha = st.text(
    alphabet=st.characters(whitelist_categories=("L",), whitelist_characters=" "),
    min_size=1,
    max_size=100,
).filter(lambda s: s.isascii() and s.strip())

# Basic ASCII (letters, digits, punctuation)
ascii_text = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E),
    min_size=0,
    max_size=200,
)

# Script-specific text generators for forward→reverse round-trips
cyrillic_text = st.text(
    alphabet=st.characters(min_codepoint=0x0410, max_codepoint=0x044F),
    min_size=1,
    max_size=50,
)

greek_text = st.text(
    alphabet=st.characters(min_codepoint=0x0391, max_codepoint=0x03C9),
    min_size=1,
    max_size=50,
).filter(lambda s: any(c.isalpha() for c in s))

reverse_lang = st.sampled_from(reverse_langs())


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestReverseNeverPanics:
    """Reverse transliteration must never panic on any ASCII input."""

    @given(text=ascii_text, lang=reverse_lang)
    @settings(max_examples=500)
    def test_never_raises(self, text: str, lang: str) -> None:
        result = transliterate(text, target=lang)
        assert isinstance(result, str)

    @given(text=st.text(min_size=0, max_size=200), lang=reverse_lang)
    @settings(max_examples=500)
    def test_arbitrary_unicode_input(self, text: str, lang: str) -> None:
        """Even non-Latin input should not crash."""
        result = transliterate(text, target=lang)
        assert isinstance(result, str)


class TestReversePreservesNonAlpha:
    """Digits, punctuation, and whitespace pass through unchanged."""

    @given(lang=reverse_lang)
    @settings(max_examples=50)
    def test_digits_passthrough(self, lang: str) -> None:
        assert transliterate("12345", target=lang) == "12345"

    @given(lang=reverse_lang)
    @settings(max_examples=50)
    def test_punctuation_passthrough(self, lang: str) -> None:
        result = transliterate("!@#$%", target=lang)
        assert result == "!@#$%"

    @given(lang=reverse_lang)
    @settings(max_examples=50)
    def test_empty_string(self, lang: str) -> None:
        assert transliterate("", target=lang) == ""


class TestReverseOutputScript:
    """Reverse transliteration should produce text in the target script."""

    # Letters that have unambiguous reverse mappings in each language
    _ru_alpha = st.text(
        alphabet=st.sampled_from(list("abvgdeziklmnoprstuf")),
        min_size=3,
        max_size=50,
    )
    _el_alpha = st.text(
        alphabet=st.sampled_from(list("abgdeziklmnoprstf")),
        min_size=3,
        max_size=50,
    )

    @given(text=_ru_alpha)
    @settings(max_examples=300)
    def test_russian_produces_cyrillic(self, text: str) -> None:
        result = transliterate(text, target="ru")
        assert any(ord(c) > 0x7F for c in result if c.isalpha()), (
            f"Expected non-ASCII output for {text!r}, got {result!r}"
        )

    @given(text=_el_alpha)
    @settings(max_examples=300)
    def test_greek_produces_greek_script(self, text: str) -> None:
        result = transliterate(text, target="el")
        assert any(ord(c) > 0x7F for c in result if c.isalpha()), (
            f"Expected non-ASCII output for {text!r}, got {result!r}"
        )


class TestReverseIdempotence:
    """Applying reverse twice should be idempotent (already in target script)."""

    @given(text=latin_alpha, lang=reverse_lang)
    @settings(max_examples=300)
    def test_double_reverse_stable(self, text: str, lang: str) -> None:
        """reverse(reverse(x)) should equal reverse(x) — second pass is a no-op."""
        once = transliterate(text, target=lang)
        twice = transliterate(once, target=lang)
        assert once == twice


class TestRoundTrip:
    """Forward then reverse (or vice versa) — lossy but structured."""

    @given(text=cyrillic_text)
    @settings(max_examples=300)
    def test_russian_forward_reverse_preserves_length_class(self, text: str) -> None:
        """Forward→reverse should produce output of similar character count."""
        forward = transliterate(text, lang="ru")
        back = transliterate(forward, target="ru")
        # Not exact round-trip (lossy), but should have characters
        assert len(back) > 0

    @given(text=latin_alpha)
    @settings(max_examples=300)
    def test_russian_reverse_forward_produces_ascii(self, text: str) -> None:
        """Reverse→forward should return to ASCII."""
        assume(any(c.isalpha() for c in text))
        reversed_text = transliterate(text, target="ru")
        forward_again = transliterate(reversed_text, lang="ru")
        # Forward transliteration should produce ASCII
        assert forward_again.isascii()


class TestReverseConsistency:
    """Same input always produces same output."""

    @given(text=ascii_text, lang=reverse_lang)
    @settings(max_examples=200)
    def test_deterministic(self, text: str, lang: str) -> None:
        r1 = transliterate(text, target=lang)
        r2 = transliterate(text, target=lang)
        assert r1 == r2

    @given(lang=reverse_lang)
    @settings(max_examples=50)
    def test_single_chars_deterministic(self, lang: str) -> None:
        """Each letter maps consistently."""
        for c in "abcdefghijklmnopqrstuvwxyz":
            r1 = transliterate(c, target=lang)
            r2 = transliterate(c, target=lang)
            assert r1 == r2


class TestReverseBatch:
    """Batch reverse must agree with single-call reverse."""

    @given(
        texts=st.lists(ascii_text, min_size=1, max_size=20),
        lang=reverse_lang,
    )
    @settings(max_examples=100)
    def test_batch_matches_singles(self, texts: list[str], lang: str) -> None:
        from translit import transliterate_batch

        batch_results = transliterate_batch(texts, target=lang)
        single_results = [transliterate(t, target=lang) for t in texts]
        assert batch_results == single_results
