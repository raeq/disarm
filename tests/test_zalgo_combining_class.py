"""#842 — `is_zalgo` called 142 ordinary Burmese place names zalgo.

`strip_zalgo` then deleted a tone mark from each, and `canonicalize` carried the
truncation into a key. `မြို့` is **one syllable** — a base consonant, a medial, two vowel
signs and a tone — and it is how Burmese is written, not stacking abuse.

#788 fixed the *disagreement* between the cap and the threshold by raising the cap to 3. It
did not ask whether 3 is the right number, and for Myanmar it is not. Raising it to 4 would
clear this corpus and stop nowhere principled: Burmese takes a second medial, so a corpus
with more of the language pushes it to 5, and each raise costs detection at the top end for
every other script.

The discriminator is not the count. It is **canonical combining class**:

- A mark with class 0 is *positioned* by the renderer — Burmese vowel signs and medials,
  Indic matras, Thai vowels. It does not stack, so it does not count.
- Zalgo is many marks at **one** position, which means many marks of one non-zero class.

Runs are counted per class, so a legitimate cluster of distinct marks never accumulates,
and an attacker cannot break up a run by interleaving classes — NFD canonically reorders
marks by class, so `("\\u0301" + "\\u0323") * 10` sorts into ten of each and reads as a run
of ten either way. The normalization does the work.

Not for a class-0 mark, though (Z1 in `formal/lean/Text`). Canonical ordering sorts marks
only *between starters*, and a class-0 mark is a starter, so `a` + three acutes + `U+034F` +
three acutes stays two runs of three in NFD. The count is therefore per base as well as per
class: a class-0 mark neither counts nor resets it, and only a non-mark starts a new base.
`tests/test_text_formal_findings.py` holds that.

Measured over the 22,963-row key-stability corpus: **142 false positives → 0**, with every
zalgo form still caught.
"""

from __future__ import annotations

import pathlib
import random
import unicodedata

import pytest

import disarm

CORPUS = pathlib.Path(__file__).parent / "fixtures" / "key_stability" / "corpus.txt"


def marks(text: str) -> int:
    return sum(1 for c in unicodedata.normalize("NFD", text) if unicodedata.category(c)[0] == "M")


#: Burmese place names from the corpus. `မြို့နယ်` is "township".
BURMESE = ["ကနီမြို့နယ်", "ကန့်ဘလူမြို့နယ်", "ကန်ပက်လက်မြို့နယ်", "ကလေးမြို့နယ်"]


@pytest.mark.parametrize("word", BURMESE, ids=lambda w: f"{len(w)}-chars")
def test_ordinary_burmese_is_not_zalgo(word: str) -> None:
    assert not disarm.is_zalgo(word), f"{word!r} is a place name"


@pytest.mark.parametrize("word", BURMESE, ids=lambda w: f"{len(w)}-chars")
def test_ordinary_burmese_keeps_every_mark(word: str) -> None:
    """The transform deleted a tone mark from each of these."""
    assert marks(disarm.strip_zalgo(word)) == marks(word)
    assert marks(disarm.canonicalize(word)) == marks(word), "the truncation reached a key"


#: Two synthetic rows #862 added to the corpus, not text anyone writes: a precomposed
#: acute letter plus three diaeresis split by ``U+0489`` (class 0), so four class-230 marks
#: on one base. They read as zalgo since Z1 (`formal/lean/Text`) stopped a class-0 mark
#: from resetting the count, which is the point of that fix.
STACKED_ACROSS_A_CLASS_ZERO_MARK = {
    "\u00e1\u0308\u0308\u0489\u0308b",
    "\u0403\u0308\u0308\u0489\u0308\u0432",
}


def test_the_whole_corpus_is_clean() -> None:
    """142 rows before, all Myanmar. A gate over the measured set, not a sample."""
    rows = [line for line in CORPUS.read_text(encoding="utf-8").split("\n") if line]
    assert len(rows) > 20_000, len(rows)
    flagged = [r for r in rows if disarm.is_zalgo(r) and r not in STACKED_ACROSS_A_CLASS_ZERO_MARK]
    assert not flagged, f"{len(flagged)} corpus rows read as zalgo; first: {flagged[:2]!r}"
    for row in STACKED_ACROSS_A_CLASS_ZERO_MARK:
        assert row in rows, "the exemption names a row the corpus no longer has"
        assert disarm.is_zalgo(row), ascii(row)


# ── what must still be caught ────────────────────────────────────────────────


def test_repeated_marks_are_still_zalgo() -> None:
    """The classic form: one mark, many times."""
    stacked = "Z" + "́" * 8
    assert disarm.is_zalgo(stacked)
    assert marks(disarm.strip_zalgo(stacked)) == 3


def test_distinct_marks_of_one_class_are_still_zalgo() -> None:
    """A realistic generator picks randomly from the diacritics block, which is one class."""
    random.seed(3)
    above = [chr(c) for c in range(0x0300, 0x0315)]
    noisy = "Z" + "".join(random.choice(above) for _ in range(9))
    assert disarm.is_zalgo(noisy)


def test_interleaving_classes_does_not_evade() -> None:
    """The obvious evasion, defeated by normalization rather than by a rule.

    NFD reorders marks by combining class, so alternating above and below sorts into two
    contiguous runs of ten. The attacker cannot present them as a sequence of runs of one.
    """
    evasive = "Z" + ("́" + "̣") * 10
    assert disarm.is_zalgo(evasive)
    assert marks(disarm.strip_zalgo(evasive)) == 6, "three kept at each of two positions"


# ── the scripts #788 was about, still right ──────────────────────────────────


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("Hebrew", "אָׁ֑"),
        ("Arabic", "بَّْ"),
        ("Bengali", "ইয়াং"),
        ("Devanagari", "क्ष्ण"),
        ("Thai", "กั้"),
        ("Vietnamese", "ệ"),
    ],
    ids=["hebrew", "arabic", "bengali", "devanagari", "thai", "vietnamese"],
)
def test_the_scripts_788_covered_are_still_covered(name: str, text: str) -> None:
    """This change generalises #788 rather than replacing it."""
    assert not disarm.is_zalgo(text), name
    assert marks(disarm.strip_zalgo(text)) == marks(text), name
