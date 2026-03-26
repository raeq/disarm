"""Tests for lang='auto' script-based language detection."""

import pytest

from translit import Slugifier, TextPipeline, slugify, transliterate


class TestLangAutoDetection:
    """lang='auto' detects script and uses appropriate language table."""

    @pytest.mark.parametrize(
        "text,expected_lang",
        [
            ("ภาษาไทย", "th"),
            ("Москва", "ru"),
            ("नमस्ते", "hi"),
            ("こんにちは", "ja"),
            ("中文", "zh"),
            ("한국어", "ko"),
            ("עברית", "he"),
            ("العربية", "ar"),
            ("ქართული", "ka"),
            ("Հայերեն", "hy"),
            ("ትግርኛ", "am"),
            ("বাংলা", "bn"),
            ("தமிழ்", "ta"),
            ("తెలుగు", "te"),
            ("ಕನ್ನಡ", "kn"),
            ("മലയാളം", "ml"),
            ("ગુજરાતી", "gu"),
            ("ਗੁਰਮੁਖੀ", "pa"),
            ("ଓଡ଼ିଆ", "or"),
            ("සිංහල", "si"),
            ("ພາສາລາວ", "lo"),
            ("မြန်မာ", "my"),
            ("ភាសាខ្មែរ", "km"),
            ("བོད་སྐད", "bo"),
            ("Ελληνικά", "el"),
        ],
    )
    def test_auto_matches_explicit_lang(self, text: str, expected_lang: str) -> None:
        auto = transliterate(text, lang="auto")
        explicit = transliterate(text, lang=expected_lang)
        assert auto == explicit

    def test_auto_ascii_passthrough(self) -> None:
        assert transliterate("hello", lang="auto") == "hello"

    def test_auto_latin_accented_uses_default(self) -> None:
        assert transliterate("café", lang="auto") == transliterate("café")

    def test_auto_mixed_latin_cyrillic(self) -> None:
        """First non-Latin script wins."""
        result = transliterate("Hello Москва", lang="auto")
        expected = transliterate("Hello Москва", lang="ru")
        assert result == expected

    def test_slugify_auto(self) -> None:
        result = slugify("ภาษาไทย", lang="auto")
        expected = slugify("ภาษาไทย", lang="th")
        assert result == expected

    def test_pipeline_auto(self) -> None:
        p = TextPipeline(transliterate=True, lang="auto")
        result = p("Москва")
        assert result.isascii()

    def test_slugifier_auto(self) -> None:
        s = Slugifier(lang="auto")
        result = s("東京タワー")
        assert result.isascii()
        assert len(result) > 0


class TestLangDiscriminator:
    """lang='auto' uses character-level discriminators for ambiguous scripts."""

    # ── Cyrillic discrimination ──

    def test_ukrainian_detected_by_yi(self) -> None:
        """Ukrainian ї triggers uk detection."""
        auto = transliterate("Київ — столиця України", lang="auto")
        explicit = transliterate("Київ — столиця України", lang="uk")
        assert auto == explicit

    def test_serbian_detected_by_dje(self) -> None:
        """Serbian ђ triggers sr detection."""
        auto = transliterate("Ђорђе и ћирилица", lang="auto")
        explicit = transliterate("Ђорђе и ћирилица", lang="sr")
        assert auto == explicit

    def test_cyrillic_without_discriminators_defaults_to_russian(self) -> None:
        """Plain Cyrillic without exclusive chars defaults to ru."""
        auto = transliterate("Москва", lang="auto")
        explicit = transliterate("Москва", lang="ru")
        assert auto == explicit

    def test_conflicting_cyrillic_discriminators_defaults_to_russian(self) -> None:
        """Mixed Ukrainian ї + Serbian ћ falls back to ru."""
        auto = transliterate("їћ", lang="auto")
        explicit = transliterate("їћ", lang="ru")
        assert auto == explicit

    # ── Arabic discrimination ──

    def test_persian_detected_by_pe(self) -> None:
        """Persian پ triggers fa detection."""
        auto = transliterate("پارسی زبان", lang="auto")
        explicit = transliterate("پارسی زبان", lang="fa")
        assert auto == explicit

    def test_arabic_without_discriminators_defaults_to_arabic(self) -> None:
        """Plain Arabic without Persian chars defaults to ar."""
        auto = transliterate("العربية", lang="auto")
        explicit = transliterate("العربية", lang="ar")
        assert auto == explicit

    # ── Latin discrimination ──

    def test_vietnamese_detected_by_horn_vowels(self) -> None:
        """Vietnamese ơ/ư triggers vi detection."""
        auto = transliterate("Thành phố Hồ Chí Minh rất đẹp và có nhiều người", lang="auto")
        explicit = transliterate(
            "Thành phố Hồ Chí Minh rất đẹp và có nhiều người", lang="vi"
        )
        assert auto == explicit

    def test_turkish_detected_by_dotless_i(self) -> None:
        """Turkish ı triggers tr detection."""
        auto = transliterate("İstanbul güzel bir şehır", lang="auto")
        explicit = transliterate("İstanbul güzel bir şehır", lang="tr")
        assert auto == explicit

    def test_german_detected_by_eszett(self) -> None:
        """German ß triggers de detection."""
        auto = transliterate("Straße nach Süden", lang="auto")
        explicit = transliterate("Straße nach Süden", lang="de")
        assert auto == explicit

    def test_latin_without_discriminators_returns_default(self) -> None:
        """Accented Latin without exclusive chars uses default transliteration."""
        auto = transliterate("café", lang="auto")
        default = transliterate("café")
        assert auto == default

    # ── Fail-safe: slug and pipeline ──

    def test_slugify_auto_persian(self) -> None:
        result = slugify("پارسی", lang="auto")
        expected = slugify("پارسی", lang="fa")
        assert result == expected

    def test_slugify_auto_ukrainian(self) -> None:
        result = slugify("Київ", lang="auto")
        expected = slugify("Київ", lang="uk")
        assert result == expected

    def test_pipeline_auto_with_discriminator(self) -> None:
        p = TextPipeline(transliterate=True, lang="auto")
        result = p("Straße")
        assert result.isascii()
