"""Tests for context-aware Persian transliteration.

Requires: data/persian_dict.bin (built from curated vocabulary)
"""

from __future__ import annotations

import pytest

from disarm import transliterate


def _has_persian_dict() -> bool:
    try:
        transliterate("\u0633\u0644\u0627\u0645", lang="fa", context=True)
        return True
    except Exception as e:
        # Only a missing dictionary is a skip condition; re-raise real bugs.
        if "not found" in str(e).lower():
            return False
        raise


needs_persian_dict = pytest.mark.skipif(
    not _has_persian_dict(),
    reason="Persian context dictionary not installed",
)


@needs_persian_dict
class TestPersianContextBasic:
    def test_context_free_unchanged(self):
        result = transliterate("\u06a9\u062a\u0627\u0628", lang="fa")
        assert result == "ktab"

    def test_context_aware_restores_vowels(self):
        result = transliterate("\u06a9\u062a\u0627\u0628", lang="fa", context=True)
        assert "e" in result  # ketab — kasra renders as 'e' in Persian

    def test_salam(self):
        result = transliterate("\u0633\u0644\u0627\u0645", lang="fa", context=True)
        assert "salam" in result.lower()

    def test_tehran(self):
        result = transliterate("\u062a\u0647\u0631\u0627\u0646", lang="fa", context=True)
        assert "tehran" in result.lower()

    def test_daneshgah(self):
        result = transliterate(
            "\u062f\u0627\u0646\u0634\u06af\u0627\u0647", lang="fa", context=True
        )
        assert "daneshgah" in result.lower()

    def test_khob(self):
        # damma → 'o' in Persian (not 'u')
        result = transliterate("\u062e\u0648\u0628", lang="fa", context=True)
        assert "kh" in result.lower()
        assert "o" in result.lower()

    def test_context_better_than_context_free(self):
        text = "\u06a9\u062a\u0627\u0628"  # ketab
        cf = transliterate(text, lang="fa", context=False)
        ca = transliterate(text, lang="fa", context=True)
        cf_vowels = sum(1 for c in cf if c in "aeiou")
        ca_vowels = sum(1 for c in ca if c in "aeiou")
        assert ca_vowels >= cf_vowels


@needs_persian_dict
class TestPersianVowelSystem:
    """Persian vowel mappings differ from Arabic: kasra=e, damma=o."""

    def test_dokhtar(self):
        # damma→o, not u
        result = transliterate("\u062f\u062e\u062a\u0631", lang="fa", context=True)
        assert "dokhtar" in result.lower()

    def test_pesar(self):
        # kasra→e, not i
        result = transliterate("\u067e\u0633\u0631", lang="fa", context=True)
        assert "pesar" in result.lower()

    def test_man(self):
        result = transliterate("\u0645\u0646", lang="fa", context=True)
        assert "man" in result.lower()

    def test_bozorg(self):
        result = transliterate("\u0628\u0632\u0631\u06af", lang="fa", context=True)
        assert "bozorg" in result.lower()


@needs_persian_dict
class TestPersianFallback:
    def test_ascii_passthrough(self):
        result = transliterate("hello", lang="fa", context=True)
        assert result == "hello"

    def test_unknown_word_falls_back(self):
        # "\u0633\u0644\u0627\u0645" (salam) is the first curated vocab entry, so it
        # never exercised the fallback. Use a synthetic token absent from the dict:
        # context-aware output must then equal context-free.
        unknown = "\u062a\u0633\u062a\u0627\u062c\u0633\u0631"
        assert transliterate(unknown, lang="fa", context=True) == transliterate(
            unknown, lang="fa", context=False
        )


@needs_persian_dict
class TestPersianList:
    def test_list_input(self):
        texts = ["\u0633\u0644\u0627\u0645", "\u06a9\u062a\u0627\u0628"]
        results = transliterate(texts, lang="fa", context=True)
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, str) for r in results)
