"""Tests for strict_iso9 scholarly Cyrillic transliteration.

ISO 9:1995 is the international standard for Cyrillic-to-Latin transliteration
used in linguistics, library science, and academic publishing. It produces
consistent, reversible results independent of source language.

Key differences from default BGN/PCGN-based transliteration:
  й → j (not y)      ю → ju (not yu)     я → ja (not ya)
  х → h (not kh)     ц → c (not ts)      ё → jo (not yo)
"""

from translit import Text, TextPipeline, transliterate


class TestISO9CoreMappings:
    """Verify the core ISO 9 divergences from default."""

    def test_y_to_j(self) -> None:
        """й → j (the signature ISO 9 choice)."""
        assert transliterate("й", strict_iso9=True) == "j"
        assert transliterate("Й", strict_iso9=True) == "J"

    def test_yu_to_ju(self) -> None:
        """ю → ju (j-based, not y-based)."""
        assert transliterate("ю", strict_iso9=True) == "ju"
        assert transliterate("Ю", strict_iso9=True) == "Ju"

    def test_ya_to_ja(self) -> None:
        """я → ja (j-based)."""
        assert transliterate("я", strict_iso9=True) == "ja"
        assert transliterate("Я", strict_iso9=True) == "Ja"

    def test_yo_to_jo(self) -> None:
        """ё → jo (j-based)."""
        assert transliterate("ё", strict_iso9=True) == "jo"
        assert transliterate("Ё", strict_iso9=True) == "Jo"

    def test_kh_to_h(self) -> None:
        """х → h (single letter in ISO 9)."""
        assert transliterate("х", strict_iso9=True) == "h"
        assert transliterate("Х", strict_iso9=True) == "H"

    def test_ts_to_c(self) -> None:
        """ц → c (single letter in ISO 9)."""
        assert transliterate("ц", strict_iso9=True) == "c"
        assert transliterate("Ц", strict_iso9=True) == "C"

    def test_hard_sign_silent(self) -> None:
        """ъ → empty (silent in ASCII-flattened ISO 9)."""
        assert transliterate("ъ", strict_iso9=True) == ""
        assert transliterate("Ъ", strict_iso9=True) == ""

    def test_soft_sign_silent(self) -> None:
        """ь → empty (silent in ASCII-flattened ISO 9)."""
        assert transliterate("ь", strict_iso9=True) == ""
        assert transliterate("Ь", strict_iso9=True) == ""


class TestISO9Words:
    """Test complete words in ISO 9 mode."""

    def test_yogurt(self) -> None:
        """The classic test: Йогурт → Jogurt (ISO 9) vs Yogurt (default)."""
        assert transliterate("Йогурт", strict_iso9=True) == "Jogurt"
        assert transliterate("Йогурт") == "Yogurt"

    def test_youth(self) -> None:
        """юность → junost (ISO 9) vs yunost (default)."""
        assert transliterate("юность", strict_iso9=True) == "junost"

    def test_apple(self) -> None:
        """яблоко → jabloko (ISO 9) vs yabloko (default)."""
        assert transliterate("яблоко", strict_iso9=True) == "jabloko"

    def test_bread(self) -> None:
        """хлеб → hleb (ISO 9) vs khleb (default)."""
        assert transliterate("хлеб", strict_iso9=True) == "hleb"

    def test_circus(self) -> None:
        """цирк → cirk (ISO 9) vs tsirk (default)."""
        assert transliterate("цирк", strict_iso9=True) == "cirk"

    def test_hedgehog(self) -> None:
        """Ёж → Jozh (ISO 9) vs Yozh (default)."""
        assert transliterate("Ёж", strict_iso9=True) == "Jozh"

    def test_moskva(self) -> None:
        """Москва — no difference (no divergent chars)."""
        assert transliterate("Москва", strict_iso9=True) == "Moskva"

    def test_privet(self) -> None:
        """Привет — no difference."""
        assert transliterate("Привет", strict_iso9=True) == "Privet"

    def test_bolshoy(self) -> None:
        """большой → bolshoj (ISO 9) — soft sign silent, й→j."""
        assert transliterate("большой", strict_iso9=True) == "bolshoj"


class TestISO9OverridesLang:
    """strict_iso9=True takes priority over lang-specific overrides."""

    def test_overrides_ru(self) -> None:
        """ISO 9 wins over lang='ru' BGN/PCGN mappings."""
        # With lang="ru": большой → bol'shoy (prime for soft sign)
        # With strict_iso9: большой → bolshoj (silent soft sign, j for й)
        result = transliterate("большой", strict_iso9=True, lang="ru")
        assert result == "bolshoj"
        assert "'" not in result  # No BGN/PCGN soft sign marker

    def test_overrides_bg(self) -> None:
        """ISO 9 wins over lang='bg' Bulgarian mappings."""
        # Bulgarian: Щ → Sht. ISO 9: Щ → Shch (pinned default).
        result = transliterate("Щука", strict_iso9=True, lang="bg")
        assert result == "Shchuka"

    def test_overrides_uk(self) -> None:
        """ISO 9 wins over lang='uk' Ukrainian mappings."""
        # Ukrainian: Г → H. ISO 9 has no override for Г, so default G applies.
        result = transliterate("Г", strict_iso9=True, lang="uk")
        assert result == "G"  # Default, not Ukrainian H


class TestISO9DefaultFallthrough:
    """Characters not in ISO 9 table fall through to default."""

    def test_latin_passthrough(self) -> None:
        """ASCII chars pass through unchanged."""
        assert transliterate("Hello", strict_iso9=True) == "Hello"

    def test_german_umlaut(self) -> None:
        """Non-Cyrillic chars use default table."""
        assert transliterate("ü", strict_iso9=True) == "u"

    def test_japanese(self) -> None:
        """Japanese kana uses default table even with iso9."""
        assert transliterate("すし", strict_iso9=True) == "sushi"

    def test_mixed_script(self) -> None:
        """Mixed Cyrillic + Latin + Japanese."""
        result = transliterate("Йогурт and すし", strict_iso9=True)
        assert result == "Jogurt and sushi"

    def test_non_cyrillic_unchanged(self) -> None:
        """ISO 9 table doesn't interfere with non-Cyrillic."""
        assert transliterate("café", strict_iso9=True) == "cafe"


class TestISO9TextBuilder:
    """Test strict_iso9 through the Text builder API."""

    def test_basic(self) -> None:
        result = Text("Йогурт").transliterate(strict_iso9=True).value
        assert result == "Jogurt"

    def test_chained(self) -> None:
        result = (
            Text("  Юность  ")
            .normalize(form="NFC")
            .transliterate(strict_iso9=True)
            .fold_case()
            .collapse_whitespace()
            .value
        )
        assert result == "junost"

    def test_default_false(self) -> None:
        """strict_iso9 defaults to False in Text builder."""
        result = Text("Йогурт").transliterate().value
        assert result == "Yogurt"


class TestISO9Pipeline:
    """Test strict_iso9 through the TextPipeline API."""

    def test_basic(self) -> None:
        pipe = TextPipeline(transliterate=True, strict_iso9=True)
        assert pipe("Йогурт") == "Jogurt"

    def test_with_fold_case(self) -> None:
        pipe = TextPipeline(transliterate=True, strict_iso9=True, fold_case=True)
        assert pipe("Юность") == "junost"

    def test_pipeline_default_false(self) -> None:
        """strict_iso9 defaults to False in pipeline."""
        pipe = TextPipeline(transliterate=True)
        assert pipe("Йогурт") == "Yogurt"

    def test_pipeline_iso9_ignores_lang(self) -> None:
        """When strict_iso9=True, lang parameter has no effect on Cyrillic."""
        pipe = TextPipeline(transliterate=True, strict_iso9=True, lang="ru")
        assert pipe("большой") == "bolshoj"


class TestISO9DefaultFlagFalse:
    """Verify strict_iso9=False (default) gives BGN/PCGN behavior."""

    def test_default_is_false(self) -> None:
        assert transliterate("Йогурт") == "Yogurt"
        assert transliterate("Йогурт", strict_iso9=False) == "Yogurt"

    def test_yu_default(self) -> None:
        assert transliterate("юность") == "yunost"
        assert transliterate("юность", strict_iso9=False) == "yunost"

    def test_kh_default(self) -> None:
        assert transliterate("хлеб") == "khleb"
        assert transliterate("хлеб", strict_iso9=False) == "khleb"
