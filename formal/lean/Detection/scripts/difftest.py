#!/usr/bin/env python3
"""Differential test: the three Lean models against the built library.

    python3 scripts/difftest.py [--exhaustive-anomaly N] [--exhaustive-smuggled N]
                                [--exhaustive-scripts N] [--random N] [--seed S]

Needs the driver built (`lake build difftest` in `formal/lean/Detection`) and an
importable `disarm`. Every abstract class maps to one concrete code point through an
injective table, so the library sees exactly the word the model reasons about.

* `A` cases: `hasAnomalies` against `disarm.has_anomalies(text)` (no lexicon).
* `S` cases: `decode` against `disarm.decode_smuggled(text)`: scheme, byte span, units
  and bytes of every payload, and `text` wherever the model decides it (ASCII payloads).
* `M` cases: `isMixed` against `disarm.is_mixed_script(text)`.

Exit status is 0 only when every case agrees. Non-ASCII characters are written as escapes
throughout, never literally.
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

ANOMALY = {
    "a": "e",
    "p": "\u00e9",
    "m": "\u0301",
    "h": "\u05d0",
    "d": "1",
    "sp": " ",
    "zw": "\u200b",
    "nj": "\u200c",
    "fmt": "\u206a",
    "shy": "\u00ad",
    "vs": "\ufe01",
    "tag": "\U000e0061",
    "pua": "\ue000",
    "rlo": "\u202e",
    "rli": "\u2067",
    "rlm": "\u200f",
    "lrm": "\u200e",
    "cr": "\r",
    "lf": "\n",
    "bel": "\x07",
}

SCRIPTS = {
    "common": "1",
    "inherited": "\u0301",
    "latin": "a",
    "greek": "\u03b1",
    "cyrillic": "\u0430",
    "hebrew": "\u05d0",
    "han": "\u4e00",
    "hira": "\u3042",
    "kana": "\u30a2",
    "hang": "\uac00",
    "deva": "\u0915",
    "beng": "\u0995",
}

#: Byte values the smuggled alphabet draws on: the ends of both selector blocks, printable
#: ASCII, the flag letters `g b e n s c t w l`, and a tag code point below the byte range.
VS_BYTES = [0, 1, 15, 16, 104, 105, 127, 128, 255]
TAG_CODES = [
    0x1F,
    0x20,
    0x41,
    0x62,
    0x63,
    0x65,
    0x67,
    0x68,
    0x69,
    0x6C,
    0x6E,
    0x73,
    0x74,
    0x77,
    0x7E,
]


def s_char(tok: str) -> str:
    fixed = {
        "z0": "\u200b",
        "z1": "\u200c",
        "zs": "\u200d",
        "x": "x",
        "flag": "\U0001f3f4",
        "cancel": "\U000e007f",
    }
    if tok in fixed:
        return fixed[tok]
    n = int(tok[1:])
    if tok[0] == "v":
        return chr(0xFE00 + n) if n < 16 else chr(0xE0100 + n - 16)
    return chr(0xE0000 + n)


def enc_tag(bs):  # tag_ascii
    return [f"t{b}" for b in bs]


def enc_vs(bs):  # variation_bytes
    return [f"v{b}" for b in bs]


def enc_zw(bs):  # zero_width_binary, MSB first
    return ["z1" if (b >> (7 - i)) & 1 else "z0" for b in bs for i in range(8)]


def run_model(lines: list[str]) -> list[str]:
    out = subprocess.run(
        [str(EXE)], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert len(out) == len(lines), (len(out), len(lines))
    return out


def anomaly_cases(args, rng):
    keys = list(ANOMALY)
    for n in range(args.exhaustive_anomaly + 1):
        yield from itertools.product(keys, repeat=n)
    for _ in range(args.random):
        yield tuple(rng.choice(keys) for _ in range(rng.randint(0, 16)))


def smuggled_alphabet():
    return (
        ["z0", "z1", "zs", "x", "flag", "cancel"]
        + [f"v{b}" for b in VS_BYTES]
        + [f"t{c}" for c in TAG_CODES]
    )


def smuggled_cases(args, rng):
    alpha = smuggled_alphabet()
    for n in range(args.exhaustive_smuggled + 1):
        yield from itertools.product(alpha, repeat=n)
    flags = [
        ["flag", "t103", "t98", "t115", "t99", "t116", "cancel"],
        ["flag", "t103", "t98", "t101", "t110", "t103", "cancel"],
        ["flag", "t103", "t98", "t115", "t99", "cancel"],
    ]
    for _ in range(args.random):
        toks: list[str] = []
        for _ in range(rng.randint(0, 5)):
            r = rng.random()
            bs = [
                rng.choice([rng.randrange(256), rng.randrange(0x20, 0x7F)])
                for _ in range(rng.randint(0, 4))
            ]
            if r < 0.2:
                toks += enc_tag([b % 0x5F + 0x20 for b in bs])
            elif r < 0.4:
                toks += enc_vs(bs)
            elif r < 0.6:
                toks += enc_zw(bs)
            elif r < 0.7:
                toks += rng.choice(flags)
            else:
                toks += [rng.choice(alpha) for _ in range(rng.randint(1, 3))]
        yield tuple(toks)


def script_cases(args, rng):
    keys = list(SCRIPTS)
    for n in range(args.exhaustive_scripts + 1):
        yield from itertools.product(keys, repeat=n)
    for _ in range(args.random):
        yield tuple(rng.choice(keys) for _ in range(rng.randint(0, 10)))


def lib_payloads(text: str) -> str:
    parts = []
    for p in disarm.decode_smuggled(text):
        parts.append((p.scheme, p.start, p.end, p.units, list(p.data), p.text))
    return parts


def model_payloads(line: str, toks: tuple[str, ...]):
    chars = [s_char(t) for t in toks]
    offs = [0]
    for c in chars:
        offs.append(offs[-1] + len(c.encode()))
    out = []
    for item in filter(None, (x.strip() for x in line.split(";"))):
        f = item.split()
        scheme, start, units = f[0], int(f[1]), int(f[2])
        bs = [int(b) for b in f[3:]]
        out.append((scheme, offs[start], offs[start + units], units, bs, bs))
    return out


def text_matches(model_bytes, lib_text) -> bool:
    if all(b < 0x80 for b in model_bytes):
        want = (
            bytes(model_bytes).decode()
            if model_bytes and all(0x20 <= b <= 0x7E for b in model_bytes)
            else None
        )
        return want == lib_text
    return True  # non-ASCII payloads: the model does not decide `text`


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exhaustive-anomaly", type=int, default=4)
    ap.add_argument("--exhaustive-smuggled", type=int, default=3)
    ap.add_argument("--exhaustive-scripts", type=int, default=4)
    ap.add_argument("--random", type=int, default=100_000)
    ap.add_argument("--seed", type=int, default=1016)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    fails = 0

    # A: has_anomalies
    cases = list(anomaly_cases(args, rng))
    answers = run_model(["A " + " ".join(c) for c in cases])
    agree = 0
    for c, ans in zip(cases, answers, strict=True):
        text = "".join(ANOMALY[t] for t in c)
        lib = disarm.has_anomalies(text)
        model = ans.split()[0] == "1"
        if lib == model:
            agree += 1
        else:
            fails += 1
            if fails <= 20:
                print("A MISMATCH", c, ascii(text), "lib", lib, "model", model)
    print(f"has_anomalies: {agree} of {len(cases)} agree")

    # S: decode_smuggled
    cases = list(smuggled_cases(args, rng))
    answers = run_model(["S " + " ".join(c) for c in cases])
    agree = 0
    for c, ans in zip(cases, answers, strict=True):
        text = "".join(s_char(t) for t in c)
        lib = lib_payloads(text)
        model = model_payloads(ans, c)
        ok = len(lib) == len(model) and all(
            lp[:5] == mp[:5] and text_matches(mp[4], lp[5])
            for lp, mp in zip(lib, model, strict=True)
        )
        if ok:
            agree += 1
        else:
            fails += 1
            if fails <= 20:
                print("S MISMATCH", c, "lib", lib, "model", model)
    print(f"decode_smuggled: {agree} of {len(cases)} agree")

    # M: is_mixed_script
    cases = list(script_cases(args, rng))
    answers = run_model(["M " + " ".join(c) for c in cases])
    agree = 0
    for c, ans in zip(cases, answers, strict=True):
        text = "".join(SCRIPTS[t] for t in c)
        lib = disarm.is_mixed_script(text)
        if lib == (ans == "1"):
            agree += 1
        else:
            fails += 1
            if fails <= 20:
                print("M MISMATCH", c, ascii(text), "lib", lib, "model", ans)
    print(f"is_mixed_script: {agree} of {len(cases)} agree")

    print("RESULT:", "all agree" if fails == 0 else f"{fails} disagreements")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
