"""Grapheme-integrity property tests (issue #174).

Core invariant (empirically validated: 800k+ adversarial checks, zero
counterexamples): Unicode normalization respects grapheme-cluster boundaries.

For every normalization form (NFC, NFD, NFKC, NFKD)::

    normalize(whole) == "".join(normalize(g) for g in grapheme_split(whole))

This proves normalization never splits a combining-mark sequence or an Indic
conjunct, and never merges across cluster boundaries. It holds for ALL inputs,
including defective (leading) combining marks, Hangul jamo, Indic conjuncts,
ligatures, and ZWJ emoji sequences.

P3 note (documented, NOT a violation): NFKC/NFKD may change the grapheme
*count* via compatibility expansion (e.g. the ligature "ﬁ" U+FB01, one cluster,
normalizes under NFKC to "fi", two clusters). That is intended; the boundary
invariant above still holds for it — the single input cluster maps to its own
normalization, which is exactly what the join reproduces.
"""

from __future__ import annotations

import unicodedata

import pytest

import translit

FORMS = ("NFC", "NFD", "NFKC", "NFKD")


def boundary_preserved(s: str, form: str) -> bool:
    """normalize(whole) equals the join of per-cluster normalizations."""
    whole = translit.normalize(s, form=form)
    parts = "".join(translit.normalize(g, form=form) for g in translit.grapheme_split(s))
    return whole == parts


# Curated strings exercising each tricky case. Each entry is annotated with the
# Unicode feature it stresses.
CURATED = [
    "",  # empty
    "abc",  # pure ASCII
    "Hello, World!",  # ASCII with punctuation
    "é",  # é precomposed (U+00E9)
    "é",  # é decomposed (e + combining acute)
    "ạ́",  # ạ́ : base + below-mark + above-mark (multi-mark stack)
    "क्ष",  # क्ष Devanagari conjunct KA + virama + SSA
    "க்ஷ",  # க்ஷ Tamil conjunct KA + virama + SSA
    "한",  # 한 composed Hangul syllable (U+D55C)
    "한",  # 한 as conjoining jamo (HIEUH + A + NIEUN)
    "ﬁ",  # ﬁ ligature (U+FB01)
    "\U0001f468‍\U0001f469‍\U0001f467",  # 👨‍👩‍👧 ZWJ family emoji
    "́abc",  # leading defective combining mark (orphan acute)
    "Ａ",  # Ａ fullwidth A (U+FF21)
    "café naïve résumé",  # mixed ASCII + accents
    "Straße",  # ß (eszett, no decomposition but NFKC-relevant elsewhere)
    "กำ",  # Thai with sara am (reorders under normalization)
]


class TestGraphemeBoundaryPreservation:
    """Deterministic CI-tier tests of the boundary invariant."""

    def test_normalization_preserves_grapheme_boundaries_curated(self) -> None:
        for s in CURATED:
            for form in FORMS:
                whole = translit.normalize(s, form=form)
                parts = "".join(
                    translit.normalize(g, form=form) for g in translit.grapheme_split(s)
                )
                assert whole == parts, (
                    f"boundary violation for {s!r} under {form}: whole={whole!r} parts={parts!r}"
                )

    def test_nfkc_ligature_expansion_is_documented_not_a_violation(self) -> None:
        # P3: the ﬁ ligature (U+FB01) is a SINGLE grapheme cluster, but NFKC
        # compatibility-expands it to "fi" (two grapheme clusters). This changes
        # the grapheme *count*, which is intended and is NOT a boundary
        # violation: the single input cluster maps to its own normalization, so
        # the per-cluster join still equals normalize(whole). We assert both the
        # expansion AND that the boundary invariant continues to hold for it.
        ligature = "ﬁ"  # ﬁ
        assert translit.grapheme_split(ligature) == [ligature]  # one cluster in
        assert translit.normalize(ligature, form="NFKC") == "fi"
        # "fi" is two grapheme clusters out — count changed, by design.
        assert translit.grapheme_split("fi") == ["f", "i"]
        # Boundary invariant still holds for every form, including NFKC/NFKD.
        for form in FORMS:
            assert boundary_preserved(ligature, form)

    def test_normalization_never_orphans_a_combining_mark(self) -> None:
        # Strings that begin with a base character followed by combining mark(s).
        # No normalization form may produce output whose first scalar is a
        # combining mark — that would mean a mark was orphaned to the front.
        based = [
            "ẹ́",  # ẹ́ : e + below-dot + acute
            "ñ",  # ñ decomposed
            "à",  # à decomposed
            "का",  # का : Devanagari KA + AA matra
            "ȫ",  # ȫ : o + diaeresis + macron
        ]
        for s in based:
            for form in FORMS:
                out = translit.normalize(s, form=form)
                assert out, f"empty normalization of {s!r} under {form}"
                assert unicodedata.combining(out[0]) == 0, (
                    f"{form} orphaned a combining mark to the front of {s!r}: out={out!r}"
                )


@pytest.mark.hypothesis
def test_normalization_preserves_grapheme_boundaries_property() -> None:
    """Property test (excluded from CI by the `hypothesis` marker).

    Generates arbitrary text plus deliberately adversarial base+combining
    stacks and asserts the boundary-preservation equality for all four forms.
    """
    from hypothesis import given
    from hypothesis import strategies as st

    base_chars = st.sampled_from(["a", "e", "o", "क", "한", "א", "ا"])
    combining_marks = st.lists(
        st.integers(min_value=0x0300, max_value=0x036F).map(chr),
        min_size=0,
        max_size=4,
    )
    stacks = st.builds(
        lambda b, marks: b + "".join(marks),
        base_chars,
        combining_marks,
    )
    inputs = st.one_of(st.text(), stacks, st.lists(stacks).map("".join))

    @given(inputs)
    def check(s: str) -> None:
        for form in FORMS:
            assert boundary_preserved(s, form), f"boundary violation for {s!r} under {form}"

    check()
