#!/usr/bin/env python3
"""`detect_scripts` and `is_mixed_script` against the UCD.

    python3 scripts/sweep_scripts.py [--scripts data/Scripts.txt] [--fonttools DIR]

Part 1 compares `detect_scripts(c)` with `Script` for every assigned code point, using the
`data/Scripts.txt` (UCD 17.0.0) the repository already carries. Part 2 compares
`is_mixed_script` on pairs with UTS #39 section 5.1 resolved over `Script_Extensions`,
restricted to characters the library assigns a script to (a curated-scope gap is not
counted). It reads `Script_Extensions` from fontTools' generated UCD tables (fontTools
4.65.0 carries UCD 17.0.0): `--fonttools` is a directory holding `fontTools/unicodedata/`,
for instance an unpacked wheel. Nothing is imported from fontTools but those two data
modules.
"""

from __future__ import annotations

import argparse
import bisect
import importlib.util
import pathlib
import sys
from collections import defaultdict

import disarm

ROOT = pathlib.Path(__file__).resolve().parents[4]


def parse_ranges(path: pathlib.Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        rng, val = (x.strip() for x in line.split(";"))
        a, _, b = rng.partition("..")
        rows.append((int(a, 16), int(b or a, 16), val))
    rows.sort()
    return rows


def lookup(rows, starts, cp):
    i = bisect.bisect_right(starts, cp) - 1
    if i >= 0 and rows[i][0] <= cp <= rows[i][1]:
        return rows[i][2]
    return None


def norm(name: str) -> str:
    return name.replace("_", "").lower()


AUG = {
    "Hani": {"Hani", "Hanb", "Jpan", "Kore"},
    "Hira": {"Hira", "Jpan"},
    "Kana": {"Kana", "Jpan"},
    "Hang": {"Hang", "Kore"},
    "Bopo": {"Bopo", "Hanb"},
}


def ranges(cps):
    out, start, prev = [], None, None
    for x in sorted(cps):
        if prev is not None and x == prev + 1:
            prev = x
            continue
        if start is not None:
            out.append((start, prev))
        start = prev = x
    if start is not None:
        out.append((start, prev))
    return ", ".join(f"U+{a:04X}" if a == b else f"U+{a:04X}-{b:04X}" for a, b in out)


def lib_script(cp):
    got = disarm.detect_scripts(chr(cp))
    return got[0].value if got else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripts", type=pathlib.Path, default=ROOT / "data" / "Scripts.txt")
    ap.add_argument("--fonttools", type=pathlib.Path, default=None)
    args = ap.parse_args()
    rows = parse_ranges(args.scripts)
    starts = [r[0] for r in rows]
    cps = [cp for cp in range(0x110000) if not 0xD800 <= cp <= 0xDFFF]

    wrong, other, gap = defaultdict(list), defaultdict(list), 0
    for cp in cps:
        ucd = lookup(rows, starts, cp)
        if ucd is None:
            continue
        lib = lib_script(cp)
        exp = None if ucd in ("Common", "Inherited") else norm(ucd)
        got = None if lib is None else norm(lib)
        if got == exp:
            continue
        if got is None:
            gap += 1
        elif exp is None:
            wrong[(lib, ucd)].append(cp)
        else:
            other[(lib, ucd)].append(cp)
    print("Part 1: detect_scripts against Script")
    print(f"  assigned code points the library gives no script (curated scope): {gap}")
    print(f"  a script where the UCD says Common/Inherited: {sum(map(len, wrong.values()))}")
    for (lib, ucd), v in sorted(wrong.items()):
        print(f"    {lib} (UCD {ucd}): {len(v)}  {ranges(v)}")
    print(f"  a different script: {sum(map(len, other.values()))}")
    for (lib, ucd), v in sorted(other.items()):
        print(f"    {lib} (UCD {ucd}): {len(v)}  {ranges(v)}")

    if args.fonttools is None:
        print("Part 2 skipped (pass --fonttools DIR)")
        return 0

    def load(name):
        path = args.fonttools / "fontTools" / "unicodedata" / f"{name}.py"
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    sc, sx = load("Scripts"), load("ScriptExtensions")

    def scx(cp):
        v = sx.VALUES[bisect.bisect_right(sx.RANGES, cp) - 1]
        if v is None:
            v = {sc.VALUES[bisect.bisect_right(sc.RANGES, cp) - 1]}
        return set(v)

    def aug(cp):
        s = scx(cp)
        if s & {"Zyyy", "Zinh", "Zzzz"}:
            return None
        out = set()
        for x in s:
            out |= AUG.get(x, {x})
        return out

    def ref_mixed(text):
        acc = None
        for ch in text:
            a = aug(ord(ch))
            if a is None:
                continue
            acc = set(a) if acc is None else acc & a
        return acc is not None and not acc

    covered = [cp for cp in cps if lib_script(cp) is not None]
    rep = {}
    for cp in covered:
        rep.setdefault(lib_script(cp), cp)
    multi = [cp for cp in covered if aug(cp) is None or len(scx(cp)) > 1]
    fp, fn = defaultdict(list), defaultdict(list)
    for cp in multi:
        for r in rep.values():
            s = chr(r) + chr(cp)
            lib, ref = disarm.is_mixed_script(s), ref_mixed(s)
            if lib and not ref:
                fp[cp].append(r)
            elif ref and not lib:
                fn[cp].append(r)
    print("Part 2: is_mixed_script against UTS #39 section 5.1 over Script_Extensions")
    print(
        f"  {len(covered)} covered code points, {len(rep)} library scripts, "
        f"{len(multi)} covered code points whose Script_Extensions is not one script"
    )
    print(
        f"  library mixed, UTS #39 single: {sum(map(len, fp.values()))} pairs over "
        f"{len(fp)} code points: {ranges(fp)}"
    )
    print(f"  UTS #39 mixed, library single: {sum(map(len, fn.values()))} pairs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
