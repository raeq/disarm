"""`lang="auto"` with `context=True` uses the dictionary of the language it detects (#1149).

The dictionary was chosen from the raw `lang` string, where "he" got Hebrew, "fa" Persian
and everything else Arabic, so "auto" always took the Arabic one. Detection ran later, per
token, once the choice had been made. Hebrew text came back context-free, and raised
`context dictionary for Arabic not found` when only the Hebrew dictionary was installed.

Each case runs in a subprocess, because dictionaries are loaded once per process and cached,
found or not. The dictionaries hold one word each, written by `conftest.trld_bytes`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import trld_bytes

KUTUB = ("\u0643\u062a\u0628", "\u0643\u064f\u062a\u064f\u0628")
SHALOM = ("\u05e9\u05dc\u05d5\u05dd", "\u05e9\u05b8\u05c1\u05dc\u05d5\u05b9\u05dd")
#: `\u067e` is Persian's own letter, so detection answers `fa` and not `ar`.
PEDAR = ("\u067e\u062f\u0631", "\u067e\u0650\u062f\u064e\u0631")
FILES = {"ar": "arabic_dict.bin", "he": "hebrew_dict.bin", "fa": "persian_dict.bin"}
WORDS = {"ar": KUTUB, "he": SHALOM, "fa": PEDAR}

PROBE = """
import json, sys
from disarm import DisarmError, inspect_auto_lang, transliterate
out = {}
for key, text, lang in json.loads(sys.argv[1]):
    try:
        out[key] = transliterate(text, lang=lang, context=True)
    except DisarmError as e:
        out[key] = "error: " + str(e)
print(json.dumps(out))
"""


def _ask(tmp_path: Path, installed: list[str], calls: list[tuple[str, str, str | None]]) -> dict:
    for code in installed:
        skeleton, form = WORDS[code]
        (tmp_path / FILES[code]).write_bytes(trld_bytes({skeleton: form}))
    env = {**os.environ, "DISARM_DICT_DIR": str(tmp_path)}
    run = subprocess.run(  # noqa: S603 - fixed argv; the probe is this module's own
        [sys.executable, "-c", PROBE, json.dumps(calls)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return json.loads(run.stdout)


@pytest.mark.parametrize("code", ["ar", "he", "fa"])
def test_auto_reads_the_dictionary_of_the_language_it_detects(tmp_path, code):
    skeleton = WORDS[code][0]
    got = _ask(
        tmp_path,
        ["ar", "he", "fa"],
        [("auto", skeleton, "auto"), ("explicit", skeleton, code), ("free", skeleton, None)],
    )
    assert got["auto"] == got["explicit"]


def test_hebrew_is_restored_and_not_read_as_context_free(tmp_path):
    got = _ask(tmp_path, ["ar", "he"], [("auto", SHALOM[0], "auto")])
    assert got["auto"] == "shalom"


def test_auto_needs_only_the_dictionary_it_detects(tmp_path):
    got = _ask(tmp_path, ["he"], [("auto", SHALOM[0], "auto")])
    assert got["auto"] == "shalom"


def test_a_missing_dictionary_is_named_for_the_language_detected(tmp_path):
    # A build also searches its own source tree, so one that holds this file cannot miss it.
    if (Path(__file__).resolve().parent.parent / "data" / FILES["he"]).exists():
        pytest.skip("this checkout's data/ holds the Hebrew dictionary")
    got = _ask(tmp_path, ["ar"], [("auto", SHALOM[0], "auto"), ("explicit", SHALOM[0], "he")])
    assert "Hebrew" in got["auto"]
    assert got["auto"] == got["explicit"]


def test_a_pointed_word_is_looked_up_by_its_own_skeleton(tmp_path):
    """Stripping chose Arabic marks for anything but "he", so niqqud stayed on the key."""
    got = _ask(tmp_path, ["he"], [("auto", SHALOM[1], "auto"), ("explicit", SHALOM[1], "he")])
    assert got["auto"] == got["explicit"]


def test_arabic_is_unchanged(tmp_path):
    got = _ask(tmp_path, ["ar"], [("auto", KUTUB[0], "auto"), ("explicit", KUTUB[0], "ar")])
    assert got["auto"] == got["explicit"] == "kutub"


def test_text_with_no_detected_language_behaves_as_no_language(tmp_path):
    got = _ask(tmp_path, ["ar"], [("auto", "hello", "auto"), ("none", "hello", None)])
    assert got["auto"] == got["none"] == "hello"


def test_a_list_detects_item_by_item(tmp_path):
    (tmp_path / FILES["ar"]).write_bytes(trld_bytes({KUTUB[0]: KUTUB[1]}))
    (tmp_path / FILES["he"]).write_bytes(trld_bytes({SHALOM[0]: SHALOM[1]}))
    probe = (
        "import json, sys\n"
        "from disarm import transliterate\n"
        "print(json.dumps(transliterate(json.loads(sys.argv[1]), lang='auto', context=True)))\n"
    )
    run = subprocess.run(  # noqa: S603 - fixed argv; the probe is this module's own
        [sys.executable, "-c", probe, json.dumps([KUTUB[0], SHALOM[0]])],
        env={**os.environ, "DISARM_DICT_DIR": str(tmp_path)},
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert json.loads(run.stdout) == ["kutub", "shalom"]
