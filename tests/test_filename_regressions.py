"""Regression tests for sanitize_filename correctness.

These tests pin exact expected outputs. If sanitize_filename behavior
changes, these tests MUST be updated intentionally.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from disarm import sanitize_filename


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


class TestReservedNamePreserveExtension:
    """Regression: reserved-name code paths must respect preserve_extension.

    Bug: both reserved-name paths in _sanitize_filename called
    apply_max_length(_, None, _, false), unconditionally disabling
    extension preservation regardless of the preserve_extension parameter.
    """

    # ── Direct reserved name hits ──

    def test_nul_txt_tight_max_length(self) -> None:
        """NUL.txt with preserve_extension=True and tight max_length."""
        result = sanitize_filename("NUL.txt", preserve_extension=True, max_length=7)
        assert result.endswith(".txt"), f"extension lost: {result}"
        assert len(result) <= 7, f"exceeds max_length: {result}"

    def test_con_dat_tight_max_length(self) -> None:
        result = sanitize_filename("CON.dat", preserve_extension=True, max_length=8)
        assert result.endswith(".dat"), f"extension lost: {result}"
        assert len(result) <= 8
        assert result.startswith("_")

    def test_aux_py_exact_fit(self) -> None:
        """_AUX.py is exactly 7 bytes — should fit in max_length=7."""
        result = sanitize_filename("AUX.py", preserve_extension=True, max_length=7)
        assert result == "_AUX.py"

    def test_prn_txt_very_tight(self) -> None:
        """max_length=5 with .txt (4 bytes) leaves 1 byte for stem."""
        result = sanitize_filename("PRN.txt", preserve_extension=True, max_length=5)
        assert result.endswith(".txt"), f"extension lost: {result}"
        assert len(result) <= 5

    def test_lpt1_log_preserve(self) -> None:
        result = sanitize_filename("LPT1.log", preserve_extension=True, max_length=9)
        assert result.endswith(".log"), f"extension lost: {result}"
        assert result.startswith("_")

    def test_com9_csv_preserve(self) -> None:
        result = sanitize_filename("COM9.csv", preserve_extension=True, max_length=9)
        assert result.endswith(".csv"), f"extension lost: {result}"
        assert result.startswith("_")

    # ── Post-truncation reserved name hits ──

    def test_nultra_txt_post_truncation(self) -> None:
        """NULtra.txt truncated so stem becomes NUL (reserved)."""
        result = sanitize_filename("NULtra.txt", preserve_extension=True, max_length=7)
        assert result.endswith(".txt"), f"extension lost: {result}"
        assert len(result) <= 7

    def test_contest_pdf_post_truncation(self) -> None:
        """CONtest.pdf truncated so stem becomes CON (reserved)."""
        result = sanitize_filename("CONtest.pdf", preserve_extension=True, max_length=8)
        assert result.endswith(".pdf"), f"extension lost: {result}"
        assert len(result) <= 8

    def test_auxiliary_doc_post_truncation(self) -> None:
        """AUXiliary.doc truncated so stem becomes AUX (reserved)."""
        result = sanitize_filename("AUXiliary.doc", preserve_extension=True, max_length=8)
        assert result.endswith(".doc"), f"extension lost: {result}"
        assert len(result) <= 8

    # ── All reserved names with extension ──

    RESERVED_NAMES = [
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM0",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT0",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    ]

    @pytest.mark.parametrize("name", RESERVED_NAMES)
    def test_all_reserved_preserve_ext(self, name: str) -> None:
        """Every reserved name with .txt must preserve the extension."""
        result = sanitize_filename(f"{name}.txt", preserve_extension=True)
        assert result.endswith(".txt"), f"extension lost for {name}: {result}"
        assert result.startswith("_"), f"missing prefix for {name}: {result}"

    @pytest.mark.parametrize("name", RESERVED_NAMES)
    def test_all_reserved_tight_preserve_ext(self, name: str) -> None:
        """Every reserved name with tight max_length must preserve extension."""
        # max_length = len("_") + len(name) + len(".tx") — tight but should keep .tx
        ml = 1 + len(name) + 3
        result = sanitize_filename(f"{name}.tx", preserve_extension=True, max_length=ml)
        assert result.endswith(".tx"), f"extension lost for {name} (max_length={ml}): {result}"
        assert len(result) <= ml

    # ── Contrast: preserve_extension=False still truncates freely ──

    def test_nul_preserve_false_no_guarantee(self) -> None:
        result = sanitize_filename("NUL.txt", preserve_extension=False, max_length=5)
        assert len(result) <= 5
        # Extension may or may not survive — that's correct

    # ── POSIX: no reserved name handling ──

    def test_posix_nul_no_prefix(self) -> None:
        result = sanitize_filename(
            "NUL.txt", platform="posix", preserve_extension=True, max_length=7
        )
        assert result.endswith(".txt"), f"extension lost: {result}"
        assert not result.startswith("_"), f"unexpected prefix on posix: {result}"


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


class TestUtf8SafeTruncation:
    """Regression: fix #1 — char_boundary_floor prevents UTF-8 corruption on truncation.

    Each test exercises a distinct truncation code path in _sanitize_filename.
    The invariant in every case: len(result) <= max_length and result is valid text.
    """

    def test_plain_stem_truncation_bounded(self) -> None:
        """Long ASCII stem truncated — output must not exceed max_length."""
        result = sanitize_filename("a" * 300 + ".txt", max_length=10)
        assert len(result) <= 10
        assert result.endswith(".txt")

    def test_reserved_name_truncation_bounded(self) -> None:
        """Reserved-name prefix (_NUL) + truncation must stay within max_length."""
        result = sanitize_filename("NUL.txt", max_length=4)
        assert len(result) <= 4

    def test_extension_exceeds_max_truncates_whole(self) -> None:
        """When extension alone exceeds max_length, the whole string is truncated."""
        result = sanitize_filename("name.verylongext", max_length=3)
        assert len(result) <= 3

    def test_post_truncation_reserved_check_bounded(self) -> None:
        """Truncation that produces a reserved name adds '_'; result stays <= max_length.

        'NULtra.txt' truncated to 3 chars becomes 'NUL' (reserved).
        The post-truncation check prefixes '_', then re-truncates to max_length.
        """
        result = sanitize_filename("NULtra.txt", max_length=3, preserve_extension=False)
        assert len(result) <= 3

    def test_stem_truncation_with_extension_bounded(self) -> None:
        """Stem budget = max_length - ext_len; combined result must be <= max_length."""
        result = sanitize_filename("a" * 100 + ".pdf", max_length=15)
        assert len(result) <= 15
        assert result.endswith(".pdf")

    def test_no_preserve_extension_truncation_bounded(self) -> None:
        """When preserve_extension=False, truncation must not exceed max_length."""
        result = sanitize_filename("a" * 100 + ".pdf", max_length=8, preserve_extension=False)
        assert len(result) <= 8


# ── Property-based invariant tests ─────────────────────────────────────
# These tests use Hypothesis to verify structural invariants that must hold
# for ALL inputs, catching any code path that silently drops extensions,
# exceeds max_length, or produces reserved filenames.

WINDOWS_RESERVED = [
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM0",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT0",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
    "CLOCK$",
    "KEYBD$",
    "SCREEN$",
]


class TestFilenameInvariants:
    """Property-based tests for sanitize_filename structural invariants.

    These are designed to catch the *class* of errors where a code path
    bypasses a parameter (preserve_extension, max_length, platform) by
    hardcoding a default instead of forwarding the caller's value.
    """

    # Only the property-based tests in this class are hypothesis-gated; the
    # deterministic regression tests above must run in CI (CI uses
    # `-m "not hypothesis"`). A module-level mark previously excluded all of them.
    pytestmark = pytest.mark.hypothesis

    @given(
        stem=st.from_regex(r"[a-zA-Z0-9]{1,20}", fullmatch=True),
        ext=st.from_regex(r"[a-z]{1,5}", fullmatch=True),
        max_length=st.integers(min_value=5, max_value=50),
    )
    @settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
    def test_preserve_extension_always_keeps_ext(
        self, stem: str, ext: str, max_length: int
    ) -> None:
        """When preserve_extension=True, the extension must survive if it fits."""
        filename = f"{stem}.{ext}"
        dot_ext = f".{ext}"
        result = sanitize_filename(filename, preserve_extension=True, max_length=max_length)
        assert len(result) <= max_length, f"exceeds max_length {max_length}: {result}"
        if len(dot_ext) < max_length:
            assert result.endswith(dot_ext), (
                f"extension '{dot_ext}' lost from '{filename}' "
                f"(max_length={max_length}): got '{result}'"
            )

    @given(
        stem=st.from_regex(r"[a-zA-Z0-9]{1,30}", fullmatch=True),
        ext=st.from_regex(r"[a-z]{1,5}", fullmatch=True),
        max_length=st.integers(min_value=1, max_value=50),
        preserve_extension=st.booleans(),
    )
    @settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
    def test_max_length_always_respected(
        self, stem: str, ext: str, max_length: int, preserve_extension: bool
    ) -> None:
        """max_length must be respected regardless of preserve_extension."""
        filename = f"{stem}.{ext}"
        result = sanitize_filename(
            filename,
            preserve_extension=preserve_extension,
            max_length=max_length,
        )
        assert len(result) <= max_length, (
            f"exceeds max_length {max_length} (preserve_extension={preserve_extension}): '{result}'"
        )

    @given(
        name=st.sampled_from(WINDOWS_RESERVED),
        ext=st.from_regex(r"[a-z]{1,4}", fullmatch=True),
        max_length=st.integers(min_value=6, max_value=50),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_reserved_name_preserve_ext(self, name: str, ext: str, max_length: int) -> None:
        """Reserved names with preserve_extension=True must keep the extension."""
        dot_ext = f".{ext}"
        filename = f"{name}{dot_ext}"
        result = sanitize_filename(filename, preserve_extension=True, max_length=max_length)
        assert len(result) <= max_length, f"exceeds max_length {max_length}: {result}"
        if len(dot_ext) < max_length:
            assert result.endswith(dot_ext), (
                f"extension '{dot_ext}' lost for reserved name '{name}': got '{result}'"
            )

    @given(
        stem=st.from_regex(r"[A-Za-z]{1,15}", fullmatch=True),
        ext=st.from_regex(r"[a-z]{1,4}", fullmatch=True),
        max_length=st.integers(min_value=1, max_value=30),
        preserve_extension=st.booleans(),
    )
    @settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
    def test_never_produces_bare_reserved_stem(
        self, stem: str, ext: str, max_length: int, preserve_extension: bool
    ) -> None:
        """No code path should produce a bare Windows reserved name as the stem."""
        filename = f"{stem}.{ext}"
        result = sanitize_filename(
            filename,
            preserve_extension=preserve_extension,
            max_length=max_length,
        )
        if result and "." in result:
            result_stem = result.rsplit(".", 1)[0]
        else:
            result_stem = result
        if result_stem:
            upper_stem = result_stem.upper()
            assert upper_stem not in WINDOWS_RESERVED, (
                f"produced bare reserved stem '{result_stem}' from '{filename}' "
                f"(max_length={max_length}, preserve_extension={preserve_extension})"
            )

    @given(
        name=st.sampled_from(WINDOWS_RESERVED),
        ext=st.from_regex(r"[a-z]{1,4}", fullmatch=True),
        max_length=st.integers(min_value=6, max_value=50),
        preserve_extension=st.booleans(),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_reserved_name_max_length_with_both_preserve_modes(
        self, name: str, ext: str, max_length: int, preserve_extension: bool
    ) -> None:
        """Reserved names must respect max_length with both preserve_extension modes."""
        filename = f"{name}.{ext}"
        result = sanitize_filename(
            filename,
            preserve_extension=preserve_extension,
            max_length=max_length,
        )
        assert len(result) <= max_length, (
            f"exceeds max_length {max_length} for reserved '{name}' "
            f"(preserve_extension={preserve_extension}): '{result}'"
        )


class TestNeverEmptyNeverDirectoryReference:
    """#485/#487: the public entrypoint never returns an empty name, a leading/trailing
    dot, or a bare ``.`` / ``..`` directory reference (downstream write-target footguns)."""

    @pytest.mark.parametrize(
        "text",
        ["", "   ", "/////", "\x00\x00", ".", "..", "_·", "_·", "_।"],
    )
    def test_strips_to_fallback_underscore(self, text: str) -> None:
        # every input that reduces to nothing — or to a directory reference — yields "_"
        assert sanitize_filename(text) == "_"

    def test_no_empty_for_any_all_stripped_input(self) -> None:
        for text in ["", "   ", "\x01\x02", "​​"]:
            assert sanitize_filename(text) != ""

    def test_no_leading_dot_dotfile(self) -> None:
        assert not sanitize_filename("../../etc/passwd").startswith(".")
        assert not sanitize_filename("\\\\.\\PhysicalDrive0").startswith(".")
        assert sanitize_filename(".bashrc") == "bashrc"

    def test_no_trailing_dot_or_space(self) -> None:
        assert sanitize_filename("report...") == "report"
        assert sanitize_filename("CON.") == "_CON"
        assert not sanitize_filename("report ").endswith(" ")

    def test_separator_then_dotlike_is_not_directory_reference(self) -> None:
        # #487 headline: "_" + MIDDLE DOT transliterated to "_." reduced to a bare "."
        for cp in (0x00B7, 0x02D9, 0x0387, 0x0589, 0x05C3, 0x0964):
            out = sanitize_filename("_" + chr(cp))
            assert out not in (".", ".."), f"directory reference from U+{cp:04X}: {out!r}"
            assert sanitize_filename(out) == out, f"non-idempotent on U+{cp:04X}"
