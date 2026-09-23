"""The slug findings of the Lean model of the output sanitizers (``formal/lean/Sanitizers``).

Each test names its finding in ``formal/lean/Sanitizers/README.md``. Non-ASCII test data
is built with ``chr`` so that no invisible or unusual character is written into this file.
"""

from __future__ import annotations

import sys
import unicodedata

import pytest

from disarm import (
    InvalidArgumentError,
    Slugifier,
    Slugify,
    UniqueSlugifier,
    slugify,
)

ZWNJ = chr(0x200C)
ZWJ = chr(0x200D)
JOINERS = (ZWNJ, ZWJ)
KA, VIRAMA, SSA = chr(0x0915), chr(0x094D), chr(0x0937)


def _nbytes(s: str) -> int:
    return len(s.encode("utf-8"))


# -- Finding 4: `allow_unicode` kept 130 `Other_Alphabetic` symbols ---------------------

ALPHABETIC_SYMBOLS = [
    chr(cp)
    for lo, hi in ((0x24B6, 0x24E9), (0x1F130, 0x1F149), (0x1F150, 0x1F169), (0x1F170, 0x1F189))
    for cp in range(lo, hi + 1)
]


def test_finding_4_the_circled_letter_is_a_separator() -> None:
    assert slugify(chr(0x24B6) + "dmin", allow_unicode=True) == "dmin"
    assert slugify("x" + chr(0x24B6) + "y", allow_unicode=True) == "x-y"


@pytest.mark.parametrize("lowercase", [True, False])
def test_finding_4_every_alphabetic_symbol_is_a_separator(lowercase: bool) -> None:
    assert len(ALPHABETIC_SYMBOLS) == 130
    for ch in ALPHABETIC_SYMBOLS:
        got = slugify(f"a{ch}b", allow_unicode=True, lowercase=lowercase)
        assert got == "a-b", f"U+{ord(ch):04X}: {got!r}"


def test_finding_4_every_kept_character_is_a_letter_digit_mark_or_inner_joiner() -> None:
    """Every scalar value, in one call: the output holds only ``L* | N* | M*``, joiners
    between two of them, and the separator.

    ``unicodedata`` may be an older Unicode than the core's; a character it does not know
    (``Cn``) is left out rather than judged.
    """
    chars = [
        chr(cp)
        for cp in range(0x80, sys.maxunicode + 1)
        if not 0xD800 <= cp <= 0xDFFF and unicodedata.category(chr(cp)) != "Cn"
    ]
    got = slugify(" ".join(chars), allow_unicode=True, lowercase=False, separator=" ")
    bad = sorted(
        {
            f"U+{ord(c):04X} {unicodedata.category(c)}"
            for c in got
            if c != " " and c not in JOINERS and unicodedata.category(c)[0] not in "LNM"
        }
    )
    assert bad == []


def test_finding_4_letters_digits_and_marks_are_still_kept() -> None:
    for text in [chr(0x2460), chr(0x2170), "caf" + chr(0xE9), KA + chr(0x093F)]:
        assert slugify(text, allow_unicode=True) == text


# -- Finding 13: a truncated `allow_unicode` slug could end in a joiner -----------------


@pytest.mark.parametrize("word_boundary", [False, True])
@pytest.mark.parametrize("joiner", JOINERS)
def test_finding_13_the_cut_drops_a_trailing_joiner(joiner: str, word_boundary: bool) -> None:
    got = slugify(f"a{joiner}b", allow_unicode=True, max_length=4, word_boundary=word_boundary)
    assert got == "a"
    got = slugify(f"ab{joiner}c", allow_unicode=True, max_length=5, word_boundary=word_boundary)
    assert got == "ab"


def test_finding_13_no_cut_ends_in_a_joiner_or_a_separator() -> None:
    texts = [
        f"a{ZWJ}b c{ZWNJ}d",
        f"{KA}{VIRAMA}{ZWJ}{SSA} x",
        f"{chr(0x645)}{chr(0x6CC)}{ZWNJ}{chr(0x631)}{chr(0x648)}{chr(0x645)} y",
    ]
    for text in texts:
        for sep in ["-", "--", ""]:
            for word_boundary in (False, True):
                for ml in range(1, _nbytes(text) + 2):
                    got = slugify(
                        text,
                        allow_unicode=True,
                        separator=sep,
                        max_length=ml,
                        word_boundary=word_boundary,
                    )
                    assert _nbytes(got) <= ml
                    assert not got.endswith(JOINERS), (text, sep, ml, word_boundary, got)
                    if sep:
                        assert not got.endswith(sep[0]), (text, sep, ml, word_boundary, got)


# -- Finding 9: `UniqueSlugifier` suffixes broke the slug's own shape -------------------


def test_finding_9_the_head_is_cut_without_doubling_the_separator() -> None:
    u = UniqueSlugifier(max_length=5)
    assert [u("ab cd") for _ in range(3)] == ["ab-cd", "ab-1", "ab-2"]


def test_finding_9_never_the_suffix_alone() -> None:
    u = UniqueSlugifier(max_length=2)
    assert u("ab") == "ab"
    with pytest.raises(InvalidArgumentError, match="need at least 3 bytes"):
        u("ab")
    u = UniqueSlugifier(max_length=3)
    assert [u("ab") for _ in range(3)] == ["ab", "a-1", "a-2"]


def test_finding_9_the_digits_are_never_cut() -> None:
    # Ten candidates fit `a-1` ... `a-9`; the tenth would need `a-10`, which does not.
    u = UniqueSlugifier(max_length=3)
    got = [u("ab") for _ in range(10)]
    assert got == ["ab"] + [f"a-{k}" for k in range(1, 10)]
    with pytest.raises(InvalidArgumentError, match="need at least 4 bytes"):
        u("ab")


def test_finding_9_an_empty_slug_is_not_suffixed() -> None:
    u = UniqueSlugifier()
    assert [u("!!!") for _ in range(3)] == ["", "", ""]
    # It is not recorded, so it never displaces a real slug.
    assert u("post") == "post"
    assert u("post") == "post-1"


def test_finding_9_an_empty_slug_does_not_consult_check() -> None:
    seen: list[str] = []

    def check(slug: str) -> bool:
        seen.append(slug)
        return False

    u = UniqueSlugifier(check=check)
    assert u("!!!") == ""
    assert seen == []


def test_finding_9_default_is_still_made_unique() -> None:
    u = UniqueSlugifier(default="n-a")
    assert [u("!!!") for _ in range(3)] == ["n-a", "n-a-1", "n-a-2"]


def test_finding_9_allow_unicode_keeps_a_cluster_whole_and_no_trailing_joiner() -> None:
    base = f"a{KA}{VIRAMA}{ZWJ}{SSA}"
    u = UniqueSlugifier(max_length=13, allow_unicode=True)
    got = [u(base) for _ in range(2)]
    assert got[0] == base
    head, _, digits = got[1].rpartition("-")
    assert digits == "1"
    assert head and not head.endswith(JOINERS)
    assert base.startswith(head)
    assert _nbytes(got[1]) <= 13


def test_finding_9_every_suffixed_slug_is_a_slug() -> None:
    for sep in ["-", "--", "_"]:
        for ml in range(len(sep) + 2, 14):
            u = UniqueSlugifier(max_length=ml, separator=sep)
            out = []
            for _ in range(12):
                try:
                    out.append(u("ab cd ef"))
                except InvalidArgumentError:
                    break
            assert len(out) == len(set(out))
            for s in out:
                assert s and _nbytes(s) <= ml
                assert not s.startswith(sep[0]) and not s.endswith(sep[0]), (sep, ml, out)
                assert sep + sep[0] not in s, (sep, ml, out)


# -- Finding 10: composition ran before lowercasing -------------------------------------


def test_finding_10_the_slug_is_nfc_and_a_fixed_point() -> None:
    t_uml = chr(0x1E97)  # LATIN SMALL LETTER T WITH DIAERESIS
    a = slugify("T" + chr(0x0308), allow_unicode=True)
    assert a == t_uml
    assert slugify(t_uml, allow_unicode=True) == t_uml
    assert unicodedata.is_normalized("NFC", a)
    assert slugify(a, allow_unicode=True) == a


def test_finding_10_upper_case_bases_with_marks_compose() -> None:
    """Latin and Greek capitals with common marks: every slug is NFC and a fixed point."""
    bases = [chr(cp) for cp in range(0x41, 0x5B)] + [
        chr(cp) for cp in range(0x0391, 0x03AA) if cp != 0x03A2
    ]
    marks = [chr(cp) for cp in (0x0300, 0x0301, 0x0302, 0x0303, 0x0308, 0x0313, 0x0342, 0x0345)]
    for base in bases:
        for mark in marks:
            got = slugify(base + mark, allow_unicode=True)
            assert unicodedata.is_normalized("NFC", got), (base, mark, got)
            assert slugify(got, allow_unicode=True) == got


# -- Finding 5: plain truncation left a partial multi-character separator ---------------


def test_finding_5_the_plain_cut_strips_a_partial_separator() -> None:
    assert slugify("a b", separator="-_", max_length=2) == "a"
    assert slugify("a b", separator="-_", max_length=2, word_boundary=True) == "a"
    assert slugify("ab cd", separator="--", max_length=3) == "ab"


# -- Finding 6: `word_boundary` dropped a whole word it had room for -------------------


def test_finding_6_a_cut_on_a_word_end_keeps_the_word() -> None:
    assert slugify("very long title here", max_length=9, word_boundary=True) == "very-long"
    # The documented examples.
    assert slugify("Very Long Title Here", max_length=10, word_boundary=True) == "very-long"
    assert slugify("a very long title here", max_length=10, word_boundary=True) == "a-very"
    assert slugify("Long Title", max_length=10, word_boundary=True) == "long-title"


# -- Finding 7: stopwords were not case-insensitive -------------------------------------


def test_finding_7_stopwords_are_case_insensitive() -> None:
    assert slugify("The Fox", stopwords=["The"]) == "fox"
    assert slugify("the Fox", stopwords=["THE"], lowercase=False) == "Fox"
    assert slugify("The Fox the", stopwords=["tHe"], save_order=True) == "fox"
    assert slugify("The Fox", stopwords=["The"], lowercase=False) == "Fox"


def test_finding_7_every_entry_point_agrees() -> None:
    assert slugify(["The Fox", "A Hen"], stopwords=["The", "A"]) == ["fox", "hen"]
    assert Slugifier(stopwords=["The"])("The Fox") == "fox"
    assert UniqueSlugifier(stopwords=["The"])("The Fox") == "fox"
    assert Slugify(to_lower=True, stop_words=("The",))("The Fox") == "fox"


# -- Finding 8: an empty separator filtered stopwords character by character ------------


def test_finding_8_an_empty_separator_has_no_words_to_filter() -> None:
    assert slugify("abc", separator="", stopwords=["b"]) == "abc"
    assert slugify("a b c", separator="", stopwords=["b"]) == "abc"
    assert slugify("bab", separator="", stopwords=["b"], save_order=True) == "bab"


# -- Finding 11: the mark cap counts a precomposed base's own marks ---------------------


def _marks(s: str) -> int:
    return sum(1 for c in unicodedata.normalize("NFD", s) if unicodedata.combining(c))


def test_finding_11_a_precomposed_base_keeps_its_own_marks_and_gains_none() -> None:
    alpha = chr(0x1F82)  # three marks in its NFD
    assert slugify(alpha, allow_unicode=True) == alpha
    assert _marks(alpha) == 3
    assert slugify(alpha + chr(0x0301), allow_unicode=True) == alpha
    assert _marks(slugify("a" + chr(0x0301) + chr(0x0302) + chr(0x0303), allow_unicode=True)) == 2
