"""NFKC amplification inside a preset is bounded (#768).

`src/limits.rs` states the project's position on input size and its single exception:

    disarm does not cap raw input size — bounding untrusted input is the caller's
    responsibility. This bound is the one exception: registered replacement *values*
    are caller-supplied and unbounded, so a tiny input can expand to an enormous
    string via a separately-registered value (an amplification a caller's own
    input-size check cannot foresee).

That reason is true of NFKC too, and NFKC was not capped. `U+FDFA` ARABIC LIGATURE
SALLALLAHOU ALAYHE WASALLAM expands to 18 characters, so a caller who bounded input at
6 MB — the mitigation the comment assigns them — got 60 MB out of `canonicalize`.
"""

from __future__ import annotations

import unicodedata

import pytest

import disarm

#: The widest single-code-point NFKC expansion in Unicode: 1 character to 18.
LIGATURE = "ﷺ"

PRESETS = [
    "canonicalize",
    "canonicalize_strict",
    "search_key",
    "catalog_key",
    "sort_key",
    "strip_obfuscation",
    "ml_normalize",
]


def test_the_expansion_is_what_the_issue_says() -> None:
    """Asserted, not assumed — the cap is only worth having if the amplification is."""
    assert len(unicodedata.normalize("NFKC", LIGATURE)) == 18


@pytest.mark.parametrize("preset", PRESETS)
def test_every_preset_is_bounded(preset: str) -> None:
    """6 MB of ligature produced 60 MB before this cap."""
    with pytest.raises(disarm.ResourceLimitError):
        getattr(disarm, preset)(LIGATURE * 2_000_000)


@pytest.mark.parametrize("preset", PRESETS)
def test_ordinary_text_is_untouched(preset: str) -> None:
    """The cap is on produced output, so nothing that stays small can trip it."""
    assert getattr(disarm, preset)("Hello world")


def test_an_expansion_under_the_ceiling_still_succeeds() -> None:
    """The bound is a ceiling on output, not a ban on expansion. 300k ligatures expand
    to 9 MB, which is under the 10 MiB limit and must still work."""
    out = disarm.canonicalize(LIGATURE * 300_000)
    assert len(out.encode()) > 8_000_000


def test_normalize_itself_is_deliberately_unbounded() -> None:
    """`normalize(form="NFKC")` is a caller naming the operation whose expansion this is.

    Bounding a function against the thing it was explicitly asked to do is a different
    decision from bounding a preset that never mentions normalization in its name. If this
    ever changes it should be because someone decided it, not because a cap leaked.
    """
    out = disarm.normalize(LIGATURE * 2_000_000, form="NFKC")
    assert len(out.encode()) > 60_000_000


def test_the_error_names_both_numbers() -> None:
    """A limit error that does not say what was produced and what was allowed leaves the
    caller guessing at how much to trim."""
    with pytest.raises(disarm.ResourceLimitError) as excinfo:
        disarm.canonicalize(LIGATURE * 2_000_000)
    message = str(excinfo.value)
    assert "66000000" in message
    assert "10485760" in message
