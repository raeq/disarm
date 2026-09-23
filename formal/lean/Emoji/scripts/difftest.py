#!/usr/bin/env python3
"""Differential test: the Lean model against the real library.

Generates random strings over the model's alphabet (the code points in
Emoji/Tables.lean), runs every one through the Lean executable and through
`disarm`, and requires identical output for every mode:

  0 replace_emoji(s, "")          1 replace_emoji(s, " ")      2 replace_emoji(s, "#")
  3 the UNBOUNDED replace model vs replace_emoji(s, "")   (window-is-an-optimisation)
  4 demojize(s)  (errors="replace", replace_with="[?]")
  5 demojize(s, errors="ignore")  6 demojize(s, errors="preserve")
  7 TextPipeline(demojize=True)(s)
  8 demojize(s, provider=PROVIDER)
  9 demojize(s, errors="replace", replace_with="")

Usage (from formal/lean/Emoji, after `lake build emojimodel`):
  PATH=/path/to/venv/bin:$PATH python3 scripts/difftest.py [N] [SEED] [MAXLEN]

Also runs every string up to length 3 exhaustively before the random ones.

With --fixed the executable runs the FIXED model (Emoji/Fixes.lean): the harness must
then report disagreements, confined to the finding classes. That is its own
sensitivity check (a harness that cannot disagree proves nothing).
"""

from __future__ import annotations

import itertools
import pathlib
import random
import subprocess
import sys

import disarm

FIXED = "--fixed" in sys.argv
if FIXED:
    sys.argv.remove("--fixed")
HERE = pathlib.Path(__file__).resolve().parents[1]
EXE = HERE / ".lake" / "build" / "bin" / "emojimodel"

ALPHABET = [
    0x1F600,
    0x1F468,
    0x1F525,
    0x2764,
    0x2122,
    0x00A9,
    0x31,
    0x2A,
    0x20E3,
    0xFE0E,
    0xFE0F,
    0x200D,
    0x1F3FB,
    0xE0041,
    0x1F1E6,
    0x1F1E7,
    0x0301,
    0x78,
    0x20,
    0x20AC,
    0x2E,
]
# Over-weight the characters sequences are built from, so chains and seams get long.
WEIGHTS = [3, 3, 2, 2, 1, 2, 2, 1, 3, 2, 3, 5, 2, 1, 2, 2, 2, 2, 1, 1, 1]

PROVIDER_TABLE = {
    (0x31,): "ONE",
    (0x1F600,): "GRIN",
    (0x1F1E6,): "LETTER A",
    (0x1F468, 0x1F3FB): "PALE MAN",
}


class Provider:
    def lookup(self, seq: list[int]) -> str | None:
        return PROVIDER_TABLE.get(tuple(seq))


PROVIDER = Provider()
PIPE = disarm.TextPipeline(demojize=True)

MODES = [
    "replace_emoji(s,'')",
    "replace_emoji(s,' ')",
    "replace_emoji(s,'#')",
    "UNBOUNDED model vs replace_emoji(s,'')",
    "demojize(s)",
    "demojize(s,errors='ignore')",
    "demojize(s,errors='preserve')",
    "TextPipeline(demojize=True)(s)",
    "demojize(s,provider=P)",
    "demojize(s,errors='replace',replace_with='')",
]


def real(s: str) -> list[str]:
    r0 = disarm.replace_emoji(s, "")
    return [
        r0,
        disarm.replace_emoji(s, " "),
        disarm.replace_emoji(s, "#"),
        r0,
        disarm.demojize(s),
        disarm.demojize(s, errors="ignore"),
        disarm.demojize(s, errors="preserve"),
        PIPE(s),
        disarm.demojize(s, provider=PROVIDER),
        disarm.demojize(s, errors="replace", replace_with=""),
    ]


def enc(s: str) -> str:
    return " ".join(f"{ord(c):X}" for c in s)


def dec(h: str) -> str:
    return "".join(chr(int(x, 16)) for x in h.split())


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    maxlen = int(sys.argv[3]) if len(sys.argv) > 3 else 24
    rng = random.Random(seed)
    inputs: list[str] = [""]
    for k in range(1, 4):
        inputs += ["".join(map(chr, t)) for t in itertools.product(ALPHABET, repeat=k)]
    for _ in range(n):
        k = rng.randint(1, maxlen)
        inputs.append("".join(chr(c) for c in rng.choices(ALPHABET, WEIGHTS, k=k)))
    # Long ZWJ chains, to push the window's growth path (#995).
    for _ in range(n // 20):
        parts = rng.choices([0x1F468, 0x1F600, 0x2764, 0x1F525], k=rng.randint(2, 12))
        mods = [0x1F3FB, 0xFE0F, 0xFE0E, 0xE0041]
        s = "\u200d".join(
            chr(p) + "".join(chr(m) for m in rng.choices(mods, k=rng.randint(0, 2))) for p in parts
        )
        tail = "".join(chr(c) for c in rng.choices(ALPHABET, WEIGHTS, k=rng.randint(0, 6)))
        head = "".join(chr(c) for c in rng.choices(ALPHABET, WEIGHTS, k=rng.randint(0, 6)))
        inputs.append(head + s + tail)

    proc = subprocess.run(
        [str(EXE)] + (["fixed"] if FIXED else []),
        input="\n".join(enc(s) if s else " " for s in inputs) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    lines = proc.stdout.splitlines()
    assert len(lines) == len(inputs), (len(lines), len(inputs))
    bad = [0] * len(MODES)
    shown = [0] * len(MODES)
    for s, line in zip(inputs, lines, strict=True):
        model = [dec(f) for f in line.split("|")]
        want = real(s)
        for i, (m, w) in enumerate(zip(model, want, strict=True)):
            if m != w:
                bad[i] += 1
                if shown[i] < 5:
                    shown[i] += 1
                    print(f"MISMATCH {MODES[i]}: in={s!a} model={m!a} real={w!a}")
    print(
        f"{len(inputs)} inputs (all {len(ALPHABET)}-letter strings up to length 3, "
        f"then {n} random up to length {maxlen} and {n // 20} long ZWJ chains), seed {seed}"
    )
    for name, b in zip(MODES, bad, strict=True):
        print(f"  {name:48s} {len(inputs) - b:8d} agree, {b} disagree")
    return 1 if any(bad) else 0


if __name__ == "__main__":
    sys.exit(main())
