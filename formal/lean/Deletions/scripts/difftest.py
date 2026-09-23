#!/usr/bin/env python3
"""Differential test: the Lean model of `resolve_deletions_into` against the real library.

    python3 scripts/difftest.py [--random N] [--exhaustive LEN] [--seed S]

Needs the model's driver built (`lake build` in `formal/lean/Deletions`) and an
importable `disarm`. Every case is run under `cr=False` and `cr=True`, through the public
surface a user reaches: `TextPipeline(resolve_deletions=True)` and
`TextPipeline(resolve_deletions=True, resolve_cr=True)`.

The abstract alphabet maps to concrete characters through injective tables, so equal
strings mean equal abstract outputs. Exit status is 0 only when every case agrees.
"""

from __future__ import annotations

import argparse
import itertools
import pathlib
import random
import subprocess
import sys

import disarm

HERE = pathlib.Path(__file__).resolve().parent.parent
EXE = HERE / ".lake" / "build" / "bin" / "difftest"

#: `v<n>`: characters `occupies_cell` answers true for. Letters, a rendering Cf (U+0605),
#: TAB, NUL, a wide CJK ideograph, and SOFT HYPHEN (Cf, but a cell to this code).
VIS = [chr(ord("a") + i) for i in range(26)] + ["\u0605", "\t", "\x00", "中", "\u00ad"]
#: `z<n>`: characters `occupies_cell` answers false for, one per predicate it ORs.
ZW = ["\u200b", "\u0301", "\u200d", "\ufe0f", "\u2060", "\u202e", "\U000e0041", "\u034f"]
#: `n<n>`: the UAX #14 mandatory breaks other than CR/LF.
BRK = ["\x0b", "\x0c", "\x85", "\u2028", "\u2029"]
CTRL = {"B": "\b", "D": "\x7f", "R": "\r", "L": "\n"}


def concrete(toks: list[str]) -> str:
    out = []
    for t in toks:
        if t in CTRL:
            out.append(CTRL[t])
        else:
            table = {"v": VIS, "z": ZW, "n": BRK}[t[0]]
            out.append(table[int(t[1:])])
    return "".join(out)


def random_case(rng: random.Random) -> list[str]:
    n = rng.randint(0, 18)
    toks = []
    for _ in range(n):
        r = rng.random()
        if r < 0.16:
            toks.append("B")
        elif r < 0.22:
            toks.append("D")
        elif r < 0.36:
            toks.append("R")
        elif r < 0.44:
            toks.append("L")
        elif r < 0.50:
            toks.append(f"n{rng.randrange(len(BRK))}")
        elif r < 0.68:
            toks.append(f"z{rng.randrange(len(ZW))}")
        else:
            toks.append(f"v{rng.randrange(len(VIS))}")
    return toks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--random", type=int, default=200_000)
    ap.add_argument("--exhaustive", type=int, default=6)
    ap.add_argument("--seed", type=int, default=937)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    cases: list[list[str]] = []
    small = ["B", "D", "R", "L", "v0", "v1", "z0", "n0"]
    for n in range(args.exhaustive + 1):
        cases.extend(list(p) for p in itertools.product(small, repeat=n))
    cases.extend(random_case(rng) for _ in range(args.random))

    lines = [f"{f} {' '.join(c)}" for c in cases for f in (0, 1)]
    proc = subprocess.run(
        [str(EXE)], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True
    )
    answers = proc.stdout.splitlines()
    assert len(answers) == len(lines), (len(answers), len(lines))

    pipes = {
        0: disarm.TextPipeline(resolve_deletions=True),
        1: disarm.TextPipeline(resolve_deletions=True, resolve_cr=True),
    }
    compared = agree = fixed_differs = 0
    failures = []
    i = 0
    for c in cases:
        text = concrete(c)
        for f in (0, 1):
            model, fixed = (s.split() for s in answers[i].split("|"))
            i += 1
            real = pipes[f](text)
            compared += 1
            if concrete(model) == real:
                agree += 1
            elif len(failures) < 20:
                failures.append((f, c, real, concrete(model)))
            if concrete(fixed) != real:
                fixed_differs += 1

    print(f"cases compared: {compared} ({len(cases)} inputs x 2 flags)")
    print(f"model == library: {agree}/{compared}")
    print(f"proposed fix differs from library on: {fixed_differs}/{compared}")
    for f, c, real, model in failures:
        print(f"DISAGREE cr={bool(f)} {c} real={real!r} model={model!r}")
    return 0 if agree == compared else 1


if __name__ == "__main__":
    sys.exit(main())
