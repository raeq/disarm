"""Tests for CJK (Chinese, Japanese, Korean) transliteration support.

Chinese: context-free Hanzi → Pinyin (no tones) from Unihan kMandarin.
Korean:  algorithmic Hangul → Revised Romanization via jamo decomposition.
Japanese: Hiragana/Katakana already supported; Kanji falls back to Chinese reading.
"""

from __future__ import annotations

from disarm import slugify, transliterate

# ---------------------------------------------------------------------------
# Chinese (Hanzi → Pinyin)
# ---------------------------------------------------------------------------


class TestChinesePinyin:
    """Context-free Hanzi → Pinyin transliteration."""

    def test_beijing(self) -> None:
        assert transliterate("北京") == "bei jing"

    def test_beijing_shi(self) -> None:
        assert transliterate("北京市") == "bei jing shi"

    def test_zhongguo(self) -> None:
        assert transliterate("中国") == "zhong guo"

    def test_common_characters(self) -> None:
        """Test a spread of common characters across frequency tiers."""
        cases = [
            ("人", "ren"),
            ("大", "da"),
            ("小", "xiao"),
            ("水", "shui"),
            ("山", "shan"),
            ("日", "ri"),
            ("月", "yue"),
            ("火", "huo"),
            ("木", "mu"),
            ("金", "jin"),
        ]
        for hanzi, expected in cases:
            assert transliterate(hanzi) == expected, f"{hanzi} → expected {expected}"

    def test_multi_character_phrase(self) -> None:
        result = transliterate("北京烤鸭")
        assert result == "bei jing kao ya"

    def test_mixed_chinese_latin(self) -> None:
        result = transliterate("Hello世界")
        assert result == "Hello shi jie"

    def test_mixed_chinese_latin_boundaries(self) -> None:
        result = transliterate("ABC北京XYZ")
        assert result == "ABC bei jing XYZ"

    def test_chinese_with_punctuation(self) -> None:
        # ASCII punctuation passes through; Chinese text is transliterated
        result = transliterate("你好!")
        assert result == "ni hao!"

    def test_lang_zh_explicit(self) -> None:
        # Explicit lang="zh" should produce same result as default
        result = transliterate("中国", lang="zh")
        assert result == "zhong guo"


class TestChineseSlugify:
    """Chinese text slugified produces hyphenated pinyin."""

    def test_slugify_chinese(self) -> None:
        assert slugify("北京烤鸭") == "bei-jing-kao-ya"

    def test_slugify_chinese_latin_mix(self) -> None:
        result = slugify("Hello 世界")
        assert result == "hello-shi-jie"

    def test_slugify_chinese_numbers(self) -> None:
        result = slugify("第1课")
        assert result == "di-1-ke"


# ---------------------------------------------------------------------------
# Korean (Hangul → Revised Romanization)
# ---------------------------------------------------------------------------


class TestKoreanRomanization:
    """Algorithmic Hangul → Revised Romanization."""

    def test_seoul(self) -> None:
        assert transliterate("서울") == "seo ul"

    def test_hanguk(self) -> None:
        assert transliterate("한국") == "han gug"

    def test_daehanminguk(self) -> None:
        assert transliterate("대한민국") == "dae han min gug"

    def test_gimchi(self) -> None:
        assert transliterate("김치") == "gim chi"

    def test_common_syllables(self) -> None:
        """Test individual syllable decomposition."""
        cases = [
            ("가", "ga"),  # ㄱ + ㅏ
            ("나", "na"),  # ㄴ + ㅏ
            ("다", "da"),  # ㄷ + ㅏ
            ("라", "ra"),  # ㄹ + ㅏ
            ("마", "ma"),  # ㅁ + ㅏ
            ("바", "ba"),  # ㅂ + ㅏ
            ("사", "sa"),  # ㅅ + ㅏ
            ("아", "a"),  # ㅇ (silent) + ㅏ
            ("자", "ja"),  # ㅈ + ㅏ
            ("차", "cha"),  # ㅊ + ㅏ
            ("카", "ka"),  # ㅋ + ㅏ
            ("타", "ta"),  # ㅌ + ㅏ
            ("파", "pa"),  # ㅍ + ㅏ
            ("하", "ha"),  # ㅎ + ㅏ
        ]
        for hangul, expected in cases:
            assert transliterate(hangul) == expected, f"{hangul} → expected {expected}"

    def test_final_consonants(self) -> None:
        """Test syllables with jongseong (final consonant)."""
        cases = [
            ("각", "gag"),  # ㄱ + ㅏ + ㄱ
            ("간", "gan"),  # ㄱ + ㅏ + ㄴ
            ("갈", "gal"),  # ㄱ + ㅏ + ㄹ
            ("감", "gam"),  # ㄱ + ㅏ + ㅁ
            ("강", "gang"),  # ㄱ + ㅏ + ㅇ
        ]
        for hangul, expected in cases:
            assert transliterate(hangul) == expected, f"{hangul} → expected {expected}"

    def test_double_consonants(self) -> None:
        """Test tense (doubled) consonants."""
        cases = [
            ("까", "kka"),  # ㄲ + ㅏ
            ("따", "tta"),  # ㄸ + ㅏ
            ("빠", "ppa"),  # ㅃ + ㅏ
            ("싸", "ssa"),  # ㅆ + ㅏ
            ("짜", "jja"),  # ㅉ + ㅏ
        ]
        for hangul, expected in cases:
            assert transliterate(hangul) == expected, f"{hangul} → expected {expected}"

    def test_complex_vowels(self) -> None:
        """Test compound vowels (diphthongs)."""
        cases = [
            ("과", "gwa"),  # ㄱ + ㅘ
            ("궈", "gwo"),  # ㄱ + ㅝ
            ("귀", "gwi"),  # ㄱ + ㅟ
            ("의", "ui"),  # ㅇ + ㅢ
        ]
        for hangul, expected in cases:
            assert transliterate(hangul) == expected, f"{hangul} → expected {expected}"

    def test_korean_latin_boundaries(self) -> None:
        result = transliterate("ABC서울XYZ")
        assert result == "ABC seo ul XYZ"

    def test_lang_ko_explicit(self) -> None:
        result = transliterate("한국", lang="ko")
        assert result == "han gug"


class TestKoreanSlugify:
    """Korean text slugified produces hyphenated romanization."""

    def test_slugify_korean(self) -> None:
        assert slugify("대한민국") == "dae-han-min-gug"

    def test_slugify_korean_latin_mix(self) -> None:
        result = slugify("Hello 서울")
        assert result == "hello-seo-ul"


# ---------------------------------------------------------------------------
# Japanese (Kanji falls back to Chinese reading)
# ---------------------------------------------------------------------------


class TestJapaneseKanji:
    """Japanese kanji uses Chinese pinyin reading as fallback."""

    def test_kanji_fallback_to_pinyin(self) -> None:
        # 東京 in Chinese reading: dong jing (not Japanese "toukyou")
        result = transliterate("東京")
        assert result == "dong jing"

    def test_hiragana_still_works(self) -> None:
        """Existing hiragana transliteration should be unaffected."""
        result = transliterate("ひらがな")
        assert result == "hiragana"

    def test_katakana_still_works(self) -> None:
        """Existing katakana transliteration should be unaffected."""
        result = transliterate("カタカナ")
        assert result == "katakana"

    def test_mixed_kanji_kana(self) -> None:
        # 東京タワー: kanji gets pinyin, katakana gets hepburn
        result = transliterate("東京タワー")
        # タワー = tawa- (prolonged mark produces -)
        # With lang=ja, ー is dropped
        assert "dong jing" in result


# ---------------------------------------------------------------------------
# Mixed CJK scripts
# ---------------------------------------------------------------------------


class TestMixedCJK:
    """Mixed Chinese/Korean/Japanese text."""

    def test_chinese_korean_together(self) -> None:
        result = transliterate("서울 is 首尔")
        assert result == "seo ul is shou er"

    def test_all_scripts_mixed(self) -> None:
        """Latin + Chinese + Korean in one string."""
        result = transliterate("Hello 北京 and 서울!")
        assert result == "Hello bei jing and seo ul!"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestCJKEdgeCases:
    """Edge cases and boundary conditions for CJK transliteration."""

    def test_single_hanzi(self) -> None:
        assert transliterate("中") == "zhong"

    def test_single_hangul(self) -> None:
        assert transliterate("한") == "han"

    def test_empty_string(self) -> None:
        assert transliterate("") == ""

    def test_error_mode_preserve_unknown(self) -> None:
        """Characters outside CJK main block with no mapping are preserved."""
        # U+20000 is CJK Extension B — not in our table
        result = transliterate("\U00020000", errors="preserve")
        assert result == "\U00020000"

    def test_error_mode_ignore_unknown(self) -> None:
        result = transliterate("\U00020000", errors="ignore")
        assert result == ""

    def test_non_cjk_unaffected(self) -> None:
        """Latin, Cyrillic, Greek transliteration must not regress."""
        assert transliterate("café") == "cafe"
        assert transliterate("Москва") == "Moskva"
        assert transliterate("Ünïcödé") == "Unicode"

    def test_cjk_spaces_not_doubled(self) -> None:
        """When CJK chars are already space-separated, don't double spaces."""
        result = transliterate("北 京")
        assert result == "bei jing"  # existing space, plus CJK space insertion
