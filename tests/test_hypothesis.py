"""Property-based tests for translit using Hypothesis.

These tests verify fundamental invariants of Unicode text processing
operations that hold across the entire input space, not just selected
examples.
"""

from __future__ import annotations

import re

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from translit import (
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
    UniqueSlugifier,
)

from conftest import unicode_text, nf_forms


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
        assert is_ascii(result), (
            f"Non-ASCII in result: {[c for c in result if ord(c) > 127]!r}"
        )

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
            assert len(set(non_empty)) == len(non_empty), (
                f"Duplicate slugs: {non_empty}"
            )
