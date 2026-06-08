"""Tests for precompiled pipeline functions."""

import pytest

from translit import (
    TranslitError,
    catalog_key,
    display_clean,
    ml_normalize,
    security_clean,
    strip_bidi,
)

# ===== security_clean =====


class TestSecurityClean:
    """Tests for security_clean(): NFKC → confusables → collapse_ws → strip bidi."""

    def test_homoglyph_cyrillic_latin(self) -> None:
        """Cyrillic р and а mixed with Latin → normalized to all-Latin."""
        assert security_clean("\u0440\u0430ypal") == "paypal"

    def test_homoglyph_cyrillic_o(self) -> None:
        """Cyrillic о mixed with Latin g, l, e → normalized."""
        assert security_clean("g\u043e\u043egle") == "google"

    def test_fullwidth_script_tag(self) -> None:
        """Fullwidth angle brackets collapsed by NFKC."""
        assert security_clean("\uff1cscript\uff1e") == "<script>"

    def test_fullwidth_sql(self) -> None:
        """Fullwidth SELECT → plain ASCII after NFKC."""
        result = security_clean("\uff33\uff25\uff2c\uff25\uff23\uff34")
        assert result == "SELECT"

    def test_ligature_bypass(self) -> None:
        """Ligature ﬁ collapsed by NFKC."""
        assert security_clean("\ufb01lter") == "filter"

    def test_zwsp_injection(self) -> None:
        """Zero-width space stripped."""
        assert security_clean("admin\u200buser") == "adminuser"

    def test_zwnj_injection(self) -> None:
        """Zero-width non-joiner stripped."""
        assert security_clean("admin\u200cuser") == "adminuser"

    def test_bom_injection(self) -> None:
        """BOM character stripped."""
        assert security_clean("admin\ufeffuser") == "adminuser"

    def test_bidi_override_rtl(self) -> None:
        """Right-to-left override stripped."""
        assert security_clean("admin\u202euser") == "adminuser"

    def test_bidi_override_ltr(self) -> None:
        """Left-to-right override stripped."""
        assert security_clean("admin\u202duser") == "adminuser"

    def test_soft_hyphen(self) -> None:
        """Soft hyphen stripped."""
        assert security_clean("pass\u00adword") == "password"

    def test_lrm_rlm(self) -> None:
        """Left-to-right mark and right-to-left mark stripped."""
        assert security_clean("hello\u200eworld") == "helloworld"
        assert security_clean("hello\u200fworld") == "helloworld"

    def test_bidi_isolates(self) -> None:
        """Bidi isolate characters stripped."""
        assert security_clean("a\u2066b\u2067c\u2068d\u2069e") == "abcde"

    def test_bidi_embedding(self) -> None:
        """Bidi embedding/pop stripped."""
        assert security_clean("a\u202ab\u202bc\u202cd") == "abcd"

    def test_control_chars_stripped(self) -> None:
        """Control characters stripped."""
        assert security_clean("hello\x00world") == "helloworld"
        assert security_clean("hello\x01world") == "helloworld"

    def test_whitespace_collapsed(self) -> None:
        """Multiple whitespace collapsed to single space."""
        assert security_clean("hello   world") == "hello world"

    def test_superscript_digits(self) -> None:
        """Superscript digits normalized by NFKC."""
        assert security_clean("\u00b9\u00b2\u00b3") == "123"

    def test_clean_text_unchanged(self) -> None:
        """Clean ASCII passes through unchanged."""
        assert security_clean("hello world") == "hello world"

    def test_combined_attack(self) -> None:
        """Multiple attack vectors in a single string."""
        # Cyrillic homoglyph + ZWSP + bidi override + soft hyphen
        result = security_clean("\u0440\u0430y\u200bp\u202ea\u00adl")
        assert result == "paypal"


# ===== ml_normalize =====


class TestMlNormalize:
    """Tests for ml_normalize(): NFKC → emoji→text → [translit] → strip_accents → fold_case → collapse_ws."""

    def test_basic_accent_strip(self) -> None:
        """Accented text normalized: café → cafe."""
        assert ml_normalize("Café") == "cafe"

    def test_full_phrase(self) -> None:
        """Multi-word accented text."""
        assert ml_normalize("Café Résumé") == "cafe resume"

    def test_german_umlauts_no_lang(self) -> None:
        """Without lang, umlauts are stripped to base: ü→u."""
        assert ml_normalize("Über") == "uber"

    def test_german_umlauts_with_lang(self) -> None:
        """With lang='de', umlauts get German transliteration: ü→ue."""
        assert ml_normalize("Über", lang="de") == "ueber"

    def test_ligature_normalized(self) -> None:
        """NFKC collapses ﬁ ligature before further processing."""
        assert ml_normalize("\ufb01lter") == "filter"

    def test_case_folding(self) -> None:
        """Case folding applied: ß→ss."""
        assert ml_normalize("Straße") == "strasse"

    def test_whitespace_collapsed(self) -> None:
        """Multiple whitespace collapsed."""
        assert ml_normalize("hello   world") == "hello world"

    def test_control_chars_stripped(self) -> None:
        """Control chars stripped."""
        assert ml_normalize("hello\x00world") == "helloworld"

    def test_fullwidth_normalized(self) -> None:
        """Fullwidth chars normalized by NFKC."""
        assert ml_normalize("\uff28ello") == "hello"

    def test_emoji_none(self) -> None:
        """emoji='none' leaves emoji as-is (they survive to output)."""
        result = ml_normalize("hello 👋", emoji="none")
        assert "👋" in result

    def test_japanese_with_lang(self) -> None:
        """Japanese kana transliterated with lang='ja'."""
        result = ml_normalize("トーキョー", lang="ja")
        assert result.isascii()

    def test_clean_ascii_passthrough(self) -> None:
        """Clean lowercase ASCII passes through."""
        assert ml_normalize("hello world") == "hello world"


# ===== catalog_key =====


class TestCatalogKey:
    """Tests for catalog_key(): NFKC → confusables → [translit] → strip_accents → fold_case → collapse_ws."""

    def test_case_insensitive(self) -> None:
        """Same title in different cases produces same key."""
        assert catalog_key("Café") == catalog_key("café") == catalog_key("CAFÉ")

    def test_accent_insensitive(self) -> None:
        """Accented and unaccented produce same key."""
        assert catalog_key("café") == catalog_key("cafe")

    def test_whitespace_normalized(self) -> None:
        """Whitespace variations produce same key."""
        assert catalog_key("hello  world") == catalog_key("hello world")

    def test_confusable_normalized(self) -> None:
        """Cyrillic homoglyphs are transliterated phonetically."""
        # Cyrillic с (U+0441) = "s", а (U+0430) = "a" → "safe"
        # Transliteration runs before confusable normalization so Cyrillic
        # characters get their correct phonetic romanization.
        assert catalog_key("\u0441\u0430fe") == "safe"

    def test_iso9_cyrillic(self) -> None:
        """ISO 9 transliteration for Cyrillic catalog records."""
        # Transliterate first with ISO 9: Й→J, о→o, г→g, а→a → "joga"
        result = catalog_key("\u0419\u043e\u0433\u0430", strict_iso9=True)
        assert result == "joga"

    def test_iso9_vs_default(self) -> None:
        """ISO 9 and default produce different keys for Cyrillic."""
        iso9 = catalog_key("\u0419\u043e\u0433\u0430", strict_iso9=True)
        default = catalog_key("\u0419\u043e\u0433\u0430")
        # ISO 9: Й→J → "joga", default: Й→Y → "yoga"
        assert iso9 != default

    def test_lang_transliteration(self) -> None:
        """Language-specific transliteration applied when lang is set."""
        result = catalog_key("Über", lang="de")
        assert "ue" in result  # German ü→ue

    def test_fullwidth_normalized(self) -> None:
        """Fullwidth chars normalized by NFKC."""
        assert catalog_key("\uff28ello") == catalog_key("Hello")

    def test_ligature_normalized(self) -> None:
        """Ligatures collapsed by NFKC."""
        assert catalog_key("\ufb01lter") == catalog_key("filter")


# ===== display_clean =====


class TestDisplayClean:
    """Tests for display_clean(): collapse_whitespace with control/zero-width stripping."""

    def test_whitespace_collapsed(self) -> None:
        """Multiple spaces → single space."""
        assert display_clean("hello   world") == "hello world"

    def test_tabs_and_newlines(self) -> None:
        """Tabs become spaces, newlines become spaces."""
        assert display_clean("hello\t\tworld") == "hello world"

    def test_null_bytes(self) -> None:
        """Null bytes stripped."""
        assert display_clean("hello\x00world") == "helloworld"

    def test_control_chars(self) -> None:
        """Various control chars stripped."""
        assert display_clean("hello\x01\x02\x03world") == "helloworld"

    def test_zwsp_stripped(self) -> None:
        """Zero-width space stripped."""
        assert display_clean("hello\u200bworld") == "helloworld"

    def test_bom_stripped(self) -> None:
        """BOM stripped."""
        assert display_clean("\ufeffhello") == "hello"

    def test_leading_trailing_trimmed(self) -> None:
        """Leading/trailing whitespace trimmed."""
        assert display_clean("  hello  ") == "hello"

    def test_unicode_whitespace(self) -> None:
        """Various Unicode whitespace variants collapsed."""
        # Em space, en space
        assert display_clean("hello\u2003\u2002world") == "hello world"

    def test_invisible_math_operators(self) -> None:
        """U+2061–2064 invisible math operators stripped as zero-width."""
        assert display_clean("a\u2061b") == "ab"  # Function Application
        assert display_clean("a\u2062b") == "ab"  # Invisible Times
        assert display_clean("a\u2063b") == "ab"  # Invisible Separator
        assert display_clean("a\u2064b") == "ab"  # Invisible Plus

    def test_clean_text_unchanged(self) -> None:
        """Clean text passes through unchanged."""
        assert display_clean("hello world") == "hello world"


# ===== strip_bidi =====


class TestStripBidi:
    """Tests for strip_bidi(): remove UAX #9 bidi formatting chars + soft hyphen."""

    # ── Soft hyphen ──────────────────────────────────────────────
    def test_soft_hyphen(self) -> None:
        assert strip_bidi("pass\u00adword") == "password"

    # ── Arabic Letter Mark (Unicode 6.3, lives in Arabic block) ──
    def test_arabic_letter_mark(self) -> None:
        """Regression: U+061C was missing — lives in Arabic block, not near other bidi chars."""
        assert strip_bidi("hello\u061cworld") == "helloworld"

    # ── Bidi marks ───────────────────────────────────────────────
    def test_lrm(self) -> None:
        assert strip_bidi("hello\u200eworld") == "helloworld"

    def test_rlm(self) -> None:
        assert strip_bidi("hello\u200fworld") == "helloworld"

    # ── Bidi embeddings / overrides ──────────────────────────────
    def test_lre(self) -> None:
        assert strip_bidi("a\u202ab") == "ab"

    def test_rle(self) -> None:
        assert strip_bidi("a\u202bb") == "ab"

    def test_pdf(self) -> None:
        assert strip_bidi("a\u202cb") == "ab"

    def test_lro(self) -> None:
        assert strip_bidi("a\u202db") == "ab"

    def test_rlo(self) -> None:
        assert strip_bidi("a\u202eb") == "ab"

    # ── Bidi isolates (Unicode 6.3) ──────────────────────────────
    def test_lri(self) -> None:
        assert strip_bidi("a\u2066b") == "ab"

    def test_rli(self) -> None:
        assert strip_bidi("a\u2067b") == "ab"

    def test_fsi(self) -> None:
        assert strip_bidi("a\u2068b") == "ab"

    def test_pdi(self) -> None:
        assert strip_bidi("a\u2069b") == "ab"

    # ── Passthrough ──────────────────────────────────────────────
    def test_clean_text_unchanged(self) -> None:
        assert strip_bidi("hello world") == "hello world"

    def test_arabic_text_preserved(self) -> None:
        """Arabic text itself is kept — only formatting chars are stripped."""
        assert strip_bidi("مرحبا") == "مرحبا"

    # ── Exhaustive: every handled char in one string ─────────────
    def test_all_bidi_chars_at_once(self) -> None:
        # 13 characters: soft hyphen + ALM + LRM + RLM + 5 embeddings + 4 isolates
        text = "\u00ad\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
        assert len(text) == 13
        assert strip_bidi("x" + text + "y") == "xy"

    # ── Security scenario: ALM used in spoofing attack ───────────
    def test_alm_in_spoofing(self) -> None:
        """ALM between Latin chars can influence bidi reordering for visual spoofing."""
        assert strip_bidi("admin\u061cuser") == "adminuser"


class TestMlNormalizeEmojiStyle:
    """Regression: fix #4 — invalid emoji_style must raise TranslitError, not silently no-op.

    Before the fix, any unknown emoji_style value silently skipped emoji expansion
    with no indication of the error.
    """

    def test_cldr_expands_emoji(self) -> None:
        """emoji='cldr' (default) must expand emoji to CLDR short names."""
        result = ml_normalize("Hello \U0001f600")
        assert "grinning face" in result

    def test_none_leaves_emoji_unchanged(self) -> None:
        """emoji='none' must leave emoji characters in place."""
        result = ml_normalize("Hello \U0001f600", emoji="none")
        assert "\U0001f600" in result

    def test_invalid_emoji_style_raises(self) -> None:
        """Any value other than 'cldr' or 'none' must raise TranslitError."""
        with pytest.raises(TranslitError, match="emoji_style"):
            ml_normalize("hello", emoji="emoji15")

    def test_invalid_emoji_style_empty_string_raises(self) -> None:
        """Empty string is not a valid emoji_style — must raise TranslitError."""
        with pytest.raises(TranslitError, match="emoji_style"):
            ml_normalize("hello", emoji="")

    def test_invalid_emoji_style_uppercase_raises(self) -> None:
        """'CLDR' (wrong case) must raise TranslitError — matching is case-sensitive."""
        with pytest.raises(TranslitError, match="emoji_style"):
            ml_normalize("hello", emoji="CLDR")


class TestPresetsMetadataOrder:
    """#141: PRESETS metadata must reflect the real execution order."""

    def test_strip_obfuscation_confusables_after_demojize(self) -> None:
        # src/presets.rs::_strip_obfuscation runs confusables AFTER demojize so
        # typographic punctuation inside emoji names is folded too (idempotency).
        from translit import PRESETS

        steps = [name for name, _ in PRESETS["strip_obfuscation"]]
        assert steps.index("confusables") > steps.index("demojize")
        assert steps == [
            "normalize",
            "strip_zalgo",
            "strip_bidi",
            "strip_zero_width",
            "demojize",
            "confusables",
            "strip_accents",
            "collapse_whitespace",
        ]
