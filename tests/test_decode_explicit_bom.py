"""Finding 14 of the Lean model of the sanitizers: a BOM overrode an explicit encoding.

`decode_to_utf8` called `Encoding::decode`, whose WHATWG BOM sniff lets a byte-order mark
override the encoding it was handed. So `decode_to_utf8(b"\\xfe\\xff\\x00A", "utf-8",
strict=True)` returned `("A", False)`: bytes that are not UTF-8 decoded as UTF-16BE, and
`strict` had nothing to catch. An explicit encoding is now the encoding used; only its own
BOM is removed. Auto-detection keeps the sniff, which #710 relies on.

Non-ASCII expectations are built with `chr()`, never written literally.
"""

from __future__ import annotations

import pytest

from disarm import DisarmError, decode_to_utf8

REPLACEMENT = chr(0xFFFD)


def test_a_utf16_bom_does_not_turn_utf8_into_utf16() -> None:
    with pytest.raises(DisarmError, match="decoding as 'UTF-8'"):
        decode_to_utf8(b"\xfe\xff\x00A", "utf-8", strict=True)
    text, had_errors = decode_to_utf8(b"\xfe\xff\x00A", "utf-8")
    assert text == REPLACEMENT * 2 + "\x00A"
    assert had_errors is True


def test_a_single_byte_charset_reads_the_bom_bytes_as_characters() -> None:
    # WHATWG maps "iso-8859-1" to windows-1252; FF and FE are y-diaeresis and thorn there.
    text, had_errors = decode_to_utf8(b"\xff\xfeA\x00B\x00", "iso-8859-1")
    assert text == chr(0xFF) + chr(0xFE) + "A\x00B\x00"
    assert had_errors is False
    assert text == b"\xff\xfeA\x00B\x00".decode("cp1252")


@pytest.mark.parametrize(
    ("data", "label"),
    [
        (b"\xef\xbb\xbfA", "utf-8"),
        (b"\xff\xfeA\x00", "utf-16le"),
        (b"\xfe\xff\x00A", "utf-16be"),
    ],
)
def test_the_encodings_own_bom_is_still_removed(data: bytes, label: str) -> None:
    assert decode_to_utf8(data, label, strict=True) == ("A", False)


def test_a_byte_order_the_label_names_is_the_one_used() -> None:
    text, _ = decode_to_utf8(b"\xfe\xff\x00A", "utf-16le")
    assert text == chr(0xFFFE) + chr(0x4100)
    assert text == b"\xfe\xff\x00A".decode("utf-16-le")


@pytest.mark.parametrize("label", ["utf-16", "UTF-16", "unicode", "ucs-2"])
@pytest.mark.parametrize("data", [b"\xfe\xff\x00A", b"\xff\xfeA\x00", b"A\x00"])
def test_a_utf16_label_without_byte_order_follows_the_bom(data: bytes, label: str) -> None:
    """Python's `utf-16` codec reads these the same way."""
    assert decode_to_utf8(data, label, strict=True) == ("A", False)
    assert data.decode("utf-16") == "A"


@pytest.mark.parametrize("data", [b"\xfe\xff\x00A", b"\xff\xfeA\x00", b"\xef\xbb\xbfA"])
def test_auto_detection_still_follows_the_bom(data: bytes) -> None:
    assert decode_to_utf8(data, strict=True) == ("A", False)
