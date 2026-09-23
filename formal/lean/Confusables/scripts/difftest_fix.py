#!/usr/bin/env python3
"""The model of the fix against a build of the fix.

Feeds the same inputs (every string over the alphabet up to length EXHAUSTIVE, then N
weighted random strings up to MAXLEN) to

* the Lean executable in ``fixed`` mode (Confusables/Fixes.lean), and
* ``probe emit`` built against a crate with the proposed patch applied
  (``repro/fix.patch``; see the README for how to build it outside the worktree),

and compares ``skeleton_key`` under the three policies (model modes 6-8). With the
shipped crate instead of the patched one, the same script must report disagreements
on the finding classes: that is its sensitivity check.

Usage (from formal/lean/Confusables, after `lake build confmodel`):
  python3 scripts/difftest_fix.py PROBE_BINARY [N] [SEED] [MAXLEN] [EXHAUSTIVE]

Needs no Python `disarm`: both sides are executables.
"""

from __future__ import annotations

import collections
import itertools
import pathlib
import random
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parents[1]
EXE = HERE / ".lake" / "build" / "bin" / "confmodel"
TABLES = (HERE / "Confusables" / "Tables.lean").read_text()
_DEF = r"def (c\w+) : Char := (?:'\\u([0-9A-F]{4})'|\(Char.ofNat 0x([0-9A-F]+)\))"
_defs = {m[0]: int(m[1] or m[2], 16) for m in re.findall(_DEF, TABLES)}
_order = re.search(r"def alphabet : List Char := \[([^\]]*)\]", TABLES).group(1).split(", ")
ALPHABET = [_defs[n] for n in _order]


def enc(cps: tuple[int, ...]) -> str:
    return " ".join(f"{c:X}" for c in cps)


def main() -> int:
    probe = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 50000
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    maxlen = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    exhaustive = int(sys.argv[5]) if len(sys.argv) > 5 else 4
    rng = random.Random(seed)
    inputs = [t for k in range(exhaustive + 1) for t in itertools.product(ALPHABET, repeat=k)]
    inputs += [tuple(rng.choices(ALPHABET, k=rng.randint(1, maxlen))) for _ in range(n)]
    feed = "".join(enc(s) + "\n" for s in inputs)
    model = subprocess.run(
        [str(EXE), "fixed"], input=feed, capture_output=True, text=True, check=True
    )
    real = subprocess.run([probe, "emit"], input=feed, capture_output=True, text=True, check=True)
    diffs = collections.Counter()
    shown = collections.defaultdict(list)
    names = ["skeleton_key", "skeleton_key(tr39)", "skeleton_key(preserve)"]
    model_lines = model.stdout.removesuffix("\n").split("\n")
    real_lines = real.stdout.removesuffix("\n").split("\n")
    for s, m, r in zip(inputs, model_lines, real_lines, strict=True):
        mm = m.split("|")[6:9]
        rr = r.split("|")[3:6]
        for i, (a, b) in enumerate(zip(mm, rr, strict=True)):
            if a != b:
                diffs[i] += 1
                if len(shown[i]) < 4:
                    shown[i].append(f"[{enc(s)}] model={a!r} probe={b!r}")
    print(f"inputs: {len(inputs)} ({exhaustive=}, {n} random to length {maxlen}, seed {seed})")
    for i, name in enumerate(names):
        print(f"  FIXED {name:24s} disagreements: {diffs[i]}")
        for line in shown[i]:
            print("       ", line)
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
