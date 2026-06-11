"""Tests for disarm.transliterate and related functions."""

import pytest

from disarm import DisarmError, is_ascii, list_langs, strip_accents, transliterate


class TestTransliterate:
    """Core transliteration tests."""

    def test_ascii_passthrough(self) -> None:
        assert transliterate("hello world") == "hello world"

    def test_empty_string(self) -> None:
        assert transliterate("") == ""

    def test_latin_diacritics(self) -> None:
        assert transliterate("café") == "cafe"
        assert transliterate("naïve") == "naive"
        assert transliterate("résumé") == "resume"

    def test_german_default(self) -> None:
        # Default table: ü → u
        assert transliterate("München") == "Munchen"

    def test_german_lang(self) -> None:
        # German override: ü → ue
        assert transliterate("München", lang="de") == "Muenchen"
        assert transliterate("Ärger", lang="de") == "Aerger"
        assert transliterate("Öl", lang="de") == "Oel"

    def test_cyrillic(self) -> None:
        assert transliterate("Москва") == "Moskva"
        assert transliterate("Привет") == "Privet"

    def test_errors_replace(self) -> None:
        # U+20000 (CJK Extension B) has no mapping — gets replaced
        result = transliterate("\U00020000", errors="replace", replace_with="?")
        assert result == "?"

    def test_errors_ignore(self) -> None:
        # U+20000 (CJK Extension B) has no mapping in our tables
        result = transliterate("\U00020000", errors="ignore")
        assert "\U00020000" not in result

    def test_errors_preserve(self) -> None:
        # U+20000 (CJK Extension B) has no mapping in our tables
        result = transliterate("\U00020000", errors="preserve")
        assert "\U00020000" in result

    def test_invalid_errors_mode(self) -> None:
        with pytest.raises(DisarmError):
            transliterate("café", errors="explode")  # type: ignore[arg-type]

    def test_mixed_ascii_unicode(self) -> None:
        assert transliterate("hello café world") == "hello cafe world"

    # --- French ---

    def test_french_default(self) -> None:
        assert transliterate("crème brûlée") == "creme brulee"
        assert transliterate("garçon") == "garcon"
        assert transliterate("français") == "francais"

    def test_french_lang(self) -> None:
        assert transliterate("cœur", lang="fr") == "coeur"
        assert transliterate("Œuvre", lang="fr") == "OEuvre"

    # --- Spanish ---

    def test_spanish_default(self) -> None:
        assert transliterate("España") == "Espana"
        assert transliterate("niño") == "nino"

    def test_spanish_lang(self) -> None:
        assert transliterate("¡Hola!", lang="es") == "!Hola!"
        assert transliterate("¿Qué?", lang="es") == "?Que?"

    # --- Norwegian ---

    def test_norwegian_lang(self) -> None:
        assert transliterate("Ål", lang="no") == "Aal"
        assert transliterate("Ørsted", lang="no") == "Oersted"
        assert transliterate("Ærlig", lang="no") == "Aerlig"

    # --- Danish ---

    def test_danish_lang(self) -> None:
        assert transliterate("København", lang="da") == "Koebenhavn"
        assert transliterate("Åben", lang="da") == "Aaben"

    # --- Swedish ---

    def test_swedish_lang(self) -> None:
        assert transliterate("Malmö", lang="sv") == "Malmoe"
        assert transliterate("Åland", lang="sv") == "Aland"  # Å stays A in Swedish
        assert transliterate("Ärende", lang="sv") == "Aerende"

    # --- Finnish ---

    def test_finnish_lang(self) -> None:
        # Finnish ä/ö are independent phonemes (not ae/oe variants like Swedish)
        assert transliterate("Hämäläinen", lang="fi") == "Hamalainen"
        assert transliterate("Öljy", lang="fi") == "Oljy"

    # --- Icelandic ---

    def test_icelandic_lang(self) -> None:
        assert transliterate("Ísland", lang="is") == "Island"
        assert transliterate("Reykjavík", lang="is") == "Reykjavik"
        assert transliterate("Þór", lang="is") == "Thor"
        assert transliterate("Guðmundur", lang="is") == "Gudmundur"

    # --- Polish ---

    def test_polish(self) -> None:
        assert transliterate("Łódź") == "Lodz"
        assert transliterate("Kraków") == "Krakow"
        assert transliterate("Gdańsk") == "Gdansk"
        assert transliterate("Wrocław") == "Wroclaw"

    # --- Czech ---

    def test_czech(self) -> None:
        assert transliterate("Dvořák") == "Dvorak"
        assert transliterate("Plzeň") == "Plzen"
        assert transliterate("České") == "Ceske"

    # --- Hungarian ---

    def test_hungarian(self) -> None:
        assert transliterate("Budapest") == "Budapest"
        assert transliterate("Győr") == "Gyor"
        assert transliterate("Pécs") == "Pecs"

    # --- Romanian ---

    def test_romanian(self) -> None:
        assert transliterate("București") == "Bucuresti"
        assert transliterate("Iași") == "Iasi"

    # --- Turkish ---

    def test_turkish(self) -> None:
        assert transliterate("İstanbul") == "Istanbul"
        assert transliterate("Türkiye") == "Turkiye"

    # --- Dutch ---

    def test_dutch(self) -> None:
        # IJ ligature
        assert transliterate("Ĳsselmeer") == "IJsselmeer"

    # --- Portuguese ---

    def test_portuguese(self) -> None:
        assert transliterate("São Paulo") == "Sao Paulo"
        assert transliterate("coração") == "coracao"

    # --- Italian ---

    def test_italian(self) -> None:
        assert transliterate("perché") == "perche"
        assert transliterate("città") == "citta"

    # --- Estonian ---

    def test_estonian_lang(self) -> None:
        assert transliterate("Tallinn") == "Tallinn"
        assert transliterate("Öö", lang="et") == "Oeoe"
        assert transliterate("Ülemiste", lang="et") == "Uelemiste"

    # --- Croatian ---

    def test_croatian(self) -> None:
        assert transliterate("Zagreb") == "Zagreb"
        assert transliterate("Čakovec") == "Cakovec"
        assert transliterate("Đakovo") == "Dakovo"

    # --- Slovenian ---

    def test_slovenian(self) -> None:
        assert transliterate("Ljubljana") == "Ljubljana"
        assert transliterate("Škofja") == "Skofja"

    # --- Slovak ---

    def test_slovak(self) -> None:
        assert transliterate("Bratislava") == "Bratislava"
        assert transliterate("Trenčín") == "Trencin"

    # --- Bulgarian ---

    def test_bulgarian_lang(self) -> None:
        assert transliterate("България", lang="bg") == "Balgariya"

    # --- Ukrainian ---

    def test_ukrainian_lang(self) -> None:
        # Ukrainian Г→H (not G)
        assert transliterate("Київ", lang="uk") == "Kyiv"

    # --- Greek ---

    def test_greek_default(self) -> None:
        assert transliterate("Αθήνα") == "Athina"
        assert transliterate("Ελλάδα") == "Ellada"

    # --- Welsh ---

    def test_welsh(self) -> None:
        assert transliterate("Ŵyr") == "Wyr"
        assert transliterate("Ŷnys") == "Ynys"

    # --- Maltese ---

    def test_maltese(self) -> None:
        assert transliterate("Għawdex") == "Ghawdex"
        assert transliterate("Ċetta") == "Cetta"

    # --- Vietnamese ---

    def test_vietnamese(self) -> None:
        assert transliterate("Hà Nội") == "Ha Noi"
        assert transliterate("Đà Nẵng") == "Da Nang"

    # --- Latin Extended Additional coverage ---

    def test_capital_sharp_s(self) -> None:
        assert transliterate("ẞ") == "SS"


class TestStripAccents:
    """Tests for accent stripping."""

    def test_basic(self) -> None:
        assert strip_accents("café") == "cafe"
        assert strip_accents("naïve") == "naive"

    def test_no_accents(self) -> None:
        assert strip_accents("hello") == "hello"

    def test_empty(self) -> None:
        assert strip_accents("") == ""


class TestIsAscii:
    """Tests for ASCII detection."""

    def test_ascii(self) -> None:
        assert is_ascii("hello world")
        assert is_ascii("")
        assert is_ascii("123!@#")

    def test_non_ascii(self) -> None:
        assert not is_ascii("café")
        assert not is_ascii("héllo")
        assert not is_ascii("日本語")


# ═══════════════════════════════════════════════════════════════════
# Language profile smoke tests
# ═══════════════════════════════════════════════════════════════════

# Maps each language code to (input, expected_output) tuples.
# One representative word per language — enough to prove the
# lang-specific PHF table is wired up and accessible.
LANG_SMOKE_TESTS: dict[str, tuple[str, str]] = {
    "bg": ("България", "Balgariya"),
    "ca": ("café", "cafe"),  # Catalan uses default Latin
    "cs": ("České", "Ceske"),
    "cy": ("Ŵyr", "Wyr"),
    "da": ("København", "Koebenhavn"),
    "de": ("München", "Muenchen"),
    "el": ("Αθήνα", "Athina"),
    "es": ("¡Hola!", "!Hola!"),
    "et": ("Öö", "Oeoe"),
    "fi": ("Hämäläinen", "Hamalainen"),
    "fr": ("cœur", "coeur"),
    "ga": ("Éire", "Eire"),  # Irish uses default Latin
    "hr": ("Čakovec", "Cakovec"),
    "hu": ("Győr", "Gyor"),
    "is": ("Þór", "Thor"),
    "it": ("perché", "perche"),
    "lt": ("Vilnius", "Vilnius"),  # Lithuanian — ASCII city name
    "lv": ("Rīga", "Riga"),
    "mt": ("Għawdex", "Ghawdex"),
    "nl": ("Ĳsselmeer", "IJsselmeer"),
    "no": ("Ørsted", "Oersted"),
    "pl": ("Łódź", "Lodz"),
    "pt": ("São Paulo", "Sao Paulo"),
    "ro": ("București", "Bucuresti"),
    "sk": ("Trenčín", "Trencin"),
    "sl": ("Škofja", "Skofja"),
    "sq": ("Tiranë", "Tirane"),
    "sr": ("Београд", "Beograd"),
    "sv": ("Malmö", "Malmoe"),
    "tr": ("İstanbul", "Istanbul"),
    "uk": ("Київ", "Kyiv"),
    "vi": ("Hà Nội", "Ha Noi"),
    "hi": ("नमस्ते", "namaste"),
    "bn": ("কলকাতা", "kalakata"),
    "ta": ("தமிழ்", "tamizh"),
    "te": ("తెలుగు", "telugu"),
    "gu": ("ગુજરાતી", "gujarati"),
    "kn": ("ಕನ್ನಡ", "kannada"),
    "ml": ("മലയാളം", "malayalam"),
    "he": ("שלום", "shlvm"),
    "hy": ("Հայաստան", "Hayastan"),
    "ka": ("თბილისი", "tbilisi"),
    "si": ("සිංහල", "simhala"),
    "th": ("กรุงเทพ", "krungethph"),
    "lo": ("ລາວ", "law"),
    "am": ("ኢትዮጵያ", "ityopya"),
    "bo": ("བོད", "boda"),
    "km": ("កម្ពុជា", "kampucha"),
    "my": ("မြန်မာ", "mrnma"),
}


class TestLanguageProfileSmoke:
    """Parametrized smoke tests: each supported language code must
    produce the expected transliteration for a representative word.

    These tests catch:
    - PHF table wiring errors (wrong lang → wrong table)
    - Missing language dispatch in lookup_lang()
    - Regressions from transliteration table edits
    """

    @pytest.mark.parametrize(
        "lang,input_text,expected",
        [pytest.param(lang, inp, exp, id=lang) for lang, (inp, exp) in LANG_SMOKE_TESTS.items()],
    )
    def test_lang_transliteration(self, lang: str, input_text: str, expected: str) -> None:
        result = transliterate(input_text, lang=lang)
        assert result == expected, (
            f"lang={lang!r}: transliterate({input_text!r}) = {result!r}, expected {expected!r}"
        )


class TestLanguageProfileRegistry:
    """Tests for the language profile system."""

    def test_list_langs_returns_all_builtin(self) -> None:
        """list_langs() must include all 60 built-in languages."""
        langs = list_langs()
        expected_langs = {
            "am",
            "ar",
            "as",
            "bg",
            "bn",
            "bo",
            "ca",
            "cs",
            "cy",
            "da",
            "de",
            "el",
            "es",
            "et",
            "fi",
            "fr",
            "ga",
            "gu",
            "he",
            "hi",
            "hr",
            "hu",
            "hy",
            "is",
            "it",
            "ja",
            "ka",
            "km",
            "kn",
            "ko",
            "lo",
            "lt",
            "lv",
            "ml",
            "mr",
            "mt",
            "my",
            "ne",
            "nl",
            "no",
            "or",
            "pa",
            "pl",
            "pt",
            "ro",
            "ru",
            "sa",
            "si",
            "sk",
            "sl",
            "sq",
            "sr",
            "sv",
            "ta",
            "te",
            "th",
            "tr",
            "uk",
            "vi",
            "zh",
        }
        for code in expected_langs:
            assert code in langs, f"Language code {code!r} missing from list_langs()"

    def test_list_langs_sorted(self) -> None:
        """list_langs() should return sorted codes."""
        langs = list_langs()
        assert langs == sorted(langs)

    @pytest.mark.parametrize(
        "lang",
        [pytest.param(lang, id=lang) for lang in LANG_SMOKE_TESTS.keys()],
    )
    def test_every_smoke_lang_is_registered(self, lang: str) -> None:
        """Every language in our smoke tests must be in list_langs()."""
        assert lang in list_langs(), (
            f"Smoke test language {lang!r} not found in list_langs(). "
            f"Add it to BUILTIN_LANGS in mod.rs."
        )

    def test_ascii_passthrough_all_langs(self) -> None:
        """Pure ASCII input should pass through unchanged for any language."""
        for lang in list_langs():
            result = transliterate("hello world 123", lang=lang)
            assert result == "hello world 123", (
                f"lang={lang!r}: ASCII passthrough failed, got {result!r}"
            )


class TestIndicTransliteration:
    """Tests for Indic (Brahmic) script transliteration."""

    # --- Devanagari (Hindi) ---

    def test_devanagari_bare_consonant(self) -> None:
        assert transliterate("क") == "ka"

    def test_devanagari_virama(self) -> None:
        assert transliterate("क्") == "k"

    def test_devanagari_matra(self) -> None:
        assert transliterate("की") == "ki"
        assert transliterate("कू") == "ku"

    def test_devanagari_namaste(self) -> None:
        assert transliterate("नमस्ते") == "namaste"

    def test_devanagari_dilli(self) -> None:
        assert transliterate("दिल्ली") == "dilli"

    def test_devanagari_mumbai(self) -> None:
        assert transliterate("मुम्बई") == "mumbai"

    def test_devanagari_digits(self) -> None:
        assert transliterate("१२३") == "123"
        assert transliterate("०") == "0"
        assert transliterate("९") == "9"

    # --- Bengali ---

    def test_bengali_basic(self) -> None:
        assert transliterate("কলকাতা") == "kalakata"

    def test_bengali_digits(self) -> None:
        assert transliterate("১২৩") == "123"

    # --- Tamil ---

    def test_tamil_basic(self) -> None:
        assert transliterate("தமிழ்") == "tamizh"

    def test_tamil_digits(self) -> None:
        assert transliterate("௧௨௩") == "123"

    # --- Telugu ---

    def test_telugu_basic(self) -> None:
        assert transliterate("తెలుగు") == "telugu"

    # --- Gujarati ---

    def test_gujarati_basic(self) -> None:
        assert transliterate("ગુજરાતી") == "gujarati"

    # --- Kannada ---

    def test_kannada_basic(self) -> None:
        result = transliterate("ಕನ್ನಡ")
        assert result == "kannada"

    # --- Malayalam ---

    def test_malayalam_basic(self) -> None:
        result = transliterate("മലയാളം")
        assert result == "malayalam"

    # --- Odia ---

    def test_odia_basic(self) -> None:
        result = transliterate("ଓଡ଼ିଆ")
        assert result.startswith("o")
        assert result.isascii()

    # --- Gurmukhi (Punjabi) ---

    def test_gurmukhi_basic(self) -> None:
        result = transliterate("ਗੁਰਮੁਖੀ")
        assert result.isascii()
        assert result.startswith("g")

    # --- Devanagari independent vowels ---

    def test_devanagari_independent_vowels(self) -> None:
        assert transliterate("अ") == "a"
        assert transliterate("आ") == "aa"
        assert transliterate("इ") == "i"
        assert transliterate("उ") == "u"
        assert transliterate("ए") == "e"
        assert transliterate("ओ") == "o"
        assert transliterate("औ") == "au"

    def test_devanagari_all_matras(self) -> None:
        assert transliterate("का") == "ka"
        assert transliterate("के") == "ke"
        assert transliterate("को") == "ko"
        assert transliterate("कै") == "kai"
        assert transliterate("कौ") == "kau"
        assert transliterate("कु") == "ku"
        assert transliterate("कृ") == "kr"

    def test_devanagari_isolated_clusters(self) -> None:
        assert transliterate("स्त") == "sta"
        assert transliterate("ल्ल") == "lla"
        assert transliterate("क्ष") == "ksha"

    def test_devanagari_consecutive_consonants_keep_inherent_a(self) -> None:
        assert transliterate("कल") == "kala"
        assert transliterate("नम") == "nama"

    def test_devanagari_anusvara(self) -> None:
        result = transliterate("हिंदी")
        assert result.isascii()
        assert result.startswith("hi")

    def test_devanagari_visarga(self) -> None:
        result = transliterate("दुःख")
        assert result.isascii()
        assert "h" in result

    def test_devanagari_nuqta(self) -> None:
        result = transliterate("क़")
        assert result.isascii()
        result2 = transliterate("ज़")
        assert result2.isascii()

    def test_bare_matra_no_crash(self) -> None:
        result = transliterate("\u093f")
        assert isinstance(result, str)

    def test_bare_virama_no_crash(self) -> None:
        result = transliterate("\u094d")
        assert isinstance(result, str)

    def test_devanagari_multiword(self) -> None:
        assert transliterate("नमस्ते दुनिया") == "namaste duniya"

    # --- Indic digit tests ---

    def test_telugu_digits(self) -> None:
        assert transliterate("౧౨౩") == "123"

    def test_gujarati_digits(self) -> None:
        assert transliterate("૧૨૩") == "123"

    def test_kannada_digits(self) -> None:
        assert transliterate("೧೨೩") == "123"

    def test_malayalam_digits(self) -> None:
        assert transliterate("൧൨൩") == "123"

    def test_gurmukhi_digits(self) -> None:
        assert transliterate("੧੨੩") == "123"

    def test_odia_digits(self) -> None:
        assert transliterate("୧୨୩") == "123"

    # --- Bengali conjunct ---

    def test_bengali_conjunct(self) -> None:
        result = transliterate("ক্ষ")
        assert result.isascii()
        assert len(result) > 0

    # --- Mixed script ---

    def test_mixed_latin_devanagari(self) -> None:
        assert transliterate("Hello नमस्ते") == "Hello namaste"

    # --- Cross-script consistency ---

    def test_all_indic_produce_ascii(self) -> None:
        """All Indic script samples should transliterate to pure ASCII."""
        samples = [
            "नमस्ते",  # Devanagari
            "কলকাতা",  # Bengali
            "தமிழ்",  # Tamil
            "తెలుగు",  # Telugu
            "ગુજરાતી",  # Gujarati
            "ಕನ್ನಡ",  # Kannada
            "മലയാളം",  # Malayalam
            "ଓଡ଼ିଆ",  # Odia
            "ਗੁਰਮੁਖੀ",  # Gurmukhi
        ]
        for sample in samples:
            result = transliterate(sample, errors="ignore")
            assert result.isascii(), f"Expected ASCII for {sample!r}, got {result!r}"
            assert len(result) > 0, f"Expected non-empty result for {sample!r}"


class TestSinhalaTransliteration:
    """Tests for Sinhala script transliteration."""

    def test_sinhala_bare_consonant(self) -> None:
        assert transliterate("\u0d9a") == "ka"

    def test_sinhala_virama(self) -> None:
        assert transliterate("\u0d9a\u0dca") == "k"

    def test_sinhala_matra(self) -> None:
        assert transliterate("\u0d9a\u0dd2") == "ki"
        assert transliterate("\u0d9a\u0dd4") == "ku"

    def test_sinhala_word(self) -> None:
        result = transliterate("සිංහල")
        assert result == "simhala"

    def test_sinhala_independent_vowels(self) -> None:
        assert transliterate("\u0d85") == "a"
        assert transliterate("\u0d89") == "i"
        assert transliterate("\u0d8b") == "u"

    def test_sinhala_digits(self) -> None:
        assert transliterate("෧෨෩") == "123"

    def test_sinhala_produces_ascii(self) -> None:
        samples = ["සිංහල", "ලංකා", "කොළඹ"]
        for sample in samples:
            result = transliterate(sample, errors="ignore")
            assert result.isascii(), f"Expected ASCII for {sample!r}, got {result!r}"
            assert len(result) > 0

    def test_sinhala_mixed_with_latin(self) -> None:
        result = transliterate("Hello සිංහල")
        assert result.isascii()
        assert "Hello" in result


class TestGeorgianTransliteration:
    """Tests for Georgian script transliteration."""

    def test_georgian_mkhedruli(self) -> None:
        assert transliterate("თბილისი") == "tbilisi"

    def test_georgian_sakartvelo(self) -> None:
        assert transliterate("საქართველო") == "sakartvelo"

    def test_georgian_alphabet_sample(self) -> None:
        """First few Mkhedruli letters."""
        assert transliterate("ა") == "a"
        assert transliterate("ბ") == "b"
        assert transliterate("გ") == "g"

    def test_georgian_digraphs(self) -> None:
        assert transliterate("ჟ") == "zh"
        assert transliterate("შ") == "sh"
        assert transliterate("ჩ") == "ch"
        assert transliterate("ხ") == "kh"

    def test_georgian_produces_ascii(self) -> None:
        samples = ["თბილისი", "საქართველო", "ქართული", "ბათუმი"]
        for sample in samples:
            result = transliterate(sample, errors="ignore")
            assert result.isascii(), f"Expected ASCII for {sample!r}, got {result!r}"
            assert len(result) > 0

    def test_georgian_mixed_with_latin(self) -> None:
        assert transliterate("Hello თბილისი") == "Hello tbilisi"

    def test_georgian_mtavruli_uppercase(self) -> None:
        """Mtavruli (U+1C90+) uppercase letters."""
        assert transliterate("\u1c90") == "A"
        assert transliterate("\u1c91") == "B"

    def test_georgian_supplement(self) -> None:
        """Georgian Supplement (U+2D00+) lowercase Nuskhuri."""
        assert transliterate("\u2d00") == "a"
        assert transliterate("\u2d01") == "b"


class TestArmenianTransliteration:
    """Tests for Armenian script transliteration."""

    def test_armenian_yerevan(self) -> None:
        assert transliterate("Երևան") == "Eryevan"

    def test_armenian_hayastan(self) -> None:
        assert transliterate("Հայաստան") == "Hayastan"

    def test_armenian_alphabet_sample(self) -> None:
        assert transliterate("Ա") == "A"
        assert transliterate("Բ") == "B"
        assert transliterate("Գ") == "G"
        assert transliterate("ա") == "a"
        assert transliterate("բ") == "b"

    def test_armenian_digraphs(self) -> None:
        assert transliterate("Ժ") == "Zh"
        assert transliterate("Շ") == "Sh"
        assert transliterate("Խ") == "Kh"
        assert transliterate("ժ") == "zh"

    def test_armenian_yev_ligature(self) -> None:
        assert transliterate("և") == "yev"

    def test_armenian_presentation_ligatures(self) -> None:
        assert transliterate("\ufb13") == "mn"
        assert transliterate("\ufb14") == "me"
        assert transliterate("\ufb15") == "mi"
        assert transliterate("\ufb16") == "vn"
        assert transliterate("\ufb17") == "mkh"

    def test_armenian_hyphen(self) -> None:
        assert transliterate("\u058a") == "-"

    def test_armenian_produces_ascii(self) -> None:
        samples = ["Հայաստան", "Երևան", "Հայերեն"]
        for sample in samples:
            result = transliterate(sample, errors="ignore")
            assert result.isascii(), f"Expected ASCII for {sample!r}, got {result!r}"
            assert len(result) > 0

    def test_armenian_mixed_with_latin(self) -> None:
        assert transliterate("Hello Երևան") == "Hello Eryevan"


class TestThaiTransliteration:
    """Tests for Thai script transliteration (RTGS)."""

    def test_thai_consonants(self) -> None:
        assert transliterate("ก") == "k"
        assert transliterate("ข") == "kh"
        assert transliterate("ง") == "ng"
        assert transliterate("จ") == "ch"

    def test_thai_vowels(self) -> None:
        assert transliterate("ะ") == "a"
        assert transliterate("า") == "a"
        assert transliterate("ิ") == "i"
        assert transliterate("ุ") == "u"

    def test_thai_leading_vowels(self) -> None:
        assert transliterate("เ") == "e"
        assert transliterate("แ") == "ae"
        assert transliterate("โ") == "o"
        assert transliterate("ไ") == "ai"

    def test_thai_tone_marks_dropped(self) -> None:
        """Tone marks should be dropped in RTGS romanization."""
        assert transliterate("น้ำ") == "nam"
        assert transliterate("ก่") == "k"
        assert transliterate("ก้") == "k"
        assert transliterate("ก๊") == "k"
        assert transliterate("ก๋") == "k"

    def test_thai_digits(self) -> None:
        assert transliterate("๐๑๒๓๔๕๖๗๘๙") == "0123456789"

    def test_thai_word_bangkok(self) -> None:
        result = transliterate("กรุงเทพ")
        assert result.isascii()
        assert "k" in result  # ก = k

    def test_thai_word_thailand(self) -> None:
        result = transliterate("ประเทศไทย")
        assert result.isascii()

    def test_thai_produces_ascii(self) -> None:
        samples = ["กรุงเทพ", "ประเทศไทย", "สวัสดี", "ภาษาไทย"]
        for sample in samples:
            result = transliterate(sample, errors="ignore")
            assert result.isascii(), f"Expected ASCII for {sample!r}, got {result!r}"
            assert len(result) > 0

    def test_thai_mixed_with_latin(self) -> None:
        result = transliterate("Hello กรุงเทพ")
        assert "Hello" in result
        assert result.isascii()

    def test_thai_baht_sign(self) -> None:
        assert transliterate("฿") == "B"


class TestLaoTransliteration:
    """Tests for Lao script transliteration (BGN/PCGN)."""

    def test_lao_consonants(self) -> None:
        assert transliterate("ກ") == "k"
        assert transliterate("ຂ") == "kh"
        assert transliterate("ງ") == "ng"
        assert transliterate("ຈ") == "ch"

    def test_lao_vowels(self) -> None:
        assert transliterate("ະ") == "a"
        assert transliterate("າ") == "a"
        assert transliterate("ິ") == "i"
        assert transliterate("ຸ") == "u"

    def test_lao_leading_vowels(self) -> None:
        assert transliterate("ເ") == "e"
        assert transliterate("ແ") == "ae"
        assert transliterate("ໂ") == "o"
        assert transliterate("ໄ") == "ai"

    def test_lao_tone_marks_dropped(self) -> None:
        """Tone marks should be dropped in BGN/PCGN romanization."""
        # Lao tone marks: U+0EC8-0ECB
        assert transliterate("ກ\u0ec8") == "k"
        assert transliterate("ກ\u0ec9") == "k"

    def test_lao_word_lao(self) -> None:
        assert transliterate("ລາວ") == "law"

    def test_lao_word_vientiane(self) -> None:
        result = transliterate("ວຽງຈັນ")
        assert result.isascii()

    def test_lao_digits(self) -> None:
        assert transliterate("໐໑໒໓໔໕໖໗໘໙") == "0123456789"

    def test_lao_produces_ascii(self) -> None:
        samples = ["ລາວ", "ວຽງຈັນ", "ສະບາຍດີ"]
        for sample in samples:
            result = transliterate(sample, errors="ignore")
            assert result.isascii(), f"Expected ASCII for {sample!r}, got {result!r}"
            assert len(result) > 0

    def test_lao_mixed_with_latin(self) -> None:
        result = transliterate("Hello ລາວ")
        assert "Hello" in result
        assert result.isascii()

    def test_lao_composite_consonants(self) -> None:
        assert transliterate("ໜ") == "hn"
        assert transliterate("ໝ") == "hm"


class TestEthiopicTransliteration:
    """Tests for Ethiopic (Ge'ez/Amharic) script transliteration."""

    def test_ethiopic_syllable_orders(self) -> None:
        """First consonant (h) through all 7 vowel orders."""
        assert transliterate("ሀ") == "he"  # order 1 (ä)
        assert transliterate("ሁ") == "hu"  # order 2
        assert transliterate("ሂ") == "hi"  # order 3
        assert transliterate("ሃ") == "ha"  # order 4
        assert transliterate("ሄ") == "he"  # order 5 (é)
        assert transliterate("ህ") == "h"  # order 6 (ə/bare)
        assert transliterate("ሆ") == "ho"  # order 7

    def test_ethiopic_ethiopia(self) -> None:
        assert transliterate("ኢትዮጵያ") == "ityopya"

    def test_ethiopic_addis_ababa(self) -> None:
        assert transliterate("አዲስ አበባ") == "edis ebeba"

    def test_ethiopic_digits(self) -> None:
        assert transliterate("፩") == "1"
        assert transliterate("፪") == "2"
        assert transliterate("፱") == "9"

    def test_ethiopic_punctuation(self) -> None:
        assert transliterate("።") == "."
        assert transliterate("፣") == ","
        assert transliterate("፧") == "?"

    def test_ethiopic_produces_ascii(self) -> None:
        samples = ["ኢትዮጵያ", "አዲስ አበባ", "ሰላም", "ኤርትራ"]
        for sample in samples:
            result = transliterate(sample, errors="ignore")
            assert result.isascii(), f"Expected ASCII for {sample!r}, got {result!r}"
            assert len(result) > 0

    def test_ethiopic_mixed_with_latin(self) -> None:
        assert transliterate("hello ሰላም") == "hello selam"


class TestMyanmarTransliteration:
    """Tests for Myanmar (Burmese) script transliteration."""

    def test_myanmar_consonants(self) -> None:
        assert transliterate("က") == "ka"
        assert transliterate("ခ") == "kha"
        assert transliterate("ဂ") == "ga"

    def test_myanmar_word(self) -> None:
        result = transliterate("မြန်မာ")
        assert result.isascii()
        assert len(result) > 0

    def test_myanmar_virama(self) -> None:
        """Asat (U+103A) strips inherent vowel."""
        assert transliterate("န်") == "n"

    def test_myanmar_dependent_vowels(self) -> None:
        """Dependent vowel replaces inherent 'a'."""
        assert transliterate("ကိ") == "ki"
        assert transliterate("ကု") == "ku"

    def test_myanmar_medials(self) -> None:
        """Medial consonants strip inherent vowel from preceding consonant."""
        result = transliterate("ကြ")  # ka + medial ra
        assert result == "kr"

    def test_myanmar_digits(self) -> None:
        assert transliterate("၀") == "0"
        assert transliterate("၉") == "9"

    def test_myanmar_punctuation(self) -> None:
        assert transliterate("၊") == ","
        assert transliterate("။") == "."

    def test_myanmar_produces_ascii(self) -> None:
        samples = ["မြန်မာ", "ရန်ကုန်", "မန္တလေး"]
        for sample in samples:
            result = transliterate(sample, errors="ignore")
            assert result.isascii(), f"Expected ASCII for {sample!r}, got {result!r}"
            assert len(result) > 0

    def test_myanmar_mixed_with_latin(self) -> None:
        result = transliterate("hello မြန်မာ")
        assert "hello" in result
        assert result.isascii()


class TestKhmerTransliteration:
    """Tests for Khmer (Cambodian) script transliteration."""

    def test_khmer_consonants(self) -> None:
        assert transliterate("ក") == "ka"
        assert transliterate("ខ") == "kha"

    def test_khmer_cambodia(self) -> None:
        assert transliterate("កម្ពុជា") == "kampucha"

    def test_khmer_coeng(self) -> None:
        """Coeng (U+17D2) stacks consonants — strips inherent vowel."""
        assert transliterate("ក្រ") == "kra"  # ka + coeng + ra

    def test_khmer_dependent_vowels(self) -> None:
        assert transliterate("កិ") == "ke"
        assert transliterate("កុ") == "ku"

    def test_khmer_digits(self) -> None:
        assert transliterate("០") == "0"
        assert transliterate("៩") == "9"

    def test_khmer_produces_ascii(self) -> None:
        samples = ["កម្ពុជា", "ភ្នំពេញ", "សៀមរាប"]
        for sample in samples:
            result = transliterate(sample, errors="ignore")
            assert result.isascii(), f"Expected ASCII for {sample!r}, got {result!r}"
            assert len(result) > 0

    def test_khmer_mixed_with_latin(self) -> None:
        result = transliterate("hello កម្ពុជា")
        assert "hello" in result
        assert result.isascii()


class TestTibetanTransliteration:
    """Tests for Tibetan script transliteration."""

    def test_tibetan_consonants(self) -> None:
        assert transliterate("ཀ") == "ka"
        assert transliterate("ཁ") == "kha"
        assert transliterate("ག") == "ga"

    def test_tibetan_tibet(self) -> None:
        result = transliterate("བོད")
        assert result == "boda"

    def test_tibetan_vowel_signs(self) -> None:
        """Vowel signs replace inherent 'a'."""
        assert transliterate("ཀི") == "ki"
        assert transliterate("ཀུ") == "ku"
        assert transliterate("ཀེ") == "ke"
        assert transliterate("ཀོ") == "ko"

    def test_tibetan_om(self) -> None:
        assert transliterate("ༀ") == "om"

    def test_tibetan_digits(self) -> None:
        assert transliterate("༠") == "0"
        assert transliterate("༩") == "9"

    def test_tibetan_produces_ascii(self) -> None:
        samples = ["བོད", "ལྷ་ས", "ༀ"]
        for sample in samples:
            result = transliterate(sample, errors="ignore")
            assert result.isascii(), f"Expected ASCII for {sample!r}, got {result!r}"
            assert len(result) > 0

    def test_tibetan_subjoined(self) -> None:
        """Subjoined consonants (stacking) produce transliteration."""
        result = transliterate("ལྷ")  # la + subjoined ha
        assert result.isascii()
        assert len(result) > 0

    def test_tibetan_mixed_with_latin(self) -> None:
        result = transliterate("hello བོད")
        assert "hello" in result
        assert result.isascii()


class TestHebrewTransliteration:
    """Tests for Hebrew script transliteration."""

    def test_hebrew_consonants_unpointed(self) -> None:
        """Unpointed Hebrew produces consonant skeleton."""
        assert transliterate("שלום") == "shlvm"
        assert transliterate("ישראל") == "yshr'l"

    def test_hebrew_final_forms(self) -> None:
        assert transliterate("ך") == "kh"
        assert transliterate("ם") == "m"
        assert transliterate("ן") == "n"
        assert transliterate("ף") == "f"
        assert transliterate("ץ") == "ts"

    def test_hebrew_nikkud(self) -> None:
        """Vowel points produce correct vowels."""
        assert transliterate("\u05b4") == "i"  # hiriq
        assert transliterate("\u05b8") == "a"  # qamats
        assert transliterate("\u05b9") == "o"  # holam
        assert transliterate("\u05bb") == "u"  # qubbuts

    def test_hebrew_presentation_forms_dagesh(self) -> None:
        """Precomposed consonant+dagesh forms give correct romanization."""
        assert transliterate("\ufb31") == "b"  # bet + dagesh
        assert transliterate("\ufb3a") == "k"  # final kaf + dagesh
        assert transliterate("\ufb44") == "p"  # pe + dagesh

    def test_hebrew_shin_sin_dots(self) -> None:
        """Shin/sin dot presentation forms distinguish sh vs s."""
        assert transliterate("\ufb2a") == "sh"  # shin + shin dot
        assert transliterate("\ufb2b") == "s"  # shin + sin dot

    def test_hebrew_maqaf(self) -> None:
        assert transliterate("\u05be") == "-"

    def test_hebrew_yiddish_ligatures(self) -> None:
        assert transliterate("\u05f0") == "v"  # double vav
        assert transliterate("\u05f1") == "vy"  # vav yod
        assert transliterate("\u05f2") == "y"  # double yod

    def test_hebrew_alef_lamed_ligature(self) -> None:
        assert transliterate("\ufb4f") == "al"

    def test_hebrew_cantillation_stripped(self) -> None:
        """Cantillation marks should be stripped (empty mapping)."""
        result = transliterate("\u0591")
        assert result == "" or result == "[?]"  # depends on error mode
        result_ignore = transliterate("\u0591", errors="ignore")
        assert result_ignore == ""

    def test_hebrew_mixed_with_latin(self) -> None:
        assert transliterate("שלום world") == "shlvm world"

    def test_hebrew_produces_ascii(self) -> None:
        samples = ["שלום", "ישראל", "ירושלים", "תל אביב"]
        for sample in samples:
            result = transliterate(sample, errors="ignore")
            assert result.isascii(), f"Expected ASCII for {sample!r}, got {result!r}"
            assert len(result) > 0, f"Expected non-empty for {sample!r}"


class TestReplaceWithEmpty:
    """Regression: fix #6 — replace_with="" is documented as equivalent to errors="ignore".

    Before the fix, this equivalence was undocumented, causing user confusion
    when empty replace_with silently dropped characters instead of replacing them.
    """

    def test_replace_with_empty_equals_ignore_latin(self) -> None:
        """replace_with='' must produce the same result as errors='ignore' for diacritics."""
        ignore = transliterate("café", errors="ignore")
        replace_empty = transliterate("café", errors="replace", replace_with="")
        assert ignore == replace_empty

    def test_replace_with_empty_equals_ignore_cjk(self) -> None:
        """replace_with='' must produce the same result as errors='ignore' for CJK fallback chars."""
        # Use a character unlikely to be in any table with no lang set
        text = "hello★world"
        ignore = transliterate(text, errors="ignore")
        replace_empty = transliterate(text, errors="replace", replace_with="")
        assert ignore == replace_empty

    def test_replace_with_nonempty_substitutes(self) -> None:
        """Non-empty replace_with must substitute the replacement string (not drop the char)."""
        result = transliterate("★", errors="replace", replace_with="[?]")
        assert result == "[?]"

    def test_unidecode_compat_uses_replace_with_empty(self) -> None:
        """The unidecode() shim uses replace_with='' — result must match errors='ignore'."""
        from disarm._compat import unidecode

        text = "café★résumé"
        compat = unidecode(text)
        native = transliterate(text, errors="replace", replace_with="")
        assert compat == native


# ---------------------------------------------------------------------------
# Real-world text samples for every supported language.
# Each entry: lang -> (native_text, description).
# The test asserts that transliterate(native_text, lang=lang).isascii() is True.
# ---------------------------------------------------------------------------
_ALL_LANG_ASCII_SAMPLES: dict[str, tuple[str, str]] = {
    # --- European (Latin-based) ---
    "bg": ("Република България е държава в Югоизточна Европа", "Bulgarian constitution"),
    "ca": ("Catalunya és una comunitat autònoma d'Espanya", "Catalan"),
    "cs": ("Česká republika je stát ve střední Evropě", "Czech"),
    "cy": ("Cymru yw gwlad sy'n rhan o'r Deyrnas Unedig", "Welsh"),
    "da": ("København er Danmarks hovedstad og største by", "Danish"),
    "de": ("Die Bundesrepublik Deutschland ist ein Bundesstaat in Mitteleuropa", "German"),
    "el": ("Η Ελληνική Δημοκρατία είναι χώρα της νοτιοανατολικής Ευρώπης", "Greek"),
    "es": ("España es un país soberano transcontinental", "Spanish"),
    "et": ("Eesti Vabariik on riik Põhja-Euroopas Läänemere ääres", "Estonian"),
    "fi": ("Suomen tasavalta on valtio Pohjois-Euroopassa", "Finnish"),
    "fr": ("La République française est un État transcontinental", "French"),
    "ga": ("Éire nó Poblacht na hÉireann is tír í", "Irish"),
    "hr": ("Republika Hrvatska je država u srednjoj Europi", "Croatian"),
    "hu": ("Magyarország közép-európai ország", "Hungarian"),
    "is": ("Ísland er eyríki á norðanverðum Atlantshafi", "Icelandic"),
    "it": ("La Repubblica Italiana è uno Stato membro dell'Unione europea", "Italian"),
    "lt": ("Lietuvos Respublika yra valstybė šiaurės Europoje", "Lithuanian"),
    "lv": ("Latvijas Republika ir valsts Ziemeļeiropā", "Latvian"),
    "mt": ("Ir-Repubblika ta' Malta hija stat gżejjer fil-Mediterran", "Maltese"),
    "nl": ("Het Koninkrijk der Nederlanden is een staat in West-Europa", "Dutch"),
    "no": ("Kongeriket Norge er et nordisk land i Skandinavia", "Norwegian"),
    "pl": ("Rzeczpospolita Polska jest państwem w Europie Środkowej", "Polish"),
    "pt": ("A República Portuguesa é um país situado no sudoeste da Europa", "Portuguese"),
    "ro": ("România este un stat situat în sud-estul Europei", "Romanian"),
    "sk": ("Slovenská republika je štát v strednej Európe", "Slovak"),
    "sl": ("Republika Slovenija je država v srednji Evropi", "Slovenian"),
    "sq": ("Republika e Shqipërisë është një shtet në Europën Juglindore", "Albanian"),
    "sr": ("Република Србија је држава у Југоисточној Европи", "Serbian"),
    "sv": ("Konungariket Sverige är ett nordiskt land på Skandinaviska halvön", "Swedish"),
    "tr": ("Türkiye Cumhuriyeti Avrupa ile Asya arasında yer alan bir ülkedir", "Turkish"),
    "uk": ("Україна є державою у Східній та Центральній Європі", "Ukrainian"),
    "vi": ("Cộng hòa xã hội chủ nghĩa Việt Nam là một quốc gia", "Vietnamese"),
    # --- East Asian ---
    "ja": ("日本国は東アジアに位置する島国である", "Japanese"),
    "ja-kunrei": ("しちつふじ", "Japanese Kunrei-shiki kana"),
    "ko": ("대한민국은 동아시아에 있는 공화국이다", "Korean"),
    "zh": ("中华人民共和国是位于东亚的社会主义国家", "Chinese"),
    # --- Middle Eastern ---
    "ar": ("المملكة العربية السعودية دولة عربية تقع في شبه الجزيرة العربية", "Arabic"),
    "fa": ("جمهوری اسلامی ایران کشوری در خاورمیانه است", "Persian"),
    "he": ("מדינת ישראל היא מדינה במזרח התיכון", "Hebrew"),
    # --- Indic ---
    "hi": ("भारत गणराज्य दक्षिण एशिया में स्थित एक देश है", "Hindi"),
    "bn": ("গণপ্রজাতন্ত্রী বাংলাদেশ দক্ষিণ এশিয়ার একটি রাষ্ট্র", "Bengali"),
    "ta": ("தமிழ்நாடு இந்தியாவின் தெற்கே அமைந்துள்ள மாநிலம்", "Tamil"),
    "te": ("తెలుగు భాష ద్రావిడ భాషా కుటుంబానికి చెందిన భాష", "Telugu"),
    "gu": ("ગુજરાત ભારતનું એક રાજ્ય છે જે ભારતના પશ્ચિમ ભાગમાં", "Gujarati"),
    "kn": ("ಕರ್ನಾಟಕ ದಕ್ಷಿಣ ಭಾರತದ ಒಂದು ರಾಜ್ಯ", "Kannada"),
    "ml": ("കേരളം ഇന്ത്യയിലെ ഒരു സംസ്ഥാനമാണ്", "Malayalam"),
    "mr": ("महाराष्ट्र हे भारतातील एक राज्य आहे", "Marathi"),
    "ne": ("नेपाल एशियाको एक स्वतन्त्र देश हो", "Nepali"),
    "or": ("ଓଡ଼ିଶା ଭାରତର ପୂର୍ବ ଉପକୂଳରେ ଅବସ୍ଥିତ", "Odia"),
    "pa": ("ਪੰਜਾਬ ਭਾਰਤ ਦਾ ਇੱਕ ਰਾਜ ਹੈ", "Punjabi"),
    "sa": ("संस्कृतम् जगतः एका प्राचीनतमा भाषा", "Sanskrit"),
    "as": ("অসম ভাৰতৰ উত্তৰ পূৰ্বাঞ্চলৰ এখন ৰাজ্য", "Assamese"),
    # --- Caucasian ---
    "hy": ("Հայաստան Հանրապետություն Հայ երկիր", "Armenian"),
    "ka": ("საქართველო სახელმწიფოა აღმოსავლეთ ევროპაში", "Georgian"),
    # --- South/Southeast Asian ---
    "si": ("ශ්‍රී ලංකා ප්‍රජාතාන්ත්‍රික සමාජවාදී ජනරජය", "Sinhala"),
    "th": ("ประเทศไทยเป็นรัฐชาติอันตั้งอยู่ในเอเชียตะวันออกเฉียงใต้", "Thai"),
    "lo": ("ສາທາລະນະລັດ ປະຊາທິປະໄຕ ປະຊາຊົນລາວ", "Lao"),
    "km": ("ព្រះរាជាណាចក្រកម្ពុជា ជាប្រទេសមួយ", "Khmer"),
    "my": ("မြန်မာနိုင်ငံသည် အရှေ့တောင်အာရှတွင်", "Myanmar"),
    # --- Tibetan ---
    "bo": ("བོད་རང་སྐྱོང་ལྗོངས་ནི་རྒྱ་ནག་གི་ཁོངས་གཏོགས", "Tibetan"),
    # --- African ---
    "am": (
        "የኢትዮጵያ ፌዴራላዊ ዲሞክራሲያዊ ሪፐብሊክ መንግሥት "
        "የፌዴራሉ መንግስት ሁለት ምክር ቤቶች ሲኖሩት እነሱም "
        "የሕዝብ ተወካዮች ምክር ቤትና የፌዴሬሽን ምክር ቤት ናቸው፡፡ "
        "የፌዴራሉ መንግስት ከፍተኛ የሕግ አውጪ ስልጣን ያለው "
        "የህዝብ ተወካዮች ምክር ቤት ነው፡፡ "
        "አባላቱም በየአምስት አመቱ በሚደረግ አብላጫ ድምፅ ያገኘ "
        "ተወዳዳሪ አሸናፊ በሚሆንበት የምርጫ ሥርዓት ይመረጣሉ፡፡ "
        "የክልል ከፍተኛ የሕግ አውጪ አካል የክልሉ ምክር ቤት ነው፡፡",
        "Amharic Ethiopian constitution preamble",
    ),
    # --- Russian (already covered by bg/sr/uk but test separately) ---
    "ru": ("Российская Федерация является демократическим федеративным государством", "Russian"),
    # --- Dhivehi (Thaana script) ---
    "dv": ("ދިވެހިރާއްޖެ", "Dhivehi Maldives"),
    # --- Javanese ---
    "jv": ("\ua990\ua99f\ua9aa\ua9a3\ua9a8", "Javanese consonants"),
    # --- Mongolian ---
    "mn": ("\u182e\u1823\u1829\u182d\u1823\u182f", "Mongolian mongol"),
    # --- New scripts (v0.3.0+) ---
    "ban": ("\u1b05\u1b13\u1b17\u1b15\u1b18", "Balinese consonants"),
    "bax": ("\ua6a0\ua6a1\ua6a2\ua6a3", "Bamum syllables"),
    "bug": ("\u1a00\u1a01\u1a02\u1a03\u1a04", "Buginese Lontara"),
    "chr": ("\u13a0\u13a1\u13a2\u13a3\u13a4", "Cherokee syllabary"),
    "cjm": ("\uaa00\uaa01\uaa02\uaa03", "Cham consonants"),
    "cop": ("\u2c80\u2c81\u2c82\u2c83\u2c84\u2c85", "Coptic letters"),
    "khb": ("\u1980\u1981\u1982\u1983", "New Tai Lue consonants"),
    "lis": ("\ua4d0\ua4d1\ua4d2\ua4d3", "Lisu Fraser letters"),
    "mni": ("\uabc0\uabc1\uabc2\uabc3", "Meetei Mayek letters"),
    "nod": ("\u1a20\u1a21\u1a22\u1a23", "Tai Tham Lanna consonants"),
    "nqo": ("\u07c1\u07c2\u07c3\u07c4", "NKo digits"),
    "sat": ("\u1c5a\u1c5b\u1c5c\u1c5d", "Ol Chiki letters"),
    "su": ("\u1b83\u1b84\u1b85\u1b86", "Sundanese consonants"),
    "syr": ("\u0710\u0712\u0713\u0715", "Syriac letters"),
    "tdd": ("\u1950\u1951\u1952\u1953", "Tai Le consonants"),
    "tl": ("\u1700\u1701\u1702\u1703", "Tagalog Baybayin"),
    "tzm": ("\u2d30\u2d31\u2d33\u2d37", "Tifinagh Berber letters"),
    "vai": ("\ua500\ua501\ua502\ua503", "Vai syllables"),
}


class TestAllLanguagesProduceAscii:
    """Every supported language must produce pure ASCII output for real-world text.

    This catches:
    - Missing TSV entries (unmapped codepoints pass through as non-ASCII)
    - Incorrect mappings that produce non-ASCII romanizations
    - Regression from TSV edits
    """

    @pytest.mark.parametrize(
        "lang,sample,desc",
        [
            pytest.param(lang, sample, desc, id=f"{lang}-{desc}")
            for lang, (sample, desc) in _ALL_LANG_ASCII_SAMPLES.items()
        ],
    )
    def test_transliterate_produces_ascii(self, lang: str, sample: str, desc: str) -> None:
        result = transliterate(sample, lang=lang)
        non_ascii = [f"U+{ord(ch):04X} ({ch})" for ch in result if ord(ch) > 127]
        assert result.isascii(), (
            f"lang={lang!r} ({desc}): non-ASCII chars in output: {non_ascii}\n"
            f"Input:  {sample!r}\n"
            f"Output: {result!r}"
        )

    @pytest.mark.parametrize(
        "lang,sample,desc",
        [
            pytest.param(lang, sample, desc, id=f"{lang}-{desc}")
            for lang, (sample, desc) in _ALL_LANG_ASCII_SAMPLES.items()
        ],
    )
    def test_transliterate_produces_nonempty(self, lang: str, sample: str, desc: str) -> None:
        """Transliteration must produce non-empty output for non-empty input."""
        result = transliterate(sample, lang=lang)
        assert len(result.strip()) > 0, (
            f"lang={lang!r} ({desc}): empty output for non-empty input\nInput: {sample!r}"
        )

    def test_all_registered_langs_have_samples(self) -> None:
        """Every language in list_langs() must have a sample in this test."""
        registered = {lang for lang in list_langs() if not lang.startswith("_")}
        sampled = set(_ALL_LANG_ASCII_SAMPLES.keys())
        missing = registered - sampled
        assert not missing, (
            f"Languages registered but missing ASCII test samples: {sorted(missing)}"
        )
