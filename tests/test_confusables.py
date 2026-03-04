"""Comprehensive tests for confusable detection and normalization.

Tests cover:
- Every Cyrillic→Latin confusable pair in the PHF table
- Every Greek→Latin confusable pair in the PHF table
- Symmetry: is_confusable() returns True for all mapped characters
- normalize_confusables() replaces all mapped characters correctly
- Edge cases: empty input, pure ASCII, non-confusable scripts
- Mixed-script detection integration
"""

import pytest

from translit import (
    normalize_confusables,
    is_confusable,
    is_mixed_script,
    detect_scripts,
)
from translit._enums import Script


# ─── Full confusable pair tables (mirrors confusables_data.rs) ──────────

CYRILLIC_TO_LATIN_PAIRS: list[tuple[str, str, str]] = [
    # (cyrillic_char, expected_latin, description)
    ("\u0430", "a", "Cyrillic а → Latin a"),
    ("\u0435", "e", "Cyrillic е → Latin e"),
    ("\u043e", "o", "Cyrillic о → Latin o"),
    ("\u0440", "p", "Cyrillic р → Latin p"),
    ("\u0441", "c", "Cyrillic с → Latin c"),
    ("\u0443", "y", "Cyrillic у → Latin y"),
    ("\u0445", "x", "Cyrillic х → Latin x"),
    ("\u0410", "A", "Cyrillic А → Latin A"),
    ("\u0412", "B", "Cyrillic В → Latin B"),
    ("\u0415", "E", "Cyrillic Е → Latin E"),
    ("\u041a", "K", "Cyrillic К → Latin K"),
    ("\u041c", "M", "Cyrillic М → Latin M"),
    ("\u041d", "H", "Cyrillic Н → Latin H"),
    ("\u041e", "O", "Cyrillic О → Latin O"),
    ("\u0420", "P", "Cyrillic Р → Latin P"),
    ("\u0421", "C", "Cyrillic С → Latin C"),
    ("\u0422", "T", "Cyrillic Т → Latin T"),
    ("\u0425", "X", "Cyrillic Х → Latin X"),
]

GREEK_TO_LATIN_PAIRS: list[tuple[str, str, str]] = [
    ("\u03bf", "o", "Greek ο → Latin o"),
    ("\u03b1", "a", "Greek α → Latin a"),
    ("\u039f", "O", "Greek Ο → Latin O"),
    ("\u0391", "A", "Greek Α → Latin A"),
    ("\u0392", "B", "Greek Β → Latin B"),
    ("\u0395", "E", "Greek Ε → Latin E"),
    ("\u0396", "Z", "Greek Ζ → Latin Z"),
    ("\u0397", "H", "Greek Η → Latin H"),
    ("\u0399", "l", "Greek Ι → Latin l"),  # TR39: visual similarity (vertical stroke)
    ("\u039a", "K", "Greek Κ → Latin K"),
    ("\u039c", "M", "Greek Μ → Latin M"),
    ("\u039d", "N", "Greek Ν → Latin N"),
    ("\u03a1", "P", "Greek Ρ → Latin P"),
    ("\u03a4", "T", "Greek Τ → Latin T"),
    ("\u03a5", "Y", "Greek Υ → Latin Y"),
    ("\u03a7", "X", "Greek Χ → Latin X"),
]

ALL_CONFUSABLE_PAIRS = CYRILLIC_TO_LATIN_PAIRS + GREEK_TO_LATIN_PAIRS


class TestNormalizeConfusables:
    """Tests for confusable normalization: every mapped char → Latin."""

    @pytest.mark.parametrize(
        "confusable,expected,desc",
        [pytest.param(c, e, d, id=d) for c, e, d in CYRILLIC_TO_LATIN_PAIRS],
    )
    def test_cyrillic_to_latin(self, confusable: str, expected: str, desc: str) -> None:
        assert normalize_confusables(confusable) == expected

    @pytest.mark.parametrize(
        "confusable,expected,desc",
        [pytest.param(c, e, d, id=d) for c, e, d in GREEK_TO_LATIN_PAIRS],
    )
    def test_greek_to_latin(self, confusable: str, expected: str, desc: str) -> None:
        assert normalize_confusables(confusable) == expected

    def test_mixed_confusable_string(self) -> None:
        """A string mixing Cyrillic and Latin confusables."""
        # "Москва" contains confusable М, о, с
        text = "\u041c\u043e\u0441\u043a\u0432\u0430"  # Москва
        result = normalize_confusables(text)
        # М→M, о→o, с→c, а→a; к and в have no Latin confusable
        assert result[0] == "M"  # М → M
        assert result[1] == "o"  # о → o
        assert result[2] == "c"  # с → c

    def test_no_confusables(self) -> None:
        assert normalize_confusables("hello") == "hello"

    def test_empty(self) -> None:
        assert normalize_confusables("") == ""

    def test_pure_ascii_passthrough(self) -> None:
        text = "The quick brown fox"
        assert normalize_confusables(text) == text

    def test_non_latin_target_returns_unchanged(self) -> None:
        """When target_script is not 'latin', no normalization occurs."""
        text = "\u0430\u0435"  # Cyrillic а е
        result = normalize_confusables(text, target_script="cyrillic")
        assert result == text


class TestIsConfusable:
    """Tests for confusable detection."""

    @pytest.mark.parametrize(
        "confusable,_expected,desc",
        [pytest.param(c, e, d, id=d) for c, e, d in ALL_CONFUSABLE_PAIRS],
    )
    def test_all_confusable_chars_detected(
        self, confusable: str, _expected: str, desc: str
    ) -> None:
        """Every character in our confusables table must be detected."""
        assert is_confusable(confusable), f"is_confusable() missed: {desc}"

    def test_not_confusable_ascii(self) -> None:
        assert not is_confusable("hello")

    def test_not_confusable_non_mapped_cyrillic(self) -> None:
        """Cyrillic characters NOT in the confusables table should not trigger."""
        # Cyrillic Ж (U+0416) has no Latin visual equivalent
        assert not is_confusable("\u0416")

    def test_not_confusable_devanagari(self) -> None:
        """Devanagari is not in the confusables table at all."""
        assert not is_confusable("हिन्दी")

    def test_empty(self) -> None:
        assert not is_confusable("")


class TestDetectScripts:
    """Script detection tests (basic — comprehensive tests in test_scripts.py)."""

    def test_latin(self) -> None:
        scripts = detect_scripts("hello")
        assert Script.LATIN in scripts

    def test_mixed(self) -> None:
        assert is_mixed_script("hello мир")

    def test_single_script(self) -> None:
        assert not is_mixed_script("hello world")

    def test_empty(self) -> None:
        assert detect_scripts("") == []


class TestConfusableTableCompleteness:
    """Meta-tests: verify our test data covers core confusable pairs."""

    def test_cyrillic_pair_count(self) -> None:
        """Verify we test 18 core Cyrillic→Latin pairs."""
        assert len(CYRILLIC_TO_LATIN_PAIRS) == 18

    def test_greek_pair_count(self) -> None:
        """Verify we test 16 core Greek→Latin pairs."""
        assert len(GREEK_TO_LATIN_PAIRS) == 16

    def test_no_duplicate_confusable_sources(self) -> None:
        """No source character should appear twice in the test tables."""
        sources = [pair[0] for pair in ALL_CONFUSABLE_PAIRS]
        assert len(sources) == len(set(sources)), "Duplicate confusable source chars"

    def test_all_targets_are_ascii(self) -> None:
        """All confusable targets should be ASCII characters."""
        for source, target, desc in ALL_CONFUSABLE_PAIRS:
            assert target.isascii(), f"Non-ASCII target in {desc}: {target!r}"

    def test_table_has_many_entries(self) -> None:
        """The TR39-generated table should have many more than the test pairs."""
        # The full table has ~1900 entries; verify a sampling of non-Cyrillic,
        # non-Greek scripts are also covered.
        assert is_confusable("\uff21")  # Fullwidth A
        assert is_confusable("\u2160")  # Roman numeral Ⅰ
