"""Bug: normalize_confusables() before transliterate() corrupts Cyrillic text.

When confusables runs first on non-Latin text, it replaces SOME Cyrillic
characters with Latin lookalikes (о→o, с→c, а→a) but leaves others as
Cyrillic (в, л, ч). transliterate() then transliterates the remaining
Cyrillic but passes through the already-Latin characters, producing
gibberish.

The fix is twofold:
1. TextPipeline must reject confusables=True + transliterate=True unless
   the step order is correct (transliterate before confusables).
2. Document the constraint clearly.
"""

from __future__ import annotations

import pytest

from translit import (
    TextPipeline,
    catalog_key,
    normalize_confusables,
    transliterate,
)


class TestConfusableBeforeTransliterateProducesGibberish:
    """Demonstrate the problem: confusables → transliterate = broken."""

    def test_catalog_key_produces_correct_output(self):
        """catalog_key does it right: transliterate → confusables."""
        result = catalog_key("Москва лучший город")
        assert "moskva" in result
        assert "[?" not in result

    def test_manual_wrong_order_produces_mixed_script(self):
        """Confusables first creates mixed Cyrillic+Latin."""
        step1 = normalize_confusables("Москва")
        # Some chars became Latin, some stayed Cyrillic
        has_latin = any("a" <= c <= "z" or "A" <= c <= "Z" for c in step1)
        has_cyrillic = any("\u0400" <= c <= "\u04ff" for c in step1)
        assert has_latin and has_cyrillic, f"Expected mixed script, got: {step1!r}"

    def test_manual_wrong_order_transliterate_produces_gibberish(self):
        """Transliterating the mixed result loses coherence."""
        step1 = normalize_confusables("Москва")
        step2 = transliterate(step1)
        # The correct transliteration is "Moskva"
        correct = transliterate("Москва")
        assert correct.lower() == "moskva"
        # The wrong-order result will NOT match
        assert step2.lower() != "moskva"


class TestTextPipelineRejectsUnsafeOrder:
    """TextPipeline must warn or error when confusables runs before transliterate."""

    def test_pipeline_with_both_flags_uses_safe_order(self):
        """When both confusables and transliterate are enabled, the pipeline
        must apply transliterate BEFORE confusables (the catalog_key order)."""
        pipe = TextPipeline(transliterate=True, confusables=True)
        result = pipe("Москва")
        assert result.isascii()
        # Must produce the same result as the safe ordering
        expected = catalog_key("Москва")
        # catalog_key also normalizes and folds case; compare transliterate→confusables
        safe = normalize_confusables(transliterate("Москва"))
        assert result == safe

    def test_pipeline_step_order_transliterate_before_confusables(self):
        """In the steps list, transliterate must come before confusables."""
        pipe = TextPipeline(transliterate=True, confusables=True)
        step_names = [name for name, _ in pipe.steps]
        if "transliterate" in step_names and "confusables" in step_names:
            assert step_names.index("transliterate") < step_names.index("confusables"), (
                f"Unsafe step order: {step_names}"
            )
