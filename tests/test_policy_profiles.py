"""Tests for policy profiles API (get_pipeline / list_profiles)."""

import pytest

from translit import (
    TextPipeline,
    TranslitError,
    get_pipeline,
    list_profiles,
)


class TestListProfiles:
    def test_returns_sorted_list(self):
        profiles = list_profiles()
        assert profiles == sorted(profiles)
        assert len(profiles) >= 5

    def test_known_profiles_present(self):
        profiles = list_profiles()
        assert "scholarly_cyrillic_iso9" in profiles
        assert "library_catalog_key_eu" in profiles
        assert "web_input_sanitize" in profiles
        assert "ml_corpus_normalize" in profiles
        assert "search_index" in profiles


class TestGetPipeline:
    def test_returns_text_pipeline(self):
        pipe = get_pipeline("scholarly_cyrillic_iso9")
        assert isinstance(pipe, TextPipeline)

    def test_unknown_profile_raises(self):
        with pytest.raises(TranslitError, match="Unknown profile"):
            get_pipeline("nonexistent_profile")

    def test_each_profile_creates_valid_pipeline(self):
        for name in list_profiles():
            pipe = get_pipeline(name)
            assert isinstance(pipe, TextPipeline)

    def test_each_profile_processes_text(self):
        for name in list_profiles():
            pipe = get_pipeline(name)
            result = pipe("Hello World")
            assert isinstance(result, str)
            assert len(result) > 0

    def test_fresh_instance_each_call(self):
        p1 = get_pipeline("ml_corpus_normalize")
        p2 = get_pipeline("ml_corpus_normalize")
        assert p1 is not p2


class TestProfileBehavior:
    def test_scholarly_cyrillic_iso9(self):
        pipe = get_pipeline("scholarly_cyrillic_iso9")
        result = pipe("Москва")
        assert isinstance(result, str)
        assert result.isascii() or any(c.isalpha() for c in result)

    def test_library_catalog_key_eu(self):
        pipe = get_pipeline("library_catalog_key_eu")
        result = pipe("München — Bayern")
        assert result.isascii()
        assert "muenchen" in result or "munchen" in result

    def test_web_input_sanitize(self):
        pipe = get_pipeline("web_input_sanitize")
        result = pipe("  Hello   World  ")
        assert result == "Hello World"

    def test_ml_corpus_normalize(self):
        pipe = get_pipeline("ml_corpus_normalize")
        result = pipe("Héllo WÖRLD")
        assert result == "hello world"

    def test_search_index(self):
        pipe = get_pipeline("search_index")
        result = pipe("München")
        assert result.isascii()
        assert result.islower()


class TestProfileStepsLock:
    """Pin the exact step lists of the key profiles so the core registry (#229)
    cannot silently change. Steps are reported in execution order (STEP_ORDER)."""

    def test_llm_guardrail_steps(self):
        assert get_pipeline("llm_guardrail").steps == [
            ("normalize", "NFKC"),
            ("strip_zalgo", "0"),
            ("strip_bidi", None),
            ("demojize", None),
            ("strip_accents", None),
            ("confusables", "latin"),
            ("fold_case", None),
            ("strip_control", None),
            ("strip_zero_width", None),
            ("collapse_whitespace", None),
        ]

    def test_rag_ingest_steps(self):
        assert get_pipeline("rag_ingest").steps == [
            ("normalize", "NFKC"),
            ("strip_bidi", None),
            ("strip_accents", None),
            ("transliterate", None),
            ("strip_control", None),
            ("strip_zero_width", None),
            ("collapse_whitespace", None),
        ]
