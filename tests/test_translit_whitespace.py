"""Every whitespace character transliterates to whitespace.

`translit_default.tsv` mapped LINE SEPARATOR and PARAGRAPH SEPARATOR to nothing, so they
joined the words either side: `transliterate("pay pal")` was `paypal`, and so were
`search_key`, `catalog_key` and `slugify`, where the `LF` form gives `pay pal`. NEXT LINE
had no row at all and came out as `[?]`. Every other whitespace character already gave a
space, as TR39's rows for these code points and `collapse_whitespace` do. Noticed while
checking the key builders against the Lean model of `resolve_deletions`
(`formal/lean/Deletions`), which treats all three as line breaks.
"""

from __future__ import annotations

import sys

import pytest

from disarm import catalog_key, search_key, slugify, transliterate

WHITESPACE = [chr(cp) for cp in range(0x80, sys.maxunicode + 1) if chr(cp).isspace()]


def test_the_sweep_is_not_empty() -> None:
    assert {"\x85", " ", " ", "　"} <= set(WHITESPACE)


@pytest.mark.parametrize("ws", WHITESPACE, ids=lambda c: f"U+{ord(c):04X}")
def test_it_separates_words(ws: str) -> None:
    assert transliterate(f"pay{ws}pal") == "pay pal"
    assert search_key(f"pay{ws}pal") == search_key("pay pal")
    assert catalog_key(f"pay{ws}pal") == catalog_key("pay pal")
    assert slugify(f"pay{ws}pal") == slugify("pay pal")
