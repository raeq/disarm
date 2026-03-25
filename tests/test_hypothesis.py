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
        [chr(c) for c in range(0x0900, 0x0E00) if chr(c).isprintable()]
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


_sinhala_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0D80, 0x0E00) if chr(c).isprintable()]
    ),
    min_size=1, max_size=30,
)


class TestSinhalaTransliterationProperties:
    """Property-based tests for Sinhala script transliteration."""

    @given(text=_sinhala_text)
    @settings(max_examples=300)
    def test_sinhala_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Sinhala: {result!r}"

    @given(text=_sinhala_text)
    @settings(max_examples=300)
    def test_sinhala_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_sinhala_text)
    @settings(max_examples=300)
    def test_sinhala_slugify_valid(self, text: str) -> None:
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Sinhala: {result!r}"


_georgian_text = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x10D0, 0x10F1)]),
    min_size=1, max_size=20,
)
_armenian_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0531, 0x0557)]
        + [chr(c) for c in range(0x0561, 0x0588)]
    ),
    min_size=1, max_size=20,
)


class TestGeorgianTransliterationProperties:
    """Property-based tests for Georgian script transliteration."""

    @given(text=_georgian_text)
    @settings(max_examples=300)
    def test_georgian_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Georgian: {result!r}"

    @given(text=_georgian_text)
    @settings(max_examples=300)
    def test_georgian_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_georgian_text)
    @settings(max_examples=300)
    def test_georgian_nonempty(self, text: str) -> None:
        """Georgian letters always produce non-empty output."""
        result = transliterate(text, errors="ignore")
        assert len(result) > 0, f"Empty result from Georgian: {text!r}"

    @given(text=_georgian_text)
    @settings(max_examples=300)
    def test_georgian_slugify_valid(self, text: str) -> None:
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Georgian: {result!r}"


class TestArmenianTransliterationProperties:
    """Property-based tests for Armenian script transliteration."""

    @given(text=_armenian_text)
    @settings(max_examples=300)
    def test_armenian_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Armenian: {result!r}"

    @given(text=_armenian_text)
    @settings(max_examples=300)
    def test_armenian_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_armenian_text)
    @settings(max_examples=300)
    def test_armenian_nonempty(self, text: str) -> None:
        """Armenian letters always produce non-empty output."""
        result = transliterate(text, errors="ignore")
        assert len(result) > 0, f"Empty result from Armenian: {text!r}"

    @given(text=_armenian_text)
    @settings(max_examples=300)
    def test_armenian_slugify_valid(self, text: str) -> None:
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Armenian: {result!r}"


_thai_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0E01, 0x0E3B)]
        + [chr(c) for c in range(0x0E40, 0x0E4C)]
    ),
    min_size=1, max_size=20,
)
_thai_consonants = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x0E01, 0x0E2F)]),
    min_size=1, max_size=20,
)
_thai_tone_marks = st.sampled_from([chr(c) for c in range(0x0E48, 0x0E4C)])
_thai_digits = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x0E50, 0x0E5A)]),
    min_size=1, max_size=10,
)
_lao_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0E81, 0x0EAF) if chr(c).isprintable()]
        + [chr(c) for c in range(0x0EB0, 0x0EBA)]
        + [chr(c) for c in range(0x0EC0, 0x0EC5)]
    ),
    min_size=1, max_size=20,
)
_lao_consonants = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in [
            0x0E81, 0x0E82, 0x0E84, 0x0E87, 0x0E88, 0x0E8A, 0x0E8D,
            0x0E94, 0x0E95, 0x0E96, 0x0E97, 0x0E99, 0x0E9A, 0x0E9B,
            0x0E9C, 0x0E9D, 0x0E9E, 0x0E9F, 0x0EA1, 0x0EA2, 0x0EA3,
            0x0EA5, 0x0EA7, 0x0EAA, 0x0EAB, 0x0EAE,
        ]]
    ),
    min_size=1, max_size=20,
)
_lao_tone_marks = st.sampled_from([chr(c) for c in range(0x0EC8, 0x0ECC)])
_lao_digits = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x0ED0, 0x0EDA)]),
    min_size=1, max_size=10,
)
_any_tai_text = st.one_of(_thai_text, _lao_text)


class TestThaiTransliterationProperties:
    """Property-based tests for Thai script transliteration."""

    @given(text=_thai_text)
    @settings(max_examples=300)
    def test_thai_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Thai: {result!r}"

    @given(text=_thai_text)
    @settings(max_examples=300)
    def test_thai_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_thai_consonants)
    @settings(max_examples=300)
    def test_thai_consonants_nonempty(self, text: str) -> None:
        """Thai consonants always produce non-empty output."""
        result = transliterate(text, errors="ignore")
        assert len(result) > 0, f"Empty result from Thai consonants: {text!r}"

    @given(text=_thai_text)
    @settings(max_examples=300)
    def test_thai_no_double_spaces(self, text: str) -> None:
        """Thai text should not produce double spaces."""
        result = transliterate(text, errors="ignore")
        assert "  " not in result, f"Double space in: {result!r}"

    @given(consonant=_thai_consonants, tone=_thai_tone_marks)
    @settings(max_examples=200)
    def test_thai_tone_marks_stripped(self, consonant: str, tone: str) -> None:
        """Tone marks should not appear in output — consonant+tone = consonant alone."""
        with_tone = transliterate(consonant + tone, errors="ignore")
        without_tone = transliterate(consonant, errors="ignore")
        assert with_tone == without_tone, (
            f"Tone mark not stripped: {consonant+tone!r} → {with_tone!r} vs {without_tone!r}"
        )

    @given(text=_thai_digits)
    @settings(max_examples=100)
    def test_thai_digits_are_arabic(self, text: str) -> None:
        """Thai digits (๐-๙) map to ASCII digits (0-9)."""
        result = transliterate(text, errors="ignore")
        assert result.isdigit(), f"Expected digits from Thai digits: {result!r}"
        assert len(result) == len(text)

    @given(text=_thai_text)
    @settings(max_examples=300)
    def test_thai_slugify_valid(self, text: str) -> None:
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Thai: {result!r}"


class TestLaoTransliterationProperties:
    """Property-based tests for Lao script transliteration."""

    @given(text=_lao_text)
    @settings(max_examples=300)
    def test_lao_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Lao: {result!r}"

    @given(text=_lao_text)
    @settings(max_examples=300)
    def test_lao_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_lao_consonants)
    @settings(max_examples=300)
    def test_lao_consonants_nonempty(self, text: str) -> None:
        """Lao consonants always produce non-empty output."""
        result = transliterate(text, errors="ignore")
        assert len(result) > 0, f"Empty result from Lao consonants: {text!r}"

    @given(text=_lao_text)
    @settings(max_examples=300)
    def test_lao_no_double_spaces(self, text: str) -> None:
        """Lao text should not produce double spaces."""
        result = transliterate(text, errors="ignore")
        assert "  " not in result, f"Double space in: {result!r}"

    @given(consonant=_lao_consonants, tone=_lao_tone_marks)
    @settings(max_examples=200)
    def test_lao_tone_marks_stripped(self, consonant: str, tone: str) -> None:
        """Tone marks should not appear in output — consonant+tone = consonant alone."""
        with_tone = transliterate(consonant + tone, errors="ignore")
        without_tone = transliterate(consonant, errors="ignore")
        assert with_tone == without_tone, (
            f"Tone mark not stripped: {consonant+tone!r} → {with_tone!r} vs {without_tone!r}"
        )

    @given(text=_lao_digits)
    @settings(max_examples=100)
    def test_lao_digits_are_arabic(self, text: str) -> None:
        """Lao digits (໐-໙) map to ASCII digits (0-9)."""
        result = transliterate(text, errors="ignore")
        assert result.isdigit(), f"Expected digits from Lao digits: {result!r}"
        assert len(result) == len(text)

    @given(text=_lao_text)
    @settings(max_examples=300)
    def test_lao_slugify_valid(self, text: str) -> None:
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Lao: {result!r}"


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

# ---------------------------------------------------------------------------
# Ethiopic strategies
# ---------------------------------------------------------------------------

_ethiopic_text = st.text(
    alphabet=st.sampled_from(
        # Main syllabary: 7 orders per consonant in 8-wide blocks
        [chr(base + i) for base in range(0x1200, 0x1358, 8) for i in range(7)]
        # Labialized consonants (specific mapped offsets)
        + [chr(base + o) for base in [0x1248, 0x1258, 0x1288, 0x12B0, 0x12C0, 0x1308]
           for o in [0, 1, 3, 4]]
        # Digits and punctuation
        + [chr(c) for c in range(0x1361, 0x137C)]
    ),
    min_size=1, max_size=20,
)
# Use only the regular 7-order consonant blocks (skip labialized/special blocks)
_ETHIOPIC_SKIP_BASES = {
    0x1248, 0x1258, 0x1288, 0x12B0, 0x12C0, 0x1308, 0x1310, 0x1318,
    0x12A0, 0x12D0,  # glottal/pharyngeal: order 6 maps to empty
}
_ethiopic_syllables = st.text(
    alphabet=st.sampled_from(
        [chr(base + i)
         for base in range(0x1200, 0x1358, 8)
         if base not in _ETHIOPIC_SKIP_BASES
         for i in range(7)]
    ),
    min_size=1, max_size=20,
)
_ethiopic_digits = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x1369, 0x137C)]),
    min_size=1, max_size=10,
)

# ---------------------------------------------------------------------------
# Myanmar strategies
# ---------------------------------------------------------------------------

_myanmar_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x1000, 0x104C) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)
_myanmar_consonants = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x1000, 0x1022)]),
    min_size=1, max_size=20,
)
_myanmar_digits = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x1040, 0x104A)]),
    min_size=1, max_size=10,
)

# ---------------------------------------------------------------------------
# Khmer strategies
# ---------------------------------------------------------------------------

_khmer_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x1780, 0x17EA) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)
_khmer_consonants = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x1780, 0x17A3)]),
    min_size=1, max_size=20,
)
_khmer_digits = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x17E0, 0x17EA)]),
    min_size=1, max_size=10,
)

# ---------------------------------------------------------------------------
# Tibetan strategies
# ---------------------------------------------------------------------------

_tibetan_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0F00, 0x0F6B) if chr(c).isprintable()]
        + [chr(c) for c in range(0x0F71, 0x0F85) if chr(c).isprintable()]
        + [chr(c) for c in range(0x0F90, 0x0FBD) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)
_tibetan_consonants = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0F40, 0x0F6A) if chr(c).isprintable() and c != 0x0F48]
    ),
    min_size=1, max_size=20,
)
_tibetan_digits = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x0F20, 0x0F2A)]),
    min_size=1, max_size=10,
)


class TestEthiopicTransliterationProperties:
    """Property-based tests for Ethiopic (Ge'ez/Amharic) script transliteration."""

    @given(text=_ethiopic_text)
    @settings(max_examples=500)
    def test_ethiopic_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Ethiopic: {result!r}"

    @given(text=_ethiopic_text)
    @settings(max_examples=300)
    def test_ethiopic_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_ethiopic_syllables)
    @settings(max_examples=300)
    def test_ethiopic_syllables_nonempty(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert len(result) > 0, f"Empty result for Ethiopic syllables: {text!r}"

    @given(text=_ethiopic_text)
    @settings(max_examples=300)
    def test_ethiopic_no_double_spaces(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert "  " not in result, f"Double space in: {result!r}"

    @given(text=_ethiopic_digits)
    @settings(max_examples=200)
    def test_ethiopic_digits_are_arabic(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert all(c.isdigit() or c.isspace() for c in result), f"Non-digit from Ethiopic digits: {result!r}"

    @given(text=_ethiopic_text)
    @settings(max_examples=300)
    def test_ethiopic_slugify_valid(self, text: str) -> None:
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Ethiopic: {result!r}"


class TestMyanmarTransliterationProperties:
    """Property-based tests for Myanmar (Burmese) script transliteration."""

    @given(text=_myanmar_text)
    @settings(max_examples=500)
    def test_myanmar_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Myanmar: {result!r}"

    @given(text=_myanmar_text)
    @settings(max_examples=300)
    def test_myanmar_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_myanmar_consonants)
    @settings(max_examples=300)
    def test_myanmar_consonants_nonempty(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert len(result) > 0, f"Empty result for Myanmar consonants: {text!r}"

    @given(text=_myanmar_text)
    @settings(max_examples=300)
    def test_myanmar_no_double_spaces(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert "  " not in result, f"Double space in: {result!r}"

    @given(text=_myanmar_digits)
    @settings(max_examples=200)
    def test_myanmar_digits_are_arabic(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert all(c.isdigit() or c.isspace() for c in result), f"Non-digit from Myanmar digits: {result!r}"

    @given(text=_myanmar_text)
    @settings(max_examples=300)
    def test_myanmar_slugify_valid(self, text: str) -> None:
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Myanmar: {result!r}"


class TestKhmerTransliterationProperties:
    """Property-based tests for Khmer (Cambodian) script transliteration."""

    @given(text=_khmer_text)
    @settings(max_examples=500)
    def test_khmer_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Khmer: {result!r}"

    @given(text=_khmer_text)
    @settings(max_examples=300)
    def test_khmer_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_khmer_consonants)
    @settings(max_examples=300)
    def test_khmer_consonants_nonempty(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert len(result) > 0, f"Empty result for Khmer consonants: {text!r}"

    @given(text=_khmer_text)
    @settings(max_examples=300)
    def test_khmer_no_double_spaces(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert "  " not in result, f"Double space in: {result!r}"

    @given(text=_khmer_digits)
    @settings(max_examples=200)
    def test_khmer_digits_are_arabic(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert all(c.isdigit() or c.isspace() for c in result), f"Non-digit from Khmer digits: {result!r}"

    @given(text=_khmer_text)
    @settings(max_examples=300)
    def test_khmer_slugify_valid(self, text: str) -> None:
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Khmer: {result!r}"


class TestTibetanTransliterationProperties:
    """Property-based tests for Tibetan script transliteration."""

    @given(text=_tibetan_text)
    @settings(max_examples=500)
    def test_tibetan_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Tibetan: {result!r}"

    @given(text=_tibetan_text)
    @settings(max_examples=300)
    def test_tibetan_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_tibetan_consonants)
    @settings(max_examples=300)
    def test_tibetan_consonants_nonempty(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert len(result) > 0, f"Empty result for Tibetan consonants: {text!r}"

    @given(text=_tibetan_text)
    @settings(max_examples=300)
    def test_tibetan_no_double_spaces(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert "  " not in result, f"Double space in: {result!r}"

    @given(text=_tibetan_digits)
    @settings(max_examples=200)
    def test_tibetan_digits_are_arabic(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert all(c.isdigit() or c.isspace() for c in result), f"Non-digit from Tibetan digits: {result!r}"

    @given(text=_tibetan_text)
    @settings(max_examples=300)
    def test_tibetan_slugify_valid(self, text: str) -> None:
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Tibetan: {result!r}"


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

    @given(latin=_latin_text, thai=_thai_text)
    @settings(max_examples=300)
    def test_latin_thai_mixture_ascii(self, latin: str, thai: str) -> None:
        """Latin + Thai mixed text transliterates to ASCII."""
        mixed = _interleave(latin, thai)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Latin+Thai: {result!r}"

    @given(latin=_latin_text, lao=_lao_text)
    @settings(max_examples=300)
    def test_latin_lao_mixture_ascii(self, latin: str, lao: str) -> None:
        """Latin + Lao mixed text transliterates to ASCII."""
        mixed = _interleave(latin, lao)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Latin+Lao: {result!r}"

    @given(thai=_thai_text, lao=_lao_text)
    @settings(max_examples=300)
    def test_thai_lao_mixture_ascii(self, thai: str, lao: str) -> None:
        """Thai + Lao mixed text transliterates to ASCII."""
        mixed = _interleave(thai, lao)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Thai+Lao: {result!r}"

    @given(indic=_any_indic_text, thai=_thai_text)
    @settings(max_examples=300)
    def test_indic_thai_mixture_ascii(self, indic: str, thai: str) -> None:
        """Indic + Thai mixed text transliterates to ASCII."""
        mixed = _interleave(indic, thai)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Indic+Thai: {result!r}"

    @given(cjk=_cjk_text, tai=_any_tai_text)
    @settings(max_examples=300)
    def test_cjk_tai_mixture_ascii(self, cjk: str, tai: str) -> None:
        """CJK + Thai/Lao mixed text transliterates to ASCII."""
        mixed = _interleave(cjk, tai)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from CJK+Tai: {result!r}"

    @given(hebrew=_hebrew_full, tai=_any_tai_text)
    @settings(max_examples=300)
    def test_hebrew_tai_mixture_ascii(self, hebrew: str, tai: str) -> None:
        """Hebrew + Thai/Lao mixed text transliterates to ASCII."""
        mixed = _interleave(hebrew, tai)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Hebrew+Tai: {result!r}"

    @given(
        latin=_extended_latin,
        cyrillic=_cyrillic_text,
        indic=_any_indic_text,
        hebrew=_hebrew_full,
        cjk=_cjk_text,
        thai=_thai_text,
        lao=_lao_text,
    )
    @settings(max_examples=200)
    def test_seven_script_mixture_ascii(
        self, latin: str, cyrillic: str, indic: str, hebrew: str,
        cjk: str, thai: str, lao: str,
    ) -> None:
        """Seven-script mixture (Latin+Cyrillic+Indic+Hebrew+CJK+Thai+Lao) → ASCII."""
        mixed = _interleave(latin, cyrillic, indic, hebrew, cjk, thai, lao)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from 7-script mix: {result!r}"

    @given(
        latin=_extended_latin,
        cyrillic=_cyrillic_text,
        indic=_any_indic_text,
        hebrew=_hebrew_full,
        cjk=_cjk_text,
        thai=_thai_text,
        lao=_lao_text,
    )
    @settings(max_examples=200)
    def test_seven_script_mixture_idempotent(
        self, latin: str, cyrillic: str, indic: str, hebrew: str,
        cjk: str, thai: str, lao: str,
    ) -> None:
        """Seven-script mixture transliteration is idempotent."""
        mixed = _interleave(latin, cyrillic, indic, hebrew, cjk, thai, lao)
        once = transliterate(mixed, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(latin=_latin_text, ethiopic=_ethiopic_text)
    @settings(max_examples=300)
    def test_latin_ethiopic_mixture_ascii(self, latin: str, ethiopic: str) -> None:
        mixed = _interleave(latin, ethiopic)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Latin+Ethiopic: {result!r}"

    @given(latin=_latin_text, myanmar=_myanmar_text)
    @settings(max_examples=300)
    def test_latin_myanmar_mixture_ascii(self, latin: str, myanmar: str) -> None:
        mixed = _interleave(latin, myanmar)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Latin+Myanmar: {result!r}"

    @given(latin=_latin_text, khmer=_khmer_text)
    @settings(max_examples=300)
    def test_latin_khmer_mixture_ascii(self, latin: str, khmer: str) -> None:
        mixed = _interleave(latin, khmer)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Latin+Khmer: {result!r}"

    @given(latin=_latin_text, tibetan=_tibetan_text)
    @settings(max_examples=300)
    def test_latin_tibetan_mixture_ascii(self, latin: str, tibetan: str) -> None:
        mixed = _interleave(latin, tibetan)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Latin+Tibetan: {result!r}"

    @given(
        latin=_extended_latin,
        cyrillic=_cyrillic_text,
        indic=_any_indic_text,
        hebrew=_hebrew_full,
        cjk=_cjk_text,
        thai=_thai_text,
        ethiopic=_ethiopic_text,
        myanmar=_myanmar_text,
        khmer=_khmer_text,
        tibetan=_tibetan_text,
    )
    @settings(max_examples=100)
    def test_ten_script_mixture_ascii(
        self, latin: str, cyrillic: str, indic: str, hebrew: str,
        cjk: str, thai: str, ethiopic: str, myanmar: str, khmer: str,
        tibetan: str,
    ) -> None:
        """Ten-script mixture → ASCII."""
        mixed = _interleave(latin, cyrillic, indic, hebrew, cjk, thai,
                           ethiopic, myanmar, khmer, tibetan)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from 10-script mix: {result!r}"


# ---------------------------------------------------------------------------
# 13. New script strategies (v0.1.5 additions)
# ---------------------------------------------------------------------------

# ── Arabic ──
_arabic_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0621, 0x064B) if chr(c).isprintable()]
        + [chr(c) for c in range(0x0660, 0x066A)]  # Arabic-Indic digits
    ),
    min_size=1, max_size=20,
)
_arabic_consonants = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x0621, 0x063B)]),
    min_size=1, max_size=20,
)
_arabic_presentation_b = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0xFE70, 0xFF00) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)

# ── Syriac ──
_syriac_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0710, 0x0730) if chr(c).isprintable()]
        + [chr(c) for c in range(0x0730, 0x0740)]  # vowel points
    ),
    min_size=1, max_size=20,
)

# ── Thaana ──
_thaana_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x0780, 0x07B1) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)

# ── N'Ko ──
_nko_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x07C0, 0x07FA) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)

# ── Coptic ──
_coptic_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x2C80, 0x2CC2) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)

# ── Cherokee ──
_cherokee_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x13A0, 0x13F6)]
        + [chr(c) for c in range(0xAB70, 0xABC0)]
    ),
    min_size=1, max_size=20,
)

# ── Canadian Aboriginal Syllabics ──
_canadian_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x1401, 0x1677) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)

# ── Vai ──
_vai_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0xA500, 0xA62C) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)

# ── Mongolian ──
_mongolian_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x1820, 0x1879) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)

# ── Runic ──
_runic_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x16A0, 0x16F9) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)

# ── Ogham ──
_ogham_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x1681, 0x169B)]
    ),
    min_size=1, max_size=20,
)

# ── Balinese ──
_balinese_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x1B05, 0x1B5A) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)
_balinese_consonants = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0x1B13, 0x1B34)]),
    min_size=1, max_size=20,
)

# ── Javanese ──
_javanese_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0xA984, 0xA9C1) if chr(c).isprintable()]
    ),
    min_size=1, max_size=20,
)
_javanese_consonants = st.text(
    alphabet=st.sampled_from([chr(c) for c in range(0xA990, 0xA9B3)]),
    min_size=1, max_size=20,
)

# ── Tai Le ──
_tai_le_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x1950, 0x196E)]
        + [chr(c) for c in range(0x1970, 0x1975)]
    ),
    min_size=1, max_size=20,
)

# ── New Tai Lue ──
_new_tai_lue_text = st.text(
    alphabet=st.sampled_from(
        [chr(c) for c in range(0x1980, 0x19AC)]
        + [chr(c) for c in range(0x19B0, 0x19CA)]
        + [chr(c) for c in range(0x19D0, 0x19DA)]
    ),
    min_size=1, max_size=20,
)

# Composite: all new scripts
_any_new_script_text = st.one_of(
    _arabic_text, _syriac_text, _thaana_text, _nko_text, _coptic_text,
    _cherokee_text, _canadian_text, _vai_text, _mongolian_text,
    _runic_text, _ogham_text, _balinese_text, _javanese_text,
    _tai_le_text, _new_tai_lue_text,
)


# ---------------------------------------------------------------------------
# 14. Arabic transliteration properties
# ---------------------------------------------------------------------------


class TestArabicTransliterationProperties:
    """Property-based tests for Arabic script transliteration."""

    @given(text=_arabic_text)
    @settings(max_examples=500)
    def test_arabic_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Arabic: {result!r}"

    @given(text=_arabic_text)
    @settings(max_examples=300)
    def test_arabic_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_arabic_consonants)
    @settings(max_examples=300)
    def test_arabic_consonants_nonempty(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert len(result) > 0, f"Empty result from Arabic consonants: {text!r}"

    @given(text=_arabic_presentation_b)
    @settings(max_examples=300)
    def test_arabic_presentation_forms_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Arabic Presentation Forms: {result!r}"

    @given(text=_arabic_text)
    @settings(max_examples=300)
    def test_arabic_no_double_spaces(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert "  " not in result, f"Double space in: {result!r}"

    @given(text=_arabic_text)
    @settings(max_examples=300)
    def test_arabic_slugify_valid(self, text: str) -> None:
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Arabic: {result!r}"


# ---------------------------------------------------------------------------
# 15. Simple alphabet / syllabary transliteration properties
# ---------------------------------------------------------------------------


class TestSimpleAlphabetTransliterationProperties:
    """Property-based tests for simple alphabets and syllabaries.

    These scripts have 1:1 character-to-romanization mappings with no
    combining marks or abugida engine — pure TSV lookup.
    """

    @given(text=_syriac_text)
    @settings(max_examples=300)
    def test_syriac_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Syriac: {result!r}"

    @given(text=_thaana_text)
    @settings(max_examples=300)
    def test_thaana_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Thaana: {result!r}"

    @given(text=_nko_text)
    @settings(max_examples=300)
    def test_nko_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from N'Ko: {result!r}"

    @given(text=_coptic_text)
    @settings(max_examples=300)
    def test_coptic_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Coptic: {result!r}"

    @given(text=_cherokee_text)
    @settings(max_examples=300)
    def test_cherokee_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Cherokee: {result!r}"

    @given(text=_canadian_text)
    @settings(max_examples=300)
    def test_canadian_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Canadian Aboriginal: {result!r}"

    @given(text=_vai_text)
    @settings(max_examples=300)
    def test_vai_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Vai: {result!r}"

    @given(text=_mongolian_text)
    @settings(max_examples=300)
    def test_mongolian_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Mongolian: {result!r}"

    @given(text=_runic_text)
    @settings(max_examples=300)
    def test_runic_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Runic: {result!r}"

    @given(text=_ogham_text)
    @settings(max_examples=300)
    def test_ogham_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Ogham: {result!r}"

    @given(text=_tai_le_text)
    @settings(max_examples=300)
    def test_tai_le_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Tai Le: {result!r}"

    @given(text=_new_tai_lue_text)
    @settings(max_examples=300)
    def test_new_tai_lue_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from New Tai Lue: {result!r}"

    # --- Idempotency ---

    @given(text=_syriac_text)
    @settings(max_examples=200)
    def test_syriac_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_thaana_text)
    @settings(max_examples=200)
    def test_thaana_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_coptic_text)
    @settings(max_examples=200)
    def test_coptic_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_cherokee_text)
    @settings(max_examples=200)
    def test_cherokee_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_mongolian_text)
    @settings(max_examples=200)
    def test_mongolian_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_runic_text)
    @settings(max_examples=200)
    def test_runic_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_ogham_text)
    @settings(max_examples=200)
    def test_ogham_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    # --- Slugify validity ---

    @given(text=_cherokee_text)
    @settings(max_examples=200)
    def test_cherokee_slugify_valid(self, text: str) -> None:
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Cherokee: {result!r}"

    @given(text=_arabic_text)
    @settings(max_examples=200)
    def test_mongolian_slugify_valid(self, text: str) -> None:
        result = slugify(text)
        if result:
            assert SLUG_PATTERN.match(result), f"Bad slug from Mongolian: {result!r}"


# ---------------------------------------------------------------------------
# 16. Brahmic abugida properties (Balinese + Javanese)
# ---------------------------------------------------------------------------


class TestBalineseJavaneseTransliterationProperties:
    """Property-based tests for Balinese and Javanese abugida scripts.

    These use the Brahmic engine (virama strips inherent 'a',
    dependent vowels replace inherent 'a').
    """

    @given(text=_balinese_text)
    @settings(max_examples=500)
    def test_balinese_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Balinese: {result!r}"

    @given(text=_balinese_text)
    @settings(max_examples=300)
    def test_balinese_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_balinese_consonants)
    @settings(max_examples=300)
    def test_balinese_consonants_nonempty(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert len(result) > 0, f"Empty result from Balinese consonants: {text!r}"

    @given(text=_balinese_consonants)
    @settings(max_examples=300)
    def test_balinese_bare_consonants_end_with_a(self, text: str) -> None:
        """Bare Balinese consonants carry inherent 'a'."""
        result = transliterate(text, errors="ignore")
        if result:
            assert result.endswith("a"), f"Bare consonants should end with 'a': {result!r}"

    @given(text=_javanese_text)
    @settings(max_examples=500)
    def test_javanese_produces_ascii(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Javanese: {result!r}"

    @given(text=_javanese_text)
    @settings(max_examples=300)
    def test_javanese_idempotent(self, text: str) -> None:
        once = transliterate(text, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(text=_javanese_consonants)
    @settings(max_examples=300)
    def test_javanese_consonants_nonempty(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert len(result) > 0, f"Empty result from Javanese consonants: {text!r}"

    @given(text=_javanese_consonants)
    @settings(max_examples=300)
    def test_javanese_bare_consonants_end_with_a(self, text: str) -> None:
        """Bare Javanese consonants carry inherent 'a'."""
        result = transliterate(text, errors="ignore")
        if result:
            assert result.endswith("a"), f"Bare consonants should end with 'a': {result!r}"

    @given(text=_balinese_text)
    @settings(max_examples=200)
    def test_balinese_no_double_spaces(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert "  " not in result, f"Double space in: {result!r}"

    @given(text=_javanese_text)
    @settings(max_examples=200)
    def test_javanese_no_double_spaces(self, text: str) -> None:
        result = transliterate(text, errors="ignore")
        assert "  " not in result, f"Double space in: {result!r}"


# ---------------------------------------------------------------------------
# 17. Expanded multi-script mixture properties (including new scripts)
# ---------------------------------------------------------------------------


class TestExpandedMultiScriptMixtureProperties:
    """Multi-script mixture tests including the 15 newly added scripts."""

    @given(arabic=_arabic_text, latin=_latin_text)
    @settings(max_examples=300)
    def test_arabic_latin_mixture_ascii(self, arabic: str, latin: str) -> None:
        mixed = _interleave(arabic, latin)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Arabic+Latin: {result!r}"

    @given(arabic=_arabic_text, indic=_any_indic_text)
    @settings(max_examples=300)
    def test_arabic_indic_mixture_ascii(self, arabic: str, indic: str) -> None:
        mixed = _interleave(arabic, indic)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Arabic+Indic: {result!r}"

    @given(arabic=_arabic_text, cjk=_cjk_text)
    @settings(max_examples=300)
    def test_arabic_cjk_mixture_ascii(self, arabic: str, cjk: str) -> None:
        mixed = _interleave(arabic, cjk)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Arabic+CJK: {result!r}"

    @given(cherokee=_cherokee_text, latin=_latin_text)
    @settings(max_examples=300)
    def test_cherokee_latin_mixture_ascii(self, cherokee: str, latin: str) -> None:
        mixed = _interleave(cherokee, latin)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Cherokee+Latin: {result!r}"

    @given(mongolian=_mongolian_text, cyrillic=_cyrillic_text)
    @settings(max_examples=300)
    def test_mongolian_cyrillic_mixture_ascii(self, mongolian: str, cyrillic: str) -> None:
        mixed = _interleave(mongolian, cyrillic)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Mongolian+Cyrillic: {result!r}"

    @given(balinese=_balinese_text, javanese=_javanese_text)
    @settings(max_examples=300)
    def test_balinese_javanese_mixture_ascii(self, balinese: str, javanese: str) -> None:
        mixed = _interleave(balinese, javanese)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Balinese+Javanese: {result!r}"

    @given(balinese=_balinese_text, indic=_any_indic_text)
    @settings(max_examples=300)
    def test_balinese_indic_mixture_ascii(self, balinese: str, indic: str) -> None:
        """Balinese + other Brahmic scripts (boundary between Indic engines)."""
        mixed = _interleave(balinese, indic)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Balinese+Indic: {result!r}"

    @given(tai_le=_tai_le_text, thai=_thai_text)
    @settings(max_examples=300)
    def test_tai_le_thai_mixture_ascii(self, tai_le: str, thai: str) -> None:
        mixed = _interleave(tai_le, thai)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from TaiLe+Thai: {result!r}"

    @given(new_tai_lue=_new_tai_lue_text, lao=_lao_text)
    @settings(max_examples=300)
    def test_new_tai_lue_lao_mixture_ascii(self, new_tai_lue: str, lao: str) -> None:
        mixed = _interleave(new_tai_lue, lao)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from NewTaiLue+Lao: {result!r}"

    @given(syriac=_syriac_text, arabic=_arabic_text)
    @settings(max_examples=300)
    def test_syriac_arabic_mixture_ascii(self, syriac: str, arabic: str) -> None:
        """Syriac + Arabic (adjacent Unicode blocks, both RTL)."""
        mixed = _interleave(syriac, arabic)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Syriac+Arabic: {result!r}"

    @given(thaana=_thaana_text, arabic=_arabic_text)
    @settings(max_examples=300)
    def test_thaana_arabic_mixture_ascii(self, thaana: str, arabic: str) -> None:
        mixed = _interleave(thaana, arabic)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Thaana+Arabic: {result!r}"

    @given(coptic=_coptic_text, greek=st.text(
        alphabet=st.sampled_from([chr(c) for c in range(0x0391, 0x03CA)]),
        min_size=1, max_size=10,
    ))
    @settings(max_examples=300)
    def test_coptic_greek_mixture_ascii(self, coptic: str, greek: str) -> None:
        """Coptic + Greek (related scripts, adjacent blocks)."""
        mixed = _interleave(coptic, greek)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from Coptic+Greek: {result!r}"

    @given(new_script=_any_new_script_text, latin=_extended_latin)
    @settings(max_examples=300)
    def test_any_new_script_with_latin_ascii(self, new_script: str, latin: str) -> None:
        """Any new script + Extended Latin → ASCII."""
        mixed = _interleave(new_script, latin)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from new_script+Latin: {result!r}"

    @given(new_script=_any_new_script_text, cjk=_cjk_text)
    @settings(max_examples=300)
    def test_any_new_script_with_cjk_ascii(self, new_script: str, cjk: str) -> None:
        """Any new script + CJK → ASCII."""
        mixed = _interleave(new_script, cjk)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from new_script+CJK: {result!r}"

    @given(
        arabic=_arabic_text,
        cherokee=_cherokee_text,
        balinese=_balinese_text,
        mongolian=_mongolian_text,
        coptic=_coptic_text,
    )
    @settings(max_examples=200)
    def test_five_new_scripts_mixture_ascii(
        self, arabic: str, cherokee: str, balinese: str,
        mongolian: str, coptic: str,
    ) -> None:
        """Five new scripts mixed together → ASCII."""
        mixed = _interleave(arabic, cherokee, balinese, mongolian, coptic)
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from 5-new-script mix: {result!r}"

    @given(
        arabic=_arabic_text,
        cherokee=_cherokee_text,
        balinese=_balinese_text,
        mongolian=_mongolian_text,
        coptic=_coptic_text,
    )
    @settings(max_examples=200)
    def test_five_new_scripts_mixture_idempotent(
        self, arabic: str, cherokee: str, balinese: str,
        mongolian: str, coptic: str,
    ) -> None:
        """Five new scripts mixture is idempotent."""
        mixed = _interleave(arabic, cherokee, balinese, mongolian, coptic)
        once = transliterate(mixed, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice

    @given(
        latin=_extended_latin,
        cyrillic=_cyrillic_text,
        arabic=_arabic_text,
        indic=_any_indic_text,
        hebrew=_hebrew_full,
        cjk=_cjk_text,
        thai=_thai_text,
        ethiopic=_ethiopic_text,
        cherokee=_cherokee_text,
        balinese=_balinese_text,
    )
    @settings(max_examples=100)
    def test_grand_mixture_ascii(
        self, latin: str, cyrillic: str, arabic: str, indic: str,
        hebrew: str, cjk: str, thai: str, ethiopic: str,
        cherokee: str, balinese: str,
    ) -> None:
        """Grand 10-family mixture including new scripts → ASCII."""
        mixed = _interleave(
            latin, cyrillic, arabic, indic, hebrew,
            cjk, thai, ethiopic, cherokee, balinese,
        )
        result = transliterate(mixed, errors="ignore")
        assert is_ascii(result), f"Non-ASCII from grand mix: {result!r}"

    @given(
        latin=_extended_latin,
        cyrillic=_cyrillic_text,
        arabic=_arabic_text,
        indic=_any_indic_text,
        hebrew=_hebrew_full,
        cjk=_cjk_text,
        thai=_thai_text,
        ethiopic=_ethiopic_text,
        cherokee=_cherokee_text,
        balinese=_balinese_text,
    )
    @settings(max_examples=100)
    def test_grand_mixture_idempotent(
        self, latin: str, cyrillic: str, arabic: str, indic: str,
        hebrew: str, cjk: str, thai: str, ethiopic: str,
        cherokee: str, balinese: str,
    ) -> None:
        """Grand 10-family mixture is idempotent."""
        mixed = _interleave(
            latin, cyrillic, arabic, indic, hebrew,
            cjk, thai, ethiopic, cherokee, balinese,
        )
        once = transliterate(mixed, errors="ignore")
        twice = transliterate(once, errors="ignore")
        assert once == twice
