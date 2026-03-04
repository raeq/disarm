"""Regression tests for sanitize_filename correctness.

These tests pin exact expected outputs. If sanitize_filename behavior
changes, these tests MUST be updated intentionally.
"""

from __future__ import annotations

from translit import sanitize_filename


class TestWindowsReservedNames:
    """Windows reserved names must be prefixed AND preserve their extension."""

    def test_con_txt(self) -> None:
        assert sanitize_filename("CON.txt") == "_CON.txt"

    def test_nul_txt(self) -> None:
        assert sanitize_filename("NUL.txt") == "_NUL.txt"

    def test_lpt1_pdf(self) -> None:
        assert sanitize_filename("LPT1.pdf") == "_LPT1.pdf"

    def test_aux_no_extension(self) -> None:
        assert sanitize_filename("AUX") == "_AUX"

    def test_con_case_insensitive(self) -> None:
        assert sanitize_filename("con.txt") == "_con.txt"

    def test_prn_mixed_case(self) -> None:
        assert sanitize_filename("Prn.doc") == "_Prn.doc"

    def test_com9_extension(self) -> None:
        assert sanitize_filename("COM9.log") == "_COM9.log"

    def test_reserved_name_posix_no_prefix(self) -> None:
        """POSIX doesn't have reserved names."""
        assert sanitize_filename("CON.txt", platform="posix") == "CON.txt"


class TestExtensionPreservingTruncation:
    """max_length truncation must preserve extension when preserve_extension=True."""

    def test_truncate_preserves_pdf(self) -> None:
        result = sanitize_filename("a" * 300 + ".pdf", max_length=20)
        assert result.endswith(".pdf")
        assert len(result) <= 20

    def test_truncate_preserves_txt(self) -> None:
        result = sanitize_filename("long_filename_here.txt", max_length=12)
        assert result.endswith(".txt")
        assert len(result) <= 12

    def test_truncate_no_extension(self) -> None:
        result = sanitize_filename("a" * 300, max_length=20)
        assert len(result) == 20

    def test_truncate_extension_longer_than_max(self) -> None:
        """If extension alone exceeds max_length, truncate the whole thing."""
        result = sanitize_filename("x.toolongext", max_length=5)
        assert len(result) <= 5

    def test_no_truncation_when_within_limit(self) -> None:
        assert sanitize_filename("short.txt", max_length=255) == "short.txt"

    def test_preserve_extension_false(self) -> None:
        result = sanitize_filename("name.pdf", max_length=5, preserve_extension=False)
        assert len(result) <= 5


class TestPathTraversal:
    """Path traversal sequences must be neutralized."""

    def test_simple_parent_traversal(self) -> None:
        result = sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert result  # should not be empty

    def test_triple_parent_traversal(self) -> None:
        result = sanitize_filename("../../../etc/passwd")
        assert ".." not in result

    def test_embedded_traversal(self) -> None:
        result = sanitize_filename("foo/../bar.txt")
        assert ".." not in result

    def test_backslash_traversal(self) -> None:
        result = sanitize_filename("..\\..\\windows\\system32")
        assert ".." not in result

    def test_single_dot_preserved(self) -> None:
        """Single dots in filenames are fine (they're part of extensions)."""
        result = sanitize_filename("file.name.txt")
        assert "." in result


class TestConsecutiveIllegalChars:
    """Consecutive illegal characters collapse to a single separator."""

    def test_adjacent_illegal(self) -> None:
        # <>: are all illegal — should produce single separator
        assert sanitize_filename("a<>:b.txt") == "a_b.txt"

    def test_many_illegal(self) -> None:
        assert sanitize_filename("a***b.txt") == "a_b.txt"

    def test_mixed_illegal_and_whitespace(self) -> None:
        result = sanitize_filename("a : b.txt")
        assert result == "a_b.txt"


class TestNFCNormalization:
    """NFC normalization ensures cross-platform consistency."""

    def test_nfd_and_nfc_same_output(self) -> None:
        """NFD input (macOS APFS style) and NFC input produce same result."""
        nfd = sanitize_filename("caf\u0065\u0301.txt")
        nfc = sanitize_filename("caf\u00e9.txt")
        assert nfd == nfc

    def test_german_umlaut_nfd_nfc(self) -> None:
        nfd = sanitize_filename("Mu\u0308nchen.txt")
        nfc = sanitize_filename("M\u00fcnchen.txt")
        assert nfd == nfc
