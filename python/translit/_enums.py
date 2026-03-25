"""Unicode script and normalization form enums."""

from __future__ import annotations

import enum


class Script(enum.Enum):
    """Unicode script identifiers (UAX #24).

    Used as return values from detect_scripts() and as
    arguments to is_confusable() / normalize_confusables().

    Covers 39 scripts with full codepoint range detection.
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
    SINHALA = "Sinhala"

    # East Asian scripts
    HAN = "Han"
    HIRAGANA = "Hiragana"
    KATAKANA = "Katakana"
    HANGUL = "Hangul"

    # Southeast Asian scripts
    THAI = "Thai"
    LAO = "Lao"
    MYANMAR = "Myanmar"
    KHMER = "Khmer"
    BALINESE = "Balinese"
    JAVANESE = "Javanese"
    TAI_LE = "TaiLe"
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

# Language code constants — non-European
LANG_AR: str = "ar"  # Arabic
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
