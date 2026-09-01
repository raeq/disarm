"""#819 — the script table may decline to answer; it may not give a different answer.

`detect_char_script` binary-searches a curated table of **block** ranges. A block is not a
script, and the difference produces two outcomes that look alike in a bug report and are
not alike at all:

* **declining** — the table names no script for a code point whose UCD script it otherwise
  covers. 11,893 of these, mostly CJK and other extension blocks. That is the curated
  61-script scope, and it costs a caller a missed detection.
* **contradicting** — the table names a *different* script than the UCD. Wrong under any
  curation policy. #819 found 33, and nineteen resolved to `Latin`, so a non-Latin letter
  beside ASCII read as single-script and `is_mixed_script` could not fire.

Nothing separated them before this file. `tests/fixtures/ucd_script_ranges.tsv` is the
independent data — without it the only available comparison is the table against itself,
which is the failure [[drift-gate-must-not-reference-drifting-thing]] describes.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

import disarm

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "ucd_script_ranges.tsv"

#: The count of declines at the time #819 was closed. A floor, not an equality: closing
#: more of them is progress and must not fail this file. A sharp *rise* would mean the
#: table lost coverage, which is what the ceiling catches.
DECLINES_WHEN_819_CLOSED = 12_541

#: `Script=Inherited` is the one disagreement that is a decision rather than a defect.
#:
#: It means "take the script of the preceding character", which a static range table
#: cannot do — there is no preceding character at lookup time. So the table names the
#: script of the block the mark lives in, which is what makes `is_mixed_script` useful on
#: Arabic or Cyrillic text carrying its own marks: an Arabic fatha inside Arabic text is
#: not evidence of script mixing.
#:
#: The exemption is checked rather than assumed — `test_the_inherited_exemption_is_real`
#: asserts every code point using it is actually a combining mark, so it cannot quietly
#: cover a genuine disagreement.
CONTEXT_DEPENDENT = "Inherited"


def ucd_scripts() -> dict[int, str]:
    out: dict[int, str] = {}
    for raw in FIXTURE.read_text(encoding="utf-8").splitlines():
        if not raw or raw.startswith("#"):
            continue
        start, end, script = raw.split("\t")
        for cp in range(int(start, 16), int(end, 16) + 1):
            out[cp] = script
    return out


def table_script(cp: int) -> str | None:
    found = disarm.detect_scripts(chr(cp))
    return found[0].name.title() if found else None


def census() -> tuple[list[tuple[int, str, str]], list[int]]:
    """`(contradictions, declines)` over every code point in the fixture."""
    contradictions: list[tuple[int, str, str]] = []
    declines: list[int] = []
    for cp, expected in ucd_scripts().items():
        actual = table_script(cp)
        if actual is None:
            declines.append(cp)
        elif actual != expected and expected != CONTEXT_DEPENDENT:
            contradictions.append((cp, expected, actual))
    return contradictions, declines


def test_the_table_never_contradicts_the_ucd() -> None:
    """The gate #819 asked for. Declining is a scope; disagreeing is a defect."""
    contradictions, _ = census()
    formatted = [
        f"U+{cp:04X} {unicodedata.name(chr(cp), '?')}: UCD says {expected}, table says {actual}"
        for cp, expected, actual in contradictions[:12]
    ]
    assert not contradictions, (
        f"{len(contradictions)} code points where the table names a different script "
        f"than the UCD:\n  " + "\n  ".join(formatted)
    )


def test_the_inherited_exemption_is_real() -> None:
    """Every code point the exemption covers must actually be a combining mark.

    Otherwise `Script=Inherited` becomes a hole a real disagreement can sit in. The whole
    argument for the exemption is that these marks take their script from context, and
    a character that is not a mark takes nothing from anywhere.
    """
    covered_by_exemption = [
        cp
        for cp, expected in ucd_scripts().items()
        if expected == CONTEXT_DEPENDENT
        and (actual := table_script(cp)) is not None
        and actual != expected
    ]
    assert covered_by_exemption, (
        "nothing uses the Inherited exemption any more; if the table now reports these "
        "as Inherited the exemption should be removed rather than left standing"
    )
    not_a_mark = [
        f"U+{cp:04X} {unicodedata.name(chr(cp), '?')} is {unicodedata.category(chr(cp))}"
        for cp in covered_by_exemption
        if unicodedata.category(chr(cp)) not in {"Mn", "Mc", "Me"}
    ]
    assert not not_a_mark, (
        "the Inherited exemption is covering code points that are not combining marks, "
        "so it is hiding a real disagreement:\n  " + "\n  ".join(not_a_mark)
    )


def test_a_mark_takes_the_script_of_the_block_it_lives_in() -> None:
    """The behaviour the exemption exists for, stated as an example.

    An Arabic fatha inside Arabic text must not read as script mixing.
    """
    assert not disarm.is_mixed_script("\u0645\u064e")  # Arabic meem + fatha
    assert not disarm.is_mixed_script("\u0430\u0485")  # Cyrillic a + dasia pneumata


def test_the_declines_are_a_scope_and_have_not_grown() -> None:
    """The other half, as a ceiling.

    Closing declines is progress and must not fail — this is not an equality. But a rise
    means the table lost coverage, which no change should do quietly.
    """
    _, declines = census()
    assert len(declines) <= DECLINES_WHEN_819_CLOSED, (
        f"the table now declines {len(declines)} code points whose script it covers, up "
        f"from {DECLINES_WHEN_819_CLOSED} when #819 closed — coverage went backwards"
    )


@pytest.mark.parametrize(
    ("char", "expected"),
    [
        ("Ϣ", "COPTIC"),  # COPTIC CAPITAL LETTER SHEI, inside the Greek block
        ("ᴦ", "GREEK"),  # GREEK LETTER SMALL CAPITAL GAMMA, in Phonetic Extensions
        ("ᴫ", "CYRILLIC"),  # CYRILLIC LETTER SMALL CAPITAL EL
        ("ᵸ", "CYRILLIC"),  # MODIFIER LETTER CYRILLIC EN
        ("ᶿ", "GREEK"),  # MODIFIER LETTER SMALL THETA
        ("ꭥ", "GREEK"),  # GREEK LETTER SMALL CAPITAL OMEGA, in Latin Extended-E
    ],
)
def test_the_named_contradictions_resolve_correctly(char: str, expected: str) -> None:
    """One per group, by name, so a failure says which block regressed."""
    assert [s.name for s in disarm.detect_scripts(char)] == [expected]


def test_the_nineteen_no_longer_pass_a_mixed_script_check() -> None:
    """The consequence that made this a defect rather than an inaccuracy.

    Nineteen of the contradictions resolved to `Latin`, so a token mixing one with ASCII
    read as single-script. This is the whole reason the census matters to a caller.
    """
    for char in ("ᴦ", "ᴫ", "ᵝ", "ᵦ", "ᵸ", "ꭥ"):
        assert disarm.is_mixed_script(f"a{char}"), (
            f"U+{ord(char):04X} is a non-Latin letter and still reads as single-script beside ASCII"
        )
    # The control: ordinary Cyrillic, which always worked.
    assert disarm.is_mixed_script("aГ")


def test_the_fixture_is_independent_of_the_table() -> None:
    """A gate built from the thing it checks proves nothing.

    The fixture is generated from `Scripts.txt`; only its *scope* comes from
    `src/scripts.rs`. If it were derived from the table's own ranges this whole file
    would be a tautology, so the shape is asserted rather than trusted.
    """
    header = FIXTURE.read_text(encoding="utf-8").split("\n", 4)
    assert "Scripts.txt" in header[0]
    assert "17.0.0" in header[0]
    scripts = {script for _, script in ucd_scripts().items()}
    assert len(scripts) > 50, "the fixture covers implausibly few scripts"
    # Ranges that the table would never produce, because they are UCD script spans
    # rather than block spans: Coptic appears in two disjoint places.
    coptic = sorted(cp for cp, s in ucd_scripts().items() if s == "Coptic")
    assert coptic[0] < 0x0400 and coptic[-1] > 0x2C00, (
        "the fixture no longer records Coptic on both sides of the Greek block, which is "
        "the case that distinguishes UCD script data from block data"
    )
