#!/usr/bin/env python3
"""Generate the per-script confusable prototype census (#963, #884).

`unmapped_confusables()` answers "which upstream sources does the bundled table not
fold" against a population of all 6,565 TR39 sources. For a script with no bundled
table that number is determined entirely by the table's absence — Greek would report
roughly the whole population, which reads as an enormous gap and means only "there is
no Greek table". A count determined by an absence is a blind spot with a number in
front of it, which is worse than the exception it replaced, because it looks like data.

The fair question, and the decision recorded on #884, is per script: **how many TR39
sources have a prototype in that script, and how many of those does the bundled table
reach.** That is a number where "0 of 159" can improve.

Two inputs, both vendored:

* ``data/confusables.txt`` — the TR39 source→prototype rows.
* ``data/Scripts.txt`` — the UCD script property, used to name the prototype's script.

The script property comes from the UCD rather than from disarm's own `SCRIPT_RANGES`,
which is a curated **block** table: it covers 60 scripts, so 207 prototypes (950 rows)
fall outside it, and they are not all `Common` — Yi and Siddham letters are in there.
Grouping them under `Common` because the block table has no range for them would move a
coverage gap into a bucket labelled "punctuation". Reading the property from the UCD
also keeps the census from being scored against disarm's own table twice.

Output: ``src/tables/data/confusable_prototype_census.tsv``, one row per prototype
script, ``script<TAB>sources<TAB>folded``.

Usage:
    python scripts/gen_confusable_census.py
    python scripts/gen_confusable_census.py --check   # exit 1 if the file is stale
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFUSABLES = ROOT / "data" / "confusables.txt"
SCRIPTS = ROOT / "data" / "Scripts.txt"
TABLES = ROOT / "src" / "tables" / "data"
OUT = TABLES / "confusable_prototype_census.tsv"

#: The bundled fold tables, in the order they are generated. A source is *reached* if
#: any of them folds it — the question is whether disarm neutralizes the source at all,
#: not whether it folds it toward the prototype TR39 chose.
FOLD_TABLES = (
    "confusables_to_latin.tsv",
    "confusables_to_cyrillic.tsv",
    "confusables_to_arabic.tsv",
    "confusables_to_hebrew.tsv",
)

_CONFUSABLE_ROW = re.compile(r"^([0-9A-F ]+)\s*;\s*([0-9A-F ]+)\s*;\s*(\w+)")
_SCRIPT_ROW = re.compile(r"^([0-9A-F]{4,6})(?:\.\.([0-9A-F]{4,6}))?\s*;\s*([A-Za-z_]+)\s*#")


def _version(path: Path, pattern: str) -> str:
    """Pull the data vintage out of a UCD file header, or fail loudly."""
    head = path.read_text(encoding="utf-8", errors="replace")[:2000]
    match = re.search(pattern, head)
    if not match:
        raise SystemExit(f"{path.name}: header does not name a version")
    return match.group(1)


def load_script_ranges() -> list[tuple[int, int, str]]:
    """UCD `Scripts.txt` as sorted, non-overlapping (start, end, script) rows."""
    ranges: list[tuple[int, int, str]] = []
    for line in SCRIPTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip() if "#" not in line else line
        match = _SCRIPT_ROW.match(line.strip())
        if not match:
            continue
        start = int(match.group(1), 16)
        end = int(match.group(2), 16) if match.group(2) else start
        ranges.append((start, end, match.group(3)))
    ranges.sort()
    if len(ranges) < 1000:
        raise SystemExit(f"Scripts.txt: parsed only {len(ranges)} ranges")
    return ranges


def script_of(cp: int, ranges: list[tuple[int, int, str]]) -> str:
    """Binary search. `Unknown` is the UCD's own name for an unassigned code point."""
    lo, hi = 0, len(ranges) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        start, end, name = ranges[mid]
        if cp < start:
            hi = mid - 1
        elif cp > end:
            lo = mid + 1
        else:
            return name
    return "Unknown"


def load_folded_sources() -> set[int]:
    """Every source code point some bundled table folds."""
    folded: set[int] = set()
    for name in FOLD_TABLES:
        path = TABLES / name
        if not path.exists():  # a target that is not bundled yet
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            field = line.split("\t", 1)[0].strip()
            if not field:
                continue
            # Multi-code-point sources exist in the contraction table only; the
            # census population is the single-code-point rows, so anything longer
            # cannot match one and is skipped rather than truncated.
            points = field.split()
            if len(points) == 1:
                try:
                    folded.add(int(points[0], 16))
                except ValueError:
                    continue
    if not folded:
        raise SystemExit("no bundled fold table produced any source")
    return folded


def build() -> tuple[str, dict[str, tuple[int, int]]]:
    ranges = load_script_ranges()
    folded = load_folded_sources()

    sources: Counter[str] = Counter()
    reached: Counter[str] = Counter()
    rows = 0
    for line in CONFUSABLES.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        match = _CONFUSABLE_ROW.match(line)
        if not match:
            continue
        src_points = match.group(1).split()
        if len(src_points) != 1:  # the census population is single sources
            continue
        rows += 1
        src = int(src_points[0], 16)
        prototype = int(match.group(2).split()[0], 16)
        script = script_of(prototype, ranges)
        sources[script] += 1
        if src in folded:
            reached[script] += 1

    if rows < 6000:
        raise SystemExit(f"confusables.txt: parsed only {rows} single-source rows")

    census = {name: (n, reached[name]) for name, n in sorted(sources.items())}
    confusables_version = _version(CONFUSABLES, r"# Version: ([0-9.]+)")
    scripts_version = _version(SCRIPTS, r"# Scripts-([0-9.]+)\.txt")
    header = (
        "# TR39 confusable sources grouped by the script of their prototype (#963).\n"
        "#\n"
        f"# `sources` is how many single-code-point sources in confusables.txt "
        f"{confusables_version} have a\n"
        "# prototype in this script; `folded` is how many of those some bundled fold\n"
        "# table reaches. A script with no bundled table reports `0 of N` rather than\n"
        "# the whole source population, which is what makes the figure one that can\n"
        "# improve.\n"
        "#\n"
        f"# The script property is the UCD's, from Scripts.txt {scripts_version}, and not\n"
        "# disarm's curated block table: that table has no range for 207 of the\n"
        "# prototypes, and they are not all Common — Yi and Siddham letters are among\n"
        "# them. Reading it from the UCD also keeps the census from being scored\n"
        "# against disarm's own table twice.\n"
        "#\n"
        "# Generated by scripts/gen_confusable_census.py - see docs/provenance.md.\n"
        "# script\tsources\tfolded\n"
    )
    body = "".join(f"{name}\t{n}\t{f}\n" for name, (n, f) in census.items())
    return header + body, census


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the committed file differs from what the inputs produce",
    )
    args = parser.parse_args()

    text, census = build()
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT.relative_to(ROOT)} is stale — rerun {Path(__file__).name}")
            return 1
        print(f"{OUT.relative_to(ROOT)} is current ({len(census)} scripts)")
        return 0

    OUT.write_text(text, encoding="utf-8")
    total = sum(n for n, _ in census.values())
    folded = sum(f for _, f in census.values())
    print(f"wrote {OUT.relative_to(ROOT)}: {len(census)} scripts, {total} sources, {folded} folded")
    for name, (n, f) in sorted(census.items(), key=lambda kv: -kv[1][0])[:8]:
        print(f"  {name:<22}{n:>6}{f:>7}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
