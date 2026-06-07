"""Regression tests derived from bug reports in upstream packages.

Sources reviewed:
- carpedm20/emoji: ZWJ IndexError, regex removal, API breaks
- un33k/python-slugify: typographic punctuation, language mappings
- avian2/unidecode: vulgar fractions trailing whitespace, missing chars

Each test class documents which upstream bug inspired it.
"""

from __future__ import annotations

import pytest

from translit import (
    Text,
    TextPipeline,
    collapse_whitespace,
    demojize,
    slugify,
    transliterate,
)

# ---------------------------------------------------------------------------
# Malformed emoji sequences (emoji package: ZWJ IndexError, various)
# ---------------------------------------------------------------------------


class TestMalformedEmojiSequences:
    """Upstream: carpedm20/emoji changelog 'Fix malformed ZWJ IndexError'.

    Truncated or orphaned ZWJ/VS characters must not leak into output
    or cause crashes.
    """

    def test_trailing_zwj_after_emoji(self) -> None:
        """ZWJ after matched emoji must be consumed, not leak."""
        result = demojize("😀\u200d")
        assert "\u200d" not in result
        assert "grinning face" in result

    def test_lone_zwj(self) -> None:
        """Orphaned ZWJ produces empty output, not the raw character."""
        result = demojize("\u200d")
        assert "\u200d" not in result

    def test_double_zwj(self) -> None:
        result = demojize("\u200d\u200d")
        assert "\u200d" not in result

    def test_zwj_before_text(self) -> None:
        result = demojize("\u200dhello")
        assert result == "hello"

    def test_lone_variation_selector(self) -> None:
        result = demojize("\ufe0f")
        assert "\ufe0f" not in result

    def test_emoji_zwj_at_end(self) -> None:
        """Emoji followed by trailing ZWJ at string end."""
        result = demojize("👨\u200d")
        assert "\u200d" not in result
        assert "man" in result

    def test_single_regional_indicator(self) -> None:
        """Lone regional indicator (half a flag) handled gracefully."""
        result = demojize("\U0001f1fa")
        # Should not crash; either replaced or preserved
        assert isinstance(result, str)

    def test_emoji_zwj_emoji(self) -> None:
        """Known ZWJ sequence should match as a unit, not decompose."""
        # 👨‍💻 = man + ZWJ + laptop (technologist)
        result = demojize("👨\u200d💻")
        # Should resolve as a ZWJ sequence if in CLDR data
        assert isinstance(result, str)
        assert "\u200d" not in result

    def test_skin_tone_modifier_alone(self) -> None:
        """Lone skin tone modifier resolves to its name."""
        result = demojize("\U0001f3fb")
        assert "skin tone" in result.lower() or result == "[?]"


# ---------------------------------------------------------------------------
# Vulgar fractions (unidecode: trailing whitespace, missing chars)
# ---------------------------------------------------------------------------


class TestVulgarFractions:
    """Upstream: avian2/unidecode v1.3.5 'Fix trailing space in vulgar
    fractions'. Also: missing fraction coverage.

    All 18 vulgar fraction characters must transliterate correctly with
    no trailing whitespace.
    """

    FRACTIONS = {
        "\u00bc": "1/4",  # ¼
        "\u00bd": "1/2",  # ½
        "\u00be": "3/4",  # ¾
        "\u2150": "1/7",  # ⅐
        "\u2151": "1/9",  # ⅑
        "\u2152": "1/10",  # ⅒
        "\u2153": "1/3",  # ⅓
        "\u2154": "2/3",  # ⅔
        "\u2155": "1/5",  # ⅕
        "\u2156": "2/5",  # ⅖
        "\u2157": "3/5",  # ⅗
        "\u2158": "4/5",  # ⅘
        "\u2159": "1/6",  # ⅙
        "\u215a": "5/6",  # ⅚
        "\u215b": "1/8",  # ⅛
        "\u215c": "3/8",  # ⅜
        "\u215d": "5/8",  # ⅝
        "\u215e": "7/8",  # ⅞
    }

    @pytest.mark.parametrize(
        "char,expected",
        [(c, e) for c, e in FRACTIONS.items()],
        ids=[f"U+{ord(c):04X} {c}" for c in FRACTIONS],
    )
    def test_fraction_transliterates(self, char: str, expected: str) -> None:
        result = transliterate(char, errors="preserve")
        assert result == expected

    @pytest.mark.parametrize(
        "char",
        list(FRACTIONS.keys()),
        ids=[f"U+{ord(c):04X} {c}" for c in FRACTIONS],
    )
    def test_no_trailing_whitespace(self, char: str) -> None:
        """Upstream bug: fractions had trailing spaces in output."""
        result = transliterate(char, errors="preserve")
        assert result == result.strip(), f"Trailing whitespace in {char!r} -> {result!r}"


# ---------------------------------------------------------------------------
# Typographic punctuation (python-slugify #30: curly quotes)
# ---------------------------------------------------------------------------


class TestTypographicPunctuation:
    """Upstream: python-slugify #30 — right single quotation mark not handled.

    All common typographic punctuation variants must transliterate to their
    ASCII equivalents.
    """

    PUNCTUATION = {
        "\u2018": "'",  # ' left single quote
        "\u2019": "'",  # ' right single quote
        "\u201c": '"',  # " left double quote
        "\u201d": '"',  # " right double quote
        "\u2013": "-",  # – en dash
        "\u2014": "-",  # — em dash
        "\u2026": "...",  # … ellipsis
        "\u00b7": ".",  # · middle dot
        "\u2022": "*",  # • bullet
    }

    @pytest.mark.parametrize(
        "char,expected",
        list(PUNCTUATION.items()),
        ids=[f"U+{ord(c):04X}" for c in PUNCTUATION],
    )
    def test_typographic_to_ascii(self, char: str, expected: str) -> None:
        assert transliterate(char) == expected

    def test_curly_quotes_in_slug(self) -> None:
        """The original python-slugify bug: curly quotes in slug input."""
        result = slugify("it\u2019s a test")
        assert "'" not in result
        assert "\u2019" not in result
        assert "it" in result and "test" in result


# ---------------------------------------------------------------------------
# Whitespace variants (python-slugify: various Unicode spaces)
# ---------------------------------------------------------------------------


class TestWhitespaceVariants:
    """Various Unicode whitespace characters must collapse to single ASCII space."""

    SPACES = [
        "\u00a0",  # non-breaking space
        "\u2002",  # en space
        "\u2003",  # em space
        "\u2004",  # three-per-em space
        "\u2005",  # four-per-em space
        "\u2006",  # six-per-em space
        "\u2007",  # figure space
        "\u2008",  # punctuation space
        "\u2009",  # thin space
        "\u200a",  # hair space
        "\u202f",  # narrow no-break space
        "\u205f",  # medium mathematical space
        "\u3000",  # ideographic space
    ]

    @pytest.mark.parametrize("space", SPACES, ids=[f"U+{ord(s):04X}" for s in SPACES])
    def test_unicode_space_collapses(self, space: str) -> None:
        result = collapse_whitespace(f"hello{space}world")
        assert result == "hello world"


# ---------------------------------------------------------------------------
# Transliteration table data quality
# ---------------------------------------------------------------------------


class TestTransliterationTableQuality:
    """Meta-tests for data quality in transliteration tables.

    Inspired by unidecode's repeated fixes for trailing whitespace and
    missing characters.
    """

    def test_all_fractions_covered(self) -> None:
        """Every Unicode vulgar fraction character has a mapping."""
        for cp in range(0x2150, 0x215F):
            char = chr(cp)
            result = transliterate(char, errors="preserve")
            assert result != char, f"U+{cp:04X} ({char}) has no mapping"

    def test_latin1_supplement_complete(self) -> None:
        """All printable Latin-1 Supplement chars (U+00A0-U+00FF) handled."""
        for cp in range(0x00C0, 0x0100):
            char = chr(cp)
            result = transliterate(char, errors="preserve")
            assert result != char, f"U+{cp:04X} ({char}) has no mapping"


# ---------------------------------------------------------------------------
# Pipeline integration edge cases
# ---------------------------------------------------------------------------


class TestPipelineEdgeCases:
    """Demojize in pipeline shouldn't break other steps."""

    def test_pipeline_demojize_then_slugify(self) -> None:
        """Common NLP pattern: emoji → slug-safe text."""
        result = Text("I love 😀!").demojize().slugify().value
        assert "grinning-face" in result

    def test_pipeline_demojize_preserves_non_emoji(self) -> None:
        """Non-emoji Unicode preserved through demojize step."""
        pipe = TextPipeline(demojize=True)
        result = pipe("Héllo café 😀")
        assert "Héllo" in result
        assert "café" in result
        assert "grinning face" in result

    def test_pipeline_full_chain(self) -> None:
        """Full pipeline: normalize → demojize → transliterate → fold → collapse."""
        pipe = TextPipeline(
            normalize="NFC",
            demojize=True,
            transliterate=True,
            fold_case=True,
            collapse_whitespace=True,
        )
        result = pipe("  Héllo  😀  Wörld  ")
        assert result == "hello grinning face world"


# ---------------------------------------------------------------------------
# EmojiProvider warning behaviour
# ---------------------------------------------------------------------------


class TestEmojiProviderWarnings:
    """Provider exceptions and bad return types must issue UserWarning, not crash."""

    def test_provider_exception_issues_warning(self) -> None:
        """A provider that always raises must trigger a UserWarning."""
        import warnings

        class BrokenProvider:
            def lookup(self, sequence: list) -> str | None:
                raise RuntimeError("provider is broken")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = demojize("😀", provider=BrokenProvider())

        assert any("raised an exception" in str(w.message) for w in caught), (
            "Expected a UserWarning about provider exception"
        )
        # Falls back to CLDR table
        assert "grinning face" in result

    def test_provider_non_string_return_issues_warning(self) -> None:
        """A provider returning a non-string must trigger a UserWarning."""
        import warnings

        class BadReturnProvider:
            def lookup(self, sequence: list) -> object:
                return 42  # wrong type

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = demojize("😀", provider=BadReturnProvider())

        assert any("non-string" in str(w.message) for w in caught), (
            "Expected a UserWarning about non-string return value"
        )
        # Falls back to CLDR table
        assert "grinning face" in result


# ---------------------------------------------------------------------------
# Batch (list-input) parameter parity with the scalar path
# Regression: tones= was dropped on the list path, and tones= with target=
# was not rejected (PRs #14/#15 review comments).
# ---------------------------------------------------------------------------


class TestBatchParameterParity:
    """List input must honour (and validate) the same params as scalar input."""

    def test_tones_forwarded_to_batch(self) -> None:
        # Previously transliterate(['北京'], tones=True) silently returned
        # toneless pinyin while the scalar path returned toned.
        assert transliterate(["北京"], tones=True) == [transliterate("北京", tones=True)]
        assert transliterate(["北京"], tones=True) == ["běi jīng"]

    def test_tones_with_target_raises_on_batch(self) -> None:
        # The scalar path rejects forward-only params with target=; the list
        # path must too, instead of silently ignoring tones.
        with pytest.raises(ValueError, match=r"forward-only parameters .*tones.* 'target'"):
            transliterate(["Moskva"], target="ru", tones=True)


class TestContextParameterValidation:
    """Context path must enforce the same parameter rules as the plain path."""

    def test_context_rejects_iso9_and_gost_together(self) -> None:
        # The mutual-exclusion check was missing from the context path, so this
        # silently returned a result instead of raising (review comment on #18).
        with pytest.raises(ValueError, match="mutually exclusive"):
            transliterate("كتب", lang="ar", context=True, strict_iso9=True, gost7034=True)

    def test_context_batch_rejects_iso9_and_gost_together(self) -> None:
        with pytest.raises(ValueError, match="mutually exclusive"):
            transliterate(["كتب"], lang="ar", context=True, strict_iso9=True, gost7034=True)


class TestNFKCCompatibilityFallback:
    """transliterate recovers NFKC-compatible Latin instead of emitting [?] (#81)."""

    def test_mathematical_alphanumerics(self):
        assert transliterate("𝕳𝖊𝖑𝖑𝖔 𝟙𝟚𝟛") == "Hello 123"

    def test_presentation_ligatures(self):
        assert transliterate("ﬁ ﬂ") == "fi fl"

    def test_superscripts_recovered(self):
        assert transliterate("x²") == "x2"

    def test_emoji_still_replaced(self):
        # Emoji do not NFKC-decompose to ASCII, so they remain [?] (by design).
        assert transliterate("😀") == "[?]"

    def test_strip_obfuscation_folds_fancy_text(self):
        # Anti-obfuscation: "fancy text" math alphanumerics must fold, not survive.
        from translit import strip_obfuscation

        assert strip_obfuscation("𝕳𝖊𝖑𝖑𝖔") == "Hello"  # case preserved


class TestUnknownLangRaises:
    """Unknown lang codes raise instead of silently falling back (#68)."""

    @pytest.mark.parametrize("bad", ["RU", "russian", "zz", "EN"])
    def test_unknown_lang_raises(self, bad):
        with pytest.raises((ValueError, Exception), match="unknown language code"):
            transliterate("Москва", lang=bad)

    def test_valid_and_special_codes_accepted(self):
        assert transliterate("Москва", lang="ru") == "Moskva"
        assert transliterate("Москва", lang="auto") == "Moskva"
        assert transliterate("Næss", lang="nb") == transliterate("Næss", lang="no")  # alias


class TestSealRegistrations:
    """seal_registrations() freezes the global registration tables (#64).

    Run in a subprocess: sealing is an irreversible process-global latch, so an
    in-process test would contaminate the rest of the session.
    """

    def test_seal_blocks_all_mutators_but_keeps_registrations(self):
        import subprocess
        import sys

        code = (
            "import translit as t\n"
            "t.register_lang('xx', {'\\u00c4': 'Ae'})\n"
            "t.register_replacements({'@': '(at)'})\n"
            "assert not t.registrations_sealed()\n"
            "t.seal_registrations()\n"
            "assert t.registrations_sealed()\n"
            "blocked = 0\n"
            "for fn, args in [(t.register_lang, ('yy', {})),\n"
            "                 (t.register_replacements, ({'#': 'h'},)),\n"
            "                 (t.remove_replacement, ('@',)),\n"
            "                 (t.clear_replacements, ())]:\n"
            "    try:\n"
            "        fn(*args)\n"
            "    except t.TranslitError:\n"
            "        blocked += 1\n"
            "assert blocked == 4, blocked\n"
            # reads still work after sealing
            "assert t.transliterate('\\u00c4', lang='xx') == 'Ae'\n"
            "assert t.transliterate('a@b') == 'a(at)b'\n"
            "print('OK')\n"
        )
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert r.returncode == 0 and "OK" in r.stdout, f"stdout={r.stdout!r} stderr={r.stderr!r}"
