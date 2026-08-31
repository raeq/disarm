"""#721 — `sanitize_filename` must not manufacture a percent escape.

The function already accepts this premise once: `collapse_dot_sequences` runs a second
time after transliteration because `U+2026` and `U+00B7` can reintroduce a `..` that was
not in the input. The same step can assemble `%2E%2E%2F` — the percent-encoded spelling of
the *same* traversal — out of characters containing no `%`, no `2`, no `E` and no `F`.
The remedy covered one spelling of traversal and not the other.
"""

from __future__ import annotations

from urllib.parse import unquote

import pytest

from disarm import sanitize_filename

# The five code points compatibility folding maps to `%`, enumerated by an exhaustive
# scan rather than assumed. A sixth appearing here means the transliteration table moved.
PERCENT_SOURCES = ["؉", "؊", "٪", "﹪", "％"]

# Every row from the issue's table that the fix changes.
MANUFACTURED = [
    ("％２Ｅ％２Ｅ％２Ｆetc.txt", "_2E_2E_2Fetc.txt"),
    ("﹪2E﹪2E﹪2Fetc.txt", "_2E_2E_2Fetc.txt"),
    ("％００.png", "_00.png"),
    ("％７Ｅroot", "_7Eroot"),
]


@pytest.mark.parametrize(("text", "want"), MANUFACTURED, ids=[r[0] for r in MANUFACTURED])
def test_a_manufactured_escape_is_neutralized(text: str, want: str) -> None:
    assert "%" not in text
    assert sanitize_filename(text) == want


@pytest.mark.parametrize(("text", "_want"), MANUFACTURED, ids=[r[0] for r in MANUFACTURED])
def test_the_result_no_longer_decodes_to_a_traversal(text: str, _want: str) -> None:
    """`serve(unquote(segment))` is a common enough shape to be worth the check."""
    out = sanitize_filename(text)
    assert unquote(out) == out
    assert ".." not in unquote(out)
    assert "/" not in unquote(out)


@pytest.mark.parametrize("ch", PERCENT_SOURCES, ids=[f"U+{ord(c):04X}" for c in PERCENT_SOURCES])
def test_every_percent_source_is_covered(ch: str) -> None:
    """Each of the five on its own, not just the four assembled rows."""
    assert "%" not in sanitize_filename(f"{ch}2Ffile.txt")


def test_the_property_is_exact() -> None:
    """`"%" not in sanitize_filename(x)` whenever `"%" not in x` — #721 §1's own test."""
    for cp in range(0x3000):
        ch = chr(cp)
        if "%" in ch:
            continue
        out = sanitize_filename(f"a{ch}b.txt")
        assert "%" not in out, f"U+{cp:04X} manufactured a percent: {out!r}"


# ── the documented boundary (#721 §2) ────────────────────────────────────────


def test_a_percent_the_caller_typed_is_kept() -> None:
    """Passing a literal `%2E%2E%2F` through is defensible — the caller wrote it.

    This is the row the issue leaves in place, and the reason the boundary needs saying
    out loud rather than being discovered: the literal `..` is removed and the
    percent-encoded spelling of the same traversal is not.
    """
    assert sanitize_filename("..%2Fetc") == "%2Fetc"
    assert unquote(sanitize_filename("..%2Fetc")) == "/etc"


@pytest.mark.parametrize("text", ["100%.txt", "report %.pdf", "50%-off.png", "%2Fetc"])
def test_an_ordinary_filename_with_a_percent_is_untouched(text: str) -> None:
    assert "%" in sanitize_filename(text)


# ── nothing else moved ───────────────────────────────────────────────────────


def test_the_literal_traversal_still_collapses() -> None:
    assert sanitize_filename("../etc") == "_etc"


@pytest.mark.parametrize(
    "text",
    [*[r[0] for r in MANUFACTURED], "..%2Fetc", "100%.txt", "../etc", "a.b.c"],
)
def test_still_idempotent(text: str) -> None:
    once = sanitize_filename(text)
    assert sanitize_filename(once) == once


def test_the_separator_is_honoured() -> None:
    """The manufactured `%` is replaced by the caller's separator, like an illegal char."""
    assert sanitize_filename("％2Fetc.txt", separator="-") == "-2Fetc.txt"
    assert sanitize_filename("％2Fetc.txt", separator="") == "2Fetc.txt"
