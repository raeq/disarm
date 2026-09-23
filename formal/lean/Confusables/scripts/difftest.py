#!/usr/bin/env python3
"""Differential test: the Lean model against the real library.

Runs every string over the model's alphabet (Confusables/Tables.lean) up to length
EXHAUSTIVE, then N weighted random strings up to MAXLEN, through the Lean executable
and through `disarm`, and compares these modes (Main.lean `modes` is the same list):

   0 normalize_confusables(s)                       (numeric)
   1 normalize_confusables(s, digit_policy="tr39")
   2 normalize_confusables(s, digit_policy="preserve")
   3 is_confusable(s)
   4 find_confusables(s)            (source and target; the byte offset is checked
                                     against the source text here, not in the model)
   5 find_unmapped_confusables(s)   (character; offset checked here)
   6 skeleton_key(s)                7 ... digit_policy="tr39"   8 ... "preserve"
   9 normalize(s, "NFC")           10 normalize(s, "NFD")      11 normalize(s, "NFKC")
  12 fold_case(s)

Usage (from formal/lean/Confusables, after `lake build confmodel`):
  PATH=/path/to/venv/bin:$PATH python3 scripts/difftest.py [N] [SEED] [MAXLEN] [EXHAUSTIVE]

With --fixed the executable runs the proposed skeleton_key fix (Fixes.lean) for modes
6-8: the harness must then report disagreements there, on the finding classes only.
That is its own sensitivity check (a harness that cannot disagree proves nothing).
"""

from __future__ import annotations

import collections
import itertools
import pathlib
import random
import re
import subprocess
import sys

import disarm

FIXED = "--fixed" in sys.argv
if FIXED:
    sys.argv.remove("--fixed")
HERE = pathlib.Path(__file__).resolve().parents[1]
EXE = HERE / ".lake" / "build" / "bin" / "confmodel"
TABLES = (HERE / "Confusables" / "Tables.lean").read_text()

# The alphabet, read back from the generated tables so the two cannot drift.
_DEF = r"def (c\w+) : Char := (?:'\\u([0-9A-F]{4})'|\(Char.ofNat 0x([0-9A-F]+)\))"
_defs = {m[0]: int(m[1] or m[2], 16) for m in re.findall(_DEF, TABLES)}
_order = re.search(r"def alphabet : List Char := \[([^\]]*)\]", TABLES).group(1).split(", ")
ALPHABET = [_defs[n] for n in _order]
# Over-weight the marks and the characters that fold, so clusters get long.
WEIGHTS = [3 if chr(cp) in "\u0300\u0301\u0308\u0327" else 2 for cp in ALPHABET]

MODES = [
    "normalize_confusables",
    "normalize_confusables(tr39)",
    "normalize_confusables(preserve)",
    "is_confusable",
    "find_confusables",
    "find_unmapped_confusables",
    "skeleton_key",
    "skeleton_key(tr39)",
    "skeleton_key(preserve)",
    "normalize(NFC)",
    "normalize(NFD)",
    "normalize(NFKC)",
    "fold_case",
]


def enc(s: str) -> str:
    return " ".join(f"{ord(c):X}" for c in s)


def offsets_ok(s: str, hits: list[tuple]) -> bool:
    """Each reported byte offset starts a character of `s`, and the hits come in order."""
    b = s.encode()
    starts = set()
    i = 0
    for ch in s:
        starts.add(i)
        i += len(ch.encode())
    offs = [h[1] for h in hits]
    return all(o in starts for o in offs) and offs == sorted(offs) and all(o < len(b) for o in offs)


def real(s: str) -> list[str]:
    fc = disarm.find_confusables(s)
    fu = disarm.find_unmapped_confusables(s)
    if not offsets_ok(s, fc) or not offsets_ok(s, fu):
        raise AssertionError(f"offset contract broken on {enc(s)}: {fc} {fu}")
    return [
        enc(disarm.normalize_confusables(s)),
        enc(disarm.normalize_confusables(s, digit_policy="tr39")),
        enc(disarm.normalize_confusables(s, digit_policy="preserve")),
        "1" if disarm.is_confusable(s) else "0",
        " ".join(f"{ord(c):X}=" + ".".join(f"{ord(x):X}" for x in t) for c, _, t in fc),
        enc("".join(c for c, _ in fu)),
        enc(disarm.skeleton_key(s)),
        enc(disarm.skeleton_key(s, digit_policy="tr39")),
        enc(disarm.skeleton_key(s, digit_policy="preserve")),
        enc(disarm.normalize(s, form="NFC")),
        enc(disarm.normalize(s, form="NFD")),
        enc(disarm.normalize(s, form="NFKC")),
        enc(disarm.fold_case(s)),
    ]


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    maxlen = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    exhaustive = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    rng = random.Random(seed)
    inputs: list[str] = []
    for k in range(exhaustive + 1):
        inputs.extend("".join(map(chr, t)) for t in itertools.product(ALPHABET, repeat=k))
    n_exh = len(inputs)
    for _ in range(n):
        k = rng.randint(1, maxlen)
        inputs.append("".join(chr(c) for c in rng.choices(ALPHABET, WEIGHTS, k=k)))
    args = [str(EXE)] + (["fixed"] if FIXED else [])
    feed = "".join(enc(s) + "\n" for s in inputs)
    proc = subprocess.run(args, input=feed, capture_output=True, text=True, check=True)
    lines = proc.stdout.removesuffix("\n").split("\n")
    diffs = collections.Counter()
    shown = collections.defaultdict(list)
    for s, line in zip(inputs, lines, strict=True):
        model = line.split("|")
        lib = real(s)
        for i, (m, r) in enumerate(zip(model, lib, strict=True)):
            if m != r:
                diffs[i] += 1
                if len(shown[i]) < 4:
                    shown[i].append(f"[{enc(s)}] model={m!r} lib={r!r}")
    print(
        f"inputs: {len(inputs)} ({n_exh} exhaustive to length {exhaustive}, {n} random to length {maxlen}, seed {seed})"
    )
    for i, name in enumerate(MODES):
        print(f"  {i:2d} {name:34s} disagreements: {diffs[i]}")
        for line in shown[i]:
            print("       ", line)
    return 1 if diffs and not FIXED else 0


if __name__ == "__main__":
    sys.exit(main())
