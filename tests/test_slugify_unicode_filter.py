"""#711 and #712 — what `allow_unicode` keeps, and where `max_length` cuts.

Both public descriptions promised a category restriction — "keep non-ASCII **letters**"
(Python) and "keep Unicode **word characters**" (Rust) — and the filter applied none:
every non-ASCII, non-whitespace code point survived, whatever its category. The default
ASCII path screened all of it. Turning on `allow_unicode` turned the whole class off.
"""

from __future__ import annotations

import unicodedata

import pytest

from disarm import slugify

# ── #712: the classes that must not reach a slug ─────────────────────────────

# Every row from the issue's table, with the ASCII path's answer beside it.
EXCLUDED = [
    ("file‮gnp.exe", "file-gnp-exe", "RLO"),
    ("a​b", "a-b", "ZWSP"),
    ("a­b", "a-b", "soft hyphen"),
    ("a﻿b", "a-b", "ZWNBSP"),
    ("a⁦b", "a-b", "LRI"),
    ("ab", "a-b", "private use"),
    ("a￾b", "a-b", "noncharacter"),
    ("a\U000e0041b", "a-b", "tag character"),
]


@pytest.mark.parametrize(("text", "want", "label"), EXCLUDED, ids=[r[2] for r in EXCLUDED])
def test_a_non_letter_never_reaches_the_slug(text: str, want: str, label: str) -> None:
    assert slugify(text, allow_unicode=True) == want


def test_the_rlo_row_is_the_one_that_matters() -> None:
    """`slugify(title, allow_unicode=True)` is the natural call for a non-Latin site.

    `'file‮gnp-exe'` renders as `fileexe.png`, and the slug is then the URL, the
    anchor text, or the filename.
    """
    assert "‮" not in slugify("file‮gnp.exe", allow_unicode=True)


def test_emoji_go_the_way_django_sends_them() -> None:
    """`So` is not `\\w`; `django.utils.text.slugify(allow_unicode=True)` drops them too."""
    assert slugify("Hello 👋 World", allow_unicode=True) == "hello-world"
    assert slugify("Hello 👋 World") == "hello-world"


def test_the_two_paths_now_screen_the_same_classes() -> None:
    """The gap was that `allow_unicode` screened nothing its ASCII sibling screens."""
    for text, _, _ in EXCLUDED:
        uni = slugify(text, allow_unicode=True)
        assert not any(unicodedata.category(c) in ("Cf", "Co", "Cn", "Cs") for c in uni), text


# ── #712 §3: the two deliberate exceptions ───────────────────────────────────


def test_a_joiner_between_letters_survives() -> None:
    """ZWNJ and ZWJ are orthographically required; dropping them changes the word."""
    assert slugify("می‌روم", allow_unicode=True) == "می‌روم"  # Persian
    assert slugify("क्‍ष", allow_unicode=True) == "क्‍ष"  # Devanagari
    assert slugify("a‍b", allow_unicode=True) == "a‍b"


@pytest.mark.parametrize("text", ["a‍", "‍a", "a‍ b", "a‌"])
def test_a_joiner_never_sits_at_a_token_edge(text: str) -> None:
    """A joiner with nothing to join to is invisible padding.

    `'👨‍'` and `'👨'` render identically and are different byte strings, so two rows
    can collide visually while a uniqueness check passes (#711).
    """
    out = slugify(text, allow_unicode=True)
    for token in out.split("-"):
        assert not token.startswith(("‌", "‍")), out
        assert not token.endswith(("‌", "‍")), out


# ── #712 §4: the zalgo cap ───────────────────────────────────────────────────


def test_stacked_marks_are_capped_at_two() -> None:
    """30 marks on one base survived. Two is the cap `Step::Zalgo(2)` uses."""
    out = slugify("a" + "̀" * 30, allow_unicode=True)
    marks = [c for c in unicodedata.normalize("NFD", out) if unicodedata.combining(c)]
    assert len(marks) <= 2, out


def test_the_cap_is_two_because_vietnamese_needs_two() -> None:
    assert slugify("Tiếng Việt", allow_unicode=True) == "tiếng-việt"


def test_a_mark_with_no_base_is_dropped() -> None:
    """A defective combining sequence — the separator before it is not a base."""
    out = slugify("̀abc", allow_unicode=True)
    assert not unicodedata.combining(out[0])


# ── #711: the cut lands on a cluster boundary ────────────────────────────────


def test_a_cut_never_splits_a_cluster() -> None:
    """A Hangul syllable is kept whole or dropped whole."""
    assert slugify("한국어", allow_unicode=True, max_length=6) == "한국"
    assert slugify("한국어", allow_unicode=True, max_length=5) == "한"


def test_a_budget_below_the_first_cluster_yields_an_empty_slug() -> None:
    """`क्षि` is one 12-byte cluster; there is no honest prefix of it.

    The alternative is a torn cluster, which #711 argues is worse: it renders as a
    different character, or ends the slug in a bare joiner. An empty slug is the same
    outcome an all-stopword input already produces.
    """
    assert slugify("क्षि", allow_unicode=True, max_length=9) == ""
    assert slugify("क्षि", allow_unicode=True, max_length=12) == "क्षि"


@pytest.mark.parametrize("n", range(1, 40))
def test_truncation_is_a_cluster_prefix_of_the_untruncated_slug(n: int) -> None:
    """The property from #711 §4, over a mixed-script input."""
    from disarm import grapheme_split

    text = "한국어 Tiếng Việt क्षि Привет"
    full = slugify(text, allow_unicode=True)
    cut = slugify(text, allow_unicode=True, max_length=n)
    assert len(cut.encode()) <= n
    assert full.startswith(cut)
    # A prefix at a cluster boundary: the cut's clusters are the full slug's, in order.
    assert grapheme_split(full)[: len(grapheme_split(cut))] == grapheme_split(cut)


@pytest.mark.parametrize("n", range(1, 40))
def test_a_truncated_slug_never_ends_in_a_mark_or_a_joiner(n: int) -> None:
    text = "한국어 Tiếng Việt क्षि می‌روم"
    cut = slugify(text, allow_unicode=True, max_length=n)
    if cut:
        # The last *code point*, not the last of its NFD: `ế` is a complete character
        # whose decomposition ends in a mark, and keeping it is the point.
        assert cut[-1] not in ("‌", "‍"), cut
        assert not unicodedata.combining(cut[-1]), cut


def test_word_boundary_reaches_the_separator_search_with_a_whole_cluster() -> None:
    """`word_boundary=True` was no help before: it called the same code-point floor."""
    text = "한국어 Tiếng Việt"
    for n in range(1, 30):
        cut = slugify(text, allow_unicode=True, max_length=n, word_boundary=True)
        assert len(cut.encode()) <= n
        assert slugify(text, allow_unicode=True).startswith(cut)


# ── the ASCII path is untouched (#711 §1) ────────────────────────────────────


@pytest.mark.parametrize("n", range(1, 25))
def test_the_ascii_path_keeps_its_cheap_route(n: int) -> None:
    text = "Hello World Foo Bar"
    assert slugify(text, max_length=n) == slugify(text, max_length=n, allow_unicode=False)
    assert len(slugify(text, max_length=n).encode()) <= n


# ── a dropped character ends a token, even with no separator to show for it ───

# `separator=""` is the case that separates "a separator was emitted" from "a base is in
# scope". Fusing the two let a joiner or a mark reattach ACROSS a removed character.
EMPTY_SEPARATOR_REATTACH = [
    ("a!‍b", "ab", "a joiner must not join two characters that were never adjacent"),
    ("a!̀b", "ab", "a mark must not move onto a letter that never carried it"),
    ("a.‍.b", "ab", "the same across a dropped dot"),
    ("a\ufeff̀b", "ab", "and across a dropped format character"),
]


@pytest.mark.parametrize(
    ("text", "want", "why"), EMPTY_SEPARATOR_REATTACH, ids=[r[0] for r in EMPTY_SEPARATOR_REATTACH]
)
def test_a_dropped_character_ends_a_token_with_an_empty_separator(
    text: str, want: str, why: str
) -> None:
    assert slugify(text, allow_unicode=True, separator="") == want, why


def test_the_empty_separator_agrees_with_the_default_one() -> None:
    """The only difference an empty separator may make is the separator itself.

    Anything else means the token-boundary state and the separator-emission state have
    been fused, which is how the reattachment above happened.
    """
    for text, _, _ in EMPTY_SEPARATOR_REATTACH:
        assert slugify(text, allow_unicode=True, separator="") == slugify(
            text, allow_unicode=True
        ).replace("-", "")


def test_a_joiner_between_adjacent_letters_still_survives_an_empty_separator() -> None:
    """The fix must not take the #712 §3 exception with it."""
    assert slugify("می‌روم", allow_unicode=True, separator="") == "می‌روم"
    assert slugify("क्‍ष", allow_unicode=True, separator="") == "क्‍ष"
