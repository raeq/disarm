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


def test_one_struck_letter_of_a_word_does_not_report() -> None:
    assert not disarm.has_anomalies("re\u0336ad please")


def test_one_overlaid_letter_alone_does_not_report() -> None:
    assert not disarm.has_anomalies("x\u0338 is not y")


# --- How much of a word, and which marks (#1194) --------------------------------

_PASSWORD = "password"


def _on(positions: list[int] | range, marks: str, word: str = _PASSWORD) -> str:
    """`word` with `marks` after each letter at `positions`."""
    return "".join(c + marks if i in positions else c for i, c in enumerate(word))


def _before_each(marks: str, word: str = _PASSWORD) -> str:
    return "".join(marks + c for c in word)


_ALL = range(8)
_ALL_BUT_LAST = range(7)
_ALL_BUT_FIRST = range(1, 8)
_EVERY_OTHER = range(0, 8, 2)
_EVERY_THIRD = range(0, 8, 3)

_STRIKES = [0x336, 0x337, 0x338, 0x20D2, 0x20D3, 0x20D8, 0x20D9, 0x20DA, 0x20E5, 0x20E6, 0x20EA]
_STRIKES += [0x20EB]
#: Each has a real use on a letter, so two of three stay clean, and styling tools use them too,
#: so a whole word still reports. They take the underline's bar, not an exemption (#1213).
_TILDE_AND_SHORT_STROKE = [0x334, 0x335]


@pytest.mark.parametrize("mark", _STRIKES, ids=lambda m: f"U+{m:04X}")
@pytest.mark.parametrize(
    "positions",
    [_ALL, _ALL_BUT_LAST, _ALL_BUT_FIRST, _EVERY_OTHER],
    ids=["every", "all-but-last", "all-but-first", "every-other"],
)
def test_a_strike_on_half_a_word_or_more_reports(positions: range, mark: int) -> None:
    """One bare letter switched the rule off, which is no bar at all (#1194)."""
    text = _on(positions, chr(mark))
    assert disarm.has_anomalies(text), ascii(text)
    assert disarm.inspect_anomalies(text).kinds == ["zalgo"], ascii(text)


@pytest.mark.parametrize("mark", [0x336, 0x332, 0x20D2], ids=lambda m: f"U+{m:04X}")
def test_a_mark_written_before_each_letter_reports(mark: int) -> None:
    """The first mark has no letter and the last letter no mark, so one bare letter is free."""
    assert disarm.has_anomalies(_before_each(chr(mark)))


def test_a_strike_on_under_half_a_word_stays_clean() -> None:
    """A stated limit, which `llm_guardrail` still removes: see `docs/limitations.md`."""
    assert not disarm.has_anomalies(_on(_EVERY_THIRD, "\u0336"))


@pytest.mark.parametrize(
    "mark", [0x332, 0x333, *_TILDE_AND_SHORT_STROKE], ids=lambda m: f"U+{m:04X}"
)
@pytest.mark.parametrize(
    "positions",
    [_ALL, _ALL_BUT_LAST, _ALL_BUT_FIRST],
    ids=["every", "all-but-last", "all-but-first"],
)
def test_an_underline_on_all_but_one_letter_reports(positions: range, mark: int) -> None:
    text = _on(positions, chr(mark))
    assert disarm.has_anomalies(text), ascii(text)
    assert disarm.inspect_anomalies(text).kinds == ["zalgo"], ascii(text)


@pytest.mark.parametrize(
    "text",
    [
        "S\u0332h\u0332ayk\u0332h\u0332",
        "s\u0332h\u0332\u0101h",
        "k\u0332h\u0332\u0101n",
        "s\u0332h\u0332\u012b",
        "G\u0332h\u0332az\u0101l\u012b",
        "F\u0332ile E\u0332dit V\u0332iew",
    ],
    ids=["shaykh", "shah", "khan", "shi", "ghazali", "menu-accelerators"],
)
def test_an_underlined_digraph_is_orthography_and_stays_clean(text: str) -> None:
    """Scholarly romanization of Arabic underlines `s\u0332h\u0332` and `k\u0332h\u0332`.

    So underlines answer to all but one letter, where a strike answers to half. A menu
    underlines one letter of each word.
    """
    assert not disarm.has_anomalies(text), ascii(text)


def test_an_underline_on_half_a_word_stays_clean() -> None:
    assert not disarm.has_anomalies(_on(_EVERY_OTHER, "\u0332"))


def _marked(spec: str, *marks: int) -> str:
    """`spec` with the next of `marks` after each letter that follows a `*` (#1213)."""
    out, seen, i = [], 0, 0
    while i < len(spec):
        if spec[i] == "*":
            out.append(spec[i + 1] + chr(marks[seen % len(marks)]))
            seen += 1
            i += 2
        else:
            out.append(spec[i])
            i += 1
    return "".join(out)


_U_MACRON, _A_MACRON = chr(0x16B), chr(0x101)


@pytest.mark.parametrize(
    ("spec", "mark"),
    [
        ("*s*h", 0x332),
        ("*s*h", 0x333),
        ("*o*n", 0x332),
        ("*k*hu*s*h", 0x332),
        (f"*k*h{_U_MACRON}*s*h", 0x332),
        ("*g*hu*s*h", 0x332),
        ("*s*ha*k*h", 0x332),
        ("*d*hi*k*h", 0x332),
        ("*p*a*ss", 0x332),
        ("*p*a*s*sw", 0x332),
        ("*S*hay*k*h", 0x332),
        (f"*s*h{_A_MACRON}h", 0x332),
        ("*ti*l", 0x334),
        ("*ge*b", 0x335),
        ("fi*l", 0x334),
        ("*pa*ss*wo*rd", 0x334),
        ("*pa*ss*wo*rd", 0x335),
        ("*pas*swo*rd", 0x336),
    ],
)
def test_the_underline_bar_leaves_these_clean(spec: str, mark: int) -> None:
    """Two digraphs cannot reach five marks, and one cannot reach three (#1210, #1213)."""
    assert not disarm.has_anomalies(_marked(spec, mark)), ascii(_marked(spec, mark))


@pytest.mark.parametrize(
    ("spec", "marks"),
    [
        ("*t*h*e", (0x332,)),
        ("*p*a*s*s", (0x332,)),
        ("*s*e*c*r*et", (0x332,)),
        ("*p*a*s*s*w*o*rd", (0x332,)),
        ("*t*i*l", (0x334,)),
        ("*p*a*s*s*w*o*rd", (0x334,)),
        ("*p*a*s*s*w*o*r*d", (0x335,)),
        ("*o*n", (0x336,)),
        ("*ti*l", (0x336,)),
        ("*ti*l", (0x337,)),
        ("*ti*l", (0x338,)),
        ("*pa*ss*wo*rd", (0x336,)),
        ("*ti*l", (0x334, 0x336)),
        ("*pa*ss*wo*rd", (0x332, 0x336)),
    ],
)
def test_the_bars_still_report_these(spec: str, marks: tuple[int, ...]) -> None:
    """A word holding a strike takes the strike's bar, so a bare tilde beside it counts."""
    text = _marked(spec, *marks)
    assert disarm.has_anomalies(text), ascii(text)
    assert disarm.inspect_anomalies(text).kinds == ["zalgo"], ascii(text)


@pytest.mark.parametrize(
    ("spec", "mark"),
    [("*s*h", 0x332), ("*k*hu*s*h", 0x332), ("*p*a*s*sw", 0x332), ("*ti*l", 0x334)],
)
def test_what_the_bars_spare_still_leaves_no_seam(spec: str, mark: int) -> None:
    """`canonicalize` keeps the mark and its output reads as the input does. `llm_guardrail`
    removes it, so the cost of each clean row is the detector's alone."""
    text = _marked(spec, mark)
    assert chr(mark) in disarm.canonicalize(text)
    assert not disarm.has_anomalies(disarm.canonicalize(text))
    assert chr(mark) not in disarm.get_pipeline("llm_guardrail")(text)


@pytest.mark.parametrize(
    ("mark", "why"),
    [
        (
            0x305,
            "an overline is a vinculum and an active-low signal: V\u0305I\u0305, R\u0305S\u0305T\u0305",
        ),
        (0x331, "a macron below is a letter in Kwak'wala, Tlingit and Semitic romanization"),
    ],
    ids=["overline", "macron-below"],
)
def test_the_line_marks_with_a_use_on_every_letter_stay_clean(mark: int, why: str) -> None:
    """A stated limit: `llm_guardrail` removes them, and only the detector does not read them."""
    assert not disarm.has_anomalies(_on(_ALL, chr(mark))), why


@pytest.mark.parametrize(
    "text",
    [
        "V\u0305I\u0305I\u0305",
        "R\u0305S\u0305T\u0305",
        "C\u0305S\u0305",
        "G\u0331a\u0331l\u0331a\u0331",
    ],
    ids=["roman-numeral", "active-low", "chip-select", "macron-below"],
)
def test_real_uses_of_the_line_marks_stay_clean(text: str) -> None:
    assert not disarm.has_anomalies(text), ascii(text)


@pytest.mark.parametrize(
    "text",
    [
        "x=\u0338y=\u0338z",
        "a<\u0338b>\u0338c=\u0338d",
        "x\u2260y\u2260z",
    ],
    ids=["chain", "three-relations", "precomposed"],
)
def test_a_chain_of_negations_counts_no_letter_as_struck(text: str) -> None:
    """The mark is on the symbol, and half the letters is now reachable by counting it."""
    assert not disarm.has_anomalies(text), ascii(text)


def test_a_class_one_mark_with_a_script_of_its_own_stays_where_it_was() -> None:
    """Bassa Vah tones are class 1 and are how that script writes tone."""
    bassa_vah = "".join(chr(0x16AD0 + i) + "\U00016af0" for i in range(6))
    assert not disarm.has_anomalies(bassa_vah)


def test_every_class_one_mark_is_counted_or_has_a_script_of_its_own() -> None:
    """A new overlay in the block for symbols has to be decided, not missed."""
    own_script = {0x1CD4, *range(0x1CE2, 0x1CE9), 0x10A39, *range(0x16AF0, 0x16AF5)}
    own_script |= {0x1BC9E, 0x1D167, 0x1D168, 0x1D169}
    class_one = {cp for cp in range(0x110000) if unicodedata.combining(chr(cp)) == 1}
    assert class_one == own_script | set(_STRIKES) | set(_TILDE_AND_SHORT_STROKE)


@pytest.mark.parametrize(
    "marks",
    [(0x301, 0x323, 0x304), (0x300, 0x316, 0x342)],
    ids=lambda m: "-".join(f"{cp:04X}" for cp in m),
)
@pytest.mark.parametrize(
    "positions",
    [_ALL, _ALL_BUT_LAST, _ALL_BUT_FIRST, _EVERY_OTHER],
    ids=["every", "all-but-last", "all-but-first", "every-other"],
)
def test_three_marks_on_half_a_latin_word_or_more_report(
    positions: range, marks: tuple[int, ...]
) -> None:
    """The stack rule had the same edge, with no overlay in it to catch them (#1194)."""
    text = _on(positions, "".join(map(chr, marks)))
    assert disarm.has_anomalies(text), ascii(text)
    assert disarm.inspect_anomalies(text).kinds == ["zalgo"], ascii(text)


def test_the_issue_stack_on_all_but_the_last_reports() -> None:
    assert disarm.has_anomalies(_on(_ALL_BUT_LAST, "\u0323\u0301\u0336"))


def test_three_marks_on_under_half_a_latin_word_stay_clean() -> None:
    assert not disarm.has_anomalies(_on(_EVERY_THIRD, "\u0301\u0323\u0304"))


def test_three_marks_on_one_letter_of_a_word_stay_clean() -> None:
    assert not disarm.has_anomalies(_on([3], "\u0301\u0323\u0304"))


def test_two_marks_on_every_letter_stay_clean_at_any_coverage() -> None:
    assert not disarm.has_anomalies(_on(_ALL, "\u0301\u0323"))
    assert not disarm.has_anomalies(_on(_ALL_BUT_LAST, "\u0301\u0323"))


@pytest.mark.parametrize(
    "marks",
    [
        "\u0336",
        "\u0332",
        "\u0305",
        "\u0331",
        "\u20d2",
        "\u20d3",
        "\u20e5",
        "\u0323\u0301\u0336",
    ],
    ids=lambda m: "-".join(f"{ord(c):04X}" for c in m),
)
@pytest.mark.parametrize(
    "build",
    [
        lambda m: _on(_ALL, m),
        lambda m: _on(_ALL_BUT_LAST, m),
        lambda m: _on(_ALL_BUT_FIRST, m),
        lambda m: _on(_EVERY_OTHER, m),
        lambda m: _on(_EVERY_THIRD, m),
        _before_each,
    ],
    ids=["every", "all-but-last", "all-but-first", "every-other", "every-third", "before-each"],
)
def test_llm_guardrail_returns_the_word_from_every_row(build, marks: str) -> None:  # noqa: ANN001
    assert disarm.get_pipeline("llm_guardrail")(build(marks)) == _PASSWORD


def test_the_finding_says_how_many_letters_carry_the_overlay() -> None:
    assert disarm.inspect_anomalies(_on(_ALL_BUT_LAST, "\u0336")).findings[0].detail == (
        "U+0336 on 7 of 8 letters"
    )


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
