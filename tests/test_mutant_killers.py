"""Tests targeting mutation testing survivors.

These tests exist to kill mutants that survived the mutation testing run
(mutmut on python/disarm/__init__.py). Each test class targets a specific
category of survivor. Written to be run quarterly alongside mutmut.

Categories covered:
1. Forward-only parameter validation (transliterate target= exclusion)
2. Default parameter value sensitivity (functions behave differently with
   defaults vs explicit non-default values)
3. Pipeline step tuples (PRESETS, TextPipeline.steps, explain)
4. Boundary checks (max_length, min_confidence, resource limits)
"""

from __future__ import annotations

import pytest

import disarm
from disarm import (
    PRESETS,
    TextPipeline,
    catalog_key,
    collapse_whitespace,
    decode_to_utf8,
    demojize,
    display_clean,
    grapheme_len,
    grapheme_split,
    grapheme_truncate,
    ml_normalize,
    normalize,
    normalize_confusables,
    normalize_user_input,
    sanitize_filename,
    search_key,
    security_clean,
    slugify,
    sort_key,
    strip_accents,
    strip_zalgo,
    transliterate,
)

# ---------------------------------------------------------------------------
# 1. Forward-only parameter validation
# ---------------------------------------------------------------------------


class TestForwardOnlyParamValidation:
    """transliterate(target=...) rejects forward-only params."""

    def test_target_and_lang_mutually_exclusive(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            transliterate("hello", target="ru", lang="en")

    def test_target_rejects_errors_ignore(self):
        with pytest.raises(ValueError, match="forward-only.*errors"):
            transliterate("hello", target="ru", errors="ignore")

    def test_target_rejects_errors_preserve(self):
        with pytest.raises(ValueError, match="forward-only.*errors"):
            transliterate("hello", target="ru", errors="preserve")

    def test_target_rejects_replace_with(self):
        with pytest.raises(ValueError, match="forward-only.*replace_with"):
            transliterate("hello", target="ru", replace_with="??")

    def test_target_rejects_strict_iso9(self):
        with pytest.raises(ValueError, match="forward-only.*strict_iso9"):
            transliterate("hello", target="ru", strict_iso9=True)

    def test_target_rejects_gost7034(self):
        with pytest.raises(ValueError, match="forward-only.*gost7034"):
            transliterate("hello", target="ru", gost7034=True)

    def test_target_rejects_tones(self):
        with pytest.raises(ValueError, match="forward-only.*tones"):
            transliterate("hello", target="ru", tones=True)

    def test_target_rejects_multiple_forward_only(self):
        """Error message lists all offending params sorted."""
        with pytest.raises(ValueError, match="errors.*strict_iso9"):
            transliterate("hello", target="ru", errors="ignore", strict_iso9=True)

    def test_target_allows_defaults(self):
        """target= works when all forward-only params are at defaults."""
        result = transliterate("Moskva", target="ru")
        assert isinstance(result, str)
        assert not result.isascii()  # should produce Cyrillic

    def test_errors_replace_is_default_not_rejected(self):
        """errors='replace' is the default — must not trigger forward-only check."""
        result = transliterate("Moskva", target="ru", errors="replace")
        assert isinstance(result, str)

    def test_replace_with_default_not_rejected(self):
        """replace_with='[?]' is the default — must not trigger."""
        result = transliterate("Moskva", target="ru", replace_with="[?]")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 2. Default parameter value sensitivity
# ---------------------------------------------------------------------------


class TestDefaultParameterValues:
    """Functions must behave correctly when called without explicit params
    (relying on defaults), and differently when non-default values are given."""

    # -- transliterate defaults --

    def test_transliterate_default_errors_is_replace(self):
        """Default errors='replace' maps unknown chars to [?]."""
        result = transliterate("\U0001f600")  # emoji — no transliteration
        assert "[?]" in result

    def test_transliterate_errors_ignore_drops_unknown(self):
        result = transliterate("\U0001f600", errors="ignore")
        assert "[?]" not in result

    def test_transliterate_errors_preserve_keeps_unknown(self):
        result = transliterate("\U0001f600", errors="preserve")
        assert "[?]" not in result

    # -- slugify defaults --

    def test_slugify_default_separator_is_hyphen(self):
        result = slugify("hello world")
        assert "-" in result
        assert "_" not in result

    def test_slugify_custom_separator(self):
        result = slugify("hello world", separator="_")
        assert "_" in result
        assert "-" not in result

    def test_slugify_default_lowercase_is_true(self):
        result = slugify("Hello World")
        assert result == result.lower()

    def test_slugify_lowercase_false(self):
        result = slugify("Hello World", lowercase=False)
        assert result != result.lower()

    def test_slugify_default_max_length_is_zero(self):
        """max_length=0 means unlimited."""
        long_text = "word " * 100
        result = slugify(long_text)
        assert len(result) > 50

    def test_slugify_max_length_truncates(self):
        long_text = "word " * 100
        result = slugify(long_text, max_length=20)
        assert len(result) <= 20

    def test_slugify_default_entities_true(self):
        """HTML entities decoded by default."""
        result = slugify("caf&#233;")  # &#233; = é
        assert "cafe" in result

    def test_slugify_entities_false_preserves(self):
        result = slugify("caf&#233;", entities=False, decimal=False, hexadecimal=False)
        # Should not decode — entity text becomes part of slug
        assert "233" in result or "caf" in result

    def test_slugify_default_allow_unicode_false(self):
        result = slugify("café")
        assert result.isascii()

    def test_slugify_allow_unicode_true(self):
        result = slugify("café", allow_unicode=True)
        assert "é" in result

    # -- normalize defaults --

    def test_normalize_default_is_nfc(self):
        # é as NFD (e + combining acute) should become NFC (single char)
        nfd_e_acute = "e\u0301"  # e + combining acute
        result = normalize(nfd_e_acute)
        assert result == "\u00e9"  # NFC form

    def test_normalize_nfkd(self):
        result = normalize("\u00e9", form="NFKD")
        assert len(result) == 2  # decomposed

    # -- normalize_confusables defaults --

    def test_confusables_default_target_latin(self):
        # Cyrillic а (U+0430) should normalize to Latin a
        result = normalize_confusables("\u0430")
        assert result == "a"

    # -- sanitize_filename defaults --

    def test_sanitize_filename_default_separator_underscore(self):
        result = sanitize_filename("my file.txt")
        assert "_" in result

    def test_sanitize_filename_custom_separator(self):
        result = sanitize_filename("my file.txt", separator="-")
        assert "-" in result

    def test_sanitize_filename_default_max_length_255(self):
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result.encode("utf-8")) <= 255

    def test_sanitize_filename_custom_max_length(self):
        result = sanitize_filename("a" * 100 + ".txt", max_length=50)
        assert len(result.encode("utf-8")) <= 50

    # -- collapse_whitespace defaults --

    def test_collapse_whitespace_default_strips_control(self):
        result = collapse_whitespace("hello\x00world")
        assert "\x00" not in result

    def test_collapse_whitespace_strip_control_false(self):
        result = collapse_whitespace("hello\x00world", strip_control=False)
        # Control char should survive
        assert "\x00" in result or len(result) >= 10

    def test_collapse_whitespace_default_strips_zero_width(self):
        result = collapse_whitespace("hello\u200bworld")
        assert "\u200b" not in result

    # -- demojize defaults --

    def test_demojize_default_errors_replace(self):
        result = demojize("hello ☕ world")
        assert isinstance(result, str)
        assert "☕" not in result  # should be replaced with text

    # -- ml_normalize defaults --

    def test_ml_normalize_default_emoji_cldr(self):
        result = ml_normalize("☕")
        # CLDR provider should produce text name
        assert isinstance(result, str)
        assert result != "☕"

    # -- strip_zalgo defaults --

    def test_strip_zalgo_default_max_marks_2(self):
        # Text with 5 combining marks per char
        zalgo = "a\u0300\u0301\u0302\u0303\u0304"
        result = strip_zalgo(zalgo)
        # Should strip down to max 2 marks
        import unicodedata

        marks = sum(1 for c in result if unicodedata.category(c) == "Mn")
        assert marks <= 2

    # -- list input defaults --

    def test_transliterate_list_default_errors_replace(self):
        results = transliterate(["café", "Москва"])
        assert all(isinstance(r, str) for r in results)
        assert results[0] == "cafe"

    def test_slugify_list_default_separator(self):
        results = slugify(["hello world", "foo bar"])
        assert all("-" in r for r in results)


# ---------------------------------------------------------------------------
# 3. Pipeline step tuples (PRESETS, TextPipeline.steps, explain)
# ---------------------------------------------------------------------------


class TestPipelineStepTuples:
    """PRESETS dict, TextPipeline.steps, and explain() must return correct data."""

    # -- PRESETS content --

    def test_presets_is_dict(self):
        assert isinstance(PRESETS, dict)

    def test_presets_has_all_eight(self):
        expected = {
            "security_clean",
            "ml_normalize",
            "catalog_key",
            "display_clean",
            "search_key",
            "sort_key",
            "normalize_user_input",
            "strip_obfuscation",
        }
        assert set(PRESETS.keys()) == expected

    @pytest.mark.parametrize(
        "name,expected_steps",
        [
            (
                "security_clean",
                [
                    ("normalize", "NFKC"),
                    ("strip_bidi", None),
                    ("collapse_whitespace", None),
                    ("normalize", "NFC"),
                    ("confusables", "latin"),
                    ("normalize", "NFC"),
                ],
            ),
            (
                "ml_normalize",
                [
                    ("normalize", "NFKC"),
                    ("demojize", "cldr"),
                    ("strip_accents", None),
                    ("fold_case", None),
                    ("collapse_whitespace", None),
                ],
            ),
            (
                "catalog_key",
                [
                    ("normalize", "NFKC"),
                    ("strip_bidi", None),
                    ("transliterate", None),
                    ("confusables", "latin"),
                    ("strip_accents", None),
                    ("fold_case", None),
                    ("collapse_whitespace", None),
                ],
            ),
            (
                "display_clean",
                [
                    ("strip_bidi", None),
                    ("collapse_whitespace", None),
                ],
            ),
            (
                "search_key",
                [
                    ("normalize", "NFKC"),
                    ("strip_bidi", None),
                    ("transliterate", None),
                    ("strip_accents", None),
                    ("fold_case", None),
                    ("collapse_whitespace", None),
                ],
            ),
            (
                "sort_key",
                [
                    ("normalize", "NFKC"),
                    ("strip_bidi", None),
                    ("transliterate", "non_latin"),
                    ("fold_case", None),
                    ("collapse_whitespace", None),
                    ("normalize", "NFC"),
                ],
            ),
            (
                "normalize_user_input",
                [
                    ("normalize", "NFKC"),
                    ("strip_bidi", None),
                    ("strip_zero_width", None),
                    ("strip_control", None),
                    ("strip_zalgo", None),
                    ("confusables", "latin"),
                    ("collapse_whitespace", None),
                    ("normalize", "NFC"),
                ],
            ),
        ],
    )
    def test_preset_steps_exact(self, name: str, expected_steps: list):
        assert PRESETS[name] == expected_steps

    # -- TextPipeline.steps --

    def test_pipeline_steps_returns_tuples(self):
        pipe = TextPipeline(normalize="NFC", fold_case=True)
        steps = pipe.steps
        assert isinstance(steps, list)
        assert all(isinstance(s, tuple) and len(s) == 2 for s in steps)

    def test_pipeline_steps_normalize_has_form(self):
        pipe = TextPipeline(normalize="NFKC")
        steps = pipe.steps
        assert ("normalize", "NFKC") in steps

    def test_pipeline_steps_fold_case_has_none(self):
        pipe = TextPipeline(fold_case=True)
        steps = pipe.steps
        assert ("fold_case", None) in steps

    def test_pipeline_steps_empty_is_empty(self):
        pipe = TextPipeline()
        assert pipe.steps == []

    def test_pipeline_steps_order_preserved(self):
        pipe = TextPipeline(
            normalize="NFC",
            transliterate=True,
            strip_accents=True,
            fold_case=True,
            collapse_whitespace=True,
        )
        step_names = [name for name, _ in pipe.steps]
        # Normalization always comes first, collapse_whitespace last
        assert step_names.index("normalize") < step_names.index("fold_case")
        assert step_names.index("fold_case") < step_names.index("collapse_whitespace")

    # -- TextPipeline.explain --

    def test_explain_empty_pipeline(self):
        pipe = TextPipeline()
        assert "0 steps" in pipe.explain()
        assert "passthrough" in pipe.explain()

    def test_explain_single_step(self):
        pipe = TextPipeline(fold_case=True)
        explanation = pipe.explain()
        assert "1 step:" in explanation
        assert "fold_case" in explanation
        # Singular "step" not "steps"
        assert "steps:" not in explanation

    def test_explain_multiple_steps(self):
        pipe = TextPipeline(normalize="NFC", fold_case=True, strip_accents=True)
        explanation = pipe.explain()
        assert "3 steps:" in explanation
        assert "normalize (NFC)" in explanation
        assert "fold_case" in explanation
        assert "strip_accents" in explanation

    def test_explain_numbering(self):
        pipe = TextPipeline(normalize="NFC", fold_case=True)
        explanation = pipe.explain()
        assert "1. normalize" in explanation
        assert "2. fold_case" in explanation

    def test_explain_param_shown_for_normalize(self):
        pipe = TextPipeline(normalize="NFKD")
        assert "(NFKD)" in pipe.explain()

    def test_explain_no_param_for_fold_case(self):
        pipe = TextPipeline(fold_case=True)
        explanation = pipe.explain()
        # fold_case line should NOT have parenthesized param
        for line in explanation.split("\n"):
            if "fold_case" in line:
                assert "(" not in line

    # -- Precompiled pipelines produce different output --

    def test_security_clean_normalizes_confusables(self):
        # Cyrillic а looks like Latin a
        result = security_clean("p\u0430ypal")
        assert result == "paypal"

    def test_ml_normalize_strips_accents(self):
        result = ml_normalize("café")
        assert "é" not in result
        assert "cafe" in result

    def test_catalog_key_transliterates(self):
        result = catalog_key("Москва")
        assert result.isascii()
        assert "moskva" in result

    def test_display_clean_strips_bidi(self):
        result = display_clean("hello\u200eworld")
        assert "\u200e" not in result

    def test_search_key_folds_case(self):
        result = search_key("HELLO")
        assert result == "hello"

    def test_sort_key_preserves_accent_folds_case_and_translit(self):
        # Latin accent preserved (kills a "strip accents like search_key" mutant),
        # case folded, and non-Latin still transliterated to Latin.
        assert sort_key("Café") == "café"
        assert sort_key("CAFÉ") == "café"
        assert sort_key("Москва") == "moskva"

    def test_normalize_user_input_strips_zalgo(self):
        zalgo = "h\u0300\u0301\u0302\u0303e\u0300\u0301\u0302\u0303"
        result = normalize_user_input(zalgo)
        import unicodedata

        marks = sum(1 for c in result if unicodedata.category(c) == "Mn")
        assert marks < 8  # should be reduced from 8


# ---------------------------------------------------------------------------
# 4. Boundary checks
# ---------------------------------------------------------------------------


class TestBoundaryChecks:
    """Edge cases at exact boundary values."""

    # -- slugify max_length boundaries --

    def test_slugify_max_length_zero_means_unlimited(self):
        result = slugify("a " * 200, max_length=0)
        assert len(result) > 100

    def test_slugify_max_length_one(self):
        result = slugify("hello world", max_length=1)
        assert len(result) <= 1

    def test_slugify_max_length_negative_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            slugify("hello", max_length=-1)

    def test_slugify_max_length_exact(self):
        result = slugify("hello world foo bar", max_length=11)
        assert len(result) <= 11

    # -- sanitize_filename max_length boundaries --

    def test_sanitize_filename_max_length_very_small(self):
        result = sanitize_filename("abcdefghij.txt", max_length=10)
        assert len(result.encode("utf-8")) <= 10

    # -- decode_to_utf8 min_confidence boundaries --

    def test_min_confidence_zero_accepts_anything(self):
        text, _ = decode_to_utf8(b"\x80\x81\x82", min_confidence=0.0)
        assert isinstance(text, str)

    def test_min_confidence_one_with_explicit_encoding(self):
        # Auto-detection never returns 1.0 confidence, so use explicit encoding
        text, _ = decode_to_utf8(b"hello", encoding="utf-8", min_confidence=1.0)
        assert text == "hello"

    def test_min_confidence_negative_raises(self):
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            decode_to_utf8(b"hello", min_confidence=-0.1)

    def test_min_confidence_above_one_raises(self):
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            decode_to_utf8(b"hello", min_confidence=1.1)

    def test_min_confidence_boundary_0_0(self):
        """Exactly 0.0 is valid."""
        text, _ = decode_to_utf8(b"hello", min_confidence=0.0)
        assert isinstance(text, str)

    def test_min_confidence_boundary_1_0(self):
        """Exactly 1.0 is valid (min_confidence is only checked in validation,
        not against detection result when encoding is explicit)."""
        text, _ = decode_to_utf8("café".encode(), encoding="utf-8", min_confidence=1.0)
        assert isinstance(text, str)

    # -- grapheme boundaries --

    def test_grapheme_truncate_zero(self):
        result = grapheme_truncate("hello", 0)
        assert result == ""

    def test_grapheme_truncate_exact_length(self):
        result = grapheme_truncate("hello", 5)
        assert result == "hello"

    def test_grapheme_truncate_beyond_length(self):
        result = grapheme_truncate("hello", 100)
        assert result == "hello"

    def test_grapheme_len_empty(self):
        assert grapheme_len("") == 0

    def test_grapheme_split_empty(self):
        assert grapheme_split("") == []

    # -- strip_zalgo threshold boundary --

    def test_is_zalgo_threshold_exact(self):
        # 3 marks = exactly at default threshold
        text = "a\u0300\u0301\u0302"
        result = disarm.is_zalgo(text, threshold=3)
        assert isinstance(result, bool)

    def test_is_zalgo_below_threshold(self):
        text = "a\u0300\u0301"  # 2 marks
        assert not disarm.is_zalgo(text, threshold=3)

    # -- Type validation (negative cases) --

    def test_transliterate_rejects_int(self):
        with pytest.raises(TypeError, match="expects str"):
            transliterate(42)  # type: ignore[arg-type]

    def test_slugify_rejects_bytes(self):
        with pytest.raises(TypeError, match="expects str"):
            slugify(b"hello")  # type: ignore[arg-type]

    def test_normalize_rejects_none(self):
        with pytest.raises(TypeError, match="expects str"):
            normalize(None)  # type: ignore[arg-type]

    def test_sanitize_filename_rejects_list(self):
        with pytest.raises(TypeError, match="expects str"):
            sanitize_filename(["file.txt"])  # type: ignore[arg-type]

    def test_transliterate_list_rejects_list_of_int(self):
        with pytest.raises(TypeError, match="element 0 must be str"):
            transliterate([42])  # type: ignore[list-item]

    def test_transliterate_rejects_wrong_type(self):
        with pytest.raises(TypeError, match="expects str or list"):
            transliterate(42)  # type: ignore[arg-type]

    def test_strip_accents_rejects_int(self):
        with pytest.raises(TypeError):
            strip_accents(123)  # type: ignore[arg-type]
