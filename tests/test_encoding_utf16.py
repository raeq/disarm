"""#710 — `detect_encoding` could not return a UTF-16 label for any input.

chardetng does not guess UTF-16, and nothing looked for a BOM before it ran. So
`detect_encoding` reported `KOI8-U` at confidence 0.95 for UTF-16LE-with-BOM while
`decode_to_utf8` read the *same bytes* correctly. The disagreement was silent, and a
caller following `detect_encoding`'s own advice — "prefer explicit encoding metadata over
detection" — carried the label to another decoder and got mojibake.

The existing suite fed `utf16le_bom` and `utf16be_bom` in, but only through
`_assert_invariants`, which checks no-panic, a valid `str`, confidence in range and no
surrogate leak. It never asserted what was detected, so both rows were green.
"""

from __future__ import annotations

import random

import pytest

from disarm import decode_to_utf8, detect_encoding

# Written as an escape, never as a literal: an invisible character pasted into a test is
# invisible in the diff and in the editor too, which is the whole reason
# `tests/test_readme_invisible_characters.py` exists for README.md. `test_this_file_has_no
# _literal_invisible_character` below holds the line for this file.
BOM = "\ufeff"

# Every row from the issue's table, with what `detect_encoding` used to say.
BOM_ROWS = [
    ("héllo wörld".encode("utf-16-le"), "UTF-16LE", "was KOI8-U"),
    (b"\xfe\xff" + "héllo wörld".encode("utf-16-be"), "UTF-16BE", "was windows-1252"),
    ("Привет".encode("utf-16"), "UTF-16LE", "was windows-1254"),
    (b"\xef\xbb\xbf" + "héllo".encode(), "UTF-8", "already UTF-8"),
]
# `"...".encode("utf-16-le")` has no BOM; `encode("utf-16")` adds a LE one.
BOM_ROWS[0] = ("héllo wörld".encode("utf-16"), "UTF-16LE", "was KOI8-U")


@pytest.mark.parametrize(
    ("data", "want", "before"), BOM_ROWS, ids=[r[1] + "/" + r[2] for r in BOM_ROWS]
)
def test_a_bom_decides_the_label(data: bytes, want: str, before: str) -> None:
    label, confidence = detect_encoding(data)
    assert label == want
    assert confidence == 0.95


@pytest.mark.parametrize(("data", "_want", "_before"), BOM_ROWS, ids=[r[1] for r in BOM_ROWS])
def test_the_label_round_trips_against_the_truth(data: bytes, _want: str, _before: str) -> None:
    """§5: decode with the label `detect_encoding` returned and compare with the truth.

    Python keeps a leading U+FEFF where encoding_rs strips it (WHATWG), so the comparison
    strips it — that convention difference is not what this test is about.
    """
    label, _ = detect_encoding(data)
    via_label = data.decode(label).lstrip(BOM)
    via_disarm, had_errors = decode_to_utf8(data)
    assert via_label == via_disarm
    assert not had_errors


def test_the_two_functions_agree_by_construction() -> None:
    """The disagreement was the defect, not the label on its own."""
    for data, _, _ in BOM_ROWS:
        label, _ = detect_encoding(data)
        decoded, _ = decode_to_utf8(data)
        assert data.decode(label).lstrip(BOM) == decoded


# ── BOM-less UTF-16 over ASCII-range text (§3) ───────────────────────────────

ASCII_RANGE = [
    "héllo wörld",
    "hello world",
    "The quick brown fox jumps over the lazy dog.",
    "Ćwiczenie żółw",  # mostly ASCII: above the half-NUL floor
    "1234567890",
]


@pytest.mark.parametrize("text", ASCII_RANGE)
@pytest.mark.parametrize("endian", ["utf-16-le", "utf-16-be"])
def test_bomless_utf16_over_ascii_range_is_detected(text: str, endian: str) -> None:
    data = text.encode(endian)
    assert b"\xff\xfe" != data[:2] and b"\xfe\xff" != data[:2]
    label, _ = detect_encoding(data)
    assert label.upper().replace("-", "") == endian.replace("-", "").upper()
    decoded, _ = decode_to_utf8(data, encoding=label)
    assert decoded == text


def test_the_decode_was_the_real_harm() -> None:
    """`decode_to_utf8` returned a NUL after every character, with `had_errors=False`.

    `strict=True` did not catch it either — windows-1252 maps every byte to something, so
    nothing was lossy by the WHATWG definition the flag reports.
    """
    data = "héllo wörld".encode("utf-16-le")
    decoded, had_errors = decode_to_utf8(data, strict=True)
    assert decoded == "héllo wörld"
    assert not had_errors
    assert "\x00" not in decoded


# ── the documented limit (§3) ────────────────────────────────────────────────

OUTSIDE_ASCII = ["Привет", "日本語テスト", "Ελληνικά", "العربية"]


@pytest.mark.parametrize("text", OUTSIDE_ASCII)
@pytest.mark.parametrize("endian", ["utf-16-le", "utf-16-be"])
def test_bomless_utf16_outside_the_ascii_range_is_not_detected(text: str, endian: str) -> None:
    """Asserted as a known negative, not left to be discovered.

    In UTF-16LE Cyrillic the high byte is `04`, not `00`, so there is no NUL and no
    deterministic signal. Guessing from script frequency is the ambiguous-bytes case
    THREAT_MODEL.md scopes out. Documented in `docs/limitations.md`.
    """
    data = text.encode(endian)
    assert b"\x00" not in data, "this test is only about the no-NUL case"
    assert not detect_encoding(data)[0].upper().startswith("UTF-16")


# ── no false positives ───────────────────────────────────────────────────────

SINGLE_BYTE = [
    ("héllo wörld", "windows-1252"),
    ("héllo wörld", "iso-8859-1"),
    ("héllo wörld", "iso-8859-15"),
    ("Привет мир", "windows-1251"),
    ("Привет мир", "koi8-r"),
    ("Ćwiczenie żółw", "iso-8859-2"),
    ("Türkçe İstanbul", "cp1254"),
    ("日本語テスト", "shift_jis"),
    ("日本語テスト", "euc-jp"),
    ("한국어 텍스트", "euc-kr"),
    ("hello world", "utf-8"),
    ("日本語テスト", "utf-8"),
]


@pytest.mark.parametrize(
    ("text", "enc"), SINGLE_BYTE, ids=[f"{r[1]}:{r[0][:8]}" for r in SINGLE_BYTE]
)
def test_real_text_is_never_labelled_utf16(text: str, enc: str) -> None:
    """Text in a single-byte encoding contains no NUL — it is a C0 control."""
    assert not detect_encoding(text.encode(enc))[0].upper().startswith("UTF-16")


def test_no_false_positive_over_random_nul_free_bytes() -> None:
    """The clean-side-must-be-zero rule is what makes the half-NUL floor safe."""
    rng = random.Random(710)
    for _ in range(4000):
        data = bytes(rng.randrange(1, 256) for _ in range(rng.randrange(0, 40)))
        assert not detect_encoding(data)[0].upper().startswith("UTF-16")


@pytest.mark.parametrize("n", [0, 1, 2, 3, 5, 7])
def test_short_and_odd_inputs_are_left_alone(n: int) -> None:
    """An odd length is not UTF-16, and under two code units there is no pattern."""
    data = b"\x00" * n
    label, _ = detect_encoding(data)
    if n < 4 or n % 2:
        assert not label.upper().startswith("UTF-16")


# ── the two review findings, pinned ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("units_with_nul", "total_units", "detected"),
    [
        (4, 4, True),  # 100% — plainly UTF-16
        (3, 4, True),  # 75%
        (2, 4, True),  # exactly the floor
        (1, 4, False),  # below it
        (3, 8, False),  # 37.5%
    ],
)
def test_the_nul_fraction_floor_is_where_the_doc_says(
    units_with_nul: int, total_units: int, detected: bool
) -> None:
    """The threshold is asserted, not described.

    The rustdoc said "90%" after the constant had moved to 0.5 — a comment and a constant
    disagreeing with nothing between them to fail. These cases straddle the real boundary,
    so moving the constant without moving the prose now breaks a test.

    Non-NUL units use `\u0400`-range bytes, which is what UTF-16LE Cyrillic actually looks
    like: high byte `04`, not `00`.
    """
    data = b"".join(b"a\x00" if i < units_with_nul else b"\x1f\x04" for i in range(total_units))
    assert detect_encoding(data)[0].upper().startswith("UTF-16") is detected


def test_this_file_has_no_literal_invisible_character() -> None:
    """An invisible pasted into a test is invisible in the diff and the editor too.

    `tests/test_readme_invisible_characters.py` guards README.md for this reason, and #794
    made the same argument for a test file that had pasted `U+202E` into its own sample.
    A test about a BOM is the easiest place to reintroduce one, so it is checked here.
    """
    import unicodedata
    from pathlib import Path

    source = Path(__file__).read_text(encoding="utf-8")
    offenders = [
        (i, f"U+{ord(c):04X}", unicodedata.name(c, "?"))
        for i, c in enumerate(source)
        if unicodedata.category(c) == "Cf"
        or (unicodedata.category(c) == "Cc" and c not in "\n\r\t")
    ]
    assert not offenders, f"write these as escapes: {offenders}"


def test_the_invisible_guard_can_fail() -> None:
    """The guard above passes trivially if its predicate is wrong; prove it can fire."""
    import unicodedata

    sample = "a" + chr(0xFEFF) + "b"
    assert any(unicodedata.category(c) == "Cf" for c in sample)
