"""Regression test: Greek and Cyrillic confusables follow TR39 *visual*
mappings, distinct from phonetic transliteration.

Greek Ρ (Rho, U+03A1) is visually identical to Latin P, but ``transliterate()``
maps it to R (phonetic). TR39 ``confusables.txt`` maps Ρ→P (visual), and
``normalize_confusables()`` follows that visual mapping. These tests guard that
phonetic-vs-visual distinction — and the ``strip_obfuscation()`` /
``canonicalize()`` flows built on it — focusing on the historically confusing
characters: the lowercase homoglyphs and the combining-mark / case-corrected
prototypes locked in by #22. The exhaustive pair table is exercised separately
in ``test_confusables.py``; this file documents the *intent*.

Inputs use ``\\uXXXX`` escapes so the exact codepoint under test is unambiguous
in source review (the literal glyph appears in the description column).
"""

from __future__ import annotations

import pytest

from disarm import normalize_confusables, strip_obfuscation


class TestGreekVisualConfusables:
    """Greek letters must map to their visual Latin equivalents, not phonetic."""

    @pytest.mark.parametrize(
        ("char", "expected", "note"),
        [
            ("\u03a1", "P", "Ρ Capital Rho — looks like P, sounds like R"),
            ("\u03c1", "p", "ρ Small Rho — looks like p"),
            ("\u0397", "H", "Η Capital Eta — looks like H, sounds like I (modern)"),
            ("\u03bd", "v", "ν Small Nu — looks like v"),
            ("\u03a7", "X", "Χ Capital Chi — looks like X"),
            ("\u03a4", "T", "Τ Capital Tau — looks like T"),
            ("\u039f", "O", "Ο Capital Omicron — visual and phonetic agree"),
            ("\u039a", "K", "Κ Capital Kappa — looks like K"),
            ("\u03b7", "n", "η Small Eta — TR39 n+combining mark, resolves to n (#22)"),
            ("\u0399", "I", "Ι Capital Iota — TR39 prototype l, case-corrected to I (#22)"),
        ],
    )
    def test_greek_visual_confusable(self, char: str, expected: str, note: str) -> None:
        result = normalize_confusables(char)
        assert result == expected, f"Greek {note}: expected {expected!r}, got {result!r}"


class TestGreekSigmaFoldsToS:
    """Σ (U+03A3) and the sigma / n-ary-summation family fold to ASCII S (#341).

    TR39 confusables.txt makes LATIN CAPITAL LETTER ESH (U+01A9) the *prototype*
    for the entire Sigma family (03A3, 2211, 2140, the math bold/italic sigmas,
    Tifinagh 2D49 all map to 01A9). Earlier — the #245 "Σ→esh oddity" —
    disarm returned that non-ASCII skeleton, on the theory that "neutralized
    (source removed) is the contract, not ASCII-folded".

    #341 reverses that contract: the non-ASCII Latin-extended prototypes fold to
    basic ASCII, and esh joins them. Sigma is phonetically 's' (and already
    transliterates to S), so the Σ→S spoof is now neutralized to plain
    ASCII instead of surviving as the confusing esh — which also leaked into
    the confusables-only ``canonicalize`` preset. Capital sigmas fold to S
    (case-preserved); the caseless summation operators and Tifinagh fold to s.
    A *deliberate, documented* reversal of the #245 decision — exactly the
    explicit (not silent) change that pin asked for.
    """

    def test_capital_sigma_folds_to_s(self) -> None:
        # U+03A3 GREEK CAPITAL LETTER SIGMA -> ASCII "S".
        result = normalize_confusables("\u03a3", target_script="latin")  # Σ
        assert result == "S", f"expected S, got {result!r}"
        assert result.isascii()
        # Neutralized: the source Greek sigma is gone (the coverage contract).
        assert "\u03a3" not in result

    def test_math_capital_sigma_folds_to_s(self) -> None:
        # U+1D6BA MATHEMATICAL BOLD CAPITAL SIGMA -> "S" (same class, case-preserved).
        assert normalize_confusables("\U0001d6ba", target_script="latin") == "S"

    def test_summation_sign_folds_to_s(self) -> None:
        # U+2211 N-ARY SUMMATION is caseless, so it folds to lowercase "s".
        assert normalize_confusables("\u2211", target_script="latin") == "s"  # ∑


class TestCyrillicVisualConfusables:
    """Cyrillic letters must map to their visual Latin equivalents."""

    @pytest.mark.parametrize(
        ("char", "expected", "note"),
        [
            ("\u0440", "p", "р Small Er — looks like p, sounds like r"),
            ("\u0441", "c", "с Small Es — looks like c, sounds like s"),
            ("\u0412", "B", "В Capital Ve — looks like B, sounds like V"),
            ("\u0435", "e", "е Small Ie — looks like e"),
            ("\u0430", "a", "а Small A — looks like a"),
            ("\u043e", "o", "о Small O — looks like o"),
        ],
    )
    def test_cyrillic_visual_confusable(self, char: str, expected: str, note: str) -> None:
        result = normalize_confusables(char)
        assert result == expected, f"Cyrillic {note}: expected {expected!r}, got {result!r}"


class TestVisualConfusablesInPipeline:
    """The visual mapping must flow through the obfuscation-stripping pipeline."""

    def test_strip_obfuscation_greek_eta_in_word(self) -> None:
        # η (U+03B7) embedded in Latin text should resolve to n
        assert strip_obfuscation("chan\u03b7el") == "channel"

    def test_strip_obfuscation_greek_iota_in_word(self) -> None:
        # Ι (U+0399) embedded in Latin text should resolve to I
        assert strip_obfuscation("\u0399nstagram") == "Instagram"

    def test_strip_obfuscation_greek_lowercase_iota_to_i(self) -> None:
        # ι (U+03B9) folds to i (#436, reverting #343's →l), so the ι-for-i
        # spoof collides with the real word even through the NFKC-first preset.
        assert strip_obfuscation("bιtcoin") == "bitcoin"
