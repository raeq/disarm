"""#916 — the confusable fold pairs glyphs by their UPRIGHT shape, and that is a decision.

An "upside-down text" generator substitutes each letter for the glyph that looks like it
rotated 180°, then reverses the string. In that text a glyph means its *rotated* form,
which is the opposite of what TR39 pairs it with. Five glyphs therefore fold to a
different letter than the generator meant — `ɯ` and `ʍ` are a swapped pair, so `gap`
flipped and canonicalized reads back as `bad`.

Upright wins. Recovering rotated text needs the string reversed, and no disarm surface
reverses anything (#917); pointing the fold the other way would leave the output reversed
and unreadable while giving up the upright spoofs the table exists for. These tests pin
both halves of that, so the trade cannot be quietly re-decided in either direction.
"""

from __future__ import annotations

import warnings

import pytest

import disarm

#: The five whose fold disagrees with what a flip generator meant, as
#: ``glyph -> (what the rotation meant, what disarm folds to)``.
#:
#: Escapes, with the glyph in the trailing comment: several are near-indistinguishable
#: in a diff from the letter they fold to, which is the whole reason they are confusable.
DISAGREEING = {
    "\u026f": ("m", "w"),  # ɯ TURNED M — rotated means m, folds to w
    "\u028d": ("w", "m"),  # ʍ TURNED W — rotated means w, folds to m
    "\u028c": ("v", "a"),  # ʌ TURNED V
    "\u0183": ("g", "b"),  # ƃ B WITH TOPBAR
    "\u027e": ("j", "r"),  # ɾ R WITH FISHHOOK
}


@pytest.mark.parametrize(("glyph", "pair"), sorted(DISAGREEING.items()))
def test_the_fold_follows_the_upright_reading(glyph: str, pair: tuple[str, str]) -> None:
    """Both halves: it lands on the upright letter, and NOT on the rotated one."""
    rotated_meaning, upright = pair
    assert disarm.canonicalize(glyph) == upright
    assert disarm.canonicalize(glyph) != rotated_meaning


def test_turned_m_and_turned_w_are_a_swapped_pair() -> None:
    """The sharpest case, and the reason the output is a word rather than a mangling."""
    assert disarm.canonicalize("ɯ") == "w"
    assert disarm.canonicalize("ʍ") == "m"


def test_the_upright_reading_catches_real_spoofs() -> None:
    """What the fold buys, and what pointing it the other way would give up."""
    assert disarm.canonicalize("ʍicrosoft") == "microsoft"
    assert disarm.canonicalize("ɯindows") == "windows"
    assert disarm.canonicalize("ʌpple") == "apple"


def test_no_surface_reverses_a_string() -> None:
    """The premise the decision rests on, asserted rather than assumed.

    Over `disarm.__all__` rather than `dir(disarm)`, and skipping types: the declared
    API is the surface a caller has, and a constructor is not a transform.

    If some surface ever did reverse, recovering rotated text would become possible and
    the trade above would be worth re-opening. Until then it is not a trade at all: the
    rotated reading is unreachable whichever way the fold points.
    """
    reversing = []
    for name in disarm.__all__:
        obj = getattr(disarm, name, None)
        # Types only: `Lexicon("abc")` crosses the Rust boundary and builds something
        # (#923 review). The question is about transforms, and a constructor is not one.
        if not callable(obj) or isinstance(obj, type):
            continue
        if _try(obj, "abc") == "cba":
            reversing.append(name)
    assert not reversing, f"a surface now reverses; #916's decision needs revisiting: {reversing}"


def _try(fn: object, text: str) -> str | None:
    """Call `fn(text)`, or None if it will not take a bare string.

    Deprecation warnings are suppressed rather than filtered by name: the point of the
    sweep is that it covers *every* public callable, and the deprecated aliases are as
    much a surface as the rest until 1.0 removes them.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        try:
            out = fn(text)  # type: ignore[operator]
        except Exception:
            return None
    return out if isinstance(out, str) else None


def test_rotated_text_is_not_recovered_and_that_is_expected() -> None:
    """Documents the observable consequence: a different plausible word, not a mangling.

    `gap` flipped is `dɐƃ`; canonicalized it is `dɐb`, which read back is
    `bɐd`. A caller must not treat canonicalized output as evidence about text that
    may have been rotated.
    """
    flipped_gap = "dɐƃ"
    assert disarm.canonicalize(flipped_gap) == "dɐb"


def test_the_detector_still_fires_on_the_rotated_shape() -> None:
    """What a caller should ask instead, per the limitations page."""
    assert disarm.has_anomalies("¿ʍou ǝɯ puɐʇsɹǝpun")


def test_limitations_states_the_orientation_assumption() -> None:
    """#916's ask: today a caller has no way to know the fold has an orientation."""
    from pathlib import Path

    page = Path(__file__).resolve().parent.parent / "docs" / "limitations.md"
    text = page.read_text(encoding="utf-8")
    assert "orientation assumption" in text
    assert "no disarm surface reverses" in text


#: The substitution an upside-down generator applies, for the glyphs that are not ASCII.
#: Standard across the common web generators.
FLIP = {
    "a": "ɐ",
    "b": "q",
    "c": "ɔ",
    "d": "p",
    "e": "ǝ",
    "f": "ɟ",
    "g": "ƃ",
    "h": "ɥ",
    "i": "ᴉ",
    "j": "ɾ",
    "k": "ʞ",
    "m": "ɯ",
    "n": "u",
    "p": "d",
    "q": "b",
    "r": "ɹ",
    "t": "ʇ",
    "u": "n",
    "v": "ʌ",
    "w": "ʍ",
    "y": "ʎ",
}


def _three_way_split() -> tuple[int, int, int]:
    """(agrees, folds elsewhere, unfolded) over the non-ASCII glyphs a flip map uses."""
    agrees = elsewhere = unfolded = 0
    for upright, glyph in FLIP.items():
        if glyph.isascii():
            continue
        got = disarm.canonicalize(glyph)
        if got == upright:
            agrees += 1
        elif got == glyph:
            unfolded += 1
        else:
            elsewhere += 1
    return agrees, elsewhere, unfolded


def test_the_three_way_split_is_recorded() -> None:
    """#916 scope item 3, in the form that survives: *wrongly folded* is its own count.

    #815's census asks only whether a code point reaches ASCII on some surface, so it
    scores all five of these as covered. A number that cannot distinguish "folds to the
    wrong letter" from "folds correctly" reads as coverage it does not have, which is
    why the split is pinned here rather than left to that sweep.
    """
    agrees, elsewhere, unfolded = _three_way_split()
    assert (agrees, elsewhere, unfolded) == (1, 5, 9), (
        f"the flip-map split moved: {agrees} agree, {elsewhere} fold elsewhere, "
        f"{unfolded} unfolded. If a fold changed, #916's decision and "
        "docs/limitations.md both need revisiting."
    )


def test_the_split_covers_every_non_ascii_flip_glyph() -> None:
    """Anti-vacuity: the three buckets must account for the whole map."""
    non_ascii = sum(1 for g in FLIP.values() if not g.isascii())
    assert sum(_three_way_split()) == non_ascii
    assert non_ascii >= 15, f"only {non_ascii} non-ASCII glyphs; the map may have drifted"
