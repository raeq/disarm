"""Stream-Safe Text Format (UAX #15) — an interop bound, not a security control.

`unicode-normalization` already shipped this; disarm did not expose it. Most of what
follows is about keeping the distinction true, because every plausible misreading of this
function is a way to use it wrongly: as a zalgo control, as a size bound, or as a
comparison key.
"""

from __future__ import annotations

import unicodedata

import pytest

import disarm

CGJ = "͏"
ACUTE = "́"

#: The standard's bound.
MAX_NONSTARTERS = 30


def test_a_short_run_is_untouched() -> None:
    s = "a" + ACUTE * (MAX_NONSTARTERS - 1)
    assert disarm.stream_safe(s) == s


def test_a_long_run_gets_a_joiner() -> None:
    s = "a" + ACUTE * 40
    out = disarm.stream_safe(s)
    assert CGJ in out
    assert len(out) > len(s)


def test_it_is_not_canonically_equivalent() -> None:
    """The property that makes it unusable as a comparison key, asserted so nobody
    reaches for it as one."""
    s = "a" + ACUTE * 40
    out = disarm.stream_safe(s)
    assert out != s
    assert disarm.normalize(out, form="NFC") != disarm.normalize(s, form="NFC")


def test_ordinary_zalgo_is_below_the_bound() -> None:
    """It is not a zalgo control. Eight stacked marks is well under 30 and passes
    through untouched, which is why `strip_zalgo` exists separately."""
    zalgo = "a" + ACUTE * 8
    assert disarm.stream_safe(zalgo) == zalgo
    assert disarm.strip_zalgo(zalgo) != zalgo


@pytest.mark.parametrize(
    ("label", "text"),
    [
        ("Hebrew, three marks", "אָׁ֑"),
        ("Arabic, shadda + fatha", "بَّ"),
        ("Devanagari conjunct", "क्ष"),
        ("Vietnamese NFD", unicodedata.normalize("NFD", "ệ")),
    ],
)
def test_real_stacking_scripts_are_untouched(label: str, text: str) -> None:
    """Legitimate stacking is nowhere near the bound. If this ever fires, the bound has
    been confused with an orthographic judgement."""
    assert disarm.stream_safe(text) == text, label


def test_the_predicate_is_a_conjunction() -> None:
    """Upstream's own doc reads "is Stream-Safe NFC". A string can be stream-safe without
    being normalized, and the answer is `False` for it — which is why the function is not
    called `is_stream_safe`."""
    decomposed = "e" + ACUTE
    assert disarm.stream_safe(decomposed) == decomposed  # already within the bound
    assert not disarm.is_normalized_stream_safe(decomposed)
    assert disarm.is_normalized_stream_safe(disarm.normalize(decomposed, form="NFC"))


@pytest.mark.parametrize("form", ["NFC", "NFD", "NFKC", "NFKD"])
def test_every_form_is_accepted(form: str) -> None:
    assert disarm.is_normalized_stream_safe("abc", form=form)


def test_an_invalid_form_is_rejected() -> None:
    with pytest.raises(disarm.InvalidArgumentError):
        disarm.is_normalized_stream_safe("abc", form="NFQ")


def test_ascii_is_a_no_op() -> None:
    assert disarm.stream_safe("Hello world") == "Hello world"
    assert disarm.is_normalized_stream_safe("Hello world")
