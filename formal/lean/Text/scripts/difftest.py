#!/usr/bin/env python3
"""Differential test: the Lean models in `Text/` against the real library.

    python3 scripts/difftest.py [--quick] [--seed S]

Needs the driver built (`lake build textmodel` in `formal/lean/Text`) and an importable
`disarm`. Every abstract token maps to a concrete character through an injective table,
so equal strings mean equal abstract outputs. Exit status is 0 only when every comparison
of the *current* model agrees; the fixed zalgo model is reported, not gated.

All non-ASCII characters in this file are written as escapes (see #802).
"""

from __future__ import annotations

import argparse
import itertools
import pathlib
import random
import subprocess
import sys
import unicodedata

import disarm

HERE = pathlib.Path(__file__).resolve().parent.parent
EXE = HERE / ".lake" / "build" / "bin" / "textmodel"


def run_model(lines: list[str]) -> list[str]:
    out: list[str] = []
    step = 200_000
    for i in range(0, len(lines), step):
        chunk = lines[i : i + step]
        proc = subprocess.run(
            [str(EXE)], input="\n".join(chunk) + "\n", capture_output=True, text=True, check=True
        )
        ans = proc.stdout.split("\n")[: len(chunk)]
        assert len(ans) == len(chunk), (len(ans), len(chunk))
        out.extend(ans)
    assert not any(a == "ERR" for a in out), "driver could not parse a case"
    return out


def words(alpha: list[str], n: int):
    for k in range(n + 1):
        yield from itertools.product(alpha, repeat=k)


class Tally:
    def __init__(self, name: str) -> None:
        self.name = name
        self.n = 0
        self.ok = 0
        self.fails: list[str] = []

    def check(self, good: bool, detail) -> None:
        self.n += 1
        if good:
            self.ok += 1
        elif len(self.fails) < 8:
            self.fails.append(repr(detail))

    def report(self) -> bool:
        print(f"  {self.name}: {self.ok}/{self.n} agree")
        for f in self.fails:
            print(f"    DISAGREE {f}")
        return self.ok == self.n


# ---------------------------------------------------------------------------------------
# zalgo
Z = {
    "a": "a",
    "b": "b",
    "e": "=",
    "A": "\u0301",
    "G": "\u0300",
    "U": "\u0316",
    "O": "\u0334",
    "N": "\u0338",
    "R": "\u20d2",
    "T": "\u0e31",
    "C": "\u034f",
}


def zalgo(rng: random.Random, quick: bool) -> list[Tally]:
    small = ["a", "e", "A", "U", "O", "N", "T"]
    cases = [list(w) for w in words(small, 5 if quick else 7)]
    full = list(Z)
    for _ in range(50_000 if quick else 300_000):
        cases.append([rng.choice(full) for _ in range(rng.randint(0, 16))])
    ks = [0, 1, 2, 3]
    lines = [f"Z {k} {' '.join(c)}" for c in cases for k in ks]
    ans = run_model(lines)
    t_pred, t_strip = Tally("is_zalgo"), Tally("strip_zalgo (NFD of output)")
    t_fix = Tally("fixed model == library, all inputs (informational: differs on the Z1/Z2 shapes)")
    t_fix_else = Tally(
        "fixed model == library, inputs with no class-0 mark and no negation overlay"
    )
    i = 0
    for c in cases:
        s = "".join(Z[t] for t in c)
        for k in ks:
            pz, pstrip, fz, fstrip = (x.split() for x in ans[i].split("|"))
            i += 1
            real_z = disarm.is_zalgo(s, threshold=k)
            real = unicodedata.normalize("NFD", disarm.strip_zalgo(s, max_marks=k))
            t_pred.check(real_z == (pz == ["1"]), (k, c, real_z))
            t_strip.check(real == "".join(Z[t] for t in pstrip), (k, c, ascii(real), pstrip))
            same = real == "".join(Z[t] for t in fstrip) and real_z == (fz == ["1"])
            t_fix.check(same, (k, c))
            if not any(t in ("T", "C", "N", "R") for t in c):
                t_fix_else.check(same, (k, c))
    return [t_pred, t_strip, t_fix, t_fix_else]


# ---------------------------------------------------------------------------------------
# width
W = {
    "a": "a",
    "1": "1",
    "x": "\x01",
    "m": "\u0301",
    "p": "\u0600",
    "r": "\u0d4e",
    "j": "\u200d",
    "c": "\u4e00",
    "q": "\u00a1",
    "E": "\U0001f600",
    "F": "\U0001f3fb",
    "I": "\U0001f1e6",
    "h": "\u263a",
    "s": "\ufe0e",
    "S": "\ufe0f",
    "k": "\u20e3",
}
W_INV = {v: k for k, v in W.items()}


def width(rng: random.Random, quick: bool) -> list[Tally]:
    alpha = list(W)
    args = [list(w) for w in words(alpha, 3)]
    strings = [
        [rng.choice(alpha) for _ in range(rng.randint(0, 10))]
        for _ in range(20_000 if quick else 200_000)
    ]
    lines: list[str] = []
    for a in args:
        for amb in (0, 1):
            lines.append(f"W {amb} {' '.join(a)}")
    plan = []
    for s in strings:
        text = "".join(W[t] for t in s)
        clusters = disarm.grapheme_split(text)
        toks = [[W_INV[ch] for ch in cl] for cl in clusters]
        for amb in (0, 1):
            plan.append((text, amb, len(toks)))
            for cl in toks:
                lines.append(f"W {amb} {' '.join(cl)}")
    ans = run_model(lines)
    t_gw, t_tw = Tally("grapheme_width (any argument)"), Tally("terminal_width (sum over clusters)")
    i = 0
    for a in args:
        text = "".join(W[t] for t in a)
        for amb in (0, 1):
            m = int(ans[i].split("|")[0])
            i += 1
            real = disarm.grapheme_width(text, ambiguous_wide=bool(amb))
            t_gw.check(real == m, (a, amb, real, m))
    for text, amb, n in plan:
        m = sum(int(ans[i + j].split("|")[0]) for j in range(n))
        i += n
        real = disarm.terminal_width(text, ambiguous_wide=bool(amb))
        t_tw.check(real == m, (ascii(text), amb, real, m))
    return [t_gw, t_tw]


# ---------------------------------------------------------------------------------------
# whitespace
S = {
    "_": " ",
    "t": "\t",
    "n": "\u00a0",
    "f": "\x1c",
    "B": "\u2800",
    "H": "\u3164",
    "L": "\u2028",
    "N": "\x85",
    "0": "\x00",
    "D": "\x7f",
    "9": "\x9b",
    "z": "\u200b",
    "Z": "\ufeff",
    "M": "\U0001d173",
    "a": "a",
    "b": "b",
    "e": "\u00e9",
}


def whitespace(rng: random.Random, quick: bool) -> list[Tally]:
    small = ["_", "t", "B", "0", "z", "a", "b"]
    cases = [list(w) for w in words(small, 5 if quick else 7)]
    full = list(S)
    for _ in range(50_000 if quick else 300_000):
        cases.append([rng.choice(full) for _ in range(rng.randint(0, 16))])
    ans = run_model([f"S {' '.join(c)}" for c in cases])
    t = [
        Tally("collapse_whitespace"),
        Tally("strip_control_chars"),
        Tally("strip_zero_width_chars"),
    ]
    fns = [disarm.collapse_whitespace, disarm.strip_control_chars, disarm.strip_zero_width_chars]
    for c, a in zip(cases, ans, strict=True):
        text = "".join(S[x] for x in c)
        for tally, fn, part in zip(t, fns, a.split("|"), strict=True):
            model = "".join(S[x] for x in part.split())
            real = fn(text)
            tally.check(real == model, (c, ascii(real), ascii(model)))
    return t


# ---------------------------------------------------------------------------------------
# invisibles
def i_char(tok: str) -> str:
    fixed = {
        "a": "a",
        "b": "b",
        "F": "\U0001f3f4",
        "X": "\U000e007f",
        "o1": "\U000e0001",
        "oA": "\U000e0041",
        "o_": "\U000e0020",
        "J": "\u034f",
        "Q": "\ufffe",
        "P": "\ue000",
        "v1": "\ufe00",
        "v17": "\U000e0100",
        "V15": "\ufe0e",
        "V16": "\ufe0f",
        "M": "\U0001d173",
        "z": "\u200b",
        "_": " ",
        "n": "\u00a0",
        "B": "\u2800",
        "0": "\x00",
        "R": "\u202e",
        "Y": "\u00ad",
    }
    if tok in fixed:
        return fixed[tok]
    assert tok[0] == "t" and len(tok) == 2
    return chr(0xE0000 + ord(tok[1]))


FLAGS = [
    ["tg", "tb", "te", "tn", "tg"],
    ["tg", "tb", "ts", "tc", "tt"],
    ["tg", "tb", "tw", "tl", "ts"],
]


def invisibles(rng: random.Random, quick: bool) -> list[Tally]:
    small = ["a", "F", "tg", "X", "V16", "P", "_", "z"]
    cases = [list(w) for w in words(small, 5 if quick else 6)]
    singles = [
        "a",
        "b",
        "F",
        "X",
        "o1",
        "oA",
        "o_",
        "J",
        "Q",
        "P",
        "v1",
        "v17",
        "V15",
        "V16",
        "M",
        "z",
        "_",
        "n",
        "B",
        "0",
        "R",
        "Y",
        "tg",
        "tq",
    ]
    for _ in range(50_000 if quick else 300_000):
        c: list[str] = []
        for _ in range(rng.randint(0, 10)):
            r = rng.random()
            if r < 0.12:
                c += ["F"] + rng.choice(FLAGS) + ["X"]
            elif r < 0.18:
                fl = list(rng.choice(FLAGS))
                fl[rng.randrange(len(fl))] = "tq"
                c += ["F"] + fl[: rng.randint(0, len(fl))] + (["X"] if rng.random() < 0.7 else [])
            else:
                c.append(rng.choice(singles))
        cases.append(c)
    ans = run_model([f"I {' '.join(c)}" for c in cases])
    t_tags, t_fmt, t_cmp = (
        Tally("strip_tags"),
        Tally("strip_format"),
        Tally("canonicalize, on this alphabet"),
    )
    for c, a in zip(cases, ans, strict=True):
        text = "".join(i_char(x) for x in c)
        parts = [p.split() for p in a.split("|")]
        conc = ["".join(i_char(x) for x in p) for p in parts]
        real = disarm.strip_tags(text)
        t_tags.check(real == conc[0], (c, ascii(real), ascii(conc[0])))
        real = disarm.strip_format(text)
        t_fmt.check(real == conc[1], (c, ascii(real), ascii(conc[1])))
        real = disarm.canonicalize(text)
        t_cmp.check(real == conc[4], (c, ascii(real), ascii(conc[4])))
    return [t_tags, t_fmt, t_cmp]


# ---------------------------------------------------------------------------------------
# fold_punctuation
DASH = ["\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212"]
SQ = ["\u2018", "\u2019", "\u201a", "\u2032"]
DQ = ["\u201c", "\u201d", "\u201e", "\u2033"]
NSP = ["\u00a0"] + [chr(c) for c in range(0x2000, 0x200B)] + ["\u202f", "\u205f", "\u3000"]
OTHER = [
    "\u3002",
    "\u00b7",
    "\u1680",
    "\u201b",
    "\u201f",
    "\u2034",
    "\u2022",
    "\ufe58",
    "\uff0d",
    "\u2e3a",
    "\u060c",
    "\u2035",
]


def p_char(tok: str) -> str:
    k, n = tok[0], tok[1:]
    if k == "A":
        return chr(int(n))
    if k == "E":
        return "\u2026"
    return {"d": DASH, "s": SQ, "q": DQ, "n": NSP, "o": OTHER}[k][int(n)]


def punct(rng: random.Random, quick: bool) -> list[Tally]:
    toks = (
        [f"A{c}" for c in range(0x20, 0x7F)]
        + [f"d{i}" for i in range(len(DASH))]
        + [f"s{i}" for i in range(len(SQ))]
        + [f"q{i}" for i in range(len(DQ))]
        + ["E"]
        + [f"n{i}" for i in range(len(NSP))]
        + [f"o{i}" for i in range(len(OTHER))]
    )
    cases = [[t] for t in toks]
    for _ in range(20_000 if quick else 100_000):
        cases.append([rng.choice(toks) for _ in range(rng.randint(0, 12))])
    ans = run_model([f"P {' '.join(c)}" for c in cases])
    t = Tally("fold_punctuation")
    for c, a in zip(cases, ans, strict=True):
        text = "".join(p_char(x) for x in c)
        model = "".join(p_char(x) for x in a.split())
        real = disarm.fold_punctuation(text)
        t.check(real == model, (c, ascii(real), ascii(model)))
    return [t]


# ---------------------------------------------------------------------------------------
# edit distance, contraction
def utils(rng: random.Random, quick: bool) -> list[Tally]:
    pairs = [("".join(a), "".join(b)) for a in words(["a", "b"], 5) for b in words(["a", "b"], 5)]
    alpha = ["a", "b", "c", "\u00e9", "\u4e2d", "\U0001f600"]
    for _ in range(20_000 if quick else 100_000):
        pairs.append(
            tuple("".join(rng.choice(alpha) for _ in range(rng.randint(0, 8))) for _ in "ab")
        )
    ans = run_model([f"E {a or '-'} {b or '-'}" for a, b in pairs])
    t_ed = Tally("edit_distance")
    for (a, b), m in zip(pairs, ans, strict=True):
        real = disarm.edit_distance(a, b)
        t_ed.check(real == int(m), (ascii(a), ascii(b), real, m))
    ws = ["".join(w) for w in words(["r", "n", "v", "c", "l", "m", "x"], 4 if quick else 6) if w]
    ans = run_model([f"K {w}" for w in ws])
    t_k = Tally("contraction (is_suspicious_hostname(contractions=True).canonical)")
    for w, m in zip(ws, ans, strict=True):
        real = disarm.is_suspicious_hostname(w + ".com", contractions=True)[1].canonical
        t_k.check(real == m + ".com", (w, real, m))
    return [t_ed, t_k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seed", type=int, default=1016)
    ap.add_argument("--only", default="zalgo,width,whitespace,invisibles,punct,utils")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    ok = True
    total = agree = 0
    for name in args.only.split(","):
        print(name)
        for t in globals()[name](rng, args.quick):
            good = t.report()
            if not t.name.startswith("fixed"):
                ok &= good
                total += t.n
                agree += t.ok
    print(f"TOTAL (current model vs library): {agree}/{total}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
