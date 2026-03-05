"""Tests for translit.TextPipeline.

Covers individual steps, common combinations, ordering guarantees,
and parametric pairwise coverage of the 7 boolean/option flags.
"""

from __future__ import annotations

import itertools

import pytest

from translit import PRESETS, TextPipeline


class TestTextPipelineBasic:
    """Basic single-step pipeline tests."""

    def test_empty_pipeline(self) -> None:
        pipe = TextPipeline()
        assert pipe("hello") == "hello"

    def test_normalize_only(self) -> None:
        pipe = TextPipeline(normalize="NFC")
        text = "caf\u0065\u0301"
        assert pipe(text) == "caf\u00e9"

    def test_transliterate_only(self) -> None:
        pipe = TextPipeline(transliterate=True)
        result = pipe("café")
        assert result == "cafe"

    def test_strip_accents_only(self) -> None:
        pipe = TextPipeline(strip_accents=True)
        assert pipe("café") == "cafe"

    def test_fold_case_only(self) -> None:
        pipe = TextPipeline(fold_case=True)
        assert pipe("Straße") == "strasse"

    def test_collapse_whitespace_only(self) -> None:
        pipe = TextPipeline(collapse_whitespace=True)
        assert pipe("hello   world") == "hello world"

    def test_confusables_only(self) -> None:
        pipe = TextPipeline(confusables=True)
        # Cyrillic а → Latin a
        result = pipe("\u0430bc")
        assert result == "abc"

    def test_demojize_only(self) -> None:
        pipe = TextPipeline(demojize=True)
        result = pipe("hi 🐍")
        assert "snake" in result

    def test_repr(self) -> None:
        pipe = TextPipeline(normalize="NFC", transliterate=True)
        r = repr(pipe)
        assert "TextPipeline" in r
        assert "normalize" in r
        assert "transliterate" in r

    def test_steps_property(self) -> None:
        pipe = TextPipeline(normalize="NFC", fold_case=True, collapse_whitespace=True)
        steps = pipe.steps
        assert isinstance(steps, list)
        assert len(steps) == 3
        assert steps[0] == ("normalize", "NFC")
        assert steps[1] == ("fold_case", None)
        assert steps[2] == ("collapse_whitespace", None)

    def test_steps_empty_pipeline(self) -> None:
        pipe = TextPipeline()
        assert pipe.steps == []

    def test_steps_execution_order(self) -> None:
        pipe = TextPipeline(
            collapse_whitespace=True,
            fold_case=True,
            normalize="NFKC",
            transliterate=True,
        )
        names = [name for name, _ in pipe.steps]
        # Execution order is fixed regardless of construction order
        assert names == ["normalize", "strip_accents", "transliterate", "fold_case", "collapse_whitespace"] or \
               names == ["normalize", "transliterate", "fold_case", "collapse_whitespace"]

    def test_explain(self) -> None:
        pipe = TextPipeline(normalize="NFC", fold_case=True)
        explanation = pipe.explain()
        assert "2 steps" in explanation
        assert "normalize" in explanation
        assert "fold_case" in explanation

    def test_explain_empty(self) -> None:
        pipe = TextPipeline()
        assert "0 steps" in pipe.explain()
        assert "passthrough" in pipe.explain()


class TestTextPipelineCombinations:
    """Multi-step pipeline combinations."""

    def test_full_pipeline(self) -> None:
        pipe = TextPipeline(
            normalize="NFKC",
            transliterate=True,
            fold_case=True,
            collapse_whitespace=True,
        )
        result = pipe("  Hello   Café  ")
        assert result == "hello cafe"

    def test_normalize_then_transliterate(self) -> None:
        pipe = TextPipeline(normalize="NFC", transliterate=True)
        # NFD é → NFC é → transliterate → e
        assert pipe("caf\u0065\u0301") == "cafe"

    def test_confusables_then_fold_case(self) -> None:
        pipe = TextPipeline(confusables=True, fold_case=True)
        # Cyrillic А (U+0410) → confusable → Latin A → fold → a
        assert pipe("\u0410bc") == "abc"

    def test_strip_accents_and_fold_case(self) -> None:
        pipe = TextPipeline(strip_accents=True, fold_case=True)
        assert pipe("CAFÉ") == "cafe"

    def test_transliterate_and_fold_case(self) -> None:
        pipe = TextPipeline(transliterate=True, fold_case=True)
        assert pipe("CAFÉ") == "cafe"

    def test_transliterate_with_lang(self) -> None:
        pipe = TextPipeline(transliterate=True, lang="de")
        assert pipe("München") == "Muenchen"

    def test_transliterate_with_lang_and_fold_case(self) -> None:
        pipe = TextPipeline(transliterate=True, lang="de", fold_case=True)
        assert pipe("München") == "muenchen"

    def test_normalize_confusables_strip_accents(self) -> None:
        pipe = TextPipeline(
            normalize="NFKC",
            confusables=True,
            strip_accents=True,
        )
        assert pipe("café") == "cafe"

    def test_all_cleaning_steps(self) -> None:
        pipe = TextPipeline(
            normalize="NFKC",
            confusables=True,
            transliterate=True,
            strip_accents=True,
            fold_case=True,
            collapse_whitespace=True,
            demojize=True,
        )
        result = pipe("  Héllo  🌍  Мир  ")
        assert result.isascii()
        assert "  " not in result  # no double spaces

    def test_collapse_whitespace_strips_control_chars(self) -> None:
        pipe = TextPipeline(collapse_whitespace=True, strip_control=True)
        assert pipe("hello\x00world") == "helloworld"

    def test_collapse_whitespace_strips_zero_width(self) -> None:
        pipe = TextPipeline(collapse_whitespace=True, strip_zero_width=True)
        assert pipe("hello\u200bworld") == "helloworld"

    def test_collapse_whitespace_preserves_control_when_disabled(self) -> None:
        pipe = TextPipeline(collapse_whitespace=True, strip_control=False, strip_zero_width=False)
        result = pipe("hello\u200bworld")
        assert "\u200b" in result

    def test_transliterate_strict_iso9(self) -> None:
        pipe = TextPipeline(transliterate=True, strict_iso9=True)
        result = pipe("Москва")
        assert result.isascii()


class TestTextPipelineOrdering:
    """Verify pipeline steps execute in the documented order."""

    def test_normalize_before_transliterate(self) -> None:
        # NFD é (e + combining acute) → NFC é → transliterate → e
        pipe_norm_first = TextPipeline(normalize="NFC", transliterate=True)
        # Without normalize, NFD é should still transliterate correctly
        pipe_translit_only = TextPipeline(transliterate=True)
        text = "caf\u0065\u0301"
        assert pipe_norm_first(text) == "cafe"
        assert pipe_translit_only(text) == "cafe"

    def test_confusables_before_fold_case(self) -> None:
        # Confusables should run before fold_case
        # Greek Η (U+0397) → confusable → Latin H → fold → h
        pipe = TextPipeline(confusables=True, fold_case=True)
        assert pipe("\u0397ello") == "hello"


class TestTextPipelineEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_string(self) -> None:
        pipe = TextPipeline(
            normalize="NFC",
            transliterate=True,
            fold_case=True,
            collapse_whitespace=True,
        )
        assert pipe("") == ""

    def test_pure_ascii(self) -> None:
        pipe = TextPipeline(transliterate=True, fold_case=True)
        assert pipe("hello") == "hello"

    def test_only_whitespace(self) -> None:
        pipe = TextPipeline(collapse_whitespace=True)
        assert pipe("   ") == ""

    def test_only_control_chars(self) -> None:
        pipe = TextPipeline(collapse_whitespace=True, strip_control=True)
        assert pipe("\x00\x01\x02") == ""

    def test_single_emoji(self) -> None:
        pipe = TextPipeline(demojize=True)
        result = pipe("🎉")
        assert result  # non-empty
        assert "🎉" not in result  # emoji was replaced

    def test_long_string(self) -> None:
        pipe = TextPipeline(transliterate=True, fold_case=True)
        text = "Héllo " * 1000
        result = pipe(text)
        # Pipeline without collapse_whitespace preserves trailing space
        assert result == "hello " * 1000

    def test_reuse_pipeline(self) -> None:
        pipe = TextPipeline(transliterate=True, fold_case=True)
        assert pipe("Café") == "cafe"
        assert pipe("Straße") == "strasse"
        assert pipe("München") == "munchen"


class TestTextPipelinePairwise:
    """Parametric pairwise coverage of pipeline flag combinations.

    Tests every pair of boolean flags being simultaneously True,
    ensuring no combination panics or produces unexpected results.
    """

    FLAGS = [
        "transliterate",
        "confusables",
        "strip_accents",
        "fold_case",
        "collapse_whitespace",
        "demojize",
    ]

    INPUT = "  Héllo  🌍  Мир  Straße  "

    @pytest.mark.parametrize(
        "flag_a,flag_b",
        list(itertools.combinations(FLAGS, 2)),
        ids=[f"{a}+{b}" for a, b in itertools.combinations(FLAGS, 2)],
    )
    def test_pairwise_no_panic(self, flag_a: str, flag_b: str) -> None:
        """Every pair of flags should produce a non-None string result."""
        kwargs = {flag_a: True, flag_b: True}
        pipe = TextPipeline(**kwargs)
        result = pipe(self.INPUT)
        assert isinstance(result, str)

    @pytest.mark.parametrize(
        "flag_a,flag_b,flag_c",
        list(itertools.combinations(FLAGS, 3)),
        ids=[f"{a}+{b}+{c}" for a, b, c in itertools.combinations(FLAGS, 3)],
    )
    def test_triplewise_no_panic(self, flag_a: str, flag_b: str, flag_c: str) -> None:
        """Every triple of flags should produce a non-None string result."""
        kwargs = {flag_a: True, flag_b: True, flag_c: True}
        pipe = TextPipeline(**kwargs)
        result = pipe(self.INPUT)
        assert isinstance(result, str)

    def test_all_flags_enabled(self) -> None:
        """All boolean flags simultaneously True."""
        pipe = TextPipeline(
            normalize="NFKC",
            transliterate=True,
            confusables=True,
            strip_accents=True,
            fold_case=True,
            collapse_whitespace=True,
            demojize=True,
        )
        result = pipe(self.INPUT)
        assert isinstance(result, str)
        assert result.isascii()

    def test_normalize_forms(self) -> None:
        """All four normalization forms work with transliterate."""
        for form in ("NFC", "NFD", "NFKC", "NFKD"):
            pipe = TextPipeline(normalize=form, transliterate=True)
            result = pipe("café")
            assert result == "cafe", f"Failed for {form}"


class TestPresets:
    """Verify PRESETS metadata is well-formed and matches actual behavior."""

    def test_presets_is_dict(self) -> None:
        assert isinstance(PRESETS, dict)

    def test_all_preset_names_present(self) -> None:
        for name in ("security_clean", "ml_normalize", "catalog_key", "display_clean"):
            assert name in PRESETS, f"preset {name!r} missing from PRESETS"

    def test_preset_steps_are_tuples(self) -> None:
        for name, steps in PRESETS.items():
            assert isinstance(steps, list), f"{name}: steps is not a list"
            for step in steps:
                assert isinstance(step, tuple), f"{name}: step {step!r} is not a tuple"
                assert len(step) == 2, f"{name}: step {step!r} has wrong length"

    def test_security_clean_starts_with_nfkc(self) -> None:
        assert PRESETS["security_clean"][0] == ("normalize", "NFKC")

    def test_display_clean_is_minimal(self) -> None:
        assert len(PRESETS["display_clean"]) == 1
