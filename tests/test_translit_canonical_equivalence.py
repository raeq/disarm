"""Canonically equivalent input transliterates the same way.

`src/transliterate.rs` describes its output as invariant to the input's normal form,
and a Lean audit of the I1-I3 argument (formal/lean/Transliterate) found where it was
not: GREEK DIALYTIKA AND OXIA and GREEK OXIA had table rows reading `x`, where their
canonical equivalents give `"` and a space, and with `tones=True` the 156 CJK
compatibility ideographs lost their tones, because the toned table is keyed by the
unified ideograph they decompose to. Swept over every code point that has a canonical
decomposition, against both its NFC and its NFD form, in both tone modes.
"""

from __future__ import annotations

import functools
import sys
import unicodedata

import pytest

from disarm import transliterate


@functools.cache
def _decomposable() -> tuple[str, ...]:
    """Scanned once and shared by both tone modes (Copilot review on #1013)."""
    out = []
    for cp in range(0x80, sys.maxunicode + 1):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        ch = chr(cp)
        if unicodedata.normalize("NFD", ch) != ch or unicodedata.normalize("NFC", ch) != ch:
            out.append(ch)
    return tuple(out)


@pytest.mark.parametrize("tones", [False, True])
def test_canonical_equivalents_agree(tones: bool) -> None:
    mismatched = [
        (f"U+{ord(ch):04X}", form, got, want)
        for ch in _decomposable()
        for form in ("NFC", "NFD")
        if (got := transliterate(ch, errors="ignore", tones=tones))
        != (want := transliterate(unicodedata.normalize(form, ch), errors="ignore", tones=tones))
    ]
    assert mismatched == [], f"{len(mismatched)} disagree, first five: {mismatched[:5]}"
