"""Tests for translit.transliterate and related functions."""

import pytest

from translit import TranslitError, is_ascii, list_langs, strip_accents, transliterate


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
        with pytest.raises(TranslitError):
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
        assert transliterate("Hämäläinen", lang="fi") == "Haemaelaeinen"
        assert transliterate("Öljy", lang="fi") == "Oeljy"

    # --- Icelandic ---

    def test_icelandic_lang(self) -> None:
        assert transliterate("Ísland", lang="is") == "Island"
        assert transliterate("Reykjavík", lang="is") == "Reykjavik"
        assert transliterate("Þór", lang="is") == "Thor"
        assert transliterate("Guðmundur", lang="is") == "Gudhmundur"

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
    "fi": ("Hämäläinen", "Haemaelaeinen"),
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
        """list_langs() must include all 37 built-in languages."""
        langs = list_langs()
        expected_langs = {
            "ar",
            "bg",
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
            "hr",
            "hu",
            "is",
            "it",
            "ja",
            "ko",
            "lt",
            "lv",
            "mt",
            "nl",
            "no",
            "pl",
            "pt",
            "ro",
            "ru",
            "sk",
            "sl",
            "sq",
            "sr",
            "sv",
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
        from translit._compat import unidecode

        text = "café★résumé"
        compat = unidecode(text)
        native = transliterate(text, errors="replace", replace_with="")
        assert compat == native
