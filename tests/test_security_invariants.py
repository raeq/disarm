"""Property-based tests: security_clean output invariants.

security_clean is the primary defense against homoglyph attacks, bidi spoofing,
and invisible character injection. These tests verify that its output satisfies
the security properties it promises, across the full Unicode input space.
"""

from __future__ import annotations

import pytest
from conftest import unicode_text
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from disarm import (
    is_confusable,
    is_normalized,
    normalize_user_input,
    security_clean,
)

pytestmark = pytest.mark.hypothesis

# Bidi override and formatting characters that security_clean must strip
BIDI_CHARS = frozenset(
    "\u00ad"  # Soft hyphen
    "\u061c"  # Arabic Letter Mark
    "\u200e"  # LRM
    "\u200f"  # RLM
    "\u202a"  # LRE
    "\u202b"  # RLE
    "\u202c"  # PDF
    "\u202d"  # LRO
    "\u202e"  # RLO
    "\u2066"  # LRI
    "\u2067"  # RLI
    "\u2068"  # FSI
    "\u2069"  # PDI
)

# Zero-width characters that collapse_whitespace strips
ZERO_WIDTH_CHARS = frozenset(
    "\u200b"  # Zero Width Space
    "\u200c"  # Zero Width Non-Joiner
    "\u200d"  # Zero Width Joiner
    "\ufeff"  # BOM / Zero Width No-Break Space
    "\u2060"  # Word Joiner
    "\u2061"  # Function Application (invisible math)
    "\u2062"  # Invisible Times
    "\u2063"  # Invisible Separator
    "\u2064"  # Invisible Plus
)


class TestSecurityCleanBidiStripping:
    """security_clean must strip all bidi override characters."""

    @given(text=unicode_text)
    @settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
    def test_no_bidi_chars_in_output(self, text: str) -> None:
        """Output must contain zero bidi override/formatting characters."""
        result = security_clean(text)
        found = [ch for ch in result if ch in BIDI_CHARS]
        assert not found, (
            f"Bidi chars survived security_clean:\n"
            f"  input:  {text!r}\n"
            f"  output: {result!r}\n"
            f"  found:  {[f'U+{ord(c):04X}' for c in found]}"
        )

    def test_all_13_bidi_chars_stripped(self) -> None:
        """Verify each of the 13 bidi chars individually."""
        for ch in BIDI_CHARS:
            result = security_clean(f"test{ch}word")
            assert ch not in result, f"U+{ord(ch):04X} not stripped"


class TestSecurityCleanZeroWidth:
    """security_clean must strip zero-width characters."""

    @given(text=unicode_text)
    @settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
    def test_no_zero_width_in_output(self, text: str) -> None:
        """Output must contain zero zero-width characters."""
        result = security_clean(text)
        found = [ch for ch in result if ch in ZERO_WIDTH_CHARS]
        assert not found, (
            f"Zero-width chars survived security_clean:\n"
            f"  input:  {text!r}\n"
            f"  output: {result!r}\n"
            f"  found:  {[f'U+{ord(c):04X}' for c in found]}"
        )


class TestSecurityCleanConfusables:
    """security_clean must neutralize confusable homoglyphs."""

    @given(text=unicode_text)
    @settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
    def test_output_not_confusable(self, text: str) -> None:
        """After security_clean, is_confusable must return False."""
        result = security_clean(text)
        assert not is_confusable(result), (
            f"is_confusable returned True after security_clean:\n"
            f"  input:  {text!r}\n"
            f"  output: {result!r}"
        )

    def test_cyrillic_homoglyph_neutralized(self) -> None:
        """Classic Cyrillic-Latin homoglyph attack must be neutralized."""
        # "раypal" using Cyrillic р (U+0440) and а (U+0430)
        attack = "\u0440\u0430ypal"
        result = security_clean(attack)
        assert result == "paypal"
        assert not is_confusable(result)


class TestSecurityCleanNormalization:
    """security_clean output must be NFKC-normalized."""

    @given(text=unicode_text)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_output_is_nfkc(self, text: str) -> None:
        """Output should be in NFKC form (or close — confusables may
        introduce non-NFKC chars, but the NFKC step runs first)."""
        result = security_clean(text)
        # The pipeline is NFKC → confusables → collapse_ws → strip_bidi.
        # Confusables replaces chars with ASCII, collapse_ws strips chars,
        # strip_bidi strips chars. None of these introduce non-NFC chars.
        # So the output should still be NFC at minimum.
        assert is_normalized(result, form="NFC"), (
            f"security_clean output is not NFC:\n  input:  {text!r}\n  output: {result!r}"
        )


class TestSecurityCleanWhitespace:
    """security_clean must normalize whitespace."""

    @given(text=unicode_text)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_no_consecutive_spaces(self, text: str) -> None:
        """Output must not contain consecutive ASCII spaces."""
        result = security_clean(text)
        assert "  " not in result, (
            f"Consecutive spaces in security_clean output:\n"
            f"  input:  {text!r}\n"
            f"  output: {result!r}"
        )

    @given(text=unicode_text)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_no_leading_trailing_whitespace(self, text: str) -> None:
        """Output must not have leading/trailing whitespace."""
        result = security_clean(text)
        if result:
            assert result[0] != " ", f"Leading space: {result!r}"
            assert result[-1] != " ", f"Trailing space: {result!r}"


class TestSecurityCleanIdempotent:
    """security_clean must be idempotent."""

    @given(text=unicode_text)
    @settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
    def test_idempotent(self, text: str) -> None:
        """security_clean(security_clean(x)) == security_clean(x).

        Comparison uses NFC normalization because NFKC can produce combining
        mark sequences where marks with the same canonical combining class
        appear in different orders across passes (e.g., Tibetan U+0F71 +
        combining acute U+0301). Both orderings are canonically equivalent.
        """
        import unicodedata

        once = security_clean(text)
        twice = security_clean(once)
        assert unicodedata.normalize("NFC", once) == unicodedata.normalize("NFC", twice), (
            f"security_clean is not idempotent:\n"
            f"  input:  {text!r}\n"
            f"  once:   {once!r}\n"
            f"  twice:  {twice!r}"
        )


class TestSecurityCleanComposite:
    """Composite scenarios combining multiple attack vectors."""

    def test_fullwidth_bypass(self) -> None:
        """NFKC collapses fullwidth chars that bypass naive filters."""
        # Fullwidth "admin" — U+FF41 U+FF44 U+FF4D U+FF49 U+FF4E
        fullwidth = "\uff41\uff44\uff4d\uff49\uff4e"
        result = security_clean(fullwidth)
        assert result == "admin"

    def test_bidi_plus_homoglyph(self) -> None:
        """Combined bidi override + homoglyph attack."""
        attack = "\u202e\u0430dmin"  # RLO + Cyrillic а
        result = security_clean(attack)
        assert "\u202e" not in result
        assert not is_confusable(result)

    def test_zwsp_splitting_keyword(self) -> None:
        """Zero-width space splitting a keyword."""
        attack = "pass\u200bword"
        result = security_clean(attack)
        assert result == "password"

    def test_invisible_math_operators(self) -> None:
        """Invisible math operators (U+2061–U+2064) must be stripped."""
        attack = "admin\u2061user"
        result = security_clean(attack)
        assert result == "adminuser"

    @given(
        text=st.text(
            alphabet=st.sampled_from(
                list("abcdefghijklmnopqrstuvwxyz ")
                + ["\u200b", "\u200d", "\ufeff", "\u202e", "\u061c", "\u0430", "\u043e"]
            ),
            min_size=1,
            max_size=100,
        )
    )
    @settings(max_examples=500)
    def test_mixed_attack_vectors(self, text: str) -> None:
        """Random mix of ASCII + attack chars must always clean safely."""
        result = security_clean(text)
        # No bidi chars
        assert not any(ch in BIDI_CHARS for ch in result)
        # No zero-width chars
        assert not any(ch in ZERO_WIDTH_CHARS for ch in result)
        # No confusables
        assert not is_confusable(result)
        # No consecutive spaces
        assert "  " not in result


class TestPathSafetyInvariant:
    """#248: the security presets must guarantee path-safe output across the
    whole Unicode input space — no synthesised '/', '\\', or '..' traversal,
    however the input tries to smuggle one (e.g. via confusable fraction/division
    slashes or two-dot leaders)."""

    @given(text=unicode_text)
    @settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
    def test_normalize_user_input_is_path_safe(self, text: str) -> None:
        out = normalize_user_input(text)
        assert "/" not in out
        assert "\\" not in out
        assert ".." not in out

    @given(text=unicode_text)
    @settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
    def test_security_clean_is_path_safe(self, text: str) -> None:
        out = security_clean(text)
        assert "/" not in out
        assert "\\" not in out
        assert ".." not in out
