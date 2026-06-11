"""Shared test fixtures and Hypothesis strategies for disarm.

Centralizes Unicode sample data and property-based testing strategies
so that new tests can import them from one place instead of
rediscovering or redeclaring them per file.
"""

from __future__ import annotations

import pytest
from hypothesis import strategies as st

from disarm._enums import Script

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

#: Full Unicode text including BMP, SMP, combining marks, emoji, CJK, etc.
unicode_text = st.text(alphabet=st.characters(codec="utf-8"))

#: The four Unicode normalization forms as strings.
nf_forms = st.sampled_from(["NFC", "NFD", "NFKC", "NFKD"])


# ---------------------------------------------------------------------------
# Canonical script samples — one per Script enum member (excluding meta)
# ---------------------------------------------------------------------------
# Keys: Script enum member
# Values: short string containing ONLY characters of that script
#         (no Common/Inherited characters like digits or spaces)

SCRIPT_SAMPLES: dict[Script, str] = {
    # Major world scripts
    Script.LATIN: "abcdef",
    Script.CYRILLIC: "Москва",
    Script.GREEK: "Ελλάδα",
    Script.ARABIC: "العربية",
    Script.HEBREW: "עברית",
    # Indic scripts
    Script.DEVANAGARI: "हिन्दी",
    Script.BENGALI: "বাংলা",
    Script.GURMUKHI: "ਗੁਰਮੁਖੀ",
    Script.GUJARATI: "ગુજરાતી",
    Script.ORIYA: "ଓଡ଼ିଆ",
    Script.TAMIL: "தமிழ்",
    Script.TELUGU: "తెలుగు",
    Script.KANNADA: "ಕನ್ನಡ",
    Script.MALAYALAM: "മലയാളം",
    Script.MEETEI_MAYEK: "\uabc0\uabc1\uabc2",  # ꯀꯁꯂ
    Script.OL_CHIKI: "\u1c5a\u1c5b\u1c5c",  # ᱚᱛᱜ
    Script.SINHALA: "සිංහල",
    # East Asian scripts
    Script.HAN: "中文漢字",
    Script.HIRAGANA: "ひらがな",
    Script.KATAKANA: "カタカナ",
    Script.HANGUL: "한국어",
    Script.LISU: "\ua4d0\ua4d1\ua4d2",  # ꓐꓑꓒ
    # Southeast Asian scripts
    Script.THAI: "ภาษาไทย",
    Script.LAO: "ພາສາລາວ",
    Script.MYANMAR: "မြန်မာ",
    Script.KHMER: "ភាសាខ្មែរ",
    Script.BALINESE: "\u1b05\u1b13\u1b17",  # ᬅᬓᬗ
    Script.BUGINESE: "\u1a00\u1a01\u1a02",  # ᨀᨁᨂ
    Script.CHAM: "\uaa00\uaa01\uaa02",  # ꨀꨁꨂ
    Script.JAVANESE: "\ua984\ua989\ua98e",  # ꦄꦉꦎ
    Script.SUNDANESE: "\u1b83\u1b84\u1b85",  # ᮃᮄᮅ
    Script.TAGALOG: "\u1700\u1701\u1702",  # ᜀᜁᜂ
    Script.TAI_LE: "\u1950\u1951\u1952",  # ᥐᥑᥒ
    Script.TAI_THAM: "\u1a20\u1a21\u1a22",  # ᨠᨡᨢ
    Script.NEW_TAI_LUE: "\u1980\u1981\u1982",  # ᦀᦁᦂ
    # Central/North Asian scripts
    Script.TIBETAN: "བོད་སྐད",
    Script.MONGOLIAN: "\u1820\u1821\u1822",  # ᠠᠡᠢ
    # Caucasian scripts
    Script.GEORGIAN: "ქართული",
    Script.ARMENIAN: "Հայերեն",
    # African scripts
    Script.ETHIOPIC: "አማርኛ",
    Script.NKO: "\u07c1\u07c2\u07c3",  # ߁߂߃
    Script.BAMUM: "\ua6a0\ua6a1\ua6a2",  # ꚠꚡꚢ
    Script.TIFINAGH: "\u2d30\u2d31\u2d33",  # ⴰⴱⴳ
    Script.VAI: "\ua500\ua501\ua502",  # ꔀꔁꔂ
    # Middle Eastern scripts
    Script.SYRIAC: "\u0710\u0712\u0713",  # ܐܒܓ
    Script.THAANA: "\u0780\u0781\u0782",  # ހށނ
    Script.COPTIC: "\u2c80\u2c81\u2c82",  # Ⲁⲁⲃ
    # Americas
    Script.CHEROKEE: "\u13a0\u13a1\u13a2",  # ᎠᎡᎢ
    Script.CANADIAN_ABORIGINAL: "\u1401\u1402\u1403",  # ᐁᐂᐃ
    # Historical European scripts
    Script.RUNIC: "\u16a0\u16a1\u16a2",  # ᚠᚡᚢ
    Script.OGHAM: "\u1681\u1682\u1683",  # ᚁᚂᚃ
    Script.GOTHIC: "\U00010330\U00010331\U00010332",  # 𐌰𐌱𐌲
    # Ancient Near Eastern scripts
    Script.OLD_PERSIAN: "\U000103a0\U000103a1\U000103a2",  # 𐎠𐎡𐎢
    Script.CUNEIFORM: "\U00012000\U00012001\U00012002",  # 𒀀𒀁𒀂
    Script.LINEAR_B: "\U00010000\U00010001\U00010002",  # 𐀀𐀁𐀂
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def script_samples() -> dict[Script, str]:
    """Return the canonical SCRIPT_SAMPLES dictionary."""
    return SCRIPT_SAMPLES
