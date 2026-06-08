"""Type stubs for translit._types."""

from __future__ import annotations

import enum
from typing import Literal, Protocol, runtime_checkable

ErrorMode = Literal["replace", "ignore", "preserve"]
TransliterateErrorMode = Literal["replace", "ignore", "preserve", "strict"]
Platform = Literal["universal", "windows", "posix"]
NormalizationForm = Literal["NFC", "NFD", "NFKC", "NFKD"]

class NF(enum.Enum):
    """Unicode normalization form constants."""

    C = "NFC"
    D = "NFD"
    KC = "NFKC"
    KD = "NFKD"

@runtime_checkable
class EmojiProvider(Protocol):
    """Protocol for custom emoji name providers."""

    def lookup(self, sequence: list[int]) -> str | None: ...
