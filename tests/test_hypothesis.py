"""Property-based tests for translit using Hypothesis.

These tests verify fundamental invariants of Unicode text processing
operations that hold across the entire input space, not just selected
examples.
"""

from __future__ import annotations

import re

from conftest import nf_forms, unicode_text
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from translit import (
    UniqueSlugifier,
    collapse_whitespace,
    fold_case,
    grapheme_len,
    grapheme_split,
    grapheme_truncate,
    is_ascii,
    is_normalized,
    normalize,
    sanitize_filename,
    slugify,
    strip_accents,
    transliterate,
)

# ---------------------------------------------------------------------------
# 1. Normalization idempotence: normalize(normalize(x, F), F) == normalize(x, F)
# ---------------------------------------------------------------------------


class TestNormalizationProperties:
    """Properties of Unicode normalization."""

    @given(text=unicode_text, form=nf_forms)
    @settings(max_examples=500)
    def test_normalize_idempotent(self, text: str, form: str) -> None:
        """Applying normalization twice yields the same result as once."""
        once = normalize(text, form=form)
        twice = normalize(once, form=form)
        assert once == twice

    @given(text=unicode_text, form=nf_forms)
    @settings(max_examples=500)
    def test_normalize_then_is_normalized(self, text: str, form: str) -> None:
        """After normalizing, is_normalized must return True."""
        result = normalize(text, form=form)
        assert is_normalized(result, form=form)


# ---------------------------------------------------------------------------
# 2. strip_accents idempotence
# ---------------------------------------------------------------------------


class TestStripAccentsProperties:
    @given(text=unicode_text)
    @settings(max_examples=500)
    def test_strip_accents_idempotent(self, text: str) -> None:
        """Removing diacriticals is a one-shot operation."""
        once = strip_accents(text)
        twice = strip_accents(once)
        assert once == twice


# ---------------------------------------------------------------------------
# 3. transliterate with errors="ignore" always produces ASCII
# ---------------------------------------------------------------------------


class TestTransliterateProperties:
    @given(text=unicode_text)
    @settings(max_examples=500)
    def test_transliterate_ignore_produces_ascii(self, text: str) -> None:
        """With errors='ignore', output contains only ASCII characters."""
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII in result: {[c for c in result if ord(c) > 127]!r}"

    @given(text=unicode_text)
    @settings(max_examples=200)
    def test_transliterate_preserve_keeps_all_chars(self, text: str) -> None:
        """With errors='preserve', every input character appears in the output
        (either transliterated or preserved verbatim), so the output is never
        shorter than the input in character count when no CJK space-insertion
        occurs.  We verify the weaker property: output is never empty when
        input is non-empty."""
        assume(len(text.strip()) > 0)
        result = transliterate(text, errors="preserve")
        assert len(result) > 0


# ---------------------------------------------------------------------------
# 4. fold_case idempotence
# ---------------------------------------------------------------------------


class TestFoldCaseProperties:
    @given(text=unicode_text)
    @settings(max_examples=500)
    def test_fold_case_idempotent(self, text: str) -> None:
        """Case folding applied twice gives the same result as once."""
        once = fold_case(text)
        twice = fold_case(once)
        assert once == twice


# ---------------------------------------------------------------------------
# 5. collapse_whitespace idempotence
# ---------------------------------------------------------------------------


class TestCollapseWhitespaceProperties:
    @given(text=unicode_text)
    @settings(max_examples=500)
    def test_collapse_whitespace_idempotent(self, text: str) -> None:
        """Collapsing whitespace twice gives the same result as once."""
        once = collapse_whitespace(text)
        twice = collapse_whitespace(once)
        assert once == twice

    @given(text=unicode_text)
    @settings(max_examples=300)
    def test_collapse_whitespace_no_leading_trailing(self, text: str) -> None:
        """Result has no leading or trailing whitespace."""
        result = collapse_whitespace(text)
        if result:
            assert result[0] != " "
            assert result[-1] != " "

    @given(text=unicode_text)
    @settings(max_examples=300)
    def test_collapse_whitespace_no_consecutive_spaces(self, text: str) -> None:
        """Result never contains two consecutive spaces."""
        result = collapse_whitespace(text)
        assert "  " not in result


# ---------------------------------------------------------------------------
# 6. grapheme_split / grapheme_len consistency
# ---------------------------------------------------------------------------


class TestGraphemeProperties:
    @given(text=unicode_text)
    @settings(max_examples=500)
    def test_grapheme_split_len_consistent(self, text: str) -> None:
        """len(grapheme_split(text)) == grapheme_len(text)."""
        parts = grapheme_split(text)
        length = grapheme_len(text)
        assert len(parts) == length

    @given(text=unicode_text)
    @settings(max_examples=500)
    def test_grapheme_split_roundtrip(self, text: str) -> None:
        """Joining grapheme_split recovers the original string."""
        parts = grapheme_split(text)
        assert "".join(parts) == text

    @given(text=unicode_text, n=st.integers(min_value=0, max_value=200))
    @settings(max_examples=500)
    def test_grapheme_truncate_respects_limit(self, text: str, n: int) -> None:
        """grapheme_truncate never exceeds the requested grapheme count."""
        result = grapheme_truncate(text, n)
        assert grapheme_len(result) <= n

    @given(text=unicode_text, n=st.integers(min_value=0, max_value=200))
    @settings(max_examples=500)
    def test_grapheme_truncate_is_prefix(self, text: str, n: int) -> None:
        """grapheme_truncate returns a prefix of the original string."""
        result = grapheme_truncate(text, n)
        assert text.startswith(result)


# ---------------------------------------------------------------------------
# 7. slugify output invariants
# ---------------------------------------------------------------------------

# Allowed slug characters (default: lowercase ASCII + digits + hyphen separator)
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class TestSlugifyProperties:
    @given(text=unicode_text)
    @settings(max_examples=500)
    def test_slugify_default_charset(self, text: str) -> None:
        """Default slugify output contains only [a-z0-9-] and no
        leading/trailing/consecutive separators."""
        result = slugify(text)
        if result:  # empty input → empty output is valid
            assert SLUG_PATTERN.match(result), f"Bad slug: {result!r}"

    @given(
        text=unicode_text,
        max_length=st.integers(min_value=1, max_value=200),
    )
    @settings(max_examples=300)
    def test_slugify_max_length_respected(self, text: str, max_length: int) -> None:
        """Output never exceeds max_length."""
        result = slugify(text, max_length=max_length)
        assert len(result) <= max_length

    @given(text=unicode_text)
    @settings(max_examples=300)
    def test_slugify_is_ascii(self, text: str) -> None:
        """Default slugify always produces ASCII output."""
        result = slugify(text)
        assert is_ascii(result)


# ---------------------------------------------------------------------------
# 8. sanitize_filename output safety
# ---------------------------------------------------------------------------

# Characters illegal on "universal" platform
UNIVERSAL_ILLEGAL = set('/:*?"<>|\\\0')
WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class TestSanitizeFilenameProperties:
    @given(text=st.text(min_size=1, alphabet=st.characters(codec="utf-8")))
    @settings(max_examples=500)
    def test_sanitize_filename_no_illegal_chars(self, text: str) -> None:
        """Output contains no platform-illegal characters."""
        result = sanitize_filename(text, platform="universal")
        illegal_found = [c for c in result if c in UNIVERSAL_ILLEGAL]
        assert not illegal_found, f"Illegal chars in {result!r}: {illegal_found}"

    @given(
        text=st.text(min_size=1, alphabet=st.characters(codec="utf-8")),
        max_length=st.integers(min_value=1, max_value=255),
    )
    @settings(max_examples=300)
    def test_sanitize_filename_max_length(self, text: str, max_length: int) -> None:
        """Output never exceeds max_length."""
        result = sanitize_filename(text, max_length=max_length)
        assert len(result) <= max_length

    @given(text=st.text(min_size=1, alphabet=st.characters(codec="utf-8")))
    @settings(max_examples=300)
    def test_sanitize_filename_not_reserved(self, text: str) -> None:
        """Output (stem before extension) is never a Windows reserved name
        on the universal platform."""
        result = sanitize_filename(text, platform="universal")
        if result:
            stem = result.split(".")[0].upper()
            assert stem not in WINDOWS_RESERVED, f"Reserved name in output: {result!r}"

    @given(text=st.text(min_size=1, alphabet=st.characters(codec="utf-8")))
    @settings(max_examples=300)
    def test_sanitize_filename_no_path_traversal(self, text: str) -> None:
        """Output never contains '..' path traversal sequences."""
        result = sanitize_filename(text, platform="universal")
        assert ".." not in result


# ---------------------------------------------------------------------------
# Deterministic regression tests for bugs found by Hypothesis
# ---------------------------------------------------------------------------


class TestSanitizeFilenameRegressions:
    """Deterministic reproductions of bugs found by property-based testing."""

    def test_illegal_char_in_extension(self) -> None:
        """'0·|' → '0.|' — pipe character leaks through the extension."""
        result = sanitize_filename("0\u00b7|", platform="universal")
        illegal = [c for c in result if c in set('/:*?"<>|\\\0')]
        assert not illegal, f"Illegal chars in {result!r}: {illegal}"

    def test_path_traversal_via_ellipsis(self) -> None:
        """'0…0·' → '0...0.' — ellipsis reintroduces '..' after the check."""
        result = sanitize_filename("0\u20260\u00b7", platform="universal")
        assert ".." not in result, f"Path traversal in {result!r}"


# ---------------------------------------------------------------------------
# 9. UniqueSlugifier uniqueness
# ---------------------------------------------------------------------------


class TestUniqueSlugifierProperties:
    @given(
        text=st.text(min_size=1, alphabet=st.characters(codec="utf-8")),
        n=st.integers(min_value=2, max_value=20),
    )
    @settings(max_examples=100)
    def test_unique_slugifier_no_duplicates(self, text: str, n: int) -> None:
        """Calling UniqueSlugifier N times with the same input produces
        N distinct slugs."""
        us = UniqueSlugifier()
        slugs = [us(text) for _ in range(n)]
        # Filter out empty slugs (input may transliterate to nothing)
        non_empty = [s for s in slugs if s]
        if non_empty:
            assert len(set(non_empty)) == len(non_empty), f"Duplicate slugs: {non_empty}"


# ---------------------------------------------------------------------------
# 10. Indic script transliteration properties
# ---------------------------------------------------------------------------

# Hypothesis strategies for script-specific text
_devanagari_consonants = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x0915, 0x093A)]),
    min_size=1, max_size=20,
)
_devanagari_vowels = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x0905, 0x0915)]),
    min_size=1, max_size=20,
)
_devanagari_full = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0900, 0x0980) if chr(c).isprintable()]
    ),
    min_size=1, max_size=30,
)
_bengali_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0980, 0x0A00) if chr(c).isprintable()]
    ),
    min_size=1, max_size=30,
)
_tamil_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0B80, 0x0C00) if chr(c).isprintable()]
    ),
    min_size=1, max_size=30,
)
_telugu_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0C00, 0x0C80) if chr(c).isprintable()]
    ),
    min_size=1, max_size=30,
)
_gujarati_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0A80, 0x0B00) if chr(c).isprintable()]
    ),
    min_size=1, max_size=30,
)
_kannada_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0C80, 0x0D00) if chr(c).isprintable()]
    ),
    min_size=1, max_size=30,
)
_malayalam_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0D00, 0x0D80) if chr(c).isprintable()]
    ),
    min_size=1, max_size=30,
)
_gurmukhi_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0A00, 0x0A80) if chr(c).isprintable()]
    ),
    min_size=1, max_size=30,
)
_odia_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0B00, 0x0B80) if chr(c).isprintable()]
    ),
    min_size=1, max_size=30,
)
_any_indic_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0900, 0x0D80) if chr(c).isprintable()]
    ),
    min_size=1, max_size=40,
)


class TestIndicTransliterationProperties:
    """Property-based tests for Indic (Brahmic) script transliteration."""

    @given(text=_devanagari_full)
    @settings(max_examples=500)
    def test_devanagari_produces_ascii(self, text: str) -> None:
        """Any Devanagari text transliterates to pure ASCII."""
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Devanagari: {result!r}"

    @given(text=_bengali_text)
    @settings(max_examples=300)
    def test_bengali_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Bengali: {result!r}"

    @given(text=_tamil_text)
    @settings(max_examples=300)
    def test_tamil_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Tamil: {result!r}"

    @given(text=_telugu_text)
    @settings(max_examples=300)
    def test_telugu_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Telugu: {result!r}"

    @given(text=_gujarati_text)
    @settings(max_examples=300)
    def test_gujarati_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Gujarati: {result!r}"

    @given(text=_kannada_text)
    @settings(max_examples=300)
    def test_kannada_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Kannada: {result!r}"

    @given(text=_malayalam_text)
    @settings(max_examples=300)
    def test_malayalam_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Malayalam: {result!r}"

    @given(text=_gurmukhi_text)
    @settings(max_examples=300)
    def test_gurmukhi_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Gurmukhi: {result!r}"

    @given(text=_odia_text)
    @settings(max_examples=300)
    def test_odia_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Odia: {result!r}"

    @given(text=_any_indic_text)
    @settings(max_examples=500)
    def test_any_indic_produces_ascii(self, text: str) -> None:
        """Any combination of characters from the full Indic range → ASCII."""
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Indic: {result!r}"

    @given(text=_any_indic_text)
    @settings(max_examples=300)
    def test_indic_transliteration_idempotent(self, text: str) -> None:
        """Transliterating Indic text twice gives the same result as once."""
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_devanagari_consonants)
    @settings(max_examples=300)
    def test_devanagari_consonants_end_with_a(self, text: str) -> None:
        """Bare Devanagari consonants (no virama/mātrā following) carry inherent 'a'.
        A string of only consonants should produce output ending in 'a'."""
        result = transliterate(text, errors="ignore")
        if result:
            assert result[-1] == "a", f"Bare consonant string should end with 'a': {result!r}"

    @given(text=_any_indic_text)
    @settings(max_examples=300)
    def test_indic_no_double_spaces(self, text: str) -> None:
        """Transliterated Indic text should not contain double spaces."""
        result = transliterate(text, errors="ignore")
        assert "  " not in result, f"Double space in: {result!r}"

    @given(text=_any_indic_text)
    @settings(max_examples=300)
    def test_indic_slugify_valid(self, text: str) -> None:
        """Slugifying any Indic text produces a valid slug."""
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Indic: {result!r}"


# ---------------------------------------------------------------------------
# 11. Hebrew script transliteration properties
# ---------------------------------------------------------------------------

_hebrew_consonants = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x05D0, 0x05EB)]),
    min_size=1, max_size=20,
)
_hebrew_nikkud = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x05B0, 0x05BE)]),
    min_size=1, max_size=10,
)
_hebrew_full = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0590, 0x0600) if chr(c).isprintable()]
    ),
    min_size=1, max_size=30,
)
_hebrew_presentation = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0xFB1D, 0xFB50) if chr(c).isprintable()]
    ),
    min_size=1, max_size=15,
)


class TestHebrewTransliterationProperties:
    """Property-based tests for Hebrew script transliteration."""

    @given(text=_hebrew_full)
    @settings(max_examples=500)
    def test_hebrew_produces_ascii(self, text: str) -> None:
        """Any Hebrew block text transliterates to pure ASCII."""
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Hebrew: {result!r}"

    @given(text=_hebrew_consonants)
    @settings(max_examples=300)
    def test_hebrew_consonants_produce_ascii(self, text: str) -> None:
        """Pure Hebrew consonants always produce ASCII.
        Note: some consonants (Alef, Ayin) are silent and map to empty."""
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Hebrew consonants: {result!r}"

    @given(text=_hebrew_presentation)
    @settings(max_examples=300)
    def test_hebrew_presentation_forms_produce_ascii(self, text: str) -> None:
        """Hebrew presentation forms (FB1D-FB4F) produce ASCII."""
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Hebrew presentation forms: {result!r}"

    @given(text=_hebrew_full)
    @settings(max_examples=300)
    def test_hebrew_transliteration_idempotent(self, text: str) -> None:
        """Transliterating Hebrew twice gives the same result as once."""
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_hebrew_full)
    @settings(max_examples=300)
    def test_hebrew_no_double_spaces(self, text: str) -> None:
        """Transliterated Hebrew text should not contain double spaces."""
        result = transliterate(text, errors="ignore")
        assert "  " not in result, f"Double space in: {result!r}"

    @given(text=_hebrew_full)
    @settings(max_examples=300)
    def test_hebrew_slugify_valid(self, text: str) -> None:
        """Slugifying any Hebrew text produces a valid slug."""
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Hebrew: {result!r}"


# ---------------------------------------------------------------------------
# 12. Multi-script mixture properties
# ---------------------------------------------------------------------------

_latin_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0041, 0x007B) if chr(c).isalpha()]
    ),
    min_size=1, max_size=20,
)
_extended_latin = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x00C0, 0x0250) if chr(c).isprintable()]
        + [chr(c) for c in range(0x1E00, 0x1F00) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)
_cyrillic_text = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x0400, 0x0500) if chr(c).isprintable()]),
    min_size=1, max_size=20,
)
_cjk_text = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x4E00, 0x5100)]),
    min_size=1, max_size=10,
)
_hangul_text = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0xAC00, 0xAD00)]),
    min_size=1, max_size=10,
)


def _interleave(*parts: str) -> str:
    """Interleave characters from multiple strings with spaces."""
    return " ".join(p for p in parts if p)


class TestMultiScriptMixtureProperties:
    """Property-based tests for multi-script text mixtures."""

    @given(latin=_latin_text, indic=_devanagari_full)
    @settings(max_examples=300)
    def test_latin_indic_mixture_ascii(self, latin: str, indic: str) -> None:
        """Latin + Indic mixed text transliterates to ASCII."""
        mixed = _interleave(latin, indic)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Latin+Indic: {result!r}"

    @given(latin=_latin_text, hebrew=_hebrew_full)
    @settings(max_examples=300)
    def test_latin_hebrew_mixture_ascii(self, latin: str, hebrew: str) -> None:
        """Latin + Hebrew mixed text transliterates to ASCII."""
        mixed = _interleave(latin, hebrew)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Latin+Hebrew: {result!r}"

    @given(indic=_any_indic_text, hebrew=_hebrew_full)
    @settings(max_examples=300)
    def test_indic_hebrew_mixture_ascii(self, indic: str, hebrew: str) -> None:
        """Indic + Hebrew mixed text transliterates to ASCII."""
        mixed = _interleave(indic, hebrew)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Indic+Hebrew: {result!r}"

    @given(
        latin=_extended_latin,
        indic=_any_indic_text,
        hebrew=_hebrew_full,
    )
    @settings(max_examples=300)
    def test_triple_mixture_ascii(self, latin: str, indic: str, hebrew: str) -> None:
        """Extended Latin + Indic + Hebrew all in one string → ASCII."""
        mixed = _interleave(latin, indic, hebrew)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from triple mix: {result!r}"

    @given(cyrillic=_cyrillic_text, indic=_any_indic_text)
    @settings(max_examples=300)
    def test_cyrillic_indic_mixture_ascii(self, cyrillic: str, indic: str) -> None:
        """Cyrillic + Indic mixed text transliterates to ASCII."""
        mixed = _interleave(cyrillic, indic)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Cyrillic+Indic: {result!r}"

    @given(cyrillic=_cyrillic_text, hebrew=_hebrew_full)
    @settings(max_examples=300)
    def test_cyrillic_hebrew_mixture_ascii(self, cyrillic: str, hebrew: str) -> None:
        """Cyrillic + Hebrew mixed text transliterates to ASCII."""
        mixed = _interleave(cyrillic, hebrew)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Cyrillic+Hebrew: {result!r}"

    @given(cjk=_cjk_text, indic=_any_indic_text)
    @settings(max_examples=300)
    def test_cjk_indic_mixture_ascii(self, cjk: str, indic: str) -> None:
        """CJK + Indic mixed text transliterates to ASCII."""
        mixed = _interleave(cjk, indic)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from CJK+Indic: {result!r}"

    @given(cjk=_cjk_text, hebrew=_hebrew_full)
    @settings(max_examples=300)
    def test_cjk_hebrew_mixture_ascii(self, cjk: str, hebrew: str) -> None:
        """CJK + Hebrew mixed text transliterates to ASCII."""
        mixed = _interleave(cjk, hebrew)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from CJK+Hebrew: {result!r}"

    @given(hangul=_hangul_text, indic=_devanagari_full)
    @settings(max_examples=300)
    def test_hangul_indic_mixture_ascii(self, hangul: str, indic: str) -> None:
        """Hangul + Indic mixed text transliterates to ASCII."""
        mixed = _interleave(hangul, indic)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Hangul+Indic: {result!r}"

    @given(extended=_extended_latin, indic=_any_indic_text)
    @settings(max_examples=300)
    def test_extended_latin_indic_mixture_ascii(self, extended: str, indic: str) -> None:
        """Extended Latin (accented) + Indic transliterates to ASCII."""
        mixed = _interleave(extended, indic)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from ExtLatin+Indic: {result!r}"

    @given(extended=_extended_latin, hebrew=_hebrew_full)
    @settings(max_examples=300)
    def test_extended_latin_hebrew_mixture_ascii(self, extended: str, hebrew: str) -> None:
        """Extended Latin (accented) + Hebrew transliterates to ASCII."""
        mixed = _interleave(extended, hebrew)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from ExtLatin+Hebrew: {result!r}"

    @given(
        latin=_extended_latin,
        cyrillic=_cyrillic_text,
        indic=_any_indic_text,
        hebrew=_hebrew_full,
        cjk=_cjk_text,
    )
    @settings(max_examples=200)
    def test_five_script_mixture_ascii(
        self, latin: str, cyrillic: str, indic: str, hebrew: str, cjk: str
    ) -> None:
        """Five-script mixture (Latin+Cyrillic+Indic+Hebrew+CJK) → ASCII."""
        mixed = _interleave(latin, cyrillic, indic, hebrew, cjk)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from 5-script mix: {result!r}"

    @given(
        latin=_extended_latin,
        cyrillic=_cyrillic_text,
        indic=_any_indic_text,
        hebrew=_hebrew_full,
        cjk=_cjk_text,
    )
    @settings(max_examples=200)
    def test_five_script_mixture_idempotent(
        self, latin: str, cyrillic: str, indic: str, hebrew: str, cjk: str
    ) -> None:
        """Five-script mixture transliteration is idempotent."""
        mixed = _interleave(latin, cyrillic, indic, hebrew, cjk)
        once = transliterate(mixed, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(
        latin=_extended_latin,
        indic=_any_indic_text,
        hebrew=_hebrew_full,
    )
    @settings(max_examples=200)
    def test_multi_script_slugify_valid(
        self, latin: str, indic: str, hebrew: str
    ) -> None:
        """Slugifying multi-script text always produces a valid slug."""
        mixed = _interleave(latin, indic, hebrew)
        result = slugify(mixed)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from multi-script: {result!r}"

    @given(
        latin=_extended_latin,
        indic=_any_indic_text,
        hebrew=_hebrew_full,
    )
    @settings(max_examples=200)
    def test_multi_script_preserve_nonempty(
        self, latin: str, indic: str, hebrew: str
    ) -> None:
        """Multi-script text with errors='preserve' is never shorter than
        it would be with errors='ignore'."""
        mixed = _interleave(latin, indic, hebrew)
        assume(len(mixed.strip()) > 0)
        ignore_result = transliterate(mixed, errors="ignore")
        preserve_result = transliterate(mixed, errors="preserve")
        assert len(preserve_result) >= len(ignore_result)
