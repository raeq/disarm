#!/usr/bin/env python3
"""Idempotence sweep, library only: `f(f(s)) == f(s)` for every surface in `surfaces.py`.

    python3 search/idempotence.py KIND [surface,surface,...]

KIND is one of

* `scalars` -- every scalar in planes 0-3 and 14 (264,192 strings);
* `pairs` -- every scalar in planes 0-1 (and the tag block) next to each of BS, ZWSP, CGJ,
  U+0301, SPACE and U+0338, on either side (1,549,824 strings);
* `pairs2` -- the same with U+20D2, VS16, U+0300, U+0327, U+0345, U+3099, U+094D, U+05B4,
  U+0489 and U+0E31 (2,583,040 strings);
* `F1` -- 21 bases x 13 removable characters x every mark, as base+glue+mark and
  base+mark+glue+mark (1,183,728);
* `F2` -- 4 bases x the 127 commonest marks, pairwise (129,032);
* `F3` -- conjoining Hangul L+V(+T) with each removable character between (55,860).

Prints, per surface, the number of strings that move on a second pass and the first few.
"""

from __future__ import annotations

import multiprocessing as mp
import sys
import unicodedata

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from surfaces import SURFACES  # noqa: E402

GLUE = [
    0x200B,
    0x34F,
    0x8,
    0x7F,
    0xFE0F,
    0xAD,
    0x202E,
    0xE0041,
    0x0,
    0x2060,
    0x200D,
    0xFDD0,
    0x3164,
]
BASES = [
    0x61,
    0x65,
    0x75,
    0x41,
    0x49,
    0xA2,
    0x3D,
    0x3C,
    0x4E2D,
    0x5E7,
    0x627,
    0x20,
    0x31,
    0x3B0,
    0x130,
    0xDF,
    0x2260,
    0xE000,
    0x1100,
    0x915,
    0xE9,
]
FREQ = list(range(0x300, 0x370)) + [
    0x20D2,
    0x20E3,
    0x489,
    0x5B4,
    0x651,
    0x93C,
    0x94D,
    0xE31,
    0x3099,
    0x302A,
    0x1AB0,
    0x1DC0,
    0xFE20,
    0x345,
    0xF39,
]


def w(*cps: int) -> str:
    return "".join(map(chr, cps))


def planes01():
    for cp in list(range(0, 0x20000)) + list(range(0xE0000, 0xE0080)):
        if not 0xD800 <= cp < 0xE000:
            yield cp


def gen(kind: str):
    if kind == "scalars":
        for cp in list(range(0, 0x40000)) + list(range(0xE0000, 0xE1000)):
            if not 0xD800 <= cp < 0xE000:
                yield chr(cp)
    elif kind in ("pairs", "pairs2"):
        glue = (
            [0x8, 0x200B, 0x34F, 0x301, 0x20, 0x338]
            if kind == "pairs"
            else [0x20D2, 0xFE0F, 0x300, 0x327, 0x345, 0x3099, 0x94D, 0x5B4, 0x489, 0xE31]
        )
        for cp in planes01():
            for g in glue:
                yield w(cp, g)
                yield w(g, cp)
    elif kind == "F1":
        marks = [
            c for c in range(0x300, 0x20000) if unicodedata.category(chr(c)) in ("Mn", "Mc", "Me")
        ]
        for b in BASES:
            for g in GLUE:
                for m in marks:
                    yield w(b, g, m)
                    yield w(b, m, g, m)
    elif kind == "F2":
        for b in (0x61, 0x3D, 0xA2, 0x627):
            for m1 in FREQ:
                for m2 in FREQ:
                    yield w(b, m1, m2)
                    yield w(b, m1, m2, m1)
    elif kind == "F3":
        for lead in range(0x1100, 0x1113):
            for v in range(0x1161, 0x1176):
                for g in GLUE + [None]:
                    yield w(lead, g, v) if g is not None else w(lead, v)
                    for t in range(0x11A8, 0x11C3, 3):
                        yield w(lead, v, g, t) if g is not None else w(lead, v, t)


def work(args):
    names, strs = args
    bad = []
    for n in names:
        f = SURFACES[n]
        cnt = 0
        for s in strs:
            a = f(s)
            b = f(a)
            if a != b:
                cnt += 1
                if cnt <= 5:
                    bad.append((n, s, a, b))
        bad.append((n, None, cnt, None))
    return bad


def main() -> None:
    kind = sys.argv[1]
    names = sys.argv[2].split(",") if len(sys.argv) > 2 else list(SURFACES)
    strs = list(gen(kind))
    with mp.Pool(4) as pool:
        res = pool.map(work, [(names, strs[i::32]) for i in range(32)])
    counts = {n: 0 for n in names}
    examples: dict[str, list] = {n: [] for n in names}
    for r in res:
        for n, s, a, b in r:
            if s is None:
                counts[n] += a
            else:
                examples[n].append((s, a, b))
    print(f"kind {kind}: {len(strs):,} strings x {len(names)} surfaces")
    for n in names:
        ex = [(ascii(s), ascii(a), ascii(b)) for s, a, b in examples[n][:3]]
        print(f"{n:<40} {counts[n]:>8}  {ex}")


if __name__ == "__main__":
    main()
