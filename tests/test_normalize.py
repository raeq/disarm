"""Tests for disarm.normalize and is_normalized."""

import pytest

from disarm import is_normalized, normalize


class TestNormalize:
    """Unicode normalization tests."""

    def test_nfc(self) -> None:
        # e + combining accent → é
        text = "caf\u0065\u0301"
        result = normalize(text, form="NFC")
        assert result == "caf\u00e9"

    def test_nfd(self) -> None:
        text = "caf\u00e9"
        result = normalize(text, form="NFD")
        assert "\u0301" in result

    def test_nfkc(self) -> None:
        # ﬁ ligature → fi
        result = normalize("\ufb01", form="NFKC")
        assert result == "fi"

    def test_nfkd(self) -> None:
        result = normalize("\ufb01", form="NFKD")
        assert result == "fi"

    def test_empty(self) -> None:
        assert normalize("", form="NFC") == ""

    def test_ascii_passthrough(self) -> None:
        assert normalize("hello", form="NFC") == "hello"

    def test_invalid_form(self) -> None:
        with pytest.raises(ValueError):  # normalize() delegates to CPython unicodedata
            normalize("café", form="INVALID")  # type: ignore[arg-type]


class TestIsNormalized:
    """Tests for normalization checking."""

    def test_nfc_normalized(self) -> None:
        assert is_normalized("caf\u00e9", form="NFC")

    def test_nfc_not_normalized(self) -> None:
        assert not is_normalized("caf\u0065\u0301", form="NFC")

    def test_ascii_always_normalized(self) -> None:
        assert is_normalized("hello", form="NFC")
        assert is_normalized("hello", form="NFD")
        assert is_normalized("hello", form="NFKC")
        assert is_normalized("hello", form="NFKD")
