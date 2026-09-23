"""`transliterate(..., context=True)` transliterates what is not an Arabic or Hebrew word.

The context engine tokenises into Arabic/Hebrew words and everything else, and
appended the "everything else" raw. So `context=True` returned `\u00e9` and `\u5317\u4eac`
unchanged where the context-free path returns ASCII, a Persian ZWNJ and Hebrew
bidi marks leaked into the output, and `errors=` never applied to any of it. The
docstring promises an ASCII transliteration, and I2 is stated for every string;
the Lean audit of that claim is what found it (`formal/lean/Transliterate`).

The context tests elsewhere skip without the built dictionaries, which are not
committed, so this one writes a minimal valid `TRLD` v1 dictionary itself. Its
content is incidental: the defect is in how non-word spans are handled, which
never consults the dictionary. It runs in a subprocess because the dictionaries
are loaded once per process and cached, found or not.
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from pathlib import Path


def _s16(s: str) -> bytes:
    b = s.encode("utf-8")
    return struct.pack("<H", len(b)) + b


def _dict_bytes(unigrams: dict[str, str]) -> bytes:
    """TRLD v1: a 24-byte header, the unigram records, no bigrams."""
    body = b"".join(
        _s16(skel) + struct.pack("<H", 1) + _s16(form) + struct.pack("<I", 1)
        for skel, form in sorted(unigrams.items())
    )
    header = b"TRLD" + struct.pack("<5I", 1, len(unigrams), 0, 24, 24 + len(body))
    return header + body


CASES = [
    # (text, lang, errors)
    ("\u00e9", "ar", "ignore"),
    ("\u5317\u4eac", "he", "ignore"),
    ("\u0645\u0631\u062d\u0628\u0627 \u00e9", "ar", "ignore"),
    ("\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645", "fa", "ignore"),
    ("\u200f\u05e9\u05dc\u05d5\u05dd\u200f", "he", "ignore"),
    ("\u5317\u4eac", "ar", "replace"),
]

PROBE = """
import json, sys
from disarm import transliterate
out = []
for text, lang, errors in json.loads(sys.argv[1]):
    out.append([
        transliterate(text, lang=lang, context=True, errors=errors),
        transliterate(text, lang=lang, errors=errors),
    ])
print(json.dumps(out))
"""


def test_context_output_matches_the_context_free_path_off_the_words(tmp_path: Path) -> None:
    for name, entries in {
        "arabic_dict.bin": {"\u0643\u062a\u0628": "\u0643\u064e\u062a\u064e\u0628\u064e"},
        "persian_dict.bin": {"\u0633\u0644\u0627\u0645": "\u0633\u064e\u0644\u0627\u0645"},
        "hebrew_dict.bin": {"\u05e9\u05dc\u05d5\u05dd": "\u05e9\u05dc\u05d5\u05dd"},
    }.items():
        (tmp_path / name).write_bytes(_dict_bytes(entries))

    env = {**os.environ, "DISARM_DICT_DIR": str(tmp_path)}
    run = subprocess.run(
        [sys.executable, "-c", PROBE, json.dumps(CASES)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    for (text, lang, errors), (with_context, without) in zip(
        CASES, json.loads(run.stdout), strict=True
    ):
        # None of these words is in the dictionary, so context=True has nothing
        # to add and must agree with the context-free path exactly.
        assert with_context == without, (text, lang, errors, with_context, without)
        if errors == "ignore":
            assert with_context.isascii(), (text, lang, with_context)
