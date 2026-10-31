"""Persian `context=True` falls back to the Arabic dictionary, as the guide says (#1148).

The guide and the Persian builder both say that a word missing from the curated vocabulary
falls back to the Arabic dictionary. The code picked one dictionary per call, and read the
Arabic one only when no Persian file existed. So with both installed, which is what
`bootstrap_dicts.sh` produces, an Arabic-origin loanword came back context-free.

Each case runs in a subprocess, because dictionaries are loaded once per process and cached.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import trld_bytes

SALAM = ("\u0633\u0644\u0627\u0645", "\u0633\u064e\u0644\u0627\u0645")
KTB = ("\u0643\u062a\u0628", "\u0643\u064f\u062a\u064f\u0628")
#: The word in the Persian vocabulary, with a reading of its own in the Arabic dictionary.
SHARED = "\u0645\u0646"
PERSIAN_READING = "\u0645\u064e\u0646"
ARABIC_READING = "\u0645\u0650\u0646"
UNKNOWN = "\u062a\u0633\u062a\u0627\u062c\u0633\u0631"

PROBE = """
import json, sys
from disarm import DisarmError, transliterate
out = []
for text, lang, context in json.loads(sys.argv[1]):
    try:
        out.append(transliterate(text, lang=lang, context=context))
    except DisarmError as e:
        out.append("error: " + str(e))
print(json.dumps(out))
"""


def _ask(tmp_path: Path, files: dict[str, bytes], calls: list[list]) -> list[str]:
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    run = subprocess.run(  # noqa: S603 - fixed argv; the probe is this module's own
        [sys.executable, "-c", PROBE, json.dumps(calls)],
        env={**os.environ, "DISARM_DICT_DIR": str(tmp_path)},
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return json.loads(run.stdout)


PERSIAN = trld_bytes({SALAM[0]: SALAM[1], SHARED: PERSIAN_READING})
ARABIC = trld_bytes({KTB[0]: KTB[1], SHARED: ARABIC_READING})
BOTH = {"persian_dict.bin": PERSIAN, "arabic_dict.bin": ARABIC}


def test_a_word_the_persian_vocabulary_lacks_comes_from_the_arabic_dictionary(tmp_path):
    with_fallback, free = _ask(tmp_path, BOTH, [[KTB[0], "fa", True], [KTB[0], "fa", False]])
    assert with_fallback == "kotob"
    assert with_fallback != free


def test_the_persian_vocabulary_wins_where_both_have_the_word(tmp_path):
    got, reading = _ask(tmp_path, BOTH, [[SHARED, "fa", True], [PERSIAN_READING, "fa", False]])
    assert got == reading


def test_a_word_in_neither_dictionary_is_context_free(tmp_path):
    got, free = _ask(tmp_path, BOTH, [[UNKNOWN, "fa", True], [UNKNOWN, "fa", False]])
    assert got == free


def test_the_persian_dictionary_alone_still_works(tmp_path):
    got, free = _ask(
        tmp_path,
        {"persian_dict.bin": PERSIAN, "arabic_dict.bin": trld_bytes({})},
        [[KTB[0], "fa", True], [KTB[0], "fa", False]],
    )
    assert got == free


def test_the_arabic_dictionary_alone_still_works(tmp_path):
    if (Path(__file__).resolve().parent.parent / "data" / "persian_dict.bin").exists():
        pytest.skip("this checkout's data/ holds the Persian dictionary")
    assert _ask(tmp_path, {"arabic_dict.bin": ARABIC}, [[KTB[0], "fa", True]]) == ["kotob"]


def test_a_corrupt_arabic_dictionary_is_reported_and_not_read_as_absent(tmp_path):
    got = _ask(
        tmp_path,
        {"persian_dict.bin": PERSIAN, "arabic_dict.bin": b"not a dictionary"},
        [[KTB[0], "fa", True]],
    )
    assert got[0].startswith("error: ")
    assert "corrupt" in got[0].lower() or "invalid" in got[0].lower()


def test_arabic_and_hebrew_read_only_their_own_dictionary(tmp_path):
    got = _ask(tmp_path, BOTH, [[SALAM[0], "ar", True], [SALAM[0], "ar", False]])
    assert got[0] == got[1]


def test_the_builder_docstring_names_what_the_builder_reads():
    source = (Path(__file__).resolve().parent.parent / "scripts/build_persian_dict.py").read_text(
        encoding="utf-8"
    )
    head = source.split('"""')[1]
    assert "appear in the Arabic Tashkeela corpus" not in head
    assert "expansion" not in head
    assert "Wiktionary" in head


def test_the_guide_counts_the_vocabulary_the_builder_holds(tmp_path):
    root = Path(__file__).resolve().parent.parent
    stats = tmp_path / "stats.json"
    subprocess.run(  # noqa: S603 - fixed argv; the builder is this repository's own
        [
            sys.executable,
            str(root / "scripts/build_persian_dict.py"),
            "-o",
            str(tmp_path / "persian_dict.bin"),
            "--json-stats",
            str(stats),
        ],
        capture_output=True,
        check=True,
        timeout=60,
    )
    entries = json.loads(stats.read_text(encoding="utf-8"))["vocab_entries"]
    page = (root / "docs/user-guide/abjad-transliteration.md").read_text(encoding="utf-8")
    assert f"Curated vocabulary \u2014 {entries} common words" in page
    assert f"{entries} curated entries" in page
