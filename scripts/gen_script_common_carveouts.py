#!/usr/bin/env python3
"""Generate `src/tables/data/script_common_carveouts.tsv` from the vendored `Scripts.txt`.

`detect_char_script` resolves a script by binary-searching `SCRIPT_RANGES`, a hand-curated
table of **block** ranges (`src/scripts.rs`). A block is not a script: the Arabic block
holds the Arabic comma, the Devanagari block holds the dandas every Indic script writes
with, and Arabic Presentation Forms-B holds `U+FEFF`, the byte order mark. The UCD gives
all of these `Script=Common`. The block table gave them the block's script, so a
BOM-prefixed English file was "mixed script" and a Bengali sentence ending in a danda was
Bengali plus Devanagari (Finding 5 of the Lean detection model in `formal/lean/Detection`).

This table is the carve-out: every code point that falls inside a `SCRIPT_RANGES` entry
naming a script, and that the UCD calls `Common`. `detect_char_script` answers `Common` for
them. It is generated rather than written by hand for the reason #819 gives: a block table
must not contradict the standard, and a hand-kept exception list is a second copy of the
standard that drifts from the first.

`Script=Inherited` is deliberately **not** carved out. Every code point the block table
gives a script where the UCD says `Inherited` is a combining mark, and naming the script
of the block it lives in is the documented exemption `tests/test_script_table_agrees_with_ucd.py`
checks: it is what lets `strip_cross_script_marks` remove an Arabic shadda from a Latin
base (CVE-2017-7833), and those marks' `Script_Extensions` are specific scripts, not every
script, so `Inherited` would be the less accurate answer of the two.

Regenerate with:

    python scripts/gen_script_common_carveouts.py           # rewrite the table
    python scripts/gen_script_common_carveouts.py --check   # exit 1 if it is stale
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_TXT = ROOT / "data" / "Scripts.txt"
SOURCE = ROOT / "src" / "scripts.rs"
OUT = ROOT / "src" / "tables" / "data" / "script_common_carveouts.tsv"

#: The Unicode version the vendored `Scripts.txt` is. Matches `assigned_ranges.tsv` and
#: the confusables data, so the crate has one Unicode story.
DATA_UNICODE_VERSION = "17.0.0"

#: The values that are not a script of their own.
NEUTRAL = {"Common", "Inherited"}

_ROW = re.compile(r'^\s*\(0x([0-9A-Fa-f]+),\s*0x([0-9A-Fa-f]+),\s*"(\w+)"\)')


def ucd_common() -> set[int]:
    """Every code point `Scripts.txt` gives `Script=Common`."""
    text = SCRIPTS_TXT.read_text(encoding="utf-8")
    first = text.splitlines()[0]
    if f"Scripts-{DATA_UNICODE_VERSION}.txt" not in first:
        sys.exit(f"{SCRIPTS_TXT} is {first!r}, not Scripts-{DATA_UNICODE_VERSION}.txt")
    out: set[int] = set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        span, script = (part.strip() for part in line.split(";"))
        if script != "Common":
            continue
        start, _, end = span.partition("..")
        out.update(range(int(start, 16), int(end or start, 16) + 1))
    return out


def table_ranges() -> list[tuple[int, int, str]]:
    """`SCRIPT_RANGES` as written in `src/scripts.rs`, read from the source."""
    source = SOURCE.read_text(encoding="utf-8")
    body = source[source.index("static SCRIPT_RANGES") :]
    body = body[: body.index("\n];")]
    rows = [
        (int(m.group(1), 16), int(m.group(2), 16), m.group(3))
        for line in body.splitlines()
        if (m := _ROW.match(line))
    ]
    if len(rows) < 100:
        sys.exit(f"parsed only {len(rows)} SCRIPT_RANGES rows from {SOURCE}")
    return rows


def carveouts() -> list[tuple[int, int, str]]:
    """Contiguous spans of UCD-`Common` code points the block table names a script for.

    Each span carries the script the block would have given it, for the reader: the
    lookup only needs the span.
    """
    common = ucd_common()
    found = sorted(
        (cp, script)
        for start, end, script in table_ranges()
        if script not in NEUTRAL
        for cp in range(start, end + 1)
        if cp in common
    )
    spans: list[list[object]] = []
    for cp, script in found:
        if spans and spans[-1][1] == cp - 1 and spans[-1][2] == script:
            spans[-1][1] = cp
        else:
            spans.append([cp, cp, script])
    return [(int(a), int(b), str(s)) for a, b, s in spans]


def render() -> str:
    spans = carveouts()
    count = sum(end - start + 1 for start, end, _ in spans)
    header = [
        "# Code points the block table in src/scripts.rs would give a script, and that",
        "# the UCD gives Script=Common (start\tend, inclusive, hex; then the block's script).",
        "#",
        "# detect_char_script answers Common for these. Script=Inherited marks are",
        "# deliberately not listed: see the docstring of the generator.",
        "#",
        f"# UCD {DATA_UNICODE_VERSION} Scripts.txt (data/Scripts.txt), {count} code points.",
        "# Generated by scripts/gen_script_common_carveouts.py. Do not hand-edit.",
    ]
    body = [f"{start:04X}\t{end:04X}\t{script}" for start, end, script in spans]
    return "\n".join(header + body) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the table is stale")
    args = parser.parse_args(argv)
    rendered = render()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != rendered:
            print(f"{OUT.relative_to(ROOT)} is stale; run {pathlib.Path(__file__).name}")
            return 1
        print(f"{OUT.relative_to(ROOT)} is current")
        return 0
    OUT.write_text(rendered, encoding="utf-8")
    spans = carveouts()
    print(
        f"wrote {OUT.relative_to(ROOT)}  spans={len(spans)}  "
        f"code_points={sum(e - s + 1 for s, e, _ in spans)}  unicode={DATA_UNICODE_VERSION}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
