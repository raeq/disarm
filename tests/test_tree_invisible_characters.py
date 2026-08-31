"""#802 — "escapes, never literals" for the tree, not just `README.md`.

`tests/test_readme_invisible_characters.py` enforces this rule on one file. Its docstring
already makes the argument, and records that the defect it guards against **shipped once**:
a literal `U+202E` in a README example reached GitHub, crates.io and PyPI reading as a
tautology. Everything that argument says about `README.md` is true of every other file in
the repository, and until now nothing checked them.

Measured on `main`: 330 literal invisible characters across the tree, 103 of them bidi
controls — the mechanism of CVE-2021-42574, in the repository of the library that detects
it. The sharpest were the Trojan Source test constants themselves, stored with literal
`U+202E`, so what a reviewer saw in an editor, in `git diff` and in the GitHub blob view
was the *reordered* form rather than the one Python parses. A construction whose entire
point is that display order and logical order disagree was stored in the form that
disagrees.

**The classes want different answers, which is why this is not a one-line lint.**

- **Bidi controls** reorder the surrounding source in an editor and in a diff. There is no
  legitimate literal use of one anywhere in this repository — every occurrence is test data
  or a documented attack string, and every one reads correctly as `\\u202e`. Never allowed.
- **Other invisibles** — ZWSP, `U+FEFF`, word joiner, soft hyphen — are worse in one way:
  a reviewer cannot see them at all. Never allowed.
- **`U+200D` ZERO WIDTH JOINER** is the exception, and it is exempted by a *mechanical*
  test rather than by judgement: a ZWJ that joins two `Extended_Pictographic` code points
  is emoji sequencing, and a page about grapheme clusters has to show a family emoji
  rendering as one glyph. `docs/user-guide/graphemes.md` alone holds 43 of them. Writing
  those as escapes makes the documentation worse without making anything safer. A ZWJ that
  is *not* between two pictographs gets no exemption — that is the smuggling case.

The exemptions live in one reviewed list here rather than in per-file pragmas, the same
line the README guard draws for homoglyphs: this test takes the half a machine can settle.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Newline, tab and carriage return are `Cc`, and are simply how a text file is written.
ALLOWED = frozenset("\n\t\r")

#: The suffixes the README guard's argument applies to — anything a reviewer reads.
SUFFIXES = frozenset(".py .rs .md .rb .mjs .ts .java .kt .toml .yml .yaml .sh .c .h".split())

#: Directories that are not ours to police.
#: Not ours to police. `tmp` is where `rake compile` stages a copy of the gem, so a
#: converted file there is a build artifact that reappears on the next compile.
SKIP = frozenset(
    {".git", "target", "node_modules", ".venv", "vendor", "build", ".gradle", "tmp", "pkg"}
)

#: UAX #9 explicit formatting characters, plus the two marks. Every one reorders text.
BIDI = frozenset("\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")

ZWJ = "\u200d"
ZWNJ = "\u200c"

#: Scripts where `U+200D`/`U+200C` are *orthography*, not smuggling.
#:
#: Found while converting the tree, and not in #802's classification: `docs/reference.md`
#: spells Sinhala `\u0dc1\u0dca\u200d\u0dbb\u0dd3` — the ZWJ forms the conjunct, and
#: writing it as an escape breaks the language sample the page exists to show. The Persian
#: ezafe in `docs/user-guide/abjad-transliteration.md` is the same with ZWNJ. The emoji
#: rule alone would have failed both, which is exactly the "gate becomes a nuisance"
#: outcome #802 §3 warns about — so the exemption is widened by measurement rather than by
#: adding pragmas to two files.
#:
#: Ranges rather than a script-property lookup because `unicodedata` exposes no script;
#: they cover the Indic blocks and the Arabic-script blocks, and nothing else. Latin,
#: Greek and Cyrillic are deliberately absent: `ad\u200dmin` is the smuggling case, and it
#: must stay a failure.
JOINING_SCRIPTS = (
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0x0900, 0x0DFF),  # Devanagari .. Sinhala
    (0x0E00, 0x0E7F),  # Thai
    (0x0F00, 0x0FFF),  # Tibetan
    (0x1000, 0x109F),  # Myanmar
    (0x1780, 0x17FF),  # Khmer
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
)

#: Files exempt from the whole rule, each with a reason. Deliberately short.
EXEMPT_FILES = {
    # The guard's own can-it-fail probe builds a literal on purpose — it has to, or the
    # probe proves nothing. #794 fixed the version of this that pasted the payload in
    # source rather than constructing it, which is why the rule is "constructed, not
    # pasted" rather than "absent".
    "tests/test_readme_invisible_characters.py",
    "tests/test_tree_invisible_characters.py",
}


def _is_pictographic(char: str) -> bool:
    """`Extended_Pictographic`, approximated by the ranges emoji sequences actually use.

    `unicodedata` does not expose the property, and pulling in a dependency to answer it
    inside a lint would be worse than an approximation whose failure mode is *stricter*
    than the real property: a code point wrongly excluded here loses its exemption and has
    to be written as an escape, which is the safe direction.
    """
    cp = ord(char)
    return (
        0x1F300 <= cp <= 0x1FAFF  # Misc Symbols and Pictographs .. Symbols Extended-A
        or 0x2600 <= cp <= 0x27BF  # Misc Symbols, Dingbats
        or 0x1F000 <= cp <= 0x1F2FF  # Mahjong .. Enclosed Ideographic Supplement
        or 0x2B00 <= cp <= 0x2BFF  # Misc Symbols and Arrows
        or cp in {0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139}
        or 0x2190 <= cp <= 0x21FF
        or 0x3030 <= cp <= 0x303D
        or 0x1F1E6 <= cp <= 0x1F1FF  # regional indicators
    )


def _exempt_zwj(text: str, index: int) -> bool:
    """A ZWJ between two pictographs is emoji sequencing, not smuggling.

    Skin-tone modifiers and variation selectors sit between the joiner and the base in a
    well-formed sequence, so they are stepped over rather than treated as the neighbour.
    """
    if text[index] != ZWJ:
        return False

    def neighbour(start: int, step: int) -> str | None:
        pos = start
        while 0 <= pos < len(text):
            char = text[pos]
            if char in {"\ufe0f", "\ufe0e"} or 0x1F3FB <= ord(char) <= 0x1F3FF:
                pos += step
                continue
            return char
        return None

    before = neighbour(index - 1, -1)
    after = neighbour(index + 1, 1)
    return bool(before and after and _is_pictographic(before) and _is_pictographic(after))


def _in_joining_script(char: str) -> bool:
    cp = ord(char)
    return any(low <= cp <= high for low, high in JOINING_SCRIPTS)


def _exempt_orthographic_joiner(text: str, index: int) -> bool:
    """A joiner between two letters of a script that requires one is orthography."""
    if text[index] not in {ZWJ, ZWNJ}:
        return False
    before = text[index - 1] if index > 0 else ""
    after = text[index + 1] if index + 1 < len(text) else ""
    return bool(
        before
        and after
        and _in_joining_script(before)
        and _in_joining_script(after)
        and unicodedata.category(before).startswith(("L", "M"))
        and unicodedata.category(after).startswith(("L", "M"))
    )


def _classify(char: str) -> str:
    if char in BIDI:
        return "bidi control"
    if char == ZWJ:
        return "zero width joiner"
    return "invisible"


def literal_invisibles(text: str) -> list[tuple[int, int, str, str]]:
    """Every disallowed literal, as `(line, column, char, class)`.

    The exemption is applied here rather than at the call site so a caller cannot forget
    it, and so the ZWJ rule is stated once.
    """
    offenders: list[tuple[int, int, str, str]] = []
    offset = 0
    for line_no, line in enumerate(text.split("\n"), 1):
        for col, char in enumerate(line, 1):
            if char in ALLOWED or unicodedata.category(char) not in {"Cf", "Cc"}:
                continue
            position = offset + col - 1
            if char == ZWJ and _exempt_zwj(text, position):
                continue
            if _exempt_orthographic_joiner(text, position):
                continue
            offenders.append((line_no, col, char, _classify(char)))
        offset += len(line) + 1
    return offenders


def _sources() -> list[Path]:
    out = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in SUFFIXES:
            continue
        if any(part in SKIP for part in path.parts):
            continue
        if str(path.relative_to(ROOT)) in EXEMPT_FILES:
            continue
        out.append(path)
    return sorted(out)


SOURCES = _sources()


def test_the_corpus_is_not_empty() -> None:
    """A gate over an empty corpus passes for the wrong reason."""
    assert len(SOURCES) > 200, len(SOURCES)


def _offenders(kinds: set[str]) -> list[str]:
    found = []
    for path in SOURCES:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, col, char, kind in literal_invisibles(text):
            if kind in kinds:
                found.append(
                    f"{path.relative_to(ROOT)}:{line_no}:{col}: "
                    f"U+{ord(char):04X} {unicodedata.name(char, 'unnamed')} ({kind})"
                )
    return found


def test_no_literal_bidi_controls_anywhere() -> None:
    """The half worth landing even if nothing else is.

    Every one of these reorders the source around it, so a reviewer reading a diff sees
    something other than what the parser sees. That is CVE-2021-42574, and the repository
    carried 103 of them.
    """
    offenders = _offenders({"bidi control"})
    assert not offenders, (
        "literal bidi controls found. Each one reorders the source around it in an "
        "editor and in a diff, so what a reviewer reads is not what the parser reads. "
        "Write them as \\uXXXX escapes:\n  " + "\n  ".join(offenders)
    )


def test_no_literal_invisibles_anywhere() -> None:
    """The other class: a reviewer cannot see these at all."""
    offenders = _offenders({"invisible"})
    assert not offenders, (
        "literal invisible characters found. They render as nothing, so the example "
        "teaches nothing and the file carries the payload it demonstrates. Write them "
        "as \\uXXXX escapes and name the code point:\n  " + "\n  ".join(offenders)
    )


def test_no_unexplained_zero_width_joiners() -> None:
    """A ZWJ outside an emoji sequence has no rendering purpose — it is smuggling."""
    offenders = _offenders({"zero width joiner"})
    assert not offenders, (
        "zero width joiners that do not join two pictographs. Inside an emoji sequence "
        "a literal ZWJ is correct and exempt; anywhere else it is invisible smuggling. "
        "Write these as \\u200d:\n  " + "\n  ".join(offenders)
    )


# ── the gate has to be able to fail, and the exemption has to be real ────────


def test_the_check_can_actually_fail() -> None:
    """Constructed, never pasted — the #794 lesson, applied to this file too."""
    payload = "example" + chr(0x202E) + chr(0x200B) + ".com"
    found = literal_invisibles(payload)
    assert [(char, kind) for _, _, char, kind in found] == [
        (chr(0x202E), "bidi control"),
        (chr(0x200B), "invisible"),
    ]


def test_an_emoji_zwj_sequence_is_exempt() -> None:
    """The family emoji `docs/user-guide/graphemes.md` needs, rendering as one glyph."""
    family = chr(0x1F469) + chr(0x200D) + chr(0x1F469) + chr(0x200D) + chr(0x1F467)
    assert literal_invisibles(family) == []


def test_an_orthographic_joiner_is_exempt() -> None:
    """Sinhala needs the ZWJ to form a conjunct; Persian needs the ZWNJ for the ezafe.

    Both are real content on pages that exist to show the script. Written as escapes the
    sample stops being the language.
    """
    sinhala = "\u0dc1\u0dca\u200d\u0dbb\u0dd3"  # ශ්‍රී — "Sri", with the conjunct
    assert literal_invisibles(sinhala) == []
    persian = "\u062e\u0627\u0646\u0647\u200c\u0647\u0627"  # خانه‌ها — houses
    assert literal_invisibles(persian) == []


def test_a_zwj_between_letters_is_not_exempt() -> None:
    """The smuggling case the exemption must not cover."""
    found = literal_invisibles("ad" + chr(0x200D) + "min")
    assert [kind for _, _, _, kind in found] == ["zero width joiner"]


def test_the_variation_selector_is_stepped_over() -> None:
    """A well-formed sequence puts VS16 between the base and the joiner."""
    heart_people = (
        chr(0x1F469) + chr(0x200D) + chr(0x2764) + chr(0xFE0F) + chr(0x200D) + chr(0x1F468)
    )
    kinds = [kind for _, _, _, kind in literal_invisibles(heart_people)]
    assert "zero width joiner" not in kinds, kinds


def test_escapes_inside_a_rust_fence_use_rust_syntax() -> None:
    """`\\uXXXX` is Python and JavaScript; Rust needs `\\u{XXXX}`.

    Converting the tree wrote `\\u200b` into a ```rust block in
    `docs/user-guide/llm-pipelines.md`, which is not valid Rust. Nothing in the Python
    suite compiles those blocks — `scripts/check_doc_rust_examples.py` does, and it is a
    separate CI job — so the mistake was invisible here and red there.

    The rule is per fence language, so it belongs beside the rule that produced the
    escapes rather than in the Rust checker.
    """
    import re

    offenders = []
    for path in SOURCES:
        if path.suffix != ".md":
            continue
        language: str | None = None
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if line.strip().startswith("```"):
                language = (line.strip()[3:].strip() or None) if language is None else None
                continue
            if language in {"rust", "rs"} and re.search(r"\\u[0-9a-fA-F]{4}(?!\})", line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()[:70]}")
    assert not offenders, (
        "Rust code blocks must spell an escape `\\u{XXXX}`, not `\\uXXXX`:\n  "
        + "\n  ".join(offenders)
    )
