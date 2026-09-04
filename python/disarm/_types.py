"""Type aliases and protocols for disarm API parameters."""

from __future__ import annotations

import enum
from typing import Literal, Protocol, runtime_checkable

ErrorMode = Literal["replace", "ignore", "preserve"]
# transliterate() additionally accepts "strict" (#184): raise on the first
# untranslatable character. Other errors= consumers (e.g. demojize) use ErrorMode.
TransliterateErrorMode = Literal["replace", "ignore", "preserve", "strict"]
Platform = Literal["universal", "windows", "posix"]
NormalizationForm = Literal["NFC", "NFD", "NFKC", "NFKD"]


class NF(enum.Enum):
    """Unicode normalization form constants.

    Provides an enum alternative to the string literals accepted by
    `normalize` and `is_normalized`.

    Members:
        C: Canonical Composition (NFC).
        D: Canonical Decomposition (NFD).
        KC: Compatibility Composition (NFKC).
        KD: Compatibility Decomposition (NFKD).

    Example::

        from disarm import NF, normalize
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
    for `demojize` and `set_emoji_provider`.

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
                      `set_emoji_provider`.

        Returns:
            The text name to substitute, or None if this provider
            does not recognize the sequence.

        Warning:
            **A match consumes the window it was shown** (#972). Returning a string —
            including ``""`` — tells the scanner that every code point in *sequence* was
            the emoji, and all of them are replaced by that string. A provider that
            answers for a window it did not match therefore deletes the characters
            around the emoji as well as the emoji::

                class Empty:
                    def lookup(self, sequence): return ""

                demojize("aa🔥bb", provider=Empty())   # -> "" , not "aabb"

            The protocol has no way to say *I matched three of these*, so return ``None``
            for any window whose leading code points you do not recognize. To remove
            emoji rather than name them, use `replace_emoji`, which decides what is an
            emoji from the UCD's properties instead of asking a provider.
        """
        ...
