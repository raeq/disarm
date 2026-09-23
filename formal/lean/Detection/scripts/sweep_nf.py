#!/usr/bin/env python3
"""Does `has_anomalies` give canonically equivalent inputs one verdict?

    python3 scripts/sweep_nf.py [--jobs N]

Every Unicode scalar `c`, in each context below, is normalized to NFC and to NFD and both
are classified. Prints, per context and direction, how many scalars split the verdict and
which kinds fire on the flagged side.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from collections import defaultdict
from multiprocessing import Pool

import disarm

CONTEXTS = [
    ("pay", "pal"),
    ("a", ""),
    ("\u00e9", "\u00e9"),
    ("", "\u2066"),
    ("\u00e9t\u00e9", "\u2067x"),
    ("\u00e9", "\u200d\u00e9"),
    ("\u00e0\u00e9", "\u200f1"),
]


def check(cp: int):
    out = []
    for i, (pre, post) in enumerate(CONTEXTS):
        s = pre + chr(cp) + post
        a = disarm.inspect_anomalies(unicodedata.normalize("NFC", s)).kinds
        b = disarm.inspect_anomalies(unicodedata.normalize("NFD", s)).kinds
        if bool(a) != bool(b):
            out.append((i, "NFC flagged" if a else "NFD flagged", tuple(a or b)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    cps = [cp for cp in range(0x110000) if not 0xD800 <= cp <= 0xDFFF]
    with Pool(args.jobs) as pool:
        results = pool.map(check, cps, chunksize=4000)
    by = defaultdict(int)
    total = 0
    for r in results:
        for i, side, kinds in r:
            by[(i, side, kinds)] += 1
            total += 1
    print(f"{len(cps)} scalars x {len(CONTEXTS)} contexts; {total} split verdicts")
    for (i, side, kinds), n in sorted(by.items(), key=lambda kv: -kv[1]):
        pre, post = CONTEXTS[i]
        print(f"  {ascii(pre)} + c + {ascii(post)}: {n} {side} {list(kinds)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
