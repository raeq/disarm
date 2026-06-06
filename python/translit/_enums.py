"""Unicode script and normalization form enums, language/script metadata."""

from __future__ import annotations

import enum
from typing import TypedDict


class Script(enum.Enum):
    """Unicode script identifiers (UAX #24).

    Used as return values from detect_scripts() and as
    arguments to is_confusable() / normalize_confusables().

    Covers 52 scripts with full codepoint range detection.
    """

    # Major world scripts
    LATIN = "Latin"
    CYRILLIC = "Cyrillic"
    GREEK = "Greek"
    ARABIC = "Arabic"
    HEBREW = "Hebrew"

    # Indic scripts
    DEVANAGARI = "Devanagari"
    BENGALI = "Bengali"
    GURMUKHI = "Gurmukhi"
    GUJARATI = "Gujarati"
    ORIYA = "Oriya"
    TAMIL = "Tamil"
    TELUGU = "Telugu"
    KANNADA = "Kannada"
    MALAYALAM = "Malayalam"
    MEETEI_MAYEK = "MeeteiMayek"
    OL_CHIKI = "OlChiki"
    SINHALA = "Sinhala"

    # East Asian scripts
    HAN = "Han"
    HIRAGANA = "Hiragana"
    KATAKANA = "Katakana"
    HANGUL = "Hangul"
    LISU = "Lisu"

    # Southeast Asian scripts
    THAI = "Thai"
    LAO = "Lao"
    MYANMAR = "Myanmar"
    KHMER = "Khmer"
    BALINESE = "Balinese"
    BUGINESE = "Buginese"
    CHAM = "Cham"
    JAVANESE = "Javanese"
    SUNDANESE = "Sundanese"
    TAGALOG = "Tagalog"
    TAI_LE = "TaiLe"
    TAI_THAM = "TaiTham"
    NEW_TAI_LUE = "NewTaiLue"

    # Central/North Asian scripts
    TIBETAN = "Tibetan"
    MONGOLIAN = "Mongolian"

    # Caucasian scripts
    GEORGIAN = "Georgian"
    ARMENIAN = "Armenian"

    # African scripts
    ETHIOPIC = "Ethiopic"
    NKO = "NKo"
    BAMUM = "Bamum"
    TIFINAGH = "Tifinagh"
    VAI = "Vai"

    # Middle Eastern scripts
    SYRIAC = "Syriac"
    THAANA = "Thaana"
    COPTIC = "Coptic"

    # Americas
    CHEROKEE = "Cherokee"
    CANADIAN_ABORIGINAL = "CanadianAboriginal"

    # Historical European scripts
    RUNIC = "Runic"
    OGHAM = "Ogham"
    GOTHIC = "Gothic"

    # Ancient Near Eastern scripts
    OLD_PERSIAN = "OldPersian"
    CUNEIFORM = "Cuneiform"
    LINEAR_B = "LinearB"

    # Meta-scripts
    COMMON = "Common"
    INHERITED = "Inherited"

    def __repr__(self) -> str:
        return f"Script.{self.name}"


# Language code constants — European
LANG_BG: str = "bg"  # Bulgarian
LANG_CA: str = "ca"  # Catalan
LANG_CS: str = "cs"  # Czech
LANG_CY: str = "cy"  # Welsh
LANG_DA: str = "da"  # Danish
LANG_DE: str = "de"  # German
LANG_EL: str = "el"  # Greek
LANG_ES: str = "es"  # Spanish
LANG_ET: str = "et"  # Estonian
LANG_FI: str = "fi"  # Finnish
LANG_FR: str = "fr"  # French
LANG_GA: str = "ga"  # Irish
LANG_HR: str = "hr"  # Croatian
LANG_HU: str = "hu"  # Hungarian
LANG_IS: str = "is"  # Icelandic
LANG_IT: str = "it"  # Italian
LANG_LT: str = "lt"  # Lithuanian
LANG_LV: str = "lv"  # Latvian
LANG_MT: str = "mt"  # Maltese
LANG_NL: str = "nl"  # Dutch
LANG_NO: str = "no"  # Norwegian
LANG_PL: str = "pl"  # Polish
LANG_PT: str = "pt"  # Portuguese
LANG_RO: str = "ro"  # Romanian
LANG_SK: str = "sk"  # Slovak
LANG_SL: str = "sl"  # Slovenian
LANG_SQ: str = "sq"  # Albanian
LANG_SR: str = "sr"  # Serbian
LANG_SV: str = "sv"  # Swedish
LANG_TR: str = "tr"  # Turkish
LANG_UK: str = "uk"  # Ukrainian
LANG_VI: str = "vi"  # Vietnamese

# Language code constants — Middle Eastern
LANG_AR: str = "ar"  # Arabic
LANG_FA: str = "fa"  # Persian (Farsi)
LANG_JA: str = "ja"  # Japanese
LANG_KO: str = "ko"  # Korean
LANG_RU: str = "ru"  # Russian
LANG_ZH: str = "zh"  # Chinese

# Language code constants — Semitic
LANG_HE: str = "he"  # Hebrew

# Language code constants — Caucasian
LANG_HY: str = "hy"  # Armenian
LANG_KA: str = "ka"  # Georgian

# Language code constants — South Asian (non-Indic)
LANG_SI: str = "si"  # Sinhala

# Language code constants — Southeast Asian (Tai)
LANG_LO: str = "lo"  # Lao
LANG_TH: str = "th"  # Thai

# Language code constants — Southeast Asian (Brahmic)
LANG_KM: str = "km"  # Khmer
LANG_MY: str = "my"  # Myanmar (Burmese)

# Language code constants — Tibetan
LANG_BO: str = "bo"  # Tibetan

# Language code constants — Ethiopian
LANG_AM: str = "am"  # Amharic

# Language code constants — Indic
LANG_AS: str = "as"  # Assamese
LANG_BN: str = "bn"  # Bengali
LANG_GU: str = "gu"  # Gujarati
LANG_HI: str = "hi"  # Hindi
LANG_KN: str = "kn"  # Kannada
LANG_ML: str = "ml"  # Malayalam
LANG_MR: str = "mr"  # Marathi
LANG_NE: str = "ne"  # Nepali
LANG_OR: str = "or"  # Odia
LANG_PA: str = "pa"  # Punjabi
LANG_SA: str = "sa"  # Sanskrit
LANG_TA: str = "ta"  # Tamil
LANG_TE: str = "te"  # Telugu

# Language code constants — New scripts (v0.1.5)
LANG_DV: str = "dv"  # Dhivehi (Thaana)
LANG_JV: str = "jv"  # Javanese
LANG_MN: str = "mn"  # Mongolian

# Language code constants — New scripts (v0.3.0+)
LANG_BAN: str = "ban"  # Balinese
LANG_BAX: str = "bax"  # Bamum
LANG_BUG: str = "bug"  # Buginese (Lontara)
LANG_CHR: str = "chr"  # Cherokee
LANG_CJM: str = "cjm"  # Cham
LANG_COP: str = "cop"  # Coptic
LANG_KHB: str = "khb"  # Tai Lue (New Tai Lue script)
LANG_LIS: str = "lis"  # Lisu (Fraser script)
LANG_MNI: str = "mni"  # Meitei (Meetei Mayek script)
LANG_NOD: str = "nod"  # Northern Thai (Tai Tham/Lanna script)
LANG_NQO: str = "nqo"  # N'Ko
LANG_SAT: str = "sat"  # Santali (Ol Chiki script)
LANG_SU: str = "su"  # Sundanese
LANG_SYR: str = "syr"  # Syriac
LANG_TDD: str = "tdd"  # Tai Le
LANG_TL: str = "tl"  # Tagalog
LANG_TZM: str = "tzm"  # Tamazight/Berber (Tifinagh script)
LANG_VAI: str = "vai"  # Vai

# Auto-detection
LANG_AUTO: str = "auto"  # Auto-detect language from script


# ---------------------------------------------------------------------------
# Structured metadata — source of truth for display names
# ---------------------------------------------------------------------------


class LangMeta(TypedDict):
    """Metadata for a built-in language profile."""

    name: str  # Display name: "German", "Coptic"
    script: str  # Primary script: "Latin", "Coptic"
    region: str  # Geographic grouping: "European", "Southeast Asian"
    context: str  # Context-aware support: "full", "partial", or "none"


class ScriptMeta(TypedDict):
    """Metadata for a recognized Unicode script."""

    name: str  # Display name: "Latin", "Coptic"
    default_lang: str | None  # Default lang code for auto-detection, or None
    example: str  # Short native-script sample
    context_aware: bool  # Whether context=True improves transliteration for this script


# Every BUILTIN_LANGS code MUST have an entry. Drift = import-time assertion.
LANG_META: dict[str, LangMeta] = {
    # European
    "bg": {"name": "Bulgarian", "script": "Cyrillic", "region": "European", "context": "none"},
    "ca": {"name": "Catalan", "script": "Latin", "region": "European", "context": "none"},
    "cs": {"name": "Czech", "script": "Latin", "region": "European", "context": "none"},
    "cy": {"name": "Welsh", "script": "Latin", "region": "European", "context": "none"},
    "da": {"name": "Danish", "script": "Latin", "region": "European", "context": "none"},
    "de": {"name": "German", "script": "Latin", "region": "European", "context": "none"},
    "el": {"name": "Greek", "script": "Greek", "region": "European", "context": "none"},
    "es": {"name": "Spanish", "script": "Latin", "region": "European", "context": "none"},
    "et": {"name": "Estonian", "script": "Latin", "region": "European", "context": "none"},
    "fi": {"name": "Finnish", "script": "Latin", "region": "European", "context": "none"},
    "fr": {"name": "French", "script": "Latin", "region": "European", "context": "none"},
    "ga": {"name": "Irish", "script": "Latin", "region": "European", "context": "none"},
    "hr": {"name": "Croatian", "script": "Latin", "region": "European", "context": "none"},
    "hu": {"name": "Hungarian", "script": "Latin", "region": "European", "context": "none"},
    "is": {"name": "Icelandic", "script": "Latin", "region": "European", "context": "none"},
    "it": {"name": "Italian", "script": "Latin", "region": "European", "context": "none"},
    "lt": {"name": "Lithuanian", "script": "Latin", "region": "European", "context": "none"},
    "lv": {"name": "Latvian", "script": "Latin", "region": "European", "context": "none"},
    "mt": {"name": "Maltese", "script": "Latin", "region": "European", "context": "none"},
    "nl": {"name": "Dutch", "script": "Latin", "region": "European", "context": "none"},
    "no": {"name": "Norwegian", "script": "Latin", "region": "European", "context": "none"},
    "pl": {"name": "Polish", "script": "Latin", "region": "European", "context": "none"},
    "pt": {"name": "Portuguese", "script": "Latin", "region": "European", "context": "none"},
    "ro": {"name": "Romanian", "script": "Latin", "region": "European", "context": "none"},
    "ru": {"name": "Russian", "script": "Cyrillic", "region": "European", "context": "none"},
    "sk": {"name": "Slovak", "script": "Latin", "region": "European", "context": "none"},
    "sl": {"name": "Slovenian", "script": "Latin", "region": "European", "context": "none"},
    "sq": {"name": "Albanian", "script": "Latin", "region": "European", "context": "none"},
    "sr": {"name": "Serbian", "script": "Cyrillic", "region": "European", "context": "none"},
    "sv": {"name": "Swedish", "script": "Latin", "region": "European", "context": "none"},
    "tr": {"name": "Turkish", "script": "Latin", "region": "European", "context": "none"},
    "uk": {"name": "Ukrainian", "script": "Cyrillic", "region": "European", "context": "none"},
    "vi": {"name": "Vietnamese", "script": "Latin", "region": "Southeast Asian", "context": "none"},
    # Middle Eastern
    "ar": {"name": "Arabic", "script": "Arabic", "region": "Middle Eastern", "context": "full"},
    "fa": {
        "name": "Persian (Farsi)",
        "script": "Arabic",
        "region": "Middle Eastern",
        "context": "partial",
    },
    "he": {"name": "Hebrew", "script": "Hebrew", "region": "Middle Eastern", "context": "full"},
    "syr": {"name": "Syriac", "script": "Syriac", "region": "Middle Eastern", "context": "none"},
    "cop": {"name": "Coptic", "script": "Coptic", "region": "Middle Eastern", "context": "none"},
    # Caucasian
    "hy": {"name": "Armenian", "script": "Armenian", "region": "Caucasian", "context": "none"},
    "ka": {"name": "Georgian", "script": "Georgian", "region": "Caucasian", "context": "none"},
    # East Asian
    "ja": {"name": "Japanese", "script": "Han", "region": "East Asian", "context": "none"},
    "ja-kunrei": {
        "name": "Japanese (Kunrei-shiki)",
        "script": "Han",
        "region": "East Asian",
        "context": "none",
    },
    "ko": {"name": "Korean", "script": "Hangul", "region": "East Asian", "context": "none"},
    "zh": {"name": "Chinese", "script": "Han", "region": "East Asian", "context": "none"},
    # Indic
    "as": {"name": "Assamese", "script": "Bengali", "region": "Indic", "context": "none"},
    "bn": {"name": "Bengali", "script": "Bengali", "region": "Indic", "context": "none"},
    "gu": {"name": "Gujarati", "script": "Gujarati", "region": "Indic", "context": "none"},
    "hi": {"name": "Hindi", "script": "Devanagari", "region": "Indic", "context": "none"},
    "kn": {"name": "Kannada", "script": "Kannada", "region": "Indic", "context": "none"},
    "ml": {"name": "Malayalam", "script": "Malayalam", "region": "Indic", "context": "none"},
    "mni": {
        "name": "Meitei (Manipuri)",
        "script": "MeeteiMayek",
        "region": "Indic",
        "context": "none",
    },
    "mr": {"name": "Marathi", "script": "Devanagari", "region": "Indic", "context": "none"},
    "ne": {"name": "Nepali", "script": "Devanagari", "region": "Indic", "context": "none"},
    "or": {"name": "Odia", "script": "Oriya", "region": "Indic", "context": "none"},
    "pa": {"name": "Punjabi", "script": "Gurmukhi", "region": "Indic", "context": "none"},
    "sa": {"name": "Sanskrit", "script": "Devanagari", "region": "Indic", "context": "none"},
    "sat": {"name": "Santali", "script": "OlChiki", "region": "Indic", "context": "none"},
    "si": {"name": "Sinhala", "script": "Sinhala", "region": "South Asian", "context": "none"},
    "ta": {"name": "Tamil", "script": "Tamil", "region": "Indic", "context": "none"},
    "te": {"name": "Telugu", "script": "Telugu", "region": "Indic", "context": "none"},
    # South Asian (non-Indic)
    "dv": {
        "name": "Dhivehi (Maldivian)",
        "script": "Thaana",
        "region": "South Asian",
        "context": "none",
    },
    # Central/North Asian
    "bo": {"name": "Tibetan", "script": "Tibetan", "region": "Central Asian", "context": "none"},
    "mn": {
        "name": "Mongolian",
        "script": "Mongolian",
        "region": "Central Asian",
        "context": "none",
    },
    # Southeast Asian
    "ban": {
        "name": "Balinese",
        "script": "Balinese",
        "region": "Southeast Asian",
        "context": "none",
    },
    "bug": {
        "name": "Buginese",
        "script": "Buginese",
        "region": "Southeast Asian",
        "context": "none",
    },
    "cjm": {
        "name": "Eastern Cham",
        "script": "Cham",
        "region": "Southeast Asian",
        "context": "none",
    },
    "jv": {
        "name": "Javanese",
        "script": "Javanese",
        "region": "Southeast Asian",
        "context": "none",
    },
    "khb": {"name": "Lü", "script": "NewTaiLue", "region": "Southeast Asian", "context": "none"},
    "km": {"name": "Khmer", "script": "Khmer", "region": "Southeast Asian", "context": "none"},
    "lo": {"name": "Lao", "script": "Lao", "region": "Southeast Asian", "context": "none"},
    "my": {
        "name": "Myanmar (Burmese)",
        "script": "Myanmar",
        "region": "Southeast Asian",
        "context": "none",
    },
    "nod": {
        "name": "Northern Thai",
        "script": "TaiTham",
        "region": "Southeast Asian",
        "context": "none",
    },
    "su": {
        "name": "Sundanese",
        "script": "Sundanese",
        "region": "Southeast Asian",
        "context": "none",
    },
    "tdd": {"name": "Tai Nüa", "script": "TaiLe", "region": "Southeast Asian", "context": "none"},
    "th": {"name": "Thai", "script": "Thai", "region": "Southeast Asian", "context": "none"},
    "tl": {
        "name": "Tagalog/Filipino",
        "script": "Tagalog",
        "region": "Southeast Asian",
        "context": "none",
    },
    # African
    "am": {"name": "Amharic", "script": "Ethiopic", "region": "African", "context": "none"},
    "bax": {"name": "Bamum", "script": "Bamum", "region": "African", "context": "none"},
    "nqo": {"name": "N'Ko", "script": "NKo", "region": "African", "context": "none"},
    "tzm": {
        "name": "Central Atlas Tamazight",
        "script": "Tifinagh",
        "region": "African",
        "context": "none",
    },
    "vai": {"name": "Vai", "script": "Vai", "region": "African", "context": "none"},
    # Americas
    "chr": {"name": "Cherokee", "script": "Cherokee", "region": "Americas", "context": "none"},
    # Other
    "lis": {"name": "Lisu", "script": "Lisu", "region": "East Asian", "context": "none"},
}

# Every Script enum value (except Common/Inherited) MUST have an entry.
SCRIPT_META: dict[str, ScriptMeta] = {
    # Major world scripts
    "Latin": {"name": "Latin", "default_lang": None, "example": "ABCabc", "context_aware": False},
    "Cyrillic": {
        "name": "Cyrillic",
        "default_lang": "ru",
        "example": "Кириллица",
        "context_aware": False,
    },
    "Greek": {"name": "Greek", "default_lang": "el", "example": "Ελληνικά", "context_aware": False},
    "Arabic": {
        "name": "Arabic",
        "default_lang": "ar",
        "example": "العربية",
        "context_aware": True,
    },
    "Hebrew": {"name": "Hebrew", "default_lang": "he", "example": "עברית", "context_aware": True},
    # Indic
    "Devanagari": {
        "name": "Devanagari",
        "default_lang": "hi",
        "example": "देवनागरी",
        "context_aware": False,
    },
    "Bengali": {"name": "Bengali", "default_lang": "bn", "example": "বাংলা", "context_aware": False},
    "Gurmukhi": {
        "name": "Gurmukhi",
        "default_lang": "pa",
        "example": "ਗੁਰਮੁਖੀ",
        "context_aware": False,
    },
    "Gujarati": {
        "name": "Gujarati",
        "default_lang": "gu",
        "example": "ગુજરાતી",
        "context_aware": False,
    },
    "Oriya": {"name": "Odia", "default_lang": "or", "example": "ଓଡ଼ିଆ", "context_aware": False},
    "Tamil": {"name": "Tamil", "default_lang": "ta", "example": "தமிழ்", "context_aware": False},
    "Telugu": {"name": "Telugu", "default_lang": "te", "example": "తెలుగు", "context_aware": False},
    "Kannada": {"name": "Kannada", "default_lang": "kn", "example": "ಕನ್ನಡ", "context_aware": False},
    "Malayalam": {
        "name": "Malayalam",
        "default_lang": "ml",
        "example": "മലയാളം",
        "context_aware": False,
    },
    "Sinhala": {"name": "Sinhala", "default_lang": "si", "example": "සිංහල", "context_aware": False},
    # East Asian
    "Han": {"name": "Han (CJK)", "default_lang": "zh", "example": "漢字", "context_aware": False},
    "Hiragana": {
        "name": "Hiragana",
        "default_lang": "ja",
        "example": "ひらがな",
        "context_aware": False,
    },
    "Katakana": {
        "name": "Katakana",
        "default_lang": "ja",
        "example": "カタカナ",
        "context_aware": False,
    },
    "Hangul": {"name": "Hangul", "default_lang": "ko", "example": "한글", "context_aware": False},
    # Southeast Asian
    "Thai": {"name": "Thai", "default_lang": "th", "example": "ไทย", "context_aware": False},
    "Lao": {"name": "Lao", "default_lang": "lo", "example": "ລາວ", "context_aware": False},
    "Myanmar": {
        "name": "Myanmar",
        "default_lang": "my",
        "example": "မြန်မာ",
        "context_aware": False,
    },
    "Khmer": {"name": "Khmer", "default_lang": "km", "example": "ខ្មែរ", "context_aware": False},
    "Balinese": {
        "name": "Balinese",
        "default_lang": "ban",
        "example": "ᬅᬓᬗ",
        "context_aware": False,
    },
    "Javanese": {"name": "Javanese", "default_lang": "jv", "example": "ꦗꦮ", "context_aware": False},
    "TaiLe": {"name": "Tai Le", "default_lang": "tdd", "example": "ᥐᥑᥒ", "context_aware": False},
    "NewTaiLue": {
        "name": "New Tai Lue",
        "default_lang": "khb",
        "example": "ᦀᦁᦂ",
        "context_aware": False,
    },
    # Central/North Asian
    "Tibetan": {"name": "Tibetan", "default_lang": "bo", "example": "བོད", "context_aware": False},
    "Mongolian": {
        "name": "Mongolian",
        "default_lang": "mn",
        "example": "ᠮᠣᠩᠭᠣᠯ",
        "context_aware": False,
    },
    # Caucasian
    "Georgian": {
        "name": "Georgian",
        "default_lang": "ka",
        "example": "ქართული",
        "context_aware": False,
    },
    "Armenian": {
        "name": "Armenian",
        "default_lang": "hy",
        "example": "Հայերեն",
        "context_aware": False,
    },
    # African
    "Ethiopic": {
        "name": "Ethiopic (Ge'ez)",
        "default_lang": "am",
        "example": "ኢትዮጵያ",
        "context_aware": False,
    },
    "NKo": {"name": "N'Ko", "default_lang": "nqo", "example": "ߒߞߏ", "context_aware": False},
    "Vai": {"name": "Vai", "default_lang": "vai", "example": "ꔀꔁꔂ", "context_aware": False},
    # Middle Eastern
    "Syriac": {"name": "Syriac", "default_lang": "syr", "example": "ܐܒܓ", "context_aware": False},
    "Thaana": {"name": "Thaana", "default_lang": "dv", "example": "ދިވެހި", "context_aware": False},
    "Coptic": {"name": "Coptic", "default_lang": "cop", "example": "Ⲁⲁ Ⲃⲃ", "context_aware": False},
    # Americas
    "Cherokee": {
        "name": "Cherokee",
        "default_lang": "chr",
        "example": "ᏣᎳᎩ",
        "context_aware": False,
    },
    "CanadianAboriginal": {
        "name": "Canadian Aboriginal Syllabics",
        "default_lang": None,
        "example": "ᐃᓄᒃᑎᑐᑦ",
        "context_aware": False,
    },
    # Historical
    "Runic": {"name": "Runic", "default_lang": None, "example": "ᚠᚢᚦ", "context_aware": False},
    "Ogham": {"name": "Ogham", "default_lang": None, "example": "ᚁᚂᚃ", "context_aware": False},
    "Gothic": {"name": "Gothic", "default_lang": None, "example": "𐌰𐌱𐌲", "context_aware": False},
    # Ancient
    "OldPersian": {
        "name": "Old Persian",
        "default_lang": None,
        "example": "𐎠𐎡𐎢",
        "context_aware": False,
    },
    "Cuneiform": {
        "name": "Cuneiform",
        "default_lang": None,
        "example": "𒀀𒀁",
        "context_aware": False,
    },
    "LinearB": {"name": "Linear B", "default_lang": None, "example": "𐀀𐀁", "context_aware": False},
    # New scripts (v0.3.0+) — not in Script enum but in SCRIPT_RANGES
    "Buginese": {
        "name": "Buginese (Lontara)",
        "default_lang": "bug",
        "example": "ᨀᨁᨂ",
        "context_aware": False,
    },
    "TaiTham": {
        "name": "Tai Tham (Lanna)",
        "default_lang": "nod",
        "example": "ᨠᨡᨢ",
        "context_aware": False,
    },
    "Sundanese": {
        "name": "Sundanese",
        "default_lang": "su",
        "example": "ᮃᮄᮅ",
        "context_aware": False,
    },
    "OlChiki": {
        "name": "Ol Chiki",
        "default_lang": "sat",
        "example": "ᱚᱛᱜ",
        "context_aware": False,
    },
    "Tifinagh": {
        "name": "Tifinagh",
        "default_lang": "tzm",
        "example": "ⴰⴱⴳ",
        "context_aware": False,
    },
    "Bamum": {"name": "Bamum", "default_lang": "bax", "example": "ꚠꚡꚢ", "context_aware": False},
    "Lisu": {
        "name": "Lisu (Fraser)",
        "default_lang": "lis",
        "example": "ꓐꓑꓒ",
        "context_aware": False,
    },
    "Cham": {"name": "Cham", "default_lang": "cjm", "example": "ꨀꨁꨂ", "context_aware": False},
    "MeeteiMayek": {
        "name": "Meetei Mayek",
        "default_lang": "mni",
        "example": "ꯀꯁꯂ",
        "context_aware": False,
    },
    "Tagalog": {
        "name": "Tagalog (Baybayin)",
        "default_lang": "tl",
        "example": "ᜀᜁᜂ",
        "context_aware": False,
    },
}


# ---------------------------------------------------------------------------
# Import-time drift assertions
# ---------------------------------------------------------------------------

# Every LANG_* constant value must have a LANG_META entry.
# ja-kunrei is a variant mode with no LANG_* constant — excluded from constant check.
_LANG_META_NO_CONST = {"ja-kunrei"}  # codes in LANG_META without a LANG_* constant
_lang_const_codes = {
    v
    for k, v in globals().items()
    if k.startswith("LANG_") and k != "LANG_AUTO" and isinstance(v, str)
}
_meta_codes = set(LANG_META.keys()) - _LANG_META_NO_CONST
_drift = _lang_const_codes.symmetric_difference(_meta_codes)
assert not _drift, (
    f"LANG_META ↔ LANG_* constant drift: {_drift}. "
    "Every LANG_* constant needs a LANG_META entry and vice versa."
)

# Every Script enum value (except meta-scripts) must have a SCRIPT_META entry
_script_enum_values = {s.value for s in Script if s.value not in ("Common", "Inherited")}

_missing_scripts = _script_enum_values - set(SCRIPT_META.keys())
assert not _missing_scripts, (
    f"SCRIPT_META missing Script enum entries: {_missing_scripts}. "
    "Every Script enum value needs a SCRIPT_META entry."
)

del _lang_const_codes, _meta_codes, _drift, _script_enum_values, _missing_scripts
