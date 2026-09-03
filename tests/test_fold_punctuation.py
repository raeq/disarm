"""``fold_punctuation`` (#703): typographic punctuation to its ASCII spelling.

Every assertion here was measured before it was written, including the two that pin what
the primitive does *not* do and what the neighbouring functions still do.
"""

import pytest

import disarm

DASHES = ["\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212"]


@pytest.mark.parametrize("dash", DASHES)
def test_the_dash_family_is_one_character(dash: str) -> None:
    assert disarm.fold_punctuation(f"a{dash}b") == "a-b"


def test_quotes_primes_ellipsis_and_spaces() -> None:
    assert disarm.fold_punctuation("He said \u201cok\u201d") == 'He said "ok"'
    assert disarm.fold_punctuation("it\u2019s") == "it's"
    assert disarm.fold_punctuation("\u201eJa\u201c") == '"Ja"'
    assert disarm.fold_punctuation("5\u2032 10\u2033") == "5' 10\""
    assert disarm.fold_punctuation("wait\u2026") == "wait..."
    assert disarm.fold_punctuation("a\u00a0b\u2009c\u3000d") == "a b c d"


@pytest.mark.parametrize("text", ["a\u3002b", "a\u060cb", "l\u00b7l", "a\u2022b", "a\u3001b"])
def test_the_non_goals_stay(text: str) -> None:
    # CJK and Arabic punctuation are those scripts' own; the middle dot is a letter in
    # Catalan; the bullet is ordinary in prose.
    assert disarm.fold_punctuation(text) == text


def test_idempotent_and_the_identity_on_ascii() -> None:
    plain = "plain - 'text' ..."
    assert disarm.fold_punctuation(plain) == plain
    once = disarm.fold_punctuation("a\u2014b \u201cq\u201d\u2026")
    assert disarm.fold_punctuation(once) == once


def test_form_preserving_like_the_targeted_strips() -> None:
    # Both halves: a decomposed letter leaves as it arrived, and the fold still applies
    # beside it. Boundary normalization is a preset's job, not this primitive's (#477).
    assert disarm.fold_punctuation("i\u0308") == "i\u0308"
    assert disarm.fold_punctuation("\u00ef") == "\u00ef"
    assert disarm.fold_punctuation("i\u0308\u2014x") == "i\u0308-x"


def test_why_it_is_separate_the_neighbours_still_split_the_family() -> None:
    # Both halves of #703's finding, as the tree stands: canonicalize leaves the em dash
    # and horizontal bar, transliterate rejects the hyphen and minus. The primitive is
    # what covers the family; neither neighbour changed.
    assert disarm.canonicalize("a\u2014b") == "a\u2014b"
    assert disarm.canonicalize("a\u2013b") == "a-b"
    assert disarm.transliterate("a\u2014b") == "a-b"
    assert disarm.transliterate("a\u2010b") == "a[?]b"
    assert disarm.canonicalize("a\u201cb") == "a''b"
    assert disarm.fold_punctuation("a\u2014b") == "a-b"
