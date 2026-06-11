"""Tests for context-aware Arabic transliteration.

These tests verify that transliterate(text, context=True) produces
better output than context-free transliteration for Arabic text,
by restoring vowels from a dictionary-based lookup with bigram context.

Requires: pip install disarm[arabic] (or data/arabic_dict.bin present)
"""

from __future__ import annotations

import pytest

from disarm import transliterate


def _has_arabic_dict() -> bool:
    """Check if Arabic context dictionary is available."""
    try:
        transliterate("\u0643\u062a\u0628", context=True)
        return True
    except Exception as e:
        # Only a missing dictionary is a skip condition; re-raise real bugs.
        if "not found" in str(e).lower():
            return False
        raise


needs_arabic_dict = pytest.mark.skipif(
    not _has_arabic_dict(),
    reason="Arabic context dictionary not installed",
)


@needs_arabic_dict
class TestContextAwareBasic:
    """Context-aware transliteration restores vowels."""

    def test_context_free_unchanged(self):
        """Default behavior (context=False) must not change."""
        result = transliterate("\u0643\u062a\u0628")  # كتب
        assert result == "ktb"

    def test_context_aware_restores_vowels(self):
        """context=True should restore vowels from dictionary."""
        result = transliterate("\u0643\u062a\u0628", context=True)
        # Should contain vowels — not just "ktb"
        assert len(result) > 3
        assert any(c in result for c in "aeiou")

    def test_greeting(self):
        """Common greeting should be transliterated correctly."""
        result = transliterate(
            "\u0627\u0644\u0633\u0644\u0627\u0645 \u0639\u0644\u064a\u0643\u0645",
            context=True,
        )
        # Should contain recognizable romanization of "as-salaam alaikum"
        assert "salam" in result.lower() or "salaam" in result.lower()

    def test_bismillah(self):
        result = transliterate(
            "\u0628\u0633\u0645 \u0627\u0644\u0644\u0647",
            context=True,
        )
        assert "bismi" in result.lower() or "bism" in result.lower()

    def test_context_better_than_context_free(self):
        """Context-aware output should have more vowels than context-free."""
        text = "\u0627\u0644\u0633\u0644\u0627\u0645 \u0639\u0644\u064a\u0643\u0645"
        cf = transliterate(text, context=False)
        ca = transliterate(text, context=True)
        # Count vowels
        cf_vowels = sum(1 for c in cf if c in "aeiou")
        ca_vowels = sum(1 for c in ca if c in "aeiou")
        assert ca_vowels > cf_vowels


@needs_arabic_dict
class TestContextFallback:
    """Words not in dictionary should fall back to context-free."""

    def test_pure_ascii_passthrough(self):
        """ASCII text should pass through unchanged."""
        result = transliterate("hello world", context=True)
        assert result == "hello world"

    def test_mixed_arabic_latin(self):
        """Mixed text should handle both parts."""
        result = transliterate("hello \u0645\u0631\u062d\u0628\u0627", context=True)
        assert "hello" in result


@needs_arabic_dict
class TestContextList:
    """context=True works with list input."""

    def test_list_input(self):
        texts = ["\u0643\u062a\u0628", "\u0645\u0631\u062d\u0628\u0627"]
        results = transliterate(texts, context=True)
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, str) for r in results)
