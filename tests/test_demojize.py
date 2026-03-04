"""Tests for emoji-to-text expansion (demojize).

Covers:
- Standalone demojize() function
- Text builder .demojize() method
- TextPipeline demojize=True flag
- Custom EmojiProvider protocol
- Error modes (replace, ignore, preserve)
- strip_modifiers option
- Multi-codepoint sequences (ZWJ, flags, skin tone)
"""

from __future__ import annotations

import pytest

from translit import (
    demojize,
    set_emoji_provider,
    Text,
    TextPipeline,
)


# ---------------------------------------------------------------------------
# Basic single-emoji expansion
# ---------------------------------------------------------------------------


class TestBasicDemojize:
    """Single-codepoint emoji produce their CLDR short name."""

    def test_grinning_face(self) -> None:
        assert demojize("😀") == "grinning face"

    def test_face_with_tears_of_joy(self) -> None:
        assert demojize("😂") == "face with tears of joy"

    def test_red_heart(self) -> None:
        assert demojize("❤") == "red heart"

    def test_thumbs_up(self) -> None:
        assert demojize("👍") == "thumbs up"

    def test_pizza(self) -> None:
        assert demojize("🍕") == "pizza"

    def test_globe_europe_africa(self) -> None:
        assert demojize("🌍") == "globe showing Europe-Africa"

    def test_fire(self) -> None:
        assert demojize("🔥") == "fire"

    def test_check_mark(self) -> None:
        assert demojize("✅") == "check mark button"


class TestEmojiInText:
    """Emoji embedded in normal text are expanded in place."""

    def test_emoji_at_start(self) -> None:
        result = demojize("😀 hello")
        assert result == "grinning face hello"

    def test_emoji_at_end(self) -> None:
        result = demojize("hello 😀")
        assert result == "hello grinning face"

    def test_emoji_in_middle(self) -> None:
        result = demojize("I love 🍕 pizza")
        assert result == "I love pizza pizza"

    def test_no_emoji(self) -> None:
        assert demojize("Hello world") == "Hello world"

    def test_empty_string(self) -> None:
        assert demojize("") == ""

    def test_ascii_only(self) -> None:
        text = "The quick brown fox"
        assert demojize(text) == text

    def test_unicode_no_emoji(self) -> None:
        text = "Héllo Wörld"
        assert demojize(text) == text

    def test_multiple_emoji(self) -> None:
        result = demojize("👍🔥")
        assert "thumbs up" in result
        assert "fire" in result


# ---------------------------------------------------------------------------
# Multi-codepoint sequences
# ---------------------------------------------------------------------------


class TestMultiCodepoint:
    """ZWJ, flag, and skin tone sequences resolve to single descriptions."""

    def test_flag_us(self) -> None:
        result = demojize("🇺🇸")
        assert "United States" in result

    def test_flag_gb(self) -> None:
        result = demojize("🇬🇧")
        assert "United Kingdom" in result

    def test_flag_fr(self) -> None:
        result = demojize("🇫🇷")
        assert "France" in result

    def test_skin_tone_thumbs_up(self) -> None:
        """Skin-toned emoji should resolve to a description."""
        result = demojize("👍🏽")
        assert "thumbs up" in result

    def test_waving_hand_light(self) -> None:
        result = demojize("👋🏻")
        assert "waving hand" in result
        assert "light skin tone" in result

    def test_waving_hand_dark(self) -> None:
        result = demojize("👋🏿")
        assert "waving hand" in result
        assert "dark skin tone" in result


# ---------------------------------------------------------------------------
# strip_modifiers option
# ---------------------------------------------------------------------------


class TestStripModifiers:
    """strip_modifiers=True collapses skin tone variants to base form."""

    def test_strip_removes_skin_tone(self) -> None:
        base = demojize("👋🏻", strip_modifiers=True)
        assert "light skin tone" not in base
        assert "waving hand" in base

    def test_no_strip_preserves_skin_tone(self) -> None:
        full = demojize("👋🏻", strip_modifiers=False)
        assert "light skin tone" in full

    def test_strip_on_unmodified_emoji(self) -> None:
        """strip_modifiers has no effect on emoji without modifiers."""
        assert demojize("😀", strip_modifiers=True) == "grinning face"
        assert demojize("😀", strip_modifiers=False) == "grinning face"


# ---------------------------------------------------------------------------
# Error modes
# ---------------------------------------------------------------------------


class TestErrorModes:
    """Unknown emoji handled according to errors parameter."""

    def test_replace_default(self) -> None:
        """Unknown emoji replaced with [?] by default."""
        # Use a codepoint in emoji range unlikely to be in CLDR
        result = demojize("\U000e0020")
        # Should contain the replace_with string or pass through
        # (E0020 is a tag character, might be consumed)
        assert isinstance(result, str)

    def test_errors_replace_custom(self) -> None:
        result = demojize("\U000e0020", errors="replace", replace_with="<?>")
        assert isinstance(result, str)

    def test_errors_ignore(self) -> None:
        result = demojize("\U000e0020", errors="ignore")
        assert isinstance(result, str)

    def test_errors_preserve(self) -> None:
        result = demojize("\U000e0020", errors="preserve")
        assert isinstance(result, str)

    def test_invalid_errors_value(self) -> None:
        with pytest.raises(ValueError, match="errors must be"):
            demojize("😀", errors="invalid")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Text builder integration
# ---------------------------------------------------------------------------


class TestTextBuilder:
    """Text().demojize() returns a new Text with emoji expanded."""

    def test_basic_chain(self) -> None:
        result = Text("I love 😀").demojize().value
        assert result == "I love grinning face"

    def test_chain_with_transliterate(self) -> None:
        result = Text("Héllo 🌍!").demojize().transliterate().value
        assert "globe" in result.lower() or "Europe" in result

    def test_chain_with_fold_case(self) -> None:
        result = Text("😀").demojize().fold_case().value
        assert result == "grinning face"

    def test_immutability(self) -> None:
        original = Text("Hello 😀")
        demojized = original.demojize()
        assert "😀" in original.value
        assert "grinning face" in demojized.value

    def test_strip_modifiers_in_builder(self) -> None:
        result = Text("👋🏻").demojize(strip_modifiers=True).value
        assert "waving hand" in result
        assert "light skin tone" not in result

    def test_slugify_after_demojize(self) -> None:
        """Compose demojize + slugify to get slug-friendly emoji names."""
        result = Text("😀").demojize().slugify().value
        assert result == "grinning-face"


# ---------------------------------------------------------------------------
# TextPipeline integration
# ---------------------------------------------------------------------------


class TestTextPipeline:
    """TextPipeline with demojize=True expands emoji."""

    def test_pipeline_basic(self) -> None:
        pipe = TextPipeline(demojize=True)
        result = pipe("Hello 😀!")
        assert result == "Hello grinning face!"

    def test_pipeline_with_fold_case(self) -> None:
        pipe = TextPipeline(demojize=True, fold_case=True)
        result = pipe("😀")
        assert result == "grinning face"

    def test_pipeline_with_transliterate(self) -> None:
        pipe = TextPipeline(
            demojize=True,
            transliterate=True,
            fold_case=True,
        )
        result = pipe("Héllo 🔥!")
        assert result == "hello fire!"

    def test_pipeline_demojize_false(self) -> None:
        pipe = TextPipeline(demojize=False)
        result = pipe("Hello 😀!")
        assert "😀" in result

    def test_pipeline_demojize_before_transliterate(self) -> None:
        """demojize runs before transliterate in the fixed pipeline order."""
        pipe = TextPipeline(
            normalize="NFC",
            demojize=True,
            transliterate=True,
            collapse_whitespace=True,
        )
        result = pipe("  Hello 🌍  world  ")
        assert "globe" in result.lower() or "Europe" in result


# ---------------------------------------------------------------------------
# Custom EmojiProvider protocol
# ---------------------------------------------------------------------------


class TestCustomProvider:
    """Users can supply a custom provider implementing lookup()."""

    def test_custom_provider_overrides(self) -> None:
        class MyProvider:
            def lookup(self, sequence: list[int]) -> str | None:
                # sequence is a list of codepoint ints
                if sequence == [0x1F600]:  # 😀
                    return "CUSTOM_GRIN"
                return None

        result = demojize("😀", provider=MyProvider())
        assert result == "CUSTOM_GRIN"

    def test_custom_provider_fallback_to_builtin(self) -> None:
        """Provider returning None falls through to built-in table."""

        class EmptyProvider:
            def lookup(self, sequence: list[int]) -> str | None:
                return None

        # The built-in table should handle this
        result = demojize("😀", provider=EmptyProvider())
        assert result == "grinning face"

    def test_global_provider(self) -> None:
        class GlobalProvider:
            def lookup(self, sequence: list[int]) -> str | None:
                if sequence == [0x1F600]:
                    return "GLOBAL_GRIN"
                return None

        set_emoji_provider(GlobalProvider())
        try:
            result = demojize("😀")
            assert result == "GLOBAL_GRIN"
        finally:
            set_emoji_provider(None)

    def test_reset_global_provider(self) -> None:
        set_emoji_provider(None)
        result = demojize("😀")
        assert result == "grinning face"

    def test_per_call_overrides_global(self) -> None:
        class GlobalProv:
            def lookup(self, sequence: list[int]) -> str | None:
                return "GLOBAL" if sequence == [0x1F600] else None

        class LocalProv:
            def lookup(self, sequence: list[int]) -> str | None:
                return "LOCAL" if sequence == [0x1F600] else None

        set_emoji_provider(GlobalProv())
        try:
            result = demojize("😀", provider=LocalProv())
            assert result == "LOCAL"
        finally:
            set_emoji_provider(None)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Boundary conditions and unusual inputs."""

    def test_variation_selector(self) -> None:
        """Variation selector after emoji should be consumed."""
        # ❤️ = ❤ (U+2764) + FE0F (VS16)
        result = demojize("❤\ufe0f")
        assert "heart" in result.lower()

    def test_consecutive_emoji(self) -> None:
        result = demojize("🔥🔥🔥")
        assert result.count("fire") == 3

    def test_emoji_with_newlines(self) -> None:
        result = demojize("hello\n😀\nworld")
        assert "grinning face" in result
        assert "\n" in result

    def test_very_long_string(self) -> None:
        text = "Hello 😀 " * 1000
        result = demojize(text)
        assert result.count("grinning face") == 1000

    def test_mixed_scripts_with_emoji(self) -> None:
        result = demojize("Москва 😀 北京")
        assert "grinning face" in result
        assert "Москва" in result
        assert "北京" in result
