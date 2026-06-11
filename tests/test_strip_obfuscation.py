"""Tests for strip_obfuscation() preset pipeline.

strip_obfuscation is the most aggressive *confusable*-normalization preset.
It does NOT transliterate and does NOT fold case. Actual pipeline:
NFKC → strip_zalgo(max_marks=0) → strip_bidi → strip_zero_width
     → demojize → confusables → strip_accents → collapse_whitespace
"""

from __future__ import annotations

from disarm import strip_obfuscation


class TestStripObfuscationBasic:
    """Core behavior: obfuscation stripped, text preserved."""

    def test_pure_cyrillic_not_transliterated(self):
        # strip_obfuscation does NOT transliterate — only resolves confusables
        # Pure Cyrillic with no Latin confusables passes through (then fold_case)
        result = strip_obfuscation("Москва")
        # Confusables maps some chars to Latin (о→o, а→a) but not all.
        # The result is NOT "moskva" — that would require transliteration — and
        # at least one non-ASCII char survives (chars without a Latin confusable
        # stay Cyrillic), proving no transliteration happened.
        assert result != "moskva"
        assert any(ord(ch) > 127 for ch in result), (
            f"expected surviving non-ASCII (no transliteration), got {result!r}"
        )

    def test_emoji_expanded(self):
        result = strip_obfuscation("hello 🔥 world")
        assert "fire" in result

    def test_adjacent_emoji_spaced(self):
        result = strip_obfuscation("🔥🔥🔥")
        assert "firefire" not in result
        parts = result.strip().split()
        assert parts.count("fire") == 3

    def test_latin_text_unchanged(self):
        result = strip_obfuscation("hello world")
        assert result == "hello world"


class TestStripObfuscationHomoglyphs:
    """Confusable homoglyphs must be neutralized via TR39 visual mapping."""

    def test_cyrillic_homoglyphs_in_latin(self):
        # Cyrillic а (U+0430) and е (U+0435) look like Latin a and e
        result = strip_obfuscation("p\u0430yp\u0430l is fr\u0435e")
        assert result == "paypal is free"

    def test_greek_eta_confusable_to_h(self):
        # Greek Η (Eta) is visually confusable with Latin H (TR39)
        # Not transliterated to I (BGN/PCGN phonetic)
        result = strip_obfuscation("\u0397ello")  # Greek Η + Latin ello
        assert result == "Hello"


class TestStripObfuscationZalgo:
    """Zalgo/combining mark abuse must be fully stripped."""

    def test_zalgo_text(self):
        result = strip_obfuscation("H\u0300\u0301\u0302\u0303a\u0300\u0301\u0302\u0303te")
        # All combining marks stripped, case preserved
        assert result == "Hate"

    def test_strikethrough_text(self):
        result = strip_obfuscation("H\u0338a\u0338t\u0338e\u0338 speech")
        assert result == "Hate speech"


class TestStripObfuscationInvisibleChars:
    """Zero-width and bidi characters must be removed."""

    def test_zero_width_space(self):
        result = strip_obfuscation("hello\u200bworld")
        assert result == "helloworld"

    def test_bidi_override(self):
        result = strip_obfuscation("admin\u202euser")
        assert result == "adminuser"

    def test_zero_width_joiner(self):
        result = strip_obfuscation("pass\u200dword")
        assert result == "password"


class TestStripObfuscationAccentsAndCase:
    """Accents stripped, case preserved."""

    def test_accented_text(self):
        result = strip_obfuscation("Café Résumé")
        assert result == "Cafe Resume"

    def test_uppercase_preserved(self):
        result = strip_obfuscation("HELLO WORLD")
        assert result == "HELLO WORLD"

    def test_german_with_lang_default(self):
        # Without lang=, ü→u (default table), not ü→ue (German override)
        result = strip_obfuscation("München")
        assert result == "Munchen"


class TestStripObfuscationWhitespace:
    """Whitespace collapsed, control chars stripped."""

    def test_multiple_spaces(self):
        result = strip_obfuscation("hello   world")
        assert result == "hello world"

    def test_control_chars(self):
        result = strip_obfuscation("hello\x00\x01world")
        assert "\x00" not in result
        assert "\x01" not in result

    def test_leading_trailing_stripped(self):
        result = strip_obfuscation("  hello  ")
        assert result == "hello"


class TestStripObfuscationEdgeCases:
    """Edge cases."""

    def test_empty_string(self):
        assert strip_obfuscation("") == ""

    def test_pure_ascii(self):
        assert strip_obfuscation("hello world") == "hello world"

    def test_already_clean(self):
        assert strip_obfuscation("clean text here") == "clean text here"
