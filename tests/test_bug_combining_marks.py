"""Bug: transliterate() replaces combining marks and zero-width chars with [?].

Combining marks and zero-width characters should be silently dropped,
not replaced with a visible [?] placeholder. The precomposed equivalents
work correctly (ñ → n, é → e), but their NFD decomposed forms produce [?]
for the combining mark component.
"""

from __future__ import annotations

from disarm import transliterate


class TestCombiningMarksNotReplaced:
    """Combining marks must be dropped, not replaced with [?]."""

    def test_combining_long_solidus_overlay(self):
        result = transliterate("a\u0338")
        assert "[?]" not in result
        assert result == "a"

    def test_combining_tilde_on_n(self):
        """Decomposed ñ (n + combining tilde) should produce 'n', not 'n[?]'."""
        result = transliterate("n\u0303")
        assert "[?]" not in result
        assert result == "n"

    def test_combining_acute_on_e(self):
        """Decomposed é (e + combining acute) should produce 'e', not 'e[?]'."""
        result = transliterate("e\u0301")
        assert "[?]" not in result
        assert result == "e"

    def test_combining_cedilla_on_c(self):
        """Decomposed ç (c + combining cedilla) should produce 'c' or 'C'."""
        result = transliterate("c\u0327")
        assert "[?]" not in result

    def test_combining_diaeresis_on_u(self):
        """Decomposed ü (u + combining diaeresis) should produce 'u'."""
        result = transliterate("u\u0308")
        assert "[?]" not in result
        assert result == "u"

    def test_multiple_combining_marks(self):
        result = transliterate("a\u0300\u0301")
        assert "[?]" not in result
        assert result == "a"

    def test_precomposed_matches_decomposed(self):
        """ñ and n+combining tilde must produce the same output."""
        precomposed = transliterate("\u00f1")  # ñ
        decomposed = transliterate("n\u0303")  # n + combining tilde
        assert precomposed == decomposed


class TestZeroWidthCharsNotReplaced:
    """Zero-width characters must be silently dropped, not replaced with [?]."""

    def test_zero_width_space(self):
        result = transliterate("a\u200bb")
        assert "[?]" not in result
        assert result == "ab"

    def test_zero_width_joiner(self):
        result = transliterate("a\u200db")
        assert "[?]" not in result
        assert result == "ab"

    def test_word_joiner(self):
        result = transliterate("a\u2060b")
        assert "[?]" not in result
        assert result == "ab"

    def test_bom_zero_width_no_break_space(self):
        result = transliterate("a\ufeffb")
        assert "[?]" not in result
        assert result == "ab"

    def test_zero_width_non_joiner(self):
        result = transliterate("a\u200cb")
        assert "[?]" not in result
        assert result == "ab"

    def test_soft_hyphen(self):
        result = transliterate("a\u00adb")
        assert "[?]" not in result
        assert result == "ab"

    def test_left_to_right_mark(self):
        result = transliterate("a\u200eb")
        assert "[?]" not in result
        assert result == "ab"

    def test_right_to_left_mark(self):
        result = transliterate("a\u200fb")
        assert "[?]" not in result
        assert result == "ab"
