"""What a word is, for the dictionary builders and for `context=True` (#1146, #1147).

The builders used to split a corpus on whitespace and key each token with its punctuation,
while the runtime looks up a bare run of script characters, so a word the corpus saw only
beside `.` or `(` was never restored. This module mirrors `is_word_char` and
`is_context_boundary` in `src/context.rs`, and
`tests/test_context_word_definition.py` asks the runtime about every code point in these
blocks, so the two cannot part again unnoticed.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import groupby

#: The blocks `is_arabic_char` and `is_hebrew_char` cover.
_SCRIPT_BLOCKS = (
    (0x0590, 0x05FF),
    (0x0600, 0x06FF),
    (0x0750, 0x077F),
    (0x08A0, 0x08FF),
    (0xFB1D, 0xFB4F),
    (0xFB50, 0xFDFF),
    (0xFE70, 0xFEFF),
)
#: Punctuation inside the Arabic blocks. Hebrew's stays: maqaf joins a compound, and geresh
#: and gershayim sit inside words and acronyms.
_ARABIC_PUNCTUATION = frozenset(
    {
        0x0609,
        0x060A,
        0x060C,
        0x060D,
        0x061B,
        0x061D,
        0x061E,
        0x061F,
        0x066A,
        0x066B,
        0x066C,
        0x066D,
        0x06D4,
        0xFD3E,
        0xFD3F,
    }
)
_BOUNDARIES = frozenset("\n\r.!?\u061f\u06d4")


def is_word_char(c: str) -> bool:
    """Whether `tokenize` in `src/context.rs` puts this character inside a word."""
    cp = ord(c)
    if cp in _ARABIC_PUNCTUATION:
        return False
    return any(low <= cp <= high for low, high in _SCRIPT_BLOCKS)


def word_runs(text: str) -> Iterator[tuple[bool, str]]:
    """Each maximal run of word or non-word characters, with which it is."""
    for is_word, run in groupby(text, key=is_word_char):
        yield is_word, "".join(run)


def is_context_boundary(span: str) -> bool:
    """Whether a non-word span ends the previous word's context, as the runtime decides."""
    return not _BOUNDARIES.isdisjoint(span)
