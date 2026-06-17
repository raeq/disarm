"""Tests for precompiled pipeline functions."""

import pytest

from disarm import (
    DisarmError,
    catalog_key,
    display_clean,
    ml_normalize,
    normalize_user_input,
    search_key,
    security_clean,
    sort_key,
    strip_bidi,
    strip_obfuscation,
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


# ===== path-safety guarantee (#248) =====


class TestPathSafety:
    """The security presets must never emit a synthesised path separator or
    `..` traversal \u2014 a confusable like U+2044 FRACTION SLASH must not become an
    actionable '/' in the output of a function named to *sanitize* input."""

    @pytest.mark.parametrize("preset", [normalize_user_input, security_clean])
    @pytest.mark.parametrize(
        "raw",
        [
            "etc\u2044passwd",  # U+2044 FRACTION SLASH (folds to '/')
            "a\u2215b",  # U+2215 DIVISION SLASH
            "x\ua4fa\u2044bin",  # U+A4FA (\u2192 '..') + fraction slash
            "\u2025\u2025/etc",  # U+2025 TWO DOT LEADER (\u2192 '..') + real slash
            "../../etc/passwd",  # plain ASCII traversal
            "a\\b\\c",  # backslash separators
        ],
    )
    def test_no_synthesised_separators(self, preset, raw: str) -> None:
        out = preset(raw)
        assert "/" not in out, f"{preset.__name__}({raw!r}) -> {out!r} contains '/'"
        assert "\\" not in out, f"{preset.__name__}({raw!r}) -> {out!r} contains '\\'"
        assert ".." not in out, f"{preset.__name__}({raw!r}) -> {out!r} contains '..'"

    def test_specific_smuggling_vectors(self) -> None:
        # The exact vectors reported in #248.
        assert normalize_user_input("etc\u2044passwd") == "etc_passwd"
        assert security_clean("a\u2215b") == "a_b"

    def test_homoglyph_folding_still_works(self) -> None:
        # Path-safety must not regress the homoglyph neutralisation.
        assert normalize_user_input("p\u0430ypal") == "paypal"
        assert security_clean("p\u0430ypal") == "paypal"

    def test_idempotent(self) -> None:
        for preset in (normalize_user_input, security_clean):
            once = preset("etc\u2044../passwd")
            assert preset(once) == once


# ===== ml_normalize =====


class TestMlNormalize:
    """Tests for ml_normalize(): NFKC → emoji→text → [disarm] → strip_accents → fold_case → collapse_ws."""

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
    """Tests for catalog_key(): NFKC → confusables → [disarm] → strip_accents → fold_case → collapse_ws."""

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
    """Regression: fix #4 — invalid emoji_style must raise DisarmError, not silently no-op.

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
        """Any value other than 'cldr' or 'none' must raise DisarmError."""
        with pytest.raises(DisarmError, match="emoji_style"):
            ml_normalize("hello", emoji="emoji15")

    def test_invalid_emoji_style_empty_string_raises(self) -> None:
        """Empty string is not a valid emoji_style — must raise DisarmError."""
        with pytest.raises(DisarmError, match="emoji_style"):
            ml_normalize("hello", emoji="")

    def test_invalid_emoji_style_uppercase_raises(self) -> None:
        """'CLDR' (wrong case) must raise DisarmError — matching is case-sensitive."""
        with pytest.raises(DisarmError, match="emoji_style"):
            ml_normalize("hello", emoji="CLDR")


class TestPresetsMetadataOrder:
    """#141: PRESETS metadata must reflect the real execution order."""

    def test_strip_obfuscation_confusables_after_demojize(self) -> None:
        # src/presets.rs::_strip_obfuscation runs confusables AFTER demojize so
        # typographic punctuation inside emoji names is folded too (idempotency).
        from disarm import PRESETS

        steps = [name for name, _ in PRESETS["strip_obfuscation"]]
        assert steps.index("confusables") > steps.index("demojize")
        assert steps == [
            "normalize",
            "strip_zalgo",
            "strip_bidi",
            "strip_zero_width",
            "demojize",
            "strip_invisibles",
            "confusables",
            "strip_accents",
            "collapse_whitespace",
        ]


# ===== #416: idempotency across an invisible-separated combining mark =====


class TestTerminalNfcIdempotency:
    """#416 — `security_clean` and `sort_key` must be fixed points even when an
    invisible code point separates a base character from a combining mark.

    Mechanism of the bug (and why the terminal NFC fixes it):

    Both pipelines run NFKC *first*, then strip invisible code points later (the
    zero-width pass folded into `collapse_whitespace`). With input
    ``"a" + U+200B + U+0301 + "b"`` the combining acute (U+0301) is NOT adjacent to
    its base `a` during the leading NFKC — the zero-width sits between them — so
    NFKC leaves it decomposed. The strip then deletes the zero-width, making
    `a` and U+0301 adjacent *after* the only normalization pass. The composed form
    (`á`, U+00E1) therefore appeared only on the *second* call, so
    ``f(x) != f(f(x))`` — which `THREAT_MODEL.md` classifies as a vulnerability.

    The fix is a terminal NFC pass appended to each pipeline (#416): it recomposes
    the adjacency the strip created, on the first call, so `f(x)` is a fixed point.
    NFC (not NFKC) is sufficient — the leading NFKC already removed every
    compatibility form and stripping only deletes code points, so nothing after it
    can reintroduce one.
    """

    # The invisible separators that trigger the bug: zero-width space/non-joiner/
    # joiner and the BOM / zero-width no-break space. Explicit escapes (not literal
    # invisibles) so the vectors are auditable and editor-safe. (CGJ U+034F joins
    # this set once #413 makes it a strip target.)
    INVISIBLES = ["\u200b", "\u200c", "\u200d", "\ufeff"]
    COMBINING_ACUTE = "\u0301"

    @pytest.mark.parametrize("preset", [security_clean, sort_key])
    @pytest.mark.parametrize("sep", INVISIBLES, ids=lambda s: f"U+{ord(s):04X}")
    def test_invisible_separated_mark_is_recomposed_and_idempotent(self, preset, sep):
        # 'a' + <invisible> + combining acute + 'b'
        text = f"a{sep}{self.COMBINING_ACUTE}b"
        once = preset(text)
        # The invisible is gone and the base+mark are recomposed to a single 'á'
        # (U+00E1) on the FIRST pass — not left decomposed for a second call.
        assert once == "áb", f"{preset.__name__}: expected composed 'áb', got {once!r}"
        # The fixed-point property the bug violated.
        assert preset(once) == once, f"{preset.__name__} not idempotent for U+{ord(sep):04X}"

    def test_security_clean_repro_from_issue(self):
        # The exact #416 repro: first call must already be composed.
        out = security_clean("a\u200b\u0301b")
        # 'a' + combining acute compose to a single 'á' (U+00E1); then 'b'.
        assert [hex(ord(c)) for c in out] == ["0xe1", "0x62"]  # á, b
        assert security_clean(out) == out

    def test_sort_key_repro_is_a_411_regression(self):
        # sort_key only has this bug because #411 made it *preserve* accents
        # instead of folding them away. `search_key` still folds (it strips the
        # accent), so it was never affected — it canonicalizes to plain "ab".
        bad = "a\u200b\u0301b"
        assert sort_key(bad) == "áb"  # accent preserved, composed (NFC)
        assert sort_key(sort_key(bad)) == sort_key(bad)  # idempotent after the fix
        assert search_key(bad) == "ab"  # contrast: folds the accent, always idempotent

    def test_unaffected_presets_were_already_idempotent(self):
        # Siblings are fixed points for a different reason and needed no change:
        # they either fold/strip the mark or never compose it. Pin that so a
        # future refactor cannot silently regress them.
        text = "a\u200b\u0301b"
        for preset in (normalize_user_input, display_clean, search_key, catalog_key, ml_normalize):
            assert preset(preset(text)) == preset(text), f"{preset.__name__} regressed"

    def test_plain_inputs_unchanged_by_terminal_nfc(self):
        # The terminal NFC is a no-op on text that has no strip-created adjacency:
        # ASCII passes through, and already-composed accents are untouched (so the
        # #411 accent-preservation outputs are stable).
        assert security_clean("hello world") == "hello world"
        assert sort_key("Über") == "über"  # "Über" -> "über", composed
        assert sort_key("café") == "café"  # already NFC

    @pytest.mark.hypothesis
    def test_idempotent_under_injected_invisibles_property(self):
        # A *targeted* property test. Plain `st.text()` almost never emits the
        # base+invisible+combining-mark shape that triggers #416 (which is why the
        # pre-existing random idempotency tests missed it), so this strategy
        # interleaves letters, combining marks, and invisibles explicitly.
        from hypothesis import given
        from hypothesis import strategies as st

        letters = st.sampled_from("abcdeáüöABCДΩ中")
        marks = st.sampled_from("\u0301\u0300\u0308\u0327")  # acute, grave, diaeresis, cedilla
        invisibles = st.sampled_from(self.INVISIBLES)
        piece = st.one_of(letters, marks, invisibles)
        strategy = st.lists(piece, min_size=1, max_size=24).map("".join)

        # Scoped to security_clean (the #416 acceptance target). sort_key's
        # terminal NFC is pinned deterministically above; a *separate* pre-existing
        # transliterate-order bug keeps it from being globally idempotent over this
        # broad alphabet (tracked in #419), so it is excluded here.
        @given(strategy)
        def check(text):
            once = security_clean(text)
            assert security_clean(once) == once, (
                f"security_clean not idempotent on {text!r}: {once!r} -> {security_clean(once)!r}"
            )

        check()


# ===== #413: invisible / non-interchange code point stripping =====


def _tags(s: str) -> str:
    """Encode an ASCII string into the Unicode Tags block (the smuggling channel)."""
    return "".join(chr(0xE0000 + ord(c)) for c in s)


# A well-formed Scotland subdivision flag: U+1F3F4 + g,b,s,c,t tag letters + cancel.
SCOTLAND_FLAG = "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f"


class TestInvisibleNonInterchangeStripping:
    """#413 — the security presets strip the LLM-smuggling and non-interchange
    code point classes that survive NFKC and the existing zero-width passes.

    Two tiers: (A) active smuggling channels (Unicode Tags U+E0000-E007F and
    variation selectors), and (B) adjacent hygiene (Combining Grapheme Joiner
    U+034F, noncharacters, Private Use Area, Braille blank U+2800). None is a
    blanket delete: valid emoji flag sequences and (in display_clean) the
    presentation selectors and PUA are preserved.
    """

    # -- (A) smuggling channels --

    def test_tag_block_smuggling_stripped(self):
        assert security_clean("hi" + _tags("PWN")) == "hi"
        assert normalize_user_input("hi" + _tags("PWN")) == "hi"

    def test_deprecated_language_tag_e0001_fixed(self):
        # U+E0001 LANGUAGE TAG used to survive even strip_obfuscation.
        assert strip_obfuscation("hi\U000e0001bye") == "hibye"
        assert security_clean("a\U000e0001b") == "ab"

    def test_variation_selectors_stripped_in_comparison_presets(self):
        assert normalize_user_input("g\ufe01data") == "gdata"  # VS2
        assert security_clean("g\U000e0100data") == "gdata"  # VS17

    # -- (B) adjacent hygiene --

    def test_cgj_stripped(self):
        # Denylist evasion: "ad" + CGJ + "min" renders as "admin".
        assert security_clean("ad\u034fmin") == "admin"
        assert normalize_user_input("ad\u034fmin") == "admin"

    def test_noncharacters_stripped(self):
        assert security_clean("a\ufffeb") == "ab"
        assert security_clean("a\ufdd0b") == "ab"
        assert security_clean("a\U0001fffeb") == "ab"  # plane-1 noncharacter

    def test_pua_stripped_in_comparison_kept_in_display(self):
        assert security_clean("a\ue000b") == "ab"  # BMP PUA
        assert security_clean("a\U000f0000b") == "ab"  # plane-15 PUA
        # display_clean preserves PUA (icon fonts) — "flag, don't delete".
        assert "\ue000" in display_clean("a\ue000b")

    def test_braille_blank_folds_to_space(self):
        # U+2800 renders blank but is category Symbol, so collapse_whitespace
        # ignored it; it now folds to a space (not deleted) so Braille round-trips.
        assert security_clean("a\u2800b") == "a b"
        assert display_clean("a\u2800b") == "a b"

    # -- carve-outs (not a blanket delete) --

    def test_emoji_flag_sequence_preserved(self):
        # The Scotland flag (U+1F3F4 + tag letters + U+E007F) must survive a
        # Tags-block strip in the rendering preset.
        assert display_clean(SCOTLAND_FLAG + " wins") == SCOTLAND_FLAG + " wins"

    def test_presentation_selector_preserved_in_display(self):
        # VS16 (emoji presentation) is kept after a base in display_clean…
        assert display_clean("❤\ufe0f") == "❤\ufe0f"
        # …but stripped in the comparison presets.
        assert "\ufe0f" not in security_clean("❤\ufe0f")

    def test_strip_obfuscation_demojize_unchanged(self):
        # The emoji path is untouched: heart + VS16 still demojizes to "red heart".
        assert strip_obfuscation("❤\ufe0f") == "red heart"

    # -- idempotency (the strips must not break the fixed-point invariant) --

    def test_idempotent_across_all_classes(self):
        samples = [
            "ad\u034fmin",  # CGJ
            "a\u200b\u034f\u0301b",  # zero-width + CGJ + combining mark
            "a\u2800b",  # Braille blank
            "ab\ufffec\ue000d",  # noncharacter + PUA
            "hi" + _tags("PWN"),  # tags
        ]
        for preset in (security_clean, normalize_user_input, display_clean, strip_obfuscation):
            for s in samples:
                assert preset(preset(s)) == preset(s), f"{preset.__name__} not idempotent on {s!r}"

    # -- standalone public helpers --

    def test_standalone_helpers(self):
        from disarm import strip_noncharacters, strip_pua, strip_tags, strip_variation_selectors

        assert strip_tags("hi" + _tags("PWN")) == "hi"
        assert strip_tags(SCOTLAND_FLAG) == SCOTLAND_FLAG  # flag preserved
        assert strip_variation_selectors("g\ufe01\U000e0100data") == "gdata"
        assert strip_noncharacters("a\ufffeb\ufdd0c") == "abc"
        assert strip_pua("a\ue000b\U000f0000c") == "abc"
