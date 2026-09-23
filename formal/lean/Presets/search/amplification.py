#!/usr/bin/env python3
"""Amplification after the NFKC ceiling, library only.

The preset output ceiling (#768) is checked on the NFKC step's output. For every assigned
scalar outside the PUA this measures len(f(c)) / max(len(c), len(NFKC(c))) in UTF-8 bytes:
how much a preset grows its input *after* the only step the ceiling watches.
"""

from __future__ import annotations

import multiprocessing as mp
import sys
import unicodedata

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from surfaces import SURFACES  # noqa: E402

import disarm  # noqa: E402

NAMES = [
    "canonicalize",
    "canonicalize_strict",
    "strip_obfuscation",
    "search_key",
    "catalog_key",
    "sort_key",
    "skeleton_key",
    "ml_normalize",
    "strip_format",
]


def work(cps):
    best = {n: (0.0, None, None) for n in NAMES}
    for cp in cps:
        c = chr(cp)
        base = max(len(c.encode()), len(disarm.normalize(c, form="NFKC").encode()))
        for n in NAMES:
            out = SURFACES[n](c)
            r = len(out.encode()) / base
            if r > best[n][0]:
                best[n] = (r, cp, out)
    return best


def main() -> None:
    cps = [
        cp
        for cp in range(0x110000)
        if not 0xD800 <= cp < 0xE000 and unicodedata.category(chr(cp)) not in ("Cn", "Co")
    ]
    with mp.Pool(4) as pool:
        res = pool.map(work, [cps[i::32] for i in range(32)])
    for n in NAMES:
        r, cp, out = max((x[n] for x in res), key=lambda t: t[0])
        print(f"{n:<22} x{r:5.2f}  U+{cp:04X} -> {ascii(out)[:60]}")


if __name__ == "__main__":
    main()
