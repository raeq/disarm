#!/usr/bin/env python3
"""The empty-key census claim, library only.

The docstrings and `docs/limitations.md`: "N single characters reduce to "" here, and so
does every string built from them." For each surface f, E_f is the set of scalars (outside
the PUA, plus one PUA representative) with f(c) == ""; this checks f(a + b) == "" for every
ordered pair of E_f.
"""

from __future__ import annotations

import multiprocessing as mp
import sys
import unicodedata

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from surfaces import SURFACES  # noqa: E402

NAMES = [
    "canonicalize",
    "canonicalize_strict",
    "strip_obfuscation",
    "ml_normalize",
    "search_key",
    "catalog_key",
    "sort_key",
    "skeleton_key",
]


def empties(name: str) -> list[str]:
    f = SURFACES[name]
    out = []
    for cp in range(0x110000):
        if 0xD800 <= cp < 0xE000:
            continue
        c = chr(cp)
        if unicodedata.category(c) == "Co" and cp != 0xE000:
            continue
        if f(c) == "":
            out.append(c)
    return out


def work(args):
    name, firsts, E = args
    f = SURFACES[name]
    bad, n = [], 0
    for a in firsts:
        for b in E:
            n += 1
            r = f(a + b)
            if r != "":
                bad.append((a + b, r))
    return n, bad


def main() -> None:
    for name in sys.argv[1].split(",") if len(sys.argv) > 1 else NAMES:
        E = empties(name)
        with mp.Pool(4) as pool:
            res = pool.map(work, [(name, E[i::16], E) for i in range(16)])
        n = sum(r[0] for r in res)
        bad = [b for r in res for b in r[1]]
        ex = [(ascii(s), r) for s, r in bad[:3]]
        print(
            f"{name:<22} |E| {len(E):>6}  pairs {n:>10,}  non-empty {len(bad):>5}  {ex}", flush=True
        )


if __name__ == "__main__":
    main()
