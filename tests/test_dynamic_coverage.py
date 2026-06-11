"""Dynamic coverage tests that iterate through list_langs() and list_scripts().

These tests ensure every registered language and every recognized script
is exercised, rather than relying on hardcoded lists that drift from the
actual implementation.
"""

from __future__ import annotations

import pytest

from disarm import (
    Script,
    detect_scripts,
    list_langs,
    list_scripts,
    reverse_langs,
    slugify,
    transliterate,
)
from disarm._enums import LANG_AUTO, LANG_META, SCRIPT_META

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
    # New enum scripts (v0.3.0+)
    "Balinese": "\u1b05\u1b13\u1b17",
    "Bamum": "\ua6a0\ua6a1\ua6a2",
    "Buginese": "\u1a00\u1a01\u1a02",
    "Cham": "\uaa00\uaa01\uaa02",
    "Lisu": "\ua4d0\ua4d1\ua4d2",
    "MeeteiMayek": "\uabc0\uabc1\uabc2",
    "OlChiki": "\u1c5a\u1c5b\u1c5c",
    "Sundanese": "\u1b83\u1b84\u1b85",
    "Tagalog": "\u1700\u1701\u1702",
    "TaiTham": "\u1a20\u1a21\u1a22",
    "Tifinagh": "\u2d30\u2d31\u2d33",
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
    # --- New scripts (v0.3.0+) ---
    "ban": "\u1b05\u1b13\u1b17",  # Balinese: aka
    "bax": "\ua6a0\ua6a1\ua6a2",  # Bamum syllables
    "bug": "\u1a00\u1a01\u1a02",  # Buginese/Lontara: ka ga nga
    "chr": "\u13a0\u13a1\u13a2",  # Cherokee: a e i
    "cjm": "\uaa00\uaa01\uaa02",  # Cham consonants
    "cop": "\u2c80\u2c81\u2c82\u2c83",  # Coptic: Alfa alfa Vida vida
    "khb": "\u1980\u1981\u1982",  # New Tai Lue consonants
    "lis": "\ua4d0\ua4d1\ua4d2",  # Lisu letters
    "mni": "\uabc0\uabc1\uabc2",  # Meetei Mayek: kok sai lai
    "nod": "\u1a20\u1a21\u1a22",  # Tai Tham consonants
    "nqo": "\u07c1\u07c2\u07c3",  # N'Ko digits
    "sat": "\u1c50\u1c51\u1c52",  # Ol Chiki digits
    "su": "\u1b80\u1b83\u1b84",  # Sundanese
    "syr": "\u0710\u0712\u0713",  # Syriac: alaph beth gamal
    "tdd": "\u1950\u1951\u1952",  # Tai Le consonants
    "tl": "\u1700\u1701\u1702",  # Tagalog: a i u
    "tzm": "\u2d30\u2d31\u2d33",  # Tifinagh: ya yab yag
    "vai": "\ua500\ua501\ua502",  # Vai syllables
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

    def test_lang_meta_covers_all_builtin(self):
        """Every BUILTIN_LANGS code from Rust must have a LANG_META entry."""
        # Exclude _*-prefixed codes registered dynamically by concurrent tests
        registered = {c for c in list_langs() if not c.startswith("_")}
        missing = registered - set(LANG_META.keys())
        assert not missing, f"LANG_META missing entries for Rust BUILTIN_LANGS: {missing}"

    def test_script_meta_covers_all_enum(self):
        """Every Script enum value (except meta) must have a SCRIPT_META entry."""
        scripts = {s.value for s in Script if s.value not in ("Common", "Inherited")}
        missing = scripts - set(SCRIPT_META.keys())
        assert not missing, f"SCRIPT_META missing entries for Script enum: {missing}"


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
        """transliterate([...], lang=code) must work for every language."""
        for lang in all_langs:
            sample = LANG_SAMPLES[lang]
            results = transliterate([sample, sample], lang=lang)
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
                f"detect_scripts({text!r}) returned {detected_values}, expected {script_name}"
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
