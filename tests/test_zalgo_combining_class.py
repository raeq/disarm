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
from pathlib import Path

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


# --- Overlay marks and stacks under the per-class floor (#1156) -----------------

_WORD = "please read"


def _spread(*marks: int) -> str:
    suffix = "".join(map(chr, marks))
    return "".join(c + suffix if c != " " else c for c in _WORD)


@pytest.mark.parametrize("mark", [0x336, 0x335, 0x334, 0x337, 0x338, 0x332, 0x333])
def test_an_overlay_on_every_letter_of_a_word_reports(mark: int) -> None:
    """One mark per base is below every count, and the marks are what the word looks like."""
    text = _spread(mark)
    assert disarm.has_anomalies(text), f"U+{mark:04X}"
    assert disarm.inspect_anomalies(text).kinds == ["zalgo"]


def test_an_overlay_on_some_letters_of_a_word_does_not_report() -> None:
    assert not disarm.has_anomalies("re\u0336ad please")


def test_one_overlaid_letter_alone_does_not_report() -> None:
    assert not disarm.has_anomalies("x\u0338 is not y")


@pytest.mark.parametrize(
    "text",
    [
        "a=\u0338b",
        "a\u2260b",
        "\u2203\u0338x",
        "x=\u0338y and a<\u0338b",
    ],
    ids=["negated-equals", "precomposed", "negated-exists", "two-negations"],
)
def test_a_negation_on_a_symbol_is_ordinary(text: str) -> None:
    """#749: `U+0338` on a symbol is how a negation is written."""
    assert not disarm.has_anomalies(text), ascii(text)


@pytest.mark.parametrize(
    "marks",
    [
        (0x301, 0x323, 0x336),
        (0x301, 0x323, 0x336, 0x334),
        (0x301, 0x323, 0x304),
        (0x300, 0x316, 0x342),
    ],
    ids=lambda m: "-".join(f"{cp:04X}" for cp in m),
)
def test_three_marks_per_latin_letter_report_across_classes(marks: tuple[int, ...]) -> None:
    assert disarm.has_anomalies(_spread(*marks))


def test_two_marks_per_letter_stay_below_it() -> None:
    assert not disarm.has_anomalies(_spread(0x301, 0x323))


@pytest.mark.parametrize(
    "text",
    [
        unicodedata.normalize("NFD", "Vi\u1ec7t Nam ti\u1ebfng Vi\u1ec7t"),
        unicodedata.normalize("NFD", "\u1ea5m \u1ee7 \u1eadt"),
        "\u0928\u092e\u0938\u094d\u0924\u0947",
        "\u05e9\u05b8\u05c1\u05dc\u05d5\u05b9\u05dd",
        "\u1019\u103c\u102d\u102f\u1037",
        "\u0e01\u0e33\u0e41\u0e1e\u0e07",
    ],
    ids=["vietnamese", "vietnamese-heavy", "hindi", "pointed-hebrew", "burmese", "thai"],
)
def test_ordinary_orthography_stays_clean(text: str) -> None:
    assert not disarm.has_anomalies(text), ascii(text)


def test_many_marks_on_a_non_latin_base_stay_where_they_were() -> None:
    """The count across classes is gated on Latin, for the Burmese evidence behind #842."""
    assert not disarm.has_anomalies("\u1019\u103b\u103c\u102d\u102f\u1037\u1038")


def test_guardrail_recovers_what_canonicalize_keeps() -> None:
    text = _spread(0x336)
    assert disarm.get_pipeline("llm_guardrail")(text) == _WORD
    assert disarm.strip_obfuscation(text) == _WORD
    assert "\u0336" in disarm.canonicalize(text)


def test_the_guide_says_what_keeps_an_overlay_and_what_removes_it() -> None:
    root = Path(__file__).resolve().parent.parent
    flat = " ".join((root / "docs/limitations.md").read_text(encoding="utf-8").split())
    assert "overlay" in flat
    assert "`canonicalize` keeps" in flat
