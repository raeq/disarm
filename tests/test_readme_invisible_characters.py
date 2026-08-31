"""The README spells invisible characters as escapes, never as literals.

The README's examples exist to show Unicode attacks — a bidi override, a
zero-width space, a homoglyph. Pasted as *literal* characters they render as
nothing, so ``canonicalize("\\u202eexample\\u200b.com") == "example.com"`` reached
GitHub, crates.io and PyPI reading ``canonicalize("example.com") == "example.com"``:
a tautology on the page, and a Trojan Source demonstration on the front page of a
library that exists to catch them. It has happened once, which is once more than a
convention prevents.

Format (``Cf``) and control (``Cc``) characters are invisible by construction, so
the rule is mechanical and this test enforces it: none may appear literally in
``README.md``. Write ``\\u202e`` and let the reader see the codepoint.
``docs/index.md`` is generated from this file, so a clean source keeps the docs
site clean too.

Homoglyphs are deliberately **not** covered here. Cyrillic and Greek letters are
legitimate content — ``Київ`` is real text, and the opening hook needs its Cyrillic
``а`` to render as ``a`` or the hook does not work — so no mechanical rule
separates a spoof from a sentence. That judgement stays with the reviewer; this
test takes the half a machine can settle.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"

#: Newline and tab are ``Cc``, and are simply how a text file is written.
_ALLOWED = frozenset("\n\t")


def _literal_invisibles(text: str) -> list[tuple[int, int, str]]:
    """Every ``Cf``/``Cc`` character in ``text``, as ``(line, column, char)``."""
    return [
        (line_no, col, char)
        for line_no, line in enumerate(text.splitlines(), 1)
        for col, char in enumerate(line, 1)
        if char not in _ALLOWED and unicodedata.category(char) in {"Cf", "Cc"}
    ]


def test_readme_has_no_literal_invisible_characters() -> None:
    offenders = _literal_invisibles(README.read_text(encoding="utf-8"))
    assert not offenders, (
        "README.md contains invisible characters written literally. They render as "
        "nothing, so the example teaches nothing and the file itself carries the "
        "payload it is meant to demonstrate. Write each one as a \\uXXXX escape and "
        "name the codepoint in a comment:\n"
        + "\n".join(
            f"  line {line_no}, column {col}: U+{ord(char):04X} {unicodedata.name(char, 'unnamed')}"
            for line_no, col, char in offenders
        )
    )


def test_the_check_can_actually_fail() -> None:
    """A gate that only ever passes is not a gate.

    Uses a synthetic sample rather than perturbing README.md, so a crash between
    perturb and restore cannot leave the working tree dirty.
    """
    # Built with chr() rather than pasted: a literal U+202E here would put the
    # very payload this test rejects into the repository, one file over from the
    # one being guarded.
    sample = f'assert canonicalize("{chr(0x202E)}example{chr(0x200B)}.com")'
    found = _literal_invisibles(sample)
    assert [f"U+{ord(char):04X}" for _, _, char in found] == ["U+202E", "U+200B"]
    assert not _literal_invisibles('assert canonicalize("\\u202eexample\\u200b.com")')
