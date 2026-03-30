"""Bug: Greek confusable mappings use phonetic values instead of TR39 visual.

Greek Ρ (Rho, U+03A1) is visually identical to Latin P, but translit maps
it to R (phonetic). TR39 confusables.txt maps Ρ→P (visual).

This affects normalize_confusables(), strip_obfuscation(), and security_clean()
— all of which should resolve homoglyphs by visual similarity, not phonetics.
"""

from __future__ import annotations

from translit import normalize_confusables


class TestGreekVisualConfusables:
    """Greek letters must map to their visual Latin equivalents, not phonetic."""

    def test_rho_looks_like_p(self):
        # Ρ (U+03A1, Greek Capital Rho) looks like Latin P, sounds like R
        result = normalize_confusables("\u03a1")
        assert result == "P", f"Greek Ρ should map to P (visual), got {result!r}"

    def test_small_rho_looks_like_p(self):
        # ρ (U+03C1, Greek Small Rho) — visually similar to p
        result = normalize_confusables("\u03c1")
        assert result == "p", f"Greek ρ should map to p (visual), got {result!r}"

    def test_eta_looks_like_h(self):
        # Η (U+0397, Greek Capital Eta) looks like Latin H, sounds like I (modern)
        result = normalize_confusables("\u0397")
        assert result == "H", f"Greek Η should map to H (visual), got {result!r}"

    def test_nu_looks_like_v(self):
        # ν (U+03BD, Greek Small Nu) looks like Latin v
        result = normalize_confusables("\u03bd")
        assert result.lower() == "v", f"Greek ν should map to v (visual), got {result!r}"

    def test_chi_looks_like_x(self):
        # Χ (U+03A7, Greek Capital Chi) looks like Latin X
        result = normalize_confusables("\u03a7")
        assert result == "X", f"Greek Χ should map to X (visual), got {result!r}"

    def test_tau_looks_like_t(self):
        # Τ (U+03A4, Greek Capital Tau) looks like Latin T
        result = normalize_confusables("\u03a4")
        assert result == "T", f"Greek Τ should map to T (visual), got {result!r}"

    def test_omicron_looks_like_o(self):
        # Ο (U+039F, Greek Capital Omicron) looks like Latin O
        # This one happens to be both phonetically and visually correct
        result = normalize_confusables("\u039f")
        assert result == "O", f"Greek Ο should map to O (visual), got {result!r}"

    def test_kappa_looks_like_k(self):
        # Κ (U+039A, Greek Capital Kappa) looks like Latin K
        result = normalize_confusables("\u039a")
        assert result == "K", f"Greek Κ should map to K (visual), got {result!r}"

    def test_small_eta_maps_to_n(self):
        # η (U+03B7, Greek Small Eta) — TR39 maps to n̩ (n + combining mark)
        # After combining mark stripping, should resolve to 'n'
        result = normalize_confusables("\u03b7")
        assert result == "n", f"Greek η should map to n (visual), got {result!r}"

    def test_capital_iota_maps_to_I(self):
        # Ι (U+0399, Greek Capital Iota) — visually identical to Latin I
        # TR39 maps to l (lowercase L) which is wrong for case-preserving usage
        result = normalize_confusables("\u0399")
        assert result == "I", f"Greek Ι should map to I (visual), got {result!r}"

    def test_strip_obfuscation_greek_eta_in_word(self):
        # η embedded in Latin text should resolve to n
        from translit import strip_obfuscation

        result = strip_obfuscation("chan\u03b7el")  # "chanηel"
        assert result == "channel", f"Expected 'channel', got {result!r}"

    def test_strip_obfuscation_greek_iota_in_word(self):
        # Ι embedded in Latin text should resolve to I
        from translit import strip_obfuscation

        result = strip_obfuscation("\u0399nstagram")  # "Ιnstagram"
        assert result == "Instagram", f"Expected 'Instagram', got {result!r}"


class TestCyrillicVisualConfusables:
    """Cyrillic letters must map to their visual Latin equivalents."""

    def test_er_looks_like_p(self):
        # р (U+0440, Cyrillic Small Er) looks like Latin p, sounds like r
        result = normalize_confusables("\u0440")
        assert result == "p", f"Cyrillic р should map to p (visual), got {result!r}"

    def test_es_looks_like_c(self):
        # с (U+0441, Cyrillic Small Es) looks like Latin c, sounds like s
        result = normalize_confusables("\u0441")
        assert result == "c", f"Cyrillic с should map to c (visual), got {result!r}"

    def test_ve_looks_like_b(self):
        # В (U+0412, Cyrillic Capital Ve) looks like Latin B, sounds like V
        result = normalize_confusables("\u0412")
        assert result == "B", f"Cyrillic В should map to B (visual), got {result!r}"

    def test_ie_looks_like_e(self):
        # е (U+0435, Cyrillic Small Ie) looks like Latin e
        result = normalize_confusables("\u0435")
        assert result == "e", f"Cyrillic е should map to e (visual), got {result!r}"

    def test_a_looks_like_a(self):
        # а (U+0430, Cyrillic Small A) looks like Latin a
        result = normalize_confusables("\u0430")
        assert result == "a", f"Cyrillic а should map to a (visual), got {result!r}"

    def test_o_looks_like_o(self):
        # о (U+043E, Cyrillic Small O) looks like Latin o
        result = normalize_confusables("\u043e")
        assert result == "o", f"Cyrillic о should map to o (visual), got {result!r}"
