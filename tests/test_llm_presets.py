"""Tests for the LLM-oriented policy profiles (issue #139).

``llm_guardrail`` hardens user/tool text against prompt-injection style
obfuscation (homoglyphs, zalgo, bidi overrides, invisibles) before it
reaches an LLM, while ``rag_ingest`` canonicalizes documents for retrieval
pipelines without destroying case.
"""

from __future__ import annotations

import unicodedata

import disarm


def test_profiles_listed() -> None:
    profiles = disarm.list_profiles()
    assert "llm_guardrail" in profiles
    assert "rag_ingest" in profiles


def test_llm_guardrail_step_order() -> None:
    steps = [name for name, _ in disarm.get_pipeline("llm_guardrail").steps]
    assert steps == [
        "normalize",
        "strip_zalgo",
        "strip_bidi",
        "demojize",
        "strip_accents",
        "confusables",
        "fold_case",
        "strip_control",
        "strip_zero_width",
        "collapse_whitespace",
    ]


def test_rag_ingest_step_order() -> None:
    steps = [name for name, _ in disarm.get_pipeline("rag_ingest").steps]
    assert steps == [
        "normalize",
        "strip_bidi",
        "strip_accents",
        "transliterate",
        "strip_control",
        "strip_zero_width",
        "collapse_whitespace",
    ]


def test_digit_invariance_litellm_t5_bug() -> None:
    # Digits must never be remapped to letters (the LiteLLM T5 model-name bug).
    result = disarm.get_pipeline("llm_guardrail")("gpt-4o")
    assert "4" in result
    assert result == "gpt-4o"


def test_rag_ingest_preserves_case() -> None:
    # rag_ingest has no fold_case step — case is meaningful for retrieval.
    result = disarm.get_pipeline("rag_ingest")("Hello World")
    assert result == "Hello World"
    assert "H" in result


def test_llm_guardrail_neutralizes_bidi_override() -> None:
    # U+202E (Right-to-Left Override) — written as an escape so the source
    # stays auditable and doesn't trip bidi-source security warnings.
    result = disarm.get_pipeline("llm_guardrail")("ad\u202emin")
    assert "\u202e" not in result


def test_llm_guardrail_neutralizes_zalgo() -> None:
    # "á" followed by extra stacked combining acute accents.
    result = disarm.get_pipeline("llm_guardrail")("á́́́b")
    assert all(not unicodedata.combining(c) for c in result)


def test_rag_ingest_strips_nul_byte() -> None:
    # The pgvector NUL-byte ingestion failure: \x00 must be gone.
    result = disarm.get_pipeline("rag_ingest")("a\x00b")
    assert "\x00" not in result


def test_llm_guardrail_resolves_cyrillic_homoglyph() -> None:
    # Cyrillic а (U+0430) in "pаypal" → ASCII.
    result = disarm.get_pipeline("llm_guardrail")("pаypal")
    assert result.isascii()


def test_llm_guardrail_folds_fullwidth_latin() -> None:
    # Fullwidth ａｂｃ → ASCII abc.
    result = disarm.get_pipeline("llm_guardrail")("ａｂｃ")
    assert result.isascii()
    assert result == "abc"


def test_llm_guardrail_strips_zero_width_joiner() -> None:
    result = disarm.get_pipeline("llm_guardrail")("a\u200db")
    assert "\u200d" not in result


def test_llm_guardrail_fullwidth_hello() -> None:
    # Representative full-output assertion.
    result = disarm.get_pipeline("llm_guardrail")("Ｈｅｌｌｏ")
    assert result == "hello"
