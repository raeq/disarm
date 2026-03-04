"""Shared test fixtures and Hypothesis strategies for translit.

Centralizes Unicode sample data and property-based testing strategies
so that new tests can import them from one place instead of
rediscovering or redeclaring them per file.
"""

from __future__ import annotations

import pytest
from hypothesis import strategies as st

from translit._enums import Script

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
    Script.SINHALA: "සිංහල",
    # East Asian scripts
    Script.HAN: "中文漢字",
    Script.HIRAGANA: "ひらがな",
    Script.KATAKANA: "カタカナ",
    Script.HANGUL: "한국어",
    # Southeast Asian scripts
    Script.THAI: "ภาษาไทย",
    Script.LAO: "ພາສາລາວ",
    Script.MYANMAR: "မြန်မာ",
    Script.KHMER: "ភាសាខ្មែរ",
    Script.BALINESE: "\u1b05\u1b13\u1b17",  # ᬅᬓᬗ
    Script.JAVANESE: "\ua984\ua989\ua98e",  # ꦄꦉꦎ
    Script.TAI_LE: "\u1950\u1951\u1952",  # ᥐᥑᥒ
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
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def script_samples() -> dict[Script, str]:
    """Return the canonical SCRIPT_SAMPLES dictionary."""
    return SCRIPT_SAMPLES
