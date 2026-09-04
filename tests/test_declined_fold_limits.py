"""The two limits of the confusable fold that 0.16.0 decided to keep (#848, #836).

Both were weighed and declined, and both are the kind of limit that reads as an oversight
unless it is written down and tested. `docs/limitations.md` carries the prose; this pins the
behaviour, so the page cannot describe a library that has since changed underneath it.

**#848 — the fold is cross-script by construction.** `scripts/gen_confusables.py` drops a
TR39 class whose members are all in one script. Keheh and kaf share a class and stay apart,
because which of them is "the same letter" is a language question and the fold takes a
target script, not a language.

**#836 — the fold keys on single code points.** A base plus a combining mark cannot be a
source at all, so six Latin pairs where a tilde and a macron disagree about precomposition
survive as written.
"""

from __future__ import annotations

import pytest

import disarm

#: Both members of a single TR39 equivalence class, one script (#848).
SAME_SCRIPT = [
    ("ک", "ك", "Arabic: keheh and kaf"),
    ("ي", "ی", "Arabic: yeh and farsi yeh"),
]

#: The six pairs where the two spellings differ in code-point count (#836).
BASE_PLUS_MARK = [
    ("G̃", "Ḡ"),
    ("g̃", "ḡ"),
    ("Ñ", "N̄"),
    ("ñ", "n̄"),
    ("Ṽ", "V̄"),
    ("ṽ", "v̄"),
]


@pytest.mark.parametrize(("a", "b", "why"), SAME_SCRIPT, ids=[c[2] for c in SAME_SCRIPT])
def test_a_same_script_pair_is_not_folded_together(a: str, b: str, why: str) -> None:
    assert disarm.canonicalize(a) != disarm.canonicalize(b), why
    assert disarm.normalize_confusables(a) != disarm.normalize_confusables(b), why


def _tr39_prototype(ch: str) -> str:
    """The prototype `confusables.txt` maps `ch` to, or `ch` itself if it is one.

    Read from the vendored upstream file rather than from disarm's generated tables: the
    claim being checked is about TR39's grouping, and checking it against a table disarm
    derived would make the assertion circular.
    """
    import re
    from pathlib import Path

    row = re.compile(r"^([0-9A-F ]+)\s*;\s*([0-9A-F ]+)\s*;")
    upstream = Path(__file__).resolve().parent.parent / "data" / "confusables.txt"
    for line in upstream.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        match = row.match(line)
        if match and "".join(chr(int(c, 16)) for c in match.group(1).split()) == ch:
            return "".join(chr(int(c, 16)) for c in match.group(2).split())
    return ch


@pytest.mark.parametrize(("a", "b", "why"), SAME_SCRIPT, ids=[c[2] for c in SAME_SCRIPT])
def test_the_same_script_pair_is_a_real_upstream_class(a: str, b: str, why: str) -> None:
    """Non-vacuity: if TR39 stopped grouping these, the limit above would be moot.

    Asserted against `data/confusables.txt` itself. The pair must resolve to one
    prototype — keheh maps directly to kaf, which is its own prototype; yeh and farsi
    yeh both map to alef maksura. Comparing the two strings for inequality, as this
    test first did, would pass for any two distinct non-ASCII characters and so could
    not notice the upstream data moving out from under the documented limitation.
    """
    assert a != b
    assert _tr39_prototype(a) == _tr39_prototype(b), why


@pytest.mark.parametrize(
    ("tilde", "macron"), BASE_PLUS_MARK, ids=[f"U+{ord(p[0][0]):04X}" for p in BASE_PLUS_MARK]
)
def test_a_base_plus_mark_pair_is_not_folded_together(tilde: str, macron: str) -> None:
    for surface in (disarm.canonicalize, disarm.canonicalize_strict, disarm.normalize_confusables):
        assert surface(f"ma{tilde}ana") != surface(f"ma{macron}ana"), surface.__name__


@pytest.mark.parametrize(
    ("tilde", "macron"), BASE_PLUS_MARK, ids=[f"U+{ord(p[0][0]):04X}" for p in BASE_PLUS_MARK]
)
def test_the_key_builders_do_merge_them(tilde: str, macron: str) -> None:
    """The other half, and the reason the fold's silence is not a contradiction: stripping
    accents is the right answer for a search index and says nothing about a spoof screen."""
    for surface in (disarm.catalog_key, disarm.search_key):
        assert surface(f"ma{tilde}ana") == surface(f"ma{macron}ana"), surface.__name__


def test_one_spelling_of_each_pair_really_is_two_code_points() -> None:
    """Non-vacuity: the class is defined by the disagreement about precomposition."""
    for tilde, macron in BASE_PLUS_MARK:
        assert len({len(tilde), len(macron)}) == 2, (tilde, macron)


def test_the_hostname_screen_sees_neither_spelling() -> None:
    """What the limit costs, stated where it is measurable (#836)."""
    for host in ("mañana.com", "man̄ana.com"):
        flagged, _analysis = disarm.is_suspicious_hostname(host)
        assert not flagged, host
