"""Type aliases and protocols for translit API parameters."""

from __future__ import annotations

import enum
from typing import Literal, Protocol, runtime_checkable

ErrorMode = Literal["replace", "ignore", "preserve"]
Platform = Literal["universal", "windows", "posix"]
NormalizationForm = Literal["NFC", "NFD", "NFKC", "NFKD"]


class NF(enum.Enum):
    """Unicode normalization form constants.

    Provides an enum alternative to the string literals accepted by
    :func:`~translit.normalize` and :func:`~translit.is_normalized`.

    Members:
        C: Canonical Composition (NFC).
        D: Canonical Decomposition (NFD).
        KC: Compatibility Composition (NFKC).
        KD: Compatibility Decomposition (NFKD).

    Example::

        from translit import NF, normalize
        normalize("ﬁ", form=NF.KC.value)  # => "fi"
    """

    C = "NFC"
    D = "NFD"
    KC = "NFKC"
    KD = "NFKD"


@runtime_checkable
class EmojiProvider(Protocol):
    """Protocol for custom emoji name providers.

    Implement this protocol to supply your own emoji-to-text mappings
    for :func:`~translit.demojize` and :func:`~translit.set_emoji_provider`.

    Example::

        class FrenchEmoji:
            def lookup(self, sequence: list[int]) -> str | None:
                table = {(0x1F600,): "visage souriant"}
                return table.get(tuple(sequence))

        demojize("hello 😀", provider=FrenchEmoji())
    """

    def lookup(self, sequence: list[int]) -> str | None:
        """Look up the text name for an emoji codepoint sequence.

        Called with successively shorter prefixes of the look-ahead window
        (longest first), so return a name only for an exact match.

        Args:
            sequence: List of Unicode codepoints forming the emoji.
                      e.g. [0x1F468, 0x200D, 0x1F469] for a ZWJ sequence.
                      At most **9 codepoints** are ever offered — the longest
                      built-in CLDR sequence; sequences longer than 9 codepoints
                      cannot be matched by a custom provider (#199). See
                      :func:`~translit.set_emoji_provider`.

        Returns:
            The text name to substitute, or None if this provider
            does not recognize the sequence.
        """
        ...
