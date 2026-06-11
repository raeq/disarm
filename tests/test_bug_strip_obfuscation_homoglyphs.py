"""Bug: strip_obfuscation() uses phonetic transliteration instead of visual
confusable mapping for homoglyph resolution.

Cyrillic р (U+0440) looks like Latin p but transliterates to r.
Cyrillic с (U+0441) looks like Latin c but transliterates to s.
Cyrillic В (U+0412) looks like Latin B but transliterates to V.

strip_obfuscation() should resolve these by visual similarity (TR39),
not phonetic value.
"""

from __future__ import annotations

from disarm import strip_obfuscation


class TestHomoglyphResolution:
    """Cyrillic homoglyphs in Latin text must resolve to their visual equivalents."""

    def test_cyrillic_r_looks_like_latin_p(self):
        # Cyrillic р (U+0440) visually = Latin p, phonetically = r
        result = strip_obfuscation("\u0440roduct")
        assert result == "product", f"got {result!r}"

    def test_cyrillic_s_looks_like_latin_c(self):
        # Cyrillic с (U+0441) visually = Latin c, phonetically = s
        result = strip_obfuscation("produ\u0441t")
        assert result == "product", f"got {result!r}"

    def test_cyrillic_ve_looks_like_latin_b(self):
        # Cyrillic В (U+0412) visually = Latin B, phonetically = V
        result = strip_obfuscation("\u0412uy cheap")
        assert result == "Buy cheap", f"got {result!r}"

    def test_spoofed_product(self):
        result = strip_obfuscation("\u0440rodu\u0441t")
        assert result == "product", f"got {result!r}"

    def test_spoofed_scam(self):
        result = strip_obfuscation("This is a s\u0441\u0430m")
        assert result == "This is a scam", f"got {result!r}"

    def test_spoofed_free_prize(self):
        result = strip_obfuscation("fr\u0435e \u0440rize")
        assert result == "free prize", f"got {result!r}"

    def test_spoofed_phishing(self):
        result = strip_obfuscation("\u0440hishing \u0430tt\u0430\u0441k")
        assert result == "phishing attack", f"got {result!r}"

    def test_spoofed_buy_cheap(self):
        result = strip_obfuscation("\u0412uy \u0441h\u0435\u0430\u0440 Viаgrа \u043enlin\u0435")
        assert "Buy" in result
        assert "cheap" in result


class TestNonHomoglyphCyrillicUnchanged:
    """Cyrillic chars with no Latin visual equivalent should still be handled."""

    def test_pure_cyrillic_word_not_transliterated(self):
        # Full Cyrillic word — no spoofing, just foreign text.
        # strip_obfuscation does NOT transliterate — only confusables.
        # Chars with Latin confusables map (о→o, а→a), others stay Cyrillic.
        result = strip_obfuscation("Москва")
        # NOT "moskva" — that requires transliterate(); some non-ASCII survives.
        assert result != "moskva", f"pure Cyrillic word was transliterated: {result!r}"
        assert any(ord(ch) > 127 for ch in result), (
            f"expected surviving non-ASCII (no transliteration), got {result!r}"
        )

    def test_identical_homoglyphs_still_work(self):
        # Cyrillic а (U+0430) = Latin a — same visual AND phonetic
        result = strip_obfuscation("c\u0430t")
        assert result == "cat", f"got {result!r}"

    def test_cyrillic_e_equals_latin_e(self):
        # Cyrillic е (U+0435) = Latin e
        result = strip_obfuscation("fr\u0435e")
        assert result == "free", f"got {result!r}"

    def test_cyrillic_o_equals_latin_o(self):
        # Cyrillic о (U+043E) = Latin o
        result = strip_obfuscation("g\u043e\u043ed")
        assert result == "good", f"got {result!r}"
