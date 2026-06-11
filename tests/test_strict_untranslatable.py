"""#184: native positional/strict reporting.

`find_untranslatable(text)` returns every character with no transliteration as
`(char, byte_offset)`; `transliterate(errors="strict")` raises on the first such
character. The unidecode compat shim's strict mode is retired onto this.
"""

from __future__ import annotations

import pytest

import disarm
from disarm import DisarmError, InvalidArgumentError, find_untranslatable, transliterate


class TestFindUntranslatable:
    def test_ascii_is_empty(self) -> None:
        assert find_untranslatable("hello world 123") == []

    def test_fully_translatable_is_empty(self) -> None:
        # café, Москва, 北京 all transliterate fully.
        assert find_untranslatable("café Москва 北京") == []

    def test_reports_char_and_byte_offset(self) -> None:
        # 'a' (1 byte) then the emoji at byte offset 1.
        assert find_untranslatable("a\U0001f600b") == [("😀", 1)]

    def test_reports_all_in_order(self) -> None:
        result = find_untranslatable("\U0001f600x\U0001f680")
        assert result == [("😀", 0), ("🚀", 5)]

    def test_rejects_non_str(self) -> None:
        with pytest.raises(TypeError):
            find_untranslatable(123)  # type: ignore[arg-type]


class TestStrictMode:
    def test_all_translatable_returns_output(self) -> None:
        assert transliterate("café", errors="strict") == "cafe"

    def test_raises_on_first_untranslatable(self) -> None:
        with pytest.raises(DisarmError) as exc:
            transliterate("a\U0001f600b", errors="strict")
        msg = str(exc.value)
        assert "😀" in msg
        assert "byte offset 1" in msg

    def test_strict_on_batch(self) -> None:
        # Raises on the first item that has an untranslatable char.
        with pytest.raises(DisarmError):
            transliterate(["ok", "a\U0001f600b"], errors="strict")

    def test_strict_batch_all_translatable(self) -> None:
        assert transliterate(["café", "naïve"], errors="strict") == ["cafe", "naive"]

    def test_strict_rejected_with_context(self) -> None:
        with pytest.raises(InvalidArgumentError, match="strict"):
            transliterate("x", errors="strict", context=True)

    def test_strict_rejected_with_target(self) -> None:
        # errors is forward-only with target=...
        with pytest.raises(InvalidArgumentError, match="forward-only"):
            transliterate("Moskva", target="ru", errors="strict")


class TestUnidecodeStrictRetirement:
    """The unidecode compat shim raises ValueError with a *character* index,
    now backed by find_untranslatable instead of the O(n) re-transliterate hack."""

    def test_strict_success(self) -> None:
        assert disarm.unidecode("café", errors="strict") == "cafe"

    def test_strict_raises_value_error_with_char_index(self) -> None:
        with pytest.raises(ValueError, match=r"at index 1"):
            disarm.unidecode("a\U0001f600b", errors="strict")
