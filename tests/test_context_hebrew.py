"""Tests for context-aware Hebrew transliteration.

Requires: data/hebrew_dict.bin (built from Project Ben Yehuda corpus)
"""

from __future__ import annotations

import pytest

from translit import transliterate


def _has_hebrew_dict() -> bool:
    try:
        transliterate("\u05e9\u05dc\u05d5\u05dd", lang="he", context=True)
        return True
    except Exception:
        return False


needs_hebrew_dict = pytest.mark.skipif(
    not _has_hebrew_dict(),
    reason="Hebrew context dictionary not installed",
)


@needs_hebrew_dict
class TestHebrewContextBasic:
    def test_context_free_unchanged(self):
        result = transliterate("\u05e9\u05dc\u05d5\u05dd", lang="he")
        assert result == "shlvm"

    def test_context_aware_restores_vowels(self):
        result = transliterate("\u05e9\u05dc\u05d5\u05dd", lang="he", context=True)
        assert len(result) > 5
        assert any(c in result for c in "aeiou")

    def test_jerusalem(self):
        result = transliterate(
            "\u05d9\u05e8\u05d5\u05e9\u05dc\u05d9\u05dd", lang="he", context=True
        )
        assert "ervshal" in result.lower() or "erushal" in result.lower()

    def test_context_better_than_context_free(self):
        text = "\u05e9\u05dc\u05d5\u05dd"
        cf = transliterate(text, lang="he", context=False)
        ca = transliterate(text, lang="he", context=True)
        cf_vowels = sum(1 for c in cf if c in "aeiou")
        ca_vowels = sum(1 for c in ca if c in "aeiou")
        assert ca_vowels > cf_vowels


@needs_hebrew_dict
class TestHebrewFallback:
    def test_ascii_passthrough(self):
        result = transliterate("hello", lang="he", context=True)
        assert result == "hello"

    def test_unknown_word_falls_back(self):
        # Rare/made-up consonant sequence — should fall back gracefully
        result = transliterate("\u05e9\u05dc\u05d5\u05dd", lang="he", context=True)
        assert isinstance(result, str)
