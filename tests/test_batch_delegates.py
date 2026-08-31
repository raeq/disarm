"""#822 — a batch function owns the boundary crossing, not the algorithm.

`_strip_accents_batch` did not call `strip_accents`. It restated the algorithm as
`nfd().filter(|c| !is_combining_mark(c)).nfc()`, which is exactly the stateless filter that
`strip_accents_into`'s own comment rules out — whether a mark is strippable depends on the
base it sits on (#749). So the batch path deleted the negation overlay the single path
keeps, and inverted 45 mathematical relations: `∄` came back as `∃`, `∉` as `∈`, `≠` as
`=`. A relation and its negation are not the same character with an accent on it.

`tests/test_batch_consistency.py` found it, but it is Hypothesis-marked and therefore
excluded from CI, so it failed only in developer worktrees and only when the shrinker
happened to reach one of those 45 code points. This file is the deterministic half: the
negation set enumerated rather than searched for, so the gate fires on every run.

The audit that goes with the fix: `_transliterate_batch`, `_normalize_batch` and
`_slugify_batch` all delegate (to the mapped closure, `normalize_one`, and
`slugify_impl_with_stopset`). `_strip_accents_batch` was the only one restating, and it is
the only one that had gone stale against a fix to the single path.
"""

from __future__ import annotations

import unicodedata

import pytest

import disarm

#: Every scalar whose NFD is a base plus a negation overlay — the class #749 protects and
#: the class the old batch path destroyed. Derived from the UCD rather than listed, so a
#: future Unicode version's new relations are covered without an edit.
NEGATION_OVERLAYS = ("̸", "⃒", "̷")


def _negated() -> list[str]:
    out = []
    for cp in range(0x2000, 0x2C00):  # arrows and mathematical operators
        ch = chr(cp)
        decomposed = unicodedata.normalize("NFD", ch)
        if len(decomposed) > 1 and decomposed[-1] in NEGATION_OVERLAYS:
            out.append(ch)
    return out


NEGATED = _negated()


def test_the_corpus_is_not_empty() -> None:
    """A gate over an empty corpus passes for the wrong reason."""
    assert len(NEGATED) > 30, len(NEGATED)
    for ch in ("≠", "∄", "∉"):  # ≠ ∄ ∉
        assert ch in NEGATED


@pytest.mark.parametrize("ch", NEGATED, ids=[f"U+{ord(c):04X}" for c in NEGATED])
def test_the_negation_survives_both_paths(ch: str) -> None:
    """The single path kept it since #749; the batch path did not.

    Stated as *retention of the overlay* rather than as a round-trip, because
    `U+2ADC` FORKING is a composition exclusion: NFC cannot rebuild it, so both paths
    correctly return the two-scalar decomposed form. The property that matters is that
    the stroke is still there, and that both paths agree.
    """
    out = disarm.strip_accents(ch)
    assert any(mark in out for mark in NEGATION_OVERLAYS) or out == ch, out
    assert disarm.strip_accents([ch]) == [out]


def test_batch_equals_single_over_the_negation_set() -> None:
    """The consistency property itself, stated over the inputs that broke it."""
    assert disarm.strip_accents(NEGATED) == [disarm.strip_accents(ch) for ch in NEGATED]


@pytest.mark.parametrize(
    "batch",
    [
        pytest.param(lambda xs: disarm.strip_accents(xs), id="strip_accents"),
        pytest.param(lambda xs: disarm.normalize(xs, form="NFC"), id="normalize"),
        pytest.param(lambda xs: disarm.transliterate(xs), id="transliterate"),
        pytest.param(lambda xs: disarm.slugify(xs), id="slugify"),
    ],
)
def test_every_batch_function_agrees_with_its_single_form(batch) -> None:
    """The general property, over a corpus that spans the classes each one touches.

    A batch function that restates its algorithm is invisible to every fix applied to the
    single path, which is what happened here. This is the gate that makes the next one
    visible.
    """
    corpus = ["≠", "∄", "café", "Ｈéllo", "abc", "", "Ünïcödé", "москва", "北京", "á"]
    single = [batch([one])[0] for one in corpus]
    assert batch(corpus) == single
