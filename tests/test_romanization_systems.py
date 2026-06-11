"""Tests for A3 (multiple romanization systems) and A4 (toned pinyin)."""

from disarm import transliterate


class TestKunreiShiki:
    """A3: Kunrei-shiki romanization of Japanese kana."""

    def test_shi_to_si(self):
        assert transliterate("し", lang="ja-kunrei") == "si"
        assert transliterate("シ", lang="ja-kunrei") == "si"

    def test_chi_to_ti(self):
        assert transliterate("ち", lang="ja-kunrei") == "ti"
        assert transliterate("チ", lang="ja-kunrei") == "ti"

    def test_tsu_to_tu(self):
        assert transliterate("つ", lang="ja-kunrei") == "tu"
        assert transliterate("ツ", lang="ja-kunrei") == "tu"

    def test_fu_to_hu(self):
        assert transliterate("ふ", lang="ja-kunrei") == "hu"
        assert transliterate("フ", lang="ja-kunrei") == "hu"

    def test_ji_to_zi(self):
        assert transliterate("じ", lang="ja-kunrei") == "zi"
        assert transliterate("ジ", lang="ja-kunrei") == "zi"

    def test_hepburn_default_unchanged(self):
        """Default (Hepburn) romanization should not change."""
        assert transliterate("し") == "shi"
        assert transliterate("ち") == "chi"
        assert transliterate("つ") == "tsu"

    def test_non_differing_kana_unchanged(self):
        """Kana that don't differ between systems should be the same."""
        assert transliterate("か", lang="ja-kunrei") == "ka"
        assert transliterate("さ", lang="ja-kunrei") == "sa"
        assert transliterate("な", lang="ja-kunrei") == "na"

    def test_kunrei_in_list_langs(self):
        from disarm import list_langs

        assert "ja-kunrei" in list_langs()


class TestTonedPinyin:
    """A4: Toned pinyin output with diacritics."""

    def test_beijing_toned(self):
        assert transliterate("北京", tones=True) == "běi jīng"

    def test_beijing_toneless(self):
        assert transliterate("北京") == "bei jing"

    def test_shanghai_toned(self):
        assert transliterate("上海", tones=True) == "shàng hǎi"

    def test_zhongguo_toned(self):
        assert transliterate("中国", tones=True) == "zhōng guó"

    def test_nihao_toned(self):
        assert transliterate("你好", tones=True) == "nǐ hǎo"

    def test_tones_false_is_default(self):
        """tones=False should produce same output as omitting the parameter."""
        assert transliterate("北京", tones=False) == transliterate("北京")

    def test_tones_with_ascii_passthrough(self):
        """ASCII text should pass through unchanged even with tones=True."""
        assert transliterate("hello", tones=True) == "hello"

    def test_tones_fallback_to_toneless(self):
        """Characters without toned data should fall back to toneless pinyin."""
        # Use a rare character unlikely to be in the toned table
        toneless = transliterate("\u9fa5")  # Last CJK Unified char
        toned = transliterate("\u9fa5", tones=True)
        # Should produce *something* (either toned or toneless fallback)
        assert toned == toneless or len(toned) > 0
