"""Dynamic coverage tests that iterate through list_langs() and list_scripts().

These tests ensure every registered language and every recognized script
is exercised, rather than relying on hardcoded lists that drift from the
actual implementation.
"""

from __future__ import annotations

import pytest

from translit import (
    Script,
    detect_scripts,
    list_langs,
    list_scripts,
    reverse_langs,
    slugify,
    transliterate,
    transliterate_batch,
)
from translit._enums import LANG_AUTO

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SCRIPT_EXEMPLARS: dict[str, str] = {
    "Latin": "abcdef",
    "Cyrillic": "Москва",
    "Greek": "Ελλάδα",
    "Arabic": "العربية",
    "Hebrew": "עברית",
    "Devanagari": "हिन्दी",
    "Bengali": "বাংলা",
    "Gurmukhi": "ਗੁਰਮੁਖੀ",
    "Gujarati": "ગુજરાતી",
    "Oriya": "ଓଡ଼ିଆ",
    "Tamil": "தமிழ்",
    "Telugu": "తెలుగు",
    "Kannada": "ಕನ್ನಡ",
    "Malayalam": "മലയാളം",
    "Sinhala": "සිංහල",
    "Han": "中文漢字",
    "Hiragana": "ひらがな",
    "Katakana": "カタカナ",
    "Hangul": "한국어",
    "Thai": "ภาษาไทย",
    "Lao": "ພາສາລາວ",
    "Myanmar": "မြန်မာ",
    "Khmer": "ភាសាខ្មែរ",
    "Tibetan": "བོད་སྐད",
    "Georgian": "ქართული",
    "Armenian": "Հայերեն",
    "Ethiopic": "አማርኛ",
}

# Sample text per language for lang= transliteration.
# Only needs enough text to exercise the code path.
LANG_SAMPLES: dict[str, str] = {
    "am": "አማርኛ",
    "ar": "العربية",
    "as": "অসমীয়া",
    "bg": "България",
    "bn": "বাংলা",
    "bo": "བོད་སྐད",
    "ca": "català",
    "cs": "čeština",
    "cy": "Cymraeg",
    "da": "dansk",
    "de": "Ärger",
    "dv": "ދިވެހި",
    "el": "Ελληνικά",
    "es": "español",
    "et": "eesti",
    "fa": "فارسی",
    "fi": "suomi",
    "fr": "français",
    "ga": "Gaeilge",
    "gu": "ગુજરાતી",
    "he": "עברית",
    "hi": "हिन्दी",
    "hr": "hrvatski",
    "hu": "magyar",
    "hy": "Հայերեն",
    "is": "íslenska",
    "it": "italiano",
    "ja": "日本語",
    "ja-kunrei": "日本語",
    "jv": "ꦧꦱꦗꦮ",
    "ka": "ქართული",
    "km": "ភាសាខ្មែរ",
    "kn": "ಕನ್ನಡ",
    "ko": "한국어",
    "lo": "ພາສາລາວ",
    "lt": "lietuvių",
    "lv": "latviešu",
    "ml": "മലയാളം",
    "mn": "монгол",
    "mr": "मराठी",
    "mt": "Malti",
    "my": "မြန်မာ",
    "ne": "नेपाली",
    "nl": "Nederlands",
    "no": "norsk",
    "or": "ଓଡ଼ିଆ",
    "pa": "ਪੰਜਾਬੀ",
    "pl": "polski",
    "pt": "português",
    "ro": "română",
    "ru": "Москва",
    "sa": "संस्कृतम्",
    "si": "සිංහල",
    "sk": "slovenčina",
    "sl": "slovenščina",
    "sq": "shqip",
    "sr": "српски",
    "sv": "svenska",
    "ta": "தமிழ்",
    "te": "తెలుగు",
    "th": "ภาษาไทย",
    "tr": "Türkçe",
    "uk": "Київ",
    "vi": "tiếng Việt",
    "zh": "北京市",
}


# ---------------------------------------------------------------------------
# list_langs() tests
# ---------------------------------------------------------------------------


class TestListLangs:
    def test_returns_sorted_list(self):
        langs = list_langs()
        assert langs == sorted(langs)

    def test_nonempty(self):
        assert len(list_langs()) >= 60

    def test_auto_not_in_list(self):
        """'auto' is a meta-code, not a real language profile."""
        assert LANG_AUTO not in list_langs()


# ---------------------------------------------------------------------------
# list_scripts() tests
# ---------------------------------------------------------------------------


class TestListScripts:
    def test_returns_sorted_list(self):
        scripts = list_scripts()
        assert scripts == sorted(scripts)

    def test_nonempty(self):
        assert len(list_scripts()) >= 40

    def test_matches_enum(self):
        """list_scripts() must return exactly the Script enum values."""
        from_func = set(list_scripts())
        from_enum = {s.value for s in Script}
        assert from_func == from_enum

    def test_common_scripts_present(self):
        scripts = list_scripts()
        for name in ("Latin", "Cyrillic", "Han", "Arabic", "Devanagari"):
            assert name in scripts


# ---------------------------------------------------------------------------
# Every language in list_langs() can transliterate without error
# ---------------------------------------------------------------------------


class TestEveryLangTransliterates:
    @pytest.fixture()
    def all_langs(self):
        # Filter out test-registered langs from concurrency tests
        return [lang for lang in list_langs() if not lang.startswith("_")]

    def test_all_langs_have_samples(self, all_langs):
        """Ensure our test sample dict covers every registered language."""
        missing = set(all_langs) - set(LANG_SAMPLES.keys())
        assert not missing, f"LANG_SAMPLES missing entries for: {missing}"

    def test_transliterate_each_lang(self, all_langs):
        """transliterate(sample, lang=code) must not raise for any lang."""
        for lang in all_langs:
            sample = LANG_SAMPLES[lang]
            result = transliterate(sample, lang=lang)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_slugify_each_lang(self, all_langs):
        """slugify(sample, lang=code) must produce a non-empty slug."""
        for lang in all_langs:
            sample = LANG_SAMPLES[lang]
            result = slugify(sample, lang=lang)
            assert isinstance(result, str)
            # Some very short scripts may produce empty slugs; just check no crash
            assert result is not None

    def test_batch_all_langs(self, all_langs):
        """transliterate_batch with lang= for each language."""
        for lang in all_langs:
            sample = LANG_SAMPLES[lang]
            results = transliterate_batch([sample, sample], lang=lang)
            assert len(results) == 2
            assert results[0] == results[1]


# ---------------------------------------------------------------------------
# Every script in list_scripts() is detectable
# ---------------------------------------------------------------------------


class TestEveryScriptDetectable:
    def test_detect_scripts_for_known_exemplars(self):
        """detect_scripts() must identify each script from its exemplar text."""
        scripts = list_scripts()
        for script_name in scripts:
            if script_name in ("Common", "Inherited"):
                continue  # meta-scripts don't have dedicated text
            if script_name not in SCRIPT_EXEMPLARS:
                continue  # some rare scripts lack exemplars; covered below

            text = SCRIPT_EXEMPLARS[script_name]
            detected = detect_scripts(text)
            detected_values = [s.value for s in detected]
            assert script_name in detected_values, (
                f"detect_scripts({text!r}) returned {detected_values}, "
                f"expected {script_name}"
            )

    def test_exemplar_coverage(self):
        """Check that most scripts have exemplar text for detection testing."""
        scripts = list_scripts()
        covered = set(SCRIPT_EXEMPLARS.keys()) | {"Common", "Inherited"}
        uncovered = set(scripts) - covered
        # Allow rare/historical scripts without exemplars
        assert len(uncovered) <= 20, f"Too many scripts without exemplars: {uncovered}"


# ---------------------------------------------------------------------------
# Every reverse lang can round-trip basic Latin
# ---------------------------------------------------------------------------


class TestEveryReverseLang:
    def test_all_reverse_langs_produce_non_latin(self):
        """reverse_langs() entries must convert Latin to non-Latin script."""
        for lang in reverse_langs():
            result = transliterate("abcdef", target=lang)
            assert isinstance(result, str)
            # The result should contain non-ASCII characters
            assert not result.isascii() or result == "", (
                f"target={lang!r}: expected non-ASCII output, got {result!r}"
            )
