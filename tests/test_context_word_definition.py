"""The dictionary builders and `context=True` agree on what a word is (#1146, #1147).

The builders split a corpus on whitespace and kept the punctuation on the key, and the
runtime looks up a bare run of script characters. So a word the corpus saw only beside `.` or
`(` was never restored, and a word's readings were ranked per punctuated variant. Going the
other way, `is_arabic_char` covers all of U+0600..U+06FF, so the Arabic comma, semicolon,
question mark and full stop stayed on the word. `is_context_boundary` lists the last two, and
the tokenizer never passed it either, so a bigram applied across a sentence end.

Both sides now take their word from one definition, and a test holds them together by asking
the runtime about every code point in the script blocks. Dictionaries are loaded once per
process and cached, so each runtime question is a subprocess.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pytest
from conftest import trld_bytes

from disarm import transliterate

ROOT = Path(__file__).resolve().parent.parent


def _builder(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


arabic = _builder("build_arabic_dict")
hebrew = _builder("build_hebrew_dict")
#: Loading a builder puts `scripts/` on the path and imports this.
words = sys.modules["context_words"]

KATABA = "\u0643\u064e\u062a\u064e\u0628\u064e"
KTB = "\u0643\u062a\u0628"
WALAD = "\u0627\u0644\u0648\u064e\u0644\u064e\u062f\u064f"
WLD = "\u0627\u0644\u0648\u0644\u062f"
KITABAN = "\u0643\u0650\u062a\u064e\u0627\u0628\u064b\u0627"
KTABA = "\u0643\u062a\u0627\u0628\u0627"
JAMILAN = "\u062c\u064e\u0645\u0650\u064a\u0644\u064b\u0627"
JMYLA = "\u062c\u0645\u064a\u0644\u0627"
DARS = "\u062f\u064e\u0631\u0652\u0633\u064c"
DARASA = "\u062f\u064e\u0631\u064e\u0633\u064e"
DRS = "\u062f\u0631\u0633"
QUESTION = "\u061f"
FULL_STOP = "\u06d4"
COMMA = "\u060c"
SEMICOLON = "\u061b"
SHALOM = "\u05e9\u05b8\u05c1\u05dc\u05d5\u05b9\u05dd"
SHLVM = "\u05e9\u05dc\u05d5\u05dd"

PROBE = """
import json, sys
from disarm import transliterate
print(json.dumps([transliterate(q, context=True) for q in json.loads(sys.argv[1])]))
"""


def _counts(builder, corpus: str, tmp_path: Path):
    path = tmp_path / "corpus.txt"
    path.write_text(corpus, encoding="utf-8")
    unigrams: dict[str, Counter[str]] = defaultdict(Counter)
    bigrams: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        builder.process_file(path, unigrams, bigrams, [0])
    return unigrams, bigrams


def _ask(dict_dir: Path, queries: list[str]) -> list[str]:
    run = subprocess.run(  # noqa: S603 - fixed argv; the probe is this module's own
        [sys.executable, "-c", PROBE, json.dumps(queries)],
        env={**os.environ, "DISARM_DICT_DIR": str(dict_dir)},
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return json.loads(run.stdout)


def _compile(unigrams, bigrams, dict_dir: Path) -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        arabic.compile_dictionary(unigrams, bigrams, dict_dir / "arabic_dict.bin", min_freq=1)


# --- the builders ------------------------------------------------------------


@pytest.mark.parametrize(
    ("corpus", "key"),
    [
        (f"({KITABAN})", KTABA),
        (f"{JAMILAN}.", JMYLA),
        (f"{WALAD}{COMMA}", WLD),
        (f"\u00ab{KATABA}\u00bb", KTB),
        (f"{KATABA}{QUESTION}", KTB),
    ],
)
def test_the_arabic_builder_keys_a_word_without_its_punctuation(tmp_path, corpus, key):
    unigrams, _ = _counts(arabic, corpus, tmp_path)
    assert list(unigrams) == [key]


def test_the_hebrew_builder_keys_a_word_without_its_punctuation(tmp_path):
    unigrams, _ = _counts(hebrew, f"({SHALOM}).", tmp_path)
    assert list(unigrams) == [SHLVM]


def test_a_word_inside_punctuation_keeps_its_readings_together(tmp_path):
    """Each punctuated variant was its own key, so the counts that rank readings were split."""
    corpus = f"{KATABA} {KATABA}. ({KATABA} {KATABA}{COMMA}"
    unigrams, _ = _counts(arabic, corpus, tmp_path)
    assert unigrams[KTB][KATABA] == 4


@pytest.mark.parametrize("mark", [QUESTION, FULL_STOP, ".", "!", "?", "\n"])
def test_the_builder_records_no_bigram_across_a_boundary(tmp_path, mark):
    _, bigrams = _counts(arabic, f"{KATABA}{mark} {DARASA}", tmp_path)
    assert not bigrams


@pytest.mark.parametrize("gap", [" ", f"{COMMA} ", f"{SEMICOLON} ", " (", " latin "])
def test_the_builder_records_a_bigram_where_the_runtime_keeps_context(tmp_path, gap):
    _, bigrams = _counts(arabic, f"{KATABA}{gap}{DARASA}", tmp_path)
    assert list(bigrams) == [(KTB, DRS)]


# --- the runtime -------------------------------------------------------------


def test_a_word_the_corpus_saw_only_beside_punctuation_is_restored(tmp_path):
    corpus = f"{KATABA} {WALAD}{COMMA} ({KITABAN}) {JAMILAN}.\n"
    unigrams, bigrams = _counts(arabic, corpus, tmp_path)
    _compile(unigrams, bigrams, tmp_path)
    got = _ask(
        tmp_path, [KTABA, JMYLA, WLD, f"{WLD}{COMMA}", f"{KTB} {WLD}{COMMA} ({KTABA}) {JMYLA}."]
    )
    kitaban, jamilan = transliterate(KITABAN), transliterate(JAMILAN)
    walad, kataba = transliterate(WALAD), transliterate(KATABA)
    assert got[:4] == [kitaban, jamilan, walad, f"{walad},"]
    assert got[4] == f"{kataba} {walad}, ({kitaban}) {jamilan}."


@pytest.mark.parametrize(("mark", "ascii_mark"), [(QUESTION, "?"), (FULL_STOP, ".")])
def test_a_sentence_end_in_the_arabic_block_resets_the_context(tmp_path, mark, ascii_mark):
    unigrams = {KTB: Counter({KATABA: 1}), DRS: Counter({DARS: 5})}
    # The second key is what a dictionary built before this change holds for the same text.
    bigrams = {(KTB, DRS): Counter({DARASA: 5}), (f"{KTB}{mark}", DRS): Counter({DARASA: 5})}
    _compile(unigrams, bigrams, tmp_path)
    across, plain, control = _ask(
        tmp_path, [f"{KTB}{mark} {DRS}", f"{KTB} {DRS}", f"{KTB}{ascii_mark} {DRS}"]
    )
    assert plain.endswith("darasa"), "the bigram has to fire without a boundary"
    assert control.endswith("darsun")
    assert across.endswith("darsun")


@pytest.mark.parametrize("mark", [COMMA, SEMICOLON])
def test_a_comma_in_the_arabic_block_keeps_the_context(tmp_path, mark):
    unigrams = {KTB: Counter({KATABA: 1}), DRS: Counter({DARS: 5})}
    bigrams = {(KTB, DRS): Counter({DARASA: 5})}
    _compile(unigrams, bigrams, tmp_path)
    assert _ask(tmp_path, [f"{KTB}{mark} {DRS}"])[0].endswith("darasa")


# --- one definition ----------------------------------------------------------

#: Every block `is_arabic_char` or `is_hebrew_char` covers.
BLOCKS = [
    (0x0590, 0x05FF),
    (0x0600, 0x06FF),
    (0x0750, 0x077F),
    (0x08A0, 0x08FF),
    (0xFB1D, 0xFB4F),
    (0xFB50, 0xFDFF),
    (0xFE70, 0xFEFF),
]


def _block_code_points() -> list[int]:
    return [cp for low, high in BLOCKS for cp in range(low, high + 1)]


def test_the_runtime_and_the_builders_agree_on_every_code_point(tmp_path):
    """A word followed by `c` is restored exactly when the builder calls `c` a non-word."""
    (tmp_path / "arabic_dict.bin").write_bytes(trld_bytes({KTB: KATABA}))
    # A mark the skeleton removes leaves the lookup working, so it says nothing either way.
    removed = set(arabic.ARABIC_DIACRITICS) | {arabic.TATWEEL}
    cases = [cp for cp in _block_code_points() if chr(cp) not in removed]
    answers = _ask(tmp_path, [f"{KTB}{chr(cp)}" for cp in cases])
    differ = [
        f"U+{cp:04X}"
        for cp, answer in zip(cases, answers, strict=True)
        if answer.startswith("kataba") == words.is_word_char(chr(cp))
    ]
    assert not differ, differ


def test_no_punctuation_in_an_arabic_block_is_part_of_a_word():
    ranges = [block for block in BLOCKS if block not in {(0x0590, 0x05FF), (0xFB1D, 0xFB4F)}]
    punctuation = [
        cp
        for low, high in ranges
        for cp in range(low, high + 1)
        if unicodedata.category(chr(cp)).startswith("P")
    ]
    assert len(punctuation) >= 14, punctuation
    assert not [f"U+{cp:04X}" for cp in punctuation if words.is_word_char(chr(cp))]


def test_hebrew_marks_inside_a_word_stay_part_of_it():
    """Maqaf joins a compound, and geresh and gershayim sit inside words and acronyms."""
    for mark in ("\u05be", "\u05f3", "\u05f4"):
        assert words.is_word_char(mark), f"U+{ord(mark):04X}"


def test_the_two_builders_share_the_definition():
    assert arabic.word_runs is hebrew.word_runs
    assert arabic.is_context_boundary is hebrew.is_context_boundary
