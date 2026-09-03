#!/usr/bin/env python3
"""Census the non-ASCII code points that read as a Latin letter and reach ASCII nowhere.

#815 asked for the census to be published as an exposure set rather than a fix-all: 299
code points is too many to promote blindly, and some — Latin Extended-D's medievalist
letters — have no sensible ASCII fold at all. What a deployment needs is the reviewed
list, and a gate so the number cannot drift upward unnoticed.

The selector is the part worth reading. #815's own sweep matched names *starting with*
`LATIN `, `MODIFIER LETTER ` or `TURNED `, or containing `SMALL CAPITAL`, and that missed
whole blocks: `NEGATIVE CIRCLED LATIN CAPITAL LETTER A` matches none of them, so 52 code
points sat outside the number. Widening it by hand went wrong three more ways, each
found by reading the output rather than by reasoning:

* **combining marks** — `COMBINING LATIN SMALL LETTER A` and 52 others are category `Mn`,
  diacritics written above a base rather than letters standing in for one. They belong to
  `strip_accents`, and counting them as unfolded exposure overstates the gap by 53.
* **Tag characters** — `TAG LATIN CAPITAL LETTER A` and 51 others are *stripped*, not
  folded (#413). Correct handling reads as "reaches no ASCII" to a naive test.
* **names that merely contain LATIN** — `LATIN CROSS` is a symbol and
  `GLAGOLITIC CAPITAL LETTER LATINATE MYSLITE` is Glagolitic. Neither depicts a Latin
  letter.

So the selector is a word-bounded `LATIN [CAPITAL|SMALL] LETTER` in the name, plus a
category of letter or symbol, which excludes marks and format characters by construction.

Usage:
    python scripts/gen_latin_shape_exposure.py            # rewrite the fixture
    python scripts/gen_latin_shape_exposure.py --check    # exit 1 if out of date
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import disarm

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "latin_shape_exposure.tsv"

#: Word-bounded so `LATINATE` and `LATIN CROSS` do not match.
NAME = re.compile(r"\bLATIN (?:CAPITAL |SMALL )?LETTER\b")

#: Every surface a caller might reasonably expect to normalise identifier text.
SURFACES = ("canonicalize", "normalize_confusables", "search_key", "catalog_key", "ml_normalize")

#: `(first, last, name)`, in code-point order. The gate asserts per block, so a table
#: refresh that widens one block fails even if the total happens to hold.
BLOCKS: tuple[tuple[int, int, str], ...] = (
    (0x0080, 0x024F, "Latin-1 Supplement / Extended-A / Extended-B"),
    (0x0250, 0x02AF, "IPA Extensions"),
    (0x02B0, 0x02FF, "Spacing Modifier Letters"),
    (0x1D00, 0x1D7F, "Phonetic Extensions"),
    (0x1D80, 0x1DBF, "Phonetic Extensions Supplement"),
    (0x1E00, 0x1EFF, "Latin Extended Additional"),
    (0x2070, 0x209F, "Superscripts and Subscripts"),
    (0x2100, 0x214F, "Letterlike Symbols"),
    (0x2460, 0x24FF, "Enclosed Alphanumerics"),
    (0x2C60, 0x2C7F, "Latin Extended-C"),
    (0xA720, 0xA7FF, "Latin Extended-D"),
    (0xAB30, 0xAB6F, "Latin Extended-E"),
    (0xFB00, 0xFB4F, "Alphabetic Presentation Forms"),
    (0xFF00, 0xFFEF, "Halfwidth and Fullwidth Forms"),
    (0x10780, 0x107BF, "Latin Extended-F"),
    (0x1D400, 0x1D7FF, "Mathematical Alphanumeric Symbols"),
    (0x1DF00, 0x1DFFF, "Latin Extended-G"),
    (0x1F100, 0x1F1FF, "Enclosed Alphanumeric Supplement"),
)


def block_of(cp: int) -> str:
    for first, last, name in BLOCKS:
        if first <= cp <= last:
            return name
    return "Unassigned to a censused block"


def depicts_a_latin_letter(cp: int) -> bool:
    ch = chr(cp)
    if ch.isascii():
        return False
    if unicodedata.category(ch)[0] not in ("L", "S"):
        return False
    return bool(NAME.search(unicodedata.name(ch, "")))


def reaches_ascii(ch: str, guardrail: object) -> bool:
    """True when *some* surface takes `ch` to non-empty ASCII.

    Deliberately the most generous reading: a code point counts as covered if anything
    at all folds it. #916 is the companion caveat — a code point can reach ASCII and
    reach the *wrong* ASCII, which this census cannot see and does not claim to.
    """
    for name in SURFACES:
        out = getattr(disarm, name)(ch)
        if out and out.isascii() and out.strip():
            return True
    out = guardrail(ch)  # type: ignore[operator]
    return bool(out and out.isascii() and out.strip())


def census() -> list[tuple[int, str, str]]:
    guardrail = disarm.get_pipeline("llm_guardrail")
    rows = []
    for cp in range(0x80, sys.maxunicode + 1):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        if not depicts_a_latin_letter(cp):
            continue
        if reaches_ascii(chr(cp), guardrail):
            continue
        rows.append((cp, block_of(cp), unicodedata.name(chr(cp), "")))
    return rows


def render(rows: list[tuple[int, str, str]]) -> str:
    out = [
        "# Non-ASCII code points that read as a Latin letter and reach ASCII on no surface.",
        "# Generated by scripts/gen_latin_shape_exposure.py (#815). Do not hand-edit.",
        f"# disarm {disarm.__version__}, UCD {unicodedata.unidata_version}, {len(rows)} rows.",
        "#",
        "# An exposure set, not a bug list: some of these have no sensible ASCII fold.",
        "# A code point LEAVING this file is a fix; one JOINING it needs a reason.",
        "codepoint\tblock\tname",
    ]
    out += [f"{cp:04X}\t{block}\t{name}" for cp, block, name in rows]
    return "\n".join(out) + "\n"


def _rows_only(text: str) -> list[str]:
    """Everything but the comment header, which carries a version that moves per release."""
    return [line for line in text.splitlines() if not line.startswith("#")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="exit 1 if the fixture is stale")
    args = ap.parse_args()
    text = render(census())
    if args.check:
        current = FIXTURE.read_text(encoding="utf-8") if FIXTURE.exists() else ""
        # The header carries the disarm version, which moves on every release; compare
        # the rows, which move only when coverage does.
        if _rows_only(current) != _rows_only(text):
            print("latin_shape_exposure.tsv is out of date; rerun without --check", file=sys.stderr)
            return 1
        print(f"fixture is up to date ({len(_rows_only(text)) - 1} rows)")
        return 0
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(text, encoding="utf-8")
    print(f"wrote {FIXTURE.relative_to(ROOT)} ({len(census())} rows)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
