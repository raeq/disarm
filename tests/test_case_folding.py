"""Comprehensive tests for full Unicode case folding (CaseFolding.txt)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from translit import fold_case
from translit._text import Text

# ── ASCII fast path ──────────────────────────────────────────────────


class TestAscii:
    def test_pure_uppercase(self) -> None:
        assert fold_case("HELLO WORLD") == "hello world"

    def test_pure_lowercase(self) -> None:
        assert fold_case("already lowercase") == "already lowercase"

    def test_mixed_case(self) -> None:
        assert fold_case("MiXeD CaSe 123!") == "mixed case 123!"

    def test_digits_and_punctuation(self) -> None:
        assert fold_case("12345!@#$%^&*()") == "12345!@#$%^&*()"

    def test_empty_string(self) -> None:
        assert fold_case("") == ""

    def test_single_char(self) -> None:
        assert fold_case("A") == "a"
        assert fold_case("z") == "z"
        assert fold_case("7") == "7"

    def test_all_ascii_letters(self) -> None:
        import string

        assert fold_case(string.ascii_uppercase) == string.ascii_lowercase
        assert fold_case(string.ascii_lowercase) == string.ascii_lowercase


# ── Latin ligatures ──────────────────────────────────────────────────


class TestLigatures:
    def test_fi_fl(self) -> None:
        assert fold_case("ﬁnd ﬂat") == "find flat"

    def test_ff_ffi_ffl(self) -> None:
        assert fold_case("ﬀ ﬃ ﬄ") == "ff ffi ffl"

    def test_st_variants(self) -> None:
        assert fold_case("ﬅ ﬆ") == "st st"


# ── Latin Extended: fold != lower ────────────────────────────────────


class TestLatinExtended:
    def test_micro_sign(self) -> None:
        """µ (U+00B5) → μ (U+03BC Greek mu), not micro sign unchanged."""
        assert fold_case("\u00b5") == "\u03bc"

    def test_long_s(self) -> None:
        """ſ (U+017F) → s, not ſ."""
        assert fold_case("\u017f") == "s"

    def test_eszett(self) -> None:
        assert fold_case("ß") == "ss"

    def test_capital_eszett(self) -> None:
        assert fold_case("ẞ") == "ss"

    def test_dotted_i(self) -> None:
        """İ (U+0130) → i + combining dot above (U+0307)."""
        assert fold_case("\u0130") == "i\u0307"

    def test_strasse(self) -> None:
        assert fold_case("Straße") == "strasse"
        assert fold_case("STRASSE") == "strasse"
        # Both should match after folding.
        assert fold_case("Straße") == fold_case("STRASSE")

    def test_latin_accented(self) -> None:
        assert fold_case("ÀÁÂÃÄÅ") == "àáâãäå"
        assert fold_case("ÈÉÊË") == "èéêë"


# ── Greek ─────────────────────────────────────────────────────────────


class TestGreek:
    def test_uppercase_alphabet(self) -> None:
        assert fold_case("ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ") == "αβγδεζηθικλμνξοπρστυφχψω"

    def test_final_sigma(self) -> None:
        """ς (U+03C2 final sigma) → σ (U+03C3)."""
        assert fold_case("\u03c2") == "\u03c3"

    def test_variant_beta(self) -> None:
        """ϐ (U+03D0 beta symbol) → β."""
        assert fold_case("\u03d0") == "\u03b2"

    def test_variant_theta(self) -> None:
        """ϑ (U+03D1 theta symbol) → θ."""
        assert fold_case("\u03d1") == "\u03b8"

    def test_variant_phi(self) -> None:
        """ϕ (U+03D5 phi symbol) → φ."""
        assert fold_case("\u03d5") == "\u03c6"

    def test_variant_pi(self) -> None:
        """ϖ (U+03D6 pi symbol) → π."""
        assert fold_case("\u03d6") == "\u03c0"

    def test_variant_kappa(self) -> None:
        """ϰ (U+03F0 kappa symbol) → κ."""
        assert fold_case("\u03f0") == "\u03ba"

    def test_variant_rho(self) -> None:
        """ϱ (U+03F1 rho symbol) → ρ."""
        assert fold_case("\u03f1") == "\u03c1"

    def test_iota_with_dialytika_and_tonos(self) -> None:
        """ΐ (U+0390) → ι + diaeresis + acute (multi-char expansion)."""
        assert fold_case("\u0390") == "\u03b9\u0308\u0301"

    def test_upsilon_with_dialytika_and_tonos(self) -> None:
        """ΰ (U+03B0) → υ + diaeresis + acute (multi-char expansion)."""
        assert fold_case("\u03b0") == "\u03c5\u0308\u0301"


# ── Cyrillic ──────────────────────────────────────────────────────────


class TestCyrillic:
    def test_russian_uppercase(self) -> None:
        assert fold_case("АБВГДЕЖЗИКЛМН") == "абвгдежзиклмн"

    def test_mixed(self) -> None:
        assert fold_case("Москва") == "москва"
        assert fold_case("КИЇВ") == "київ"


# ── Armenian ──────────────────────────────────────────────────────────


class TestArmenian:
    def test_uppercase(self) -> None:
        assert fold_case("\u0531") == "\u0561"  # Ա → ա

    def test_ligature_ew(self) -> None:
        """Armenian և (U+0587) → եւ (two chars)."""
        assert fold_case("\u0587") == "\u0565\u0582"


# ── Georgian ──────────────────────────────────────────────────────────


class TestGeorgian:
    def test_mtavruli(self) -> None:
        """Mtavruli Ა (U+1C90) → Mkhedruli ა (U+10D0)."""
        assert fold_case("\u1c90") == "\u10d0"


# ── Cherokee ──────────────────────────────────────────────────────────


class TestCherokee:
    def test_cherokee_uppercase_identity(self) -> None:
        """Cherokee uppercase forms (U+13A0–U+13EF) have no folding entry → identity."""
        assert fold_case("\u13a0") == "\u13a0"  # Ꭰ stays Ꭰ

    def test_cherokee_small_folds_to_uppercase(self) -> None:
        """Cherokee small (U+AB70–U+ABBF) fold to uppercase (U+13A0–U+13EF)."""
        assert fold_case("\uab70") == "\u13a0"  # ꭰ → Ꭰ
        assert fold_case("\uab71") == "\u13a1"  # ꭱ → Ꭱ

    def test_cherokee_small_letter_mv(self) -> None:
        """U+13FD folds to U+13F5."""
        assert fold_case("\u13fd") == "\u13f5"


# ── Supplementary plane scripts ───────────────────────────────────────


class TestSupplementaryPlane:
    def test_deseret(self) -> None:
        """Deseret capital 𐐀 (U+10400) → small 𐐨 (U+10428)."""
        assert fold_case("\U00010400") == "\U00010428"

    def test_osage(self) -> None:
        """Osage capital 𐒰 (U+104B0) → small 𐓘 (U+104D8)."""
        assert fold_case("\U000104b0") == "\U000104d8"

    def test_warang_citi(self) -> None:
        """Warang Citi capital 𑢠 (U+118A0) → small 𑣀 (U+118C0)."""
        assert fold_case("\U000118a0") == "\U000118c0"

    def test_adlam(self) -> None:
        """Adlam capital 𞤀 (U+1E900) → small 𞤢 (U+1E922)."""
        assert fold_case("\U0001e900") == "\U0001e922"


# ── Fullwidth Latin ───────────────────────────────────────────────────


class TestFullwidth:
    def test_fullwidth_a_to_z(self) -> None:
        assert fold_case("\uff21") == "\uff41"  # Ａ → ａ
        assert fold_case("\uff3a") == "\uff5a"  # Ｚ → ｚ

    def test_fullwidth_string(self) -> None:
        assert fold_case("ＡＢＣＤ") == "ａｂｃｄ"


# ── Identity / passthrough ───────────────────────────────────────────


class TestIdentity:
    def test_cjk(self) -> None:
        assert fold_case("你好世界") == "你好世界"

    def test_emoji(self) -> None:
        assert fold_case("🎉🚀💡") == "🎉🚀💡"

    def test_already_folded(self) -> None:
        assert fold_case("café résumé naïve") == "café résumé naïve"

    def test_arabic(self) -> None:
        """Arabic has no case distinction; should pass through."""
        assert fold_case("مرحبا") == "مرحبا"

    def test_thai(self) -> None:
        assert fold_case("สวัสดี") == "สวัสดี"

    def test_devanagari(self) -> None:
        assert fold_case("नमस्ते") == "नमस्ते"


# ── Edge cases ────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_string_length_grows(self) -> None:
        assert fold_case("ßßß") == "ssssss"
        assert len(fold_case("ßßß")) == 6

    def test_combining_characters_preserved(self) -> None:
        """Combining marks not in CaseFolding.txt pass through."""
        assert fold_case("e\u0301") == "e\u0301"

    def test_fold_equals_casefold(self) -> None:
        """Our fold_case should match Python's str.casefold() for common strings."""
        test_strings = [
            "Hello World",
            "Straße",
            "ΣΟΦΙΑ",
            "Москва",
            "ﬁnd ﬂat",
            "µ ſ ϐ ϑ",
            "café résumé",
        ]
        for s in test_strings:
            assert fold_case(s) == s.casefold(), (
                f"fold_case({s!r}) = {fold_case(s)!r} != {s.casefold()!r}"
            )

    def test_bmp_boundary(self) -> None:
        """Characters near the BMP boundary."""
        assert fold_case("\uffff") == "\uffff"
        assert fold_case("\U00010000") == "\U00010000"


# ── Mixed-script strings ─────────────────────────────────────────────


class TestMixedScripts:
    def test_ascii_and_greek(self) -> None:
        assert fold_case("Café ΣΟΦΙΑ") == "café σοφια"

    def test_ascii_and_cjk(self) -> None:
        assert fold_case("Hello 你好 WORLD") == "hello 你好 world"

    def test_ascii_german_umlaut(self) -> None:
        assert fold_case("ABC Straße ÄÖÜ") == "abc strasse äöü"

    def test_latin_cyrillic_greek(self) -> None:
        assert fold_case("ABC АБВ ΑΒΓ") == "abc абв αβγ"


# ── Text builder integration ─────────────────────────────────────────


class TestTextBuilder:
    def test_fold_case_method(self) -> None:
        assert Text("Straße").fold_case().value == "strasse"

    def test_fold_case_chained(self) -> None:
        result = Text("  HELLO  ").collapse_whitespace().fold_case().value
        assert result == "hello"

    def test_fold_case_ligatures(self) -> None:
        assert Text("ﬁnd").fold_case().value == "find"


# ── Casefold correctness against Python's str.casefold() ─────────────


class TestAgainstPythonCasefold:
    """Verify that fold_case matches Python's str.casefold() for a wide
    range of characters. str.casefold() is the CPython reference
    implementation of full Unicode case folding."""

    @pytest.mark.parametrize(
        "codepoint",
        [
            0x0041,  # A
            0x005A,  # Z
            0x00B5,  # µ micro sign
            0x00DF,  # ß
            0x0130,  # İ
            0x017F,  # ſ
            0x01A9,  # Ʃ
            0x03A3,  # Σ
            0x03C2,  # ς
            0x03D0,  # ϐ
            0x0410,  # А Cyrillic
            0x0531,  # Ա Armenian
            0x0587,  # և Armenian ligature
            0x10400,  # 𐐀 Deseret
            0x104B0,  # 𐒰 Osage
            0x118A0,  # 𑢠 Warang Citi
            0x1E900,  # 𞤀 Adlam
            0x1E9E,  # ẞ capital eszett
            0xAB70,  # ꭰ Cherokee small (folds to U+13A0)
            0x1C90,  # Ა Georgian Mtavruli
            0xFF21,  # Ａ Fullwidth
            0xFB01,  # ﬁ ligature
            0xFB03,  # ﬃ ligature
        ],
    )
    def test_matches_python_casefold(self, codepoint: int) -> None:
        ch = chr(codepoint)
        expected = ch.casefold()
        result = fold_case(ch)
        assert result == expected, (
            f"U+{codepoint:04X} ({ch!r}): fold_case={result!r}, casefold={expected!r}"
        )


# ── Hypothesis property-based tests ──────────────────────────────────


class TestProperties:
    @given(st.text(max_size=200))
    @settings(max_examples=500)
    def test_idempotent(self, text: str) -> None:
        """fold(fold(x)) == fold(x) for all strings."""
        once = fold_case(text)
        twice = fold_case(once)
        assert once == twice

    @given(st.text(max_size=200))
    @settings(max_examples=500)
    def test_no_ascii_uppercase_in_output(self, text: str) -> None:
        result = fold_case(text)
        for ch in result:
            if ch.isascii():
                assert not ch.isupper(), f"ASCII uppercase {ch!r} in output {result!r}"

    @given(st.text(max_size=200))
    @settings(max_examples=500)
    def test_never_drops_chars(self, text: str) -> None:
        """Case folding never reduces character count (though byte length
        may shrink for ligatures like ﬅ → st)."""
        result = fold_case(text)
        assert len(result) >= len(text)

    @given(st.text(alphabet=st.characters(max_codepoint=127), max_size=200))
    @settings(max_examples=200)
    def test_ascii_stays_ascii(self, text: str) -> None:
        result = fold_case(text)
        assert result.isascii() or text == "", f"non-ASCII in fold of ASCII: {result!r}"

    @given(st.text(max_size=100))
    @settings(max_examples=500)
    def test_matches_python_casefold(self, text: str) -> None:
        """fold_case should agree with str.casefold() on all inputs."""
        assert fold_case(text) == text.casefold()
