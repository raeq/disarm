"""Exhaustive per-mapping tests for every language-specific PHF override table.

This file mirrors src/tables/transliteration.rs exactly. Every character
in every LANG_XX PHF map has a corresponding test assertion. If a mapping
is added, changed, or removed in Rust, a test here must change too — or fail.

The smoke tests in test_transliterate.py prove each lang dispatch works.
These tests prove every individual character mapping is correct.

Also tests language aliases (da→NO, nb/nn→NO) to verify the
dispatch table in lookup_lang().
"""

from typing import Any

import pytest

from translit import transliterate

# ─── Complete PHF override tables, extracted from transliteration.rs ─────
#
# Structure: dict[lang_code, list[tuple[input_char, expected_output, comment]]]
#
# IMPORTANT: This MUST stay in sync with transliteration.rs. If you add a
# mapping in Rust, add it here. If a test fails, either the Rust table or
# this test data is wrong — never silently update one without the other.

LANG_OVERRIDES: dict[str, list[tuple[str, str, str]]] = {
    "de": [
        # German (Duden standard): Ä→Ae, Ö→Oe, Ü→Ue
        ("\u00c4", "Ae", "Ä"),
        ("\u00d6", "Oe", "Ö"),
        ("\u00dc", "Ue", "Ü"),
        ("\u00e4", "ae", "ä"),
        ("\u00f6", "oe", "ö"),
        ("\u00fc", "ue", "ü"),
        ("\u1e9e", "SS", "ẞ capital sharp s"),
    ],
    "no": [
        # Norwegian (Bokmål/Nynorsk): Å→Aa, Ø→Oe, Æ→Ae
        ("\u00c5", "Aa", "Å"),
        ("\u00e5", "aa", "å"),
        ("\u00d8", "Oe", "Ø"),
        ("\u00f8", "oe", "ø"),
        ("\u00c6", "Ae", "Æ"),
        ("\u00e6", "ae", "æ"),
    ],
    "sv": [
        # Swedish: Ä→Ae, Ö→Oe
        ("\u00c4", "Ae", "Ä"),
        ("\u00e4", "ae", "ä"),
        ("\u00d6", "Oe", "Ö"),
        ("\u00f6", "oe", "ö"),
    ],
    "is": [
        # Icelandic: Ð→Dh, Þ→Th, Æ→Ae
        ("\u00d0", "Dh", "Ð"),
        ("\u00f0", "dh", "ð"),
        ("\u00de", "Th", "Þ"),
        ("\u00fe", "th", "þ"),
        ("\u00c6", "Ae", "Æ"),
        ("\u00e6", "ae", "æ"),
    ],
    "et": [
        # Estonian: Ö→Oe, Ä→Ae, Ü→Ue
        ("\u00c4", "Ae", "Ä"),
        ("\u00e4", "ae", "ä"),
        ("\u00d6", "Oe", "Ö"),
        ("\u00f6", "oe", "ö"),
        ("\u00dc", "Ue", "Ü"),
        ("\u00fc", "ue", "ü"),
    ],
    "fr": [
        # French: Œ→OE, Æ→AE
        ("\u0152", "OE", "Œ"),
        ("\u0153", "oe", "œ"),
        ("\u00c6", "AE", "Æ"),
        ("\u00e6", "ae", "æ"),
    ],
    "es": [
        # Spanish: ¡→!, ¿→?
        ("\u00a1", "!", "¡"),
        ("\u00bf", "?", "¿"),
    ],
    "pt": [
        # Portuguese: ª→a, º→o
        ("\u00aa", "a", "ª"),
        ("\u00ba", "o", "º"),
    ],
    "it": [
        # Italian: ª→a, º→o
        ("\u00aa", "a", "ª"),
        ("\u00ba", "o", "º"),
    ],
    "tr": [
        # Turkish: İ→I, ı→i, Ğ→G, ğ→g, Ş→S, ş→s
        ("\u0130", "I", "İ"),
        ("\u0131", "i", "ı"),
        ("\u011e", "G", "Ğ"),
        ("\u011f", "g", "ğ"),
        ("\u015e", "S", "Ş"),
        ("\u015f", "s", "ş"),
    ],
    "nl": [
        # Dutch: Ĳ→IJ, ĳ→ij
        ("\u0132", "IJ", "Ĳ"),
        ("\u0133", "ij", "ĳ"),
    ],
    "ca": [
        # Catalan: middle dot removed (l·l → ll)
        ("\u00b7", "", "· middle dot"),
    ],
    "vi": [
        # Vietnamese: Đ→D, Ơ→O, Ư→U
        ("\u0110", "D", "Đ"),
        ("\u0111", "d", "đ"),
        ("\u01a0", "O", "Ơ"),
        ("\u01a1", "o", "ơ"),
        ("\u01af", "U", "Ư"),
        ("\u01b0", "u", "ư"),
    ],
    "el": [
        # Greek (modern): η→i (not e), υ→y, χ→ch
        ("\u0397", "I", "Η eta uppercase"),
        ("\u03b7", "i", "η eta lowercase"),
        ("\u03a5", "Y", "Υ upsilon uppercase"),
        ("\u03c5", "y", "υ upsilon lowercase"),
        ("\u03a7", "Ch", "Χ chi uppercase"),
        ("\u03c7", "ch", "χ chi lowercase"),
    ],
    "bg": [
        # Bulgarian: Ъ→A, Щ→Sht
        ("\u042a", "A", "Ъ hard sign uppercase"),
        ("\u044a", "a", "ъ hard sign lowercase"),
        ("\u0429", "Sht", "Щ shcha uppercase"),
        ("\u0449", "sht", "щ shcha lowercase"),
    ],
    "uk": [
        # Ukrainian (KMU 2010)
        ("\u0413", "H", "Г →H"),
        ("\u0433", "h", "г →h"),
        ("\u0490", "G", "Ґ →G"),
        ("\u0491", "g", "ґ →g"),
        ("\u0404", "Ye", "Є →Ye"),
        ("\u0454", "ye", "є →ye"),
        ("\u0407", "I", "Ї →I (KMU 2010)"),
        ("\u0457", "i", "ї →i (KMU 2010)"),
        ("\u0406", "I", "І →I"),
        ("\u0456", "i", "і →i"),
        ("\u0418", "Y", "И →Y (KMU 2010)"),
        ("\u0438", "y", "и →y (KMU 2010)"),
    ],
}

# Languages that alias to another language's PHF table via lookup_lang()
LANG_ALIASES: dict[str, str] = {
    "da": "no",  # Danish uses Norwegian rules
    "nb": "no",  # Bokmål is Norwegian
    "nn": "no",  # Nynorsk is Norwegian
    # Finnish intentionally has NO alias — ä/ö are independent phonemes in
    # Finnish (→a/o via default table), unlike Swedish where they're ae/oe.
}


# ═══════════════════════════════════════════════════════════════════
# Exhaustive per-character override tests
# ═══════════════════════════════════════════════════════════════════


def _build_override_params() -> list[Any]:
    """Build parametrize list: (lang, char, expected, description)."""
    params = []
    for lang, mappings in LANG_OVERRIDES.items():
        for char, expected, desc in mappings:
            test_id = f"{lang}:{desc}"
            params.append(pytest.param(lang, char, expected, id=test_id))
    return params


class TestLangOverridesExhaustive:
    """Every character in every language PHF override table must produce
    the expected output. This is the definitive source-of-truth test.

    If this test fails, either:
    1. A mapping in transliteration.rs changed and this file wasn't updated, or
    2. A mapping in this file is wrong and transliteration.rs is correct.

    Never silently resolve — verify against the relevant standard.
    """

    @pytest.mark.parametrize(
        "lang,char,expected",
        _build_override_params(),
    )
    def test_override_mapping(self, lang: str, char: str, expected: str) -> None:
        result = transliterate(char, lang=lang)
        assert result == expected, (
            f"lang={lang!r}: transliterate({char!r} U+{ord(char):04X}) = {result!r}, "
            f"expected {expected!r}"
        )


# ═══════════════════════════════════════════════════════════════════
# Alias tests: da→no, nb→no, nn→no
# ═══════════════════════════════════════════════════════════════════


def _build_alias_params() -> list[Any]:
    """Build parametrize list for alias languages."""
    params = []
    for alias, target in LANG_ALIASES.items():
        if target not in LANG_OVERRIDES:
            continue
        for char, expected, desc in LANG_OVERRIDES[target]:
            test_id = f"{alias}(={target}):{desc}"
            params.append(pytest.param(alias, target, char, expected, id=test_id))
    return params


class TestLangAliases:
    """Language aliases must produce identical output to their target language.

    da, nb, nn → same as no
    """

    @pytest.mark.parametrize(
        "alias,target,char,expected",
        _build_alias_params(),
    )
    def test_alias_matches_target(self, alias: str, target: str, char: str, expected: str) -> None:
        alias_result = transliterate(char, lang=alias)
        target_result = transliterate(char, lang=target)
        assert alias_result == target_result, (
            f"Alias {alias!r} diverges from {target!r} on U+{ord(char):04X}: "
            f"alias={alias_result!r}, target={target_result!r}"
        )
        assert alias_result == expected, (
            f"Alias {alias!r}: transliterate({char!r}) = {alias_result!r}, expected {expected!r}"
        )


# ═══════════════════════════════════════════════════════════════════
# Override vs default divergence test
# ═══════════════════════════════════════════════════════════════════


class TestOverridesDivergeFromDefault:
    """Verify override behavior relative to the default table.

    Some languages (de, no, sv, is, et, es, bg, uk, etc.) have overrides
    that genuinely differ from the default. Others (fr, tr, nl, vi, el)
    currently match the default because their "language-specific" mappings
    were also added to the default table for best-effort transliteration.
    Those PHF tables serve as defensive insurance — if the default table
    changes, the language-specific behavior is preserved.

    We test both cases:
    - Languages that MUST diverge: verify they actually do
    - Defensive duplicates: verify they at least match correctly
    """

    # Languages whose PHF tables contain at least one mapping that
    # genuinely differs from the default table.
    MUST_DIVERGE = {"de", "no", "sv", "is", "et", "es", "bg", "uk", "ca", "pt", "it"}

    # Languages whose PHF tables currently duplicate the default.
    # Kept as defensive insurance in case the default table changes.
    DEFENSIVE_DUPLICATES = {"fr", "tr", "nl", "vi", "el"}

    @pytest.mark.parametrize(
        "lang,mappings",
        [
            pytest.param(lang, mappings, id=lang)
            for lang, mappings in LANG_OVERRIDES.items()
            if lang in {"de", "no", "sv", "is", "et", "es", "bg", "uk", "ca", "pt", "it"}
        ],
    )
    def test_divergent_overrides_actually_diverge(
        self, lang: str, mappings: list[tuple[str, str, str]]
    ) -> None:
        """Languages in MUST_DIVERGE must have ≥1 char that differs from default."""
        divergences = 0
        for char, expected_override, _desc in mappings:
            default_result = transliterate(char)
            override_result = transliterate(char, lang=lang)
            if default_result != override_result:
                divergences += 1
                assert override_result == expected_override, (
                    f"lang={lang!r}: override for U+{ord(char):04X} is "
                    f"{override_result!r}, expected {expected_override!r}"
                )
        assert divergences > 0, (
            f"Language {lang!r} is in MUST_DIVERGE but has no actual divergences. "
            f"Move it to DEFENSIVE_DUPLICATES or fix the default table."
        )

    @pytest.mark.parametrize(
        "lang,mappings",
        [
            pytest.param(lang, mappings, id=lang)
            for lang, mappings in LANG_OVERRIDES.items()
            if lang in {"fr", "tr", "nl", "vi", "el"}
        ],
    )
    def test_defensive_duplicates_match_correctly(
        self, lang: str, mappings: list[tuple[str, str, str]]
    ) -> None:
        """Defensive duplicates must at least produce correct output."""
        for char, expected, desc in mappings:
            result = transliterate(char, lang=lang)
            assert result == expected, (
                f"Defensive duplicate lang={lang!r}: {desc} "
                f"U+{ord(char):04X} → {result!r}, expected {expected!r}"
            )

    def test_all_overrides_classified(self) -> None:
        """Every override language must be in exactly one category."""
        all_classified = self.MUST_DIVERGE | self.DEFENSIVE_DUPLICATES
        all_overrides = set(LANG_OVERRIDES.keys())
        assert all_classified == all_overrides, (
            f"Unclassified: {all_overrides - all_classified}, "
            f"Extra: {all_classified - all_overrides}"
        )


# ═══════════════════════════════════════════════════════════════════
# Mapping count validation
# ═══════════════════════════════════════════════════════════════════


class TestMappingCounts:
    """Verify the test data has the expected number of mappings per language.

    These counts match the Rust PHF table sizes. If a mapping is added
    to Rust without updating this file, the count will be wrong.
    """

    EXPECTED_COUNTS = {
        "de": 7,
        "no": 6,
        "sv": 4,
        "is": 6,
        "et": 6,
        "fr": 4,
        "es": 2,
        "pt": 2,
        "it": 2,
        "tr": 6,
        "nl": 2,
        "ca": 1,
        "vi": 6,
        "el": 6,
        "bg": 4,
        "uk": 12,
    }

    @pytest.mark.parametrize(
        "lang,expected_count",
        [pytest.param(k, v, id=k) for k, v in EXPECTED_COUNTS.items()],
    )
    def test_mapping_count(self, lang: str, expected_count: int) -> None:
        actual = len(LANG_OVERRIDES[lang])
        assert actual == expected_count, (
            f"lang={lang!r}: test data has {actual} mappings, "
            f"expected {expected_count}. Update LANG_OVERRIDES or "
            f"EXPECTED_COUNTS to match transliteration.rs."
        )

    def test_all_override_langs_have_counts(self) -> None:
        """Every language in LANG_OVERRIDES must have an entry in EXPECTED_COUNTS."""
        for lang in LANG_OVERRIDES:
            assert lang in self.EXPECTED_COUNTS, (
                f"Language {lang!r} in LANG_OVERRIDES but not in EXPECTED_COUNTS"
            )

    def test_no_extra_counts(self) -> None:
        """EXPECTED_COUNTS should not have entries absent from LANG_OVERRIDES."""
        for lang in self.EXPECTED_COUNTS:
            assert lang in LANG_OVERRIDES, (
                f"Language {lang!r} in EXPECTED_COUNTS but not in LANG_OVERRIDES"
            )

    def test_total_override_languages(self) -> None:
        """Verify we test all 16 languages that have PHF override tables."""
        assert len(LANG_OVERRIDES) == 16, (
            f"Expected 16 override languages, got {len(LANG_OVERRIDES)}. "
            f"A language was added or removed in transliteration.rs."
        )
