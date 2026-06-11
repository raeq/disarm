"""Tests for expanded language support: Russian, Serbian, Japanese kana.

Covers:
- Default Cyrillic й→y change (BGN/PCGN over ISO 9)
- Russian (lang="ru") BGN/PCGN override table
- Serbian (lang="sr") practical romanization
- Hiragana (U+3040–U+309F) → Modified Hepburn
- Katakana (U+30A0–U+30FF) → Modified Hepburn
- Half-width Katakana (U+FF65–U+FF9F) → Modified Hepburn
- NFKC normalization path for half-width dakuten/handakuten
"""

from disarm import Text, TextPipeline, normalize, slugify, transliterate

# ---------------------------------------------------------------------------
# Default Cyrillic: й→y (BGN/PCGN)
# ---------------------------------------------------------------------------


class TestDefaultCyrillicY:
    """Default table now uses й→y (BGN/PCGN) instead of й→j (ISO 9)."""

    def test_lowercase_y(self) -> None:
        assert transliterate("й") == "y"

    def test_uppercase_y(self) -> None:
        assert transliterate("Й") == "Y"

    def test_yogurt(self) -> None:
        assert transliterate("Йогурт") == "Yogurt"

    def test_yabloko(self) -> None:
        """яблоко uses я→ya; й not involved but verifying no regression."""
        assert transliterate("яблоко") == "yabloko"

    def test_may(self) -> None:
        """май (May) — й at word end."""
        assert transliterate("май") == "may"

    def test_moskovsky(self) -> None:
        """Московский — й at word end."""
        result = transliterate("Московский")
        assert result.endswith("y")
        assert "Y" not in result[1:]  # Only possible uppercase is M at start


# ---------------------------------------------------------------------------
# Russian (lang="ru") — BGN/PCGN override
# ---------------------------------------------------------------------------


class TestRussianOverride:
    """lang='ru' provides BGN/PCGN romanization with sign markers."""

    def test_yogurt(self) -> None:
        assert transliterate("Йогурт", lang="ru") == "Yogurt"

    def test_hard_sign(self) -> None:
        """Ъ → double prime in BGN/PCGN."""
        result = transliterate("объект", lang="ru")
        assert '"' in result

    def test_soft_sign(self) -> None:
        """Ь → prime in BGN/PCGN."""
        result = transliterate("большой", lang="ru")
        # BGN/PCGN: большой → bol'shoy
        assert "'" in result

    def test_hard_sign_default_silent(self) -> None:
        """Default table drops hard sign entirely."""
        result = transliterate("объект")
        assert '"' not in result
        assert result == "obekt"

    def test_soft_sign_default_silent(self) -> None:
        """Default table drops soft sign entirely."""
        result = transliterate("большой")
        assert "'" not in result
        assert result == "bolshoy"

    def test_moskva(self) -> None:
        assert transliterate("Москва", lang="ru") == "Moskva"

    def test_yo(self) -> None:
        """Ё → Yo in both default and ru."""
        assert transliterate("ёж", lang="ru") == "yozh"
        assert transliterate("ёж") == "yozh"

    def test_shchi(self) -> None:
        """Щ → Shch in both default and ru."""
        assert transliterate("щука", lang="ru") == "shchuka"

    def test_full_sentence(self) -> None:
        result = transliterate("Привет мир", lang="ru")
        assert result == "Privet mir"

    def test_slug_russian(self) -> None:
        """Russian text through slugify pipeline."""
        result = slugify("Йогурт и кефир")
        assert "yogurt" in result
        assert "kefir" in result


# ---------------------------------------------------------------------------
# Serbian (lang="sr") — practical romanization
# ---------------------------------------------------------------------------


class TestSerbianOverride:
    """lang='sr' provides practical Serbian Cyrillic romanization."""

    def test_tsh_to_c(self) -> None:
        """Ћ → C (ASCII approximation of Ć)."""
        assert transliterate("Ћирилица", lang="sr") == "Cirilitsa"

    def test_tsh_lowercase(self) -> None:
        assert transliterate("ћирилица", lang="sr") == "cirilitsa"

    def test_dzh_to_dz(self) -> None:
        """Џ → Dz (simplified)."""
        assert transliterate("Џемпер", lang="sr") == "Dzemper"

    def test_dj(self) -> None:
        """Ђ → Dj (Serbian standard)."""
        assert transliterate("Ђурађ", lang="sr") == "Djuradj"

    def test_lj_nj(self) -> None:
        """Љ → Lj, Њ → Nj."""
        assert transliterate("Љубљана", lang="sr") == "Ljubljana"
        assert transliterate("Његош", lang="sr") == "Njegosh"

    def test_j(self) -> None:
        """Ј → J."""
        assert transliterate("Јован", lang="sr") == "Jovan"

    def test_default_serbian_chars(self) -> None:
        """Default table values for comparison."""
        assert transliterate("Ћ") == "Tsh"  # Default
        assert transliterate("Џ") == "Dzh"  # Default

    def test_slug_serbian(self) -> None:
        result = slugify("Ћирилица", lang="sr")
        assert "cirilitsa" in result


# ---------------------------------------------------------------------------
# Hiragana → Modified Hepburn
# ---------------------------------------------------------------------------


class TestHiragana:
    """Hiragana characters (U+3040–U+309F) transliterate to Hepburn romaji."""

    def test_sushi(self) -> None:
        assert transliterate("すし") == "sushi"

    def test_konnichiwa(self) -> None:
        assert transliterate("こんにちは") == "konnichiha"

    def test_arigatou(self) -> None:
        assert transliterate("ありがとう") == "arigatou"

    def test_vowels(self) -> None:
        assert transliterate("あいうえお") == "aiueo"

    def test_ka_row(self) -> None:
        assert transliterate("かきくけこ") == "kakikukeko"

    def test_sa_row(self) -> None:
        assert transliterate("さしすせそ") == "sashisuseso"

    def test_ta_row(self) -> None:
        assert transliterate("たちつてと") == "tachitsuteto"

    def test_na_row(self) -> None:
        assert transliterate("なにぬねの") == "naninuneno"

    def test_ha_row(self) -> None:
        assert transliterate("はひふへほ") == "hahifuheho"

    def test_ma_row(self) -> None:
        assert transliterate("まみむめも") == "mamimumemo"

    def test_ya_row(self) -> None:
        assert transliterate("やゆよ") == "yayuyo"

    def test_ra_row(self) -> None:
        assert transliterate("らりるれろ") == "rarirurero"

    def test_wa_wo_n(self) -> None:
        assert transliterate("わをん") == "wawon"

    def test_dakuten_ga_row(self) -> None:
        assert transliterate("がぎぐげご") == "gagigugego"

    def test_dakuten_za_row(self) -> None:
        assert transliterate("ざじずぜぞ") == "zajizuzezo"

    def test_dakuten_da_row(self) -> None:
        assert transliterate("だぢづでど") == "dadidudedo"

    def test_dakuten_ba_row(self) -> None:
        assert transliterate("ばびぶべぼ") == "babibubebo"

    def test_handakuten_pa_row(self) -> None:
        assert transliterate("ぱぴぷぺぽ") == "papipupepo"

    def test_small_ya_yu_yo(self) -> None:
        """Small kana used in combination (e.g., きゃ = kya) are individual chars."""
        assert transliterate("ゃゅょ") == "yayuyo"

    def test_small_tsu(self) -> None:
        """っ (small tsu) is gemination marker — just 'tsu' per-char."""
        assert transliterate("っ") == "tsu"


# ---------------------------------------------------------------------------
# Katakana → Modified Hepburn
# ---------------------------------------------------------------------------


class TestKatakana:
    """Katakana characters (U+30A0–U+30FF) transliterate to Hepburn romaji."""

    def test_ramen(self) -> None:
        assert transliterate("ラーメン") == "ra-men"

    def test_tokyo(self) -> None:
        assert transliterate("トーキョー") == "to-kiyo-"

    def test_vowels(self) -> None:
        assert transliterate("アイウエオ") == "aiueo"

    def test_ka_row(self) -> None:
        assert transliterate("カキクケコ") == "kakikukeko"

    def test_sa_row(self) -> None:
        assert transliterate("サシスセソ") == "sashisuseso"

    def test_ta_row(self) -> None:
        assert transliterate("タチツテト") == "tachitsuteto"

    def test_na_row(self) -> None:
        assert transliterate("ナニヌネノ") == "naninuneno"

    def test_ha_row(self) -> None:
        assert transliterate("ハヒフヘホ") == "hahifuheho"

    def test_ma_row(self) -> None:
        assert transliterate("マミムメモ") == "mamimumemo"

    def test_ya_row(self) -> None:
        assert transliterate("ヤユヨ") == "yayuyo"

    def test_ra_row(self) -> None:
        assert transliterate("ラリルレロ") == "rarirurero"

    def test_wa_wo_n(self) -> None:
        assert transliterate("ワヲン") == "wawon"

    def test_dakuten_ga_row(self) -> None:
        assert transliterate("ガギグゲゴ") == "gagigugego"

    def test_dakuten_za_row(self) -> None:
        assert transliterate("ザジズゼゾ") == "zajizuzezo"

    def test_dakuten_da_row(self) -> None:
        assert transliterate("ダヂヅデド") == "dadidudedo"

    def test_dakuten_ba_row(self) -> None:
        assert transliterate("バビブベボ") == "babibubebo"

    def test_handakuten_pa_row(self) -> None:
        assert transliterate("パピプペポ") == "papipupepo"

    def test_middle_dot(self) -> None:
        """・ (middle dot) transliterates to space."""
        assert transliterate("ハロー・ワールド") == "haro- wa-rudo"

    def test_prolonged_sound_mark(self) -> None:
        """ー transliterates to hyphen."""
        assert transliterate("ー") == "-"

    def test_vu(self) -> None:
        """ヴ (vu) for foreign words."""
        assert transliterate("ヴ") == "vu"


# ---------------------------------------------------------------------------
# Half-width Katakana
# ---------------------------------------------------------------------------


class TestHalfWidthKatakana:
    """Half-width Katakana (U+FF65–U+FF9F) — per-char transliteration."""

    def test_basic_ka_ta_ka_na(self) -> None:
        """ｶﾀｶﾅ → katakana."""
        assert transliterate("ｶﾀｶﾅ") == "katakana"

    def test_vowels(self) -> None:
        assert transliterate("ｱｲｳｴｵ") == "aiueo"

    def test_consonant_rows(self) -> None:
        assert transliterate("ｶｷｸｹｺ") == "kakikukeko"
        assert transliterate("ｻｼｽｾｿ") == "sashisuseso"
        assert transliterate("ﾀﾁﾂﾃﾄ") == "tachitsuteto"
        assert transliterate("ﾅﾆﾇﾈﾉ") == "naninuneno"
        assert transliterate("ﾊﾋﾌﾍﾎ") == "hahifuheho"
        assert transliterate("ﾏﾐﾑﾒﾓ") == "mamimumemo"
        assert transliterate("ﾔﾕﾖ") == "yayuyo"
        assert transliterate("ﾗﾘﾙﾚﾛ") == "rarirurero"
        assert transliterate("ﾜﾝ") == "wan"

    def test_wo(self) -> None:
        assert transliterate("ｦ") == "wo"

    def test_small_forms(self) -> None:
        assert transliterate("ｧｨｩｪｫ") == "aiueo"
        assert transliterate("ｬｭｮ") == "yayuyo"
        assert transliterate("ｯ") == "tsu"

    def test_prolonged_sound(self) -> None:
        assert transliterate("ｰ") == "-"

    def test_middle_dot(self) -> None:
        assert transliterate("･") == " "

    def test_dakuten_standalone(self) -> None:
        """Standalone dakuten/handakuten markers produce empty string."""
        assert transliterate("ﾞ") == ""
        assert transliterate("ﾟ") == ""

    def test_nfkc_then_transliterate(self) -> None:
        """NFKC normalization merges half-width + dakuten into full-width.
        This is the recommended path for proper voiced consonant handling."""
        # ﾊﾞ (ha + dakuten) → NFKC → バ (ba)
        text = "ﾊﾞ"
        normalized = normalize(text, form="NFKC")
        result = transliterate(normalized)
        assert result == "ba"

    def test_nfkc_handakuten(self) -> None:
        """NFKC merges half-width + handakuten → full-width pa-row."""
        text = "ﾊﾟ"
        normalized = normalize(text, form="NFKC")
        result = transliterate(normalized)
        assert result == "pa"

    def test_pipeline_nfkc_transliterate(self) -> None:
        """TextPipeline with NFKC + transliterate handles half-width correctly."""
        pipe = TextPipeline(
            normalize="NFKC",
            transliterate=True,
        )
        assert pipe("ﾊﾞﾅﾅ") == "banana"

    def test_text_builder_nfkc_transliterate(self) -> None:
        """Text builder chain: NFKC → transliterate for half-width dakuten."""
        result = Text("ﾊﾞﾅﾅ").normalize(form="NFKC").transliterate().value
        assert result == "banana"


# ---------------------------------------------------------------------------
# Cross-script integration
# ---------------------------------------------------------------------------


class TestCrossScriptIntegration:
    """Mixed-script text transliterates each script correctly."""

    def test_russian_japanese_mixed(self) -> None:
        result = transliterate("Москва-トーキョー")
        assert "Moskva" in result
        assert "to-kiyo-" in result

    def test_slug_japanese(self) -> None:
        result = slugify("ラーメン")
        assert "ra" in result
        assert "men" in result

    def test_slug_russian(self) -> None:
        result = slugify("Привет мир")
        assert "privet" in result
        assert "mir" in result

    def test_pipeline_russian(self) -> None:
        pipe = TextPipeline(
            transliterate=True,
            fold_case=True,
            collapse_whitespace=True,
        )
        result = pipe("  Йогурт  и  Кефир  ")
        assert result == "yogurt i kefir"

    def test_pipeline_japanese(self) -> None:
        pipe = TextPipeline(
            normalize="NFKC",
            transliterate=True,
            fold_case=True,
        )
        result = pipe("ラーメン")
        assert result == "ra-men"

    def test_text_builder_japanese(self) -> None:
        result = Text("すし").transliterate().value
        assert result == "sushi"

    def test_text_builder_russian(self) -> None:
        result = Text("Йогурт").transliterate(lang="ru").value
        assert result == "Yogurt"
