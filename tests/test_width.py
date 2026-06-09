"""Tests for terminal column width: terminal_width / grapheme_width (#224).

Golden vectors and the I_w1–I_w5 invariants run in CI; the property sweep is
Hypothesis (tier 2) and the differential against ``wcwidth`` is formal (tier 3).
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from translit import grapheme_len, grapheme_width, terminal_width

# --- Golden vectors (A2–A6) -------------------------------------------------


@pytest.mark.parametrize(
    "text,width",
    [
        ("", 0),
        ("hello", 5),
        ("世", 2),  # CJK wide
        ("世界", 4),
        ("한", 2),  # composed Hangul syllable
        ("Ａ", 2),  # U+FF21 fullwidth
        ("ｱ", 1),  # U+FF71 halfwidth katakana
        ("café", 4),  # NFC
        ("café", 4),  # NFD (combining acute is 0)
        ("́", 0),  # lone combining mark (I_w5)
        ("😀", 2),  # Emoji_Presentation
        ("☺️", 2),  # VS16 → emoji
        ("☺︎", 1),  # VS15 → text presentation
        ("🇫🇷", 2),  # regional-indicator flag
        ("1️⃣", 2),  # keycap
        ("👨‍👩‍👧‍👦", 2),  # ZWJ family
        ("\t", 0),  # tab not expanded (A5)
        ("​", 0),  # ZWSP
        ("a\x00b", 2),  # NUL is 0
    ],
)
def test_golden(text: str, width: int) -> None:
    assert terminal_width(text) == width


def test_grapheme_width_basics() -> None:
    assert grapheme_width("A") == 1
    assert grapheme_width("世") == 2
    assert grapheme_width("👨‍👩‍👧‍👦") == 2


def test_ambiguous_policy() -> None:
    # U+00A1 is East Asian Ambiguous: narrow by default, wide on request (A3).
    assert terminal_width("¡") == 1
    assert terminal_width("¡", ambiguous_wide=True) == 2
    assert grapheme_width("¡", ambiguous_wide=True) == 2


# --- Invariants I_w1–I_w5 ---------------------------------------------------


@pytest.mark.parametrize("s", ["", "hello world", "a-b_c.123!"])
def test_iw1_ascii_equals_len(s: str) -> None:
    assert terminal_width(s) == len(s.encode("ascii"))


def test_iw5_zero_width_clusters() -> None:
    assert grapheme_width("́") == 0  # combining
    assert grapheme_width("‍") == 0  # ZWJ
    assert grapheme_width("️") == 0  # lone VS16


@given(st.text(max_size=200))
def test_iw2_bounds(s: str) -> None:
    assert 0 <= terminal_width(s) <= 2 * grapheme_len(s)


@given(st.text(max_size=100), st.text(max_size=100))
def test_iw3_additivity_across_space(a: str, b: str) -> None:
    # A space between the parts guarantees no cluster merges across the join.
    assert terminal_width(f"{a} {b}") == terminal_width(a) + 1 + terminal_width(b)


@given(st.text(max_size=200))
def test_iw4_determinism(s: str) -> None:
    assert terminal_width(s) == terminal_width(s)


# --- Differential vs wcwidth (independent oracle), classified by UCD --------


def _load_emoji_presentation() -> set[int]:
    """Emoji_Presentation code points, from the committed generated table."""
    path = (
        Path(__file__).resolve().parents[1] / "src" / "tables" / "data" / "emoji_presentation.tsv"
    )
    cps: set[int] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        start, end = (int(x, 16) for x in line.split("\t"))
        cps.update(range(start, end + 1))
    return cps


@pytest.mark.formal
def test_differential_vs_wcwidth() -> None:
    """Every divergence from wcwidth must be explained by a UCD property.

    wcwidth is an independent value oracle; unicodedata classifies whether a
    divergence is one of translit's documented policies — controls/format
    zeroed (A4/A5), emoji-presented widened (A6), isolated spacing marks kept
    narrow (A4), or translit following UCD East Asian Width where wcwidth's own
    table over-widens a symbol. Anything else is a real bug.
    """
    wcwidth = pytest.importorskip("wcwidth").wcwidth
    emoji_pres = _load_emoji_presentation()
    undocumented: list[tuple[str, int, int, str, str]] = []
    for cp in range(0x110000):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        c = chr(cp)
        tw = grapheme_width(c)
        ww = wcwidth(c)
        if tw == ww:
            continue
        cat = unicodedata.category(c)
        eaw = unicodedata.east_asian_width(c)
        allowed = (
            (ww == -1 and tw == 0)  # A7: controls report 0, not -1
            or (cat in ("Cc", "Cf") and tw == 0)  # A4/A5: control/format zeroed
            or tw == 0  # other default-ignorable / combining we zero
            or (cp in emoji_pres and tw == 2)  # A6: emoji presentation widened
            or cat == "Mc"  # A4: spacing marks not zeroed (width follows EAW)
            or (eaw not in ("W", "F") and tw == 1)  # follow UCD EAW; wcwidth over-wide
        )
        if not allowed:
            undocumented.append((hex(cp), tw, ww, cat, eaw))
    assert not undocumented, (
        f"{len(undocumented)} undocumented width divergences from wcwidth: {undocumented[:20]}"
    )
