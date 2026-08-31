"""A negation overlay is not an accent (#749).

`strip_accents` removed every `Mn`. `U+0338 COMBINING LONG SOLIDUS OVERLAY` and
`U+20D2 COMBINING LONG VERTICAL LINE OVERLAY` are not diacritics — on a relation symbol
they *are* the negation, so removing one leaves the positive operator. `≠` became `=`,
and every surface running the step emitted output asserting the opposite of its input.

The rule is about the base, not the code point. The same `U+0338` on a **letter** is
strikethrough obfuscation, which `strip_obfuscation` exists to remove.
"""

from __future__ import annotations

import functools
import unicodedata

import pytest

import disarm

OVERLAYS = ("̸", "⃒")

SURFACES = [
    "strip_accents",
    "search_key",
    "catalog_key",
    "sort_key",
    "canonicalize",
    "canonicalize_strict",
    "strip_obfuscation",
    "ml_normalize",
    "normalize_confusables",
]


@functools.cache
def _negated() -> tuple[int, ...]:
    """Every assigned code point whose NFD carries a negation overlay.

    Cached: this is a full 0x110000 scan and several tests want the population, one of
    them once per surface.
    """
    out = []
    for cp in range(0x110000):
        if 0xD800 <= cp <= 0xDFFF or cp in (0x0338, 0x20D2):
            continue
        ch = chr(cp)
        if unicodedata.category(ch) == "Cn":
            continue
        if any(c in OVERLAYS for c in unicodedata.normalize("NFD", ch)):
            out.append(cp)
    return tuple(out)


def _positive_base(ch: str) -> str:
    d = unicodedata.normalize("NFD", ch)
    return unicodedata.normalize("NFC", "".join(c for c in d if c not in OVERLAYS))


def test_the_population_is_what_the_issue_says() -> None:
    """45 composed code points, asserted rather than assumed."""
    assert len(_negated()) == 45


@pytest.mark.parametrize(
    ("symbol", "positive"),
    [("≠", "="), ("≮", "<"), ("≯", ">"), ("∄", "∃"), ("∤", "∣"), ("↚", "←")],
)
def test_a_negation_never_becomes_its_positive(symbol: str, positive: str) -> None:
    """The defect, one row at a time. Each of these returned `positive` before #749."""
    for name in SURFACES:
        out = getattr(disarm, name)(symbol)
        assert out != positive, f"{name}({symbol!r}) inverted to {positive!r}"


@pytest.mark.formal
def test_no_surface_inverts_any_negation() -> None:
    """Tier 3: the whole class against every surface.

    One residual is expected and named: `U+2ADC` is a composition exclusion, so NFKC
    leaves it decomposed and the transliterate step drops the orphaned overlay. That is a
    different mechanism from the two this change fixes, and it is asserted here as a
    known negative rather than left to be rediscovered.
    """
    known = {0x2ADC}
    for name in SURFACES:
        fn = getattr(disarm, name)
        inverted = {
            cp
            for cp in _negated()
            if fn(chr(cp)) == _positive_base(chr(cp)) and fn(chr(cp)) != chr(cp)
        }
        assert inverted <= known, (
            f"{name} inverts {sorted(inverted - known)} beyond the known residual"
        )


def test_strikethrough_on_letters_is_still_stripped() -> None:
    """The counter-case, and the reason the rule reads the base.

    A blanket exemption for `U+0338` would preserve this too, and it is a moderation
    bypass — which is why `strip_obfuscation` has a test for it.
    """
    assert disarm.strip_obfuscation("H̸a̸t̸e̸ speech") == "Hate speech"


def test_ordinary_accents_still_strip() -> None:
    assert disarm.strip_accents("café") == "cafe"
    assert disarm.strip_accents("José") == "Jose"


def test_zalgo_is_still_capped() -> None:
    """The overlays are exempt from the cap, not the cap from the overlays."""
    assert disarm.strip_zalgo("a" + "́" * 10) != "a" + "́" * 10


@pytest.mark.parametrize("run", [1, 2, 5, 50, 1000])
def test_a_run_of_overlays_does_not_bypass_the_zalgo_cap(run: int) -> None:
    """Exactly one overlay per base survives, however many arrive.

    The exemption is for *a* negation — a relation carries one stroke. A run of them is
    stacking whatever the base is, and exempting the whole run would let `Zalgo(0)`
    through untouched, which is the thing that step exists to stop.
    """
    stacked = "=" + "\u0338" * run
    assert len(disarm.strip_zalgo(stacked, max_marks=0)) == 1
    assert disarm.strip_zalgo(stacked, max_marks=0) == "\u2260"
    assert len(disarm.strip_accents(stacked)) == 1
    # And the same run on a letter is still stripped outright — it is strikethrough.
    assert disarm.strip_zalgo("a" + "\u0338" * run, max_marks=0) == "a"


def test_each_base_gets_its_own_overlay() -> None:
    """One per base, not one per string."""
    assert disarm.strip_accents("=\u0338=\u0338") == "\u2260\u2260"
    assert disarm.strip_zalgo("=\u0338\u0338=\u0338\u0338", max_marks=0) == "\u2260\u2260"
