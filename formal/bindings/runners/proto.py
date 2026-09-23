"""The harness protocol, shared by the Python-hosted runners (Python binding, C ABI).

See `../README.md` ("The harness") and `../rust_oracle/src/main.rs`, whose `enc`
this mirrors byte for byte.
"""

from __future__ import annotations

import os
import sys
import zlib
from collections.abc import Callable
from typing import Any

NSCALAR = 0x110000 - 0x800
BLOCK = 4096


class Rec:
    """A struct-shaped value: encoded as `r<n>:` + fields, in declared order."""

    def __init__(self, *fields: Any) -> None:
        self.fields = fields


class Err(Exception):
    """A binding error normalised to the oracle's two classes: 'inv' or 'err'."""

    def __init__(self, kind: str, msg: str) -> None:
        super().__init__(msg)
        self.kind = kind
        self.msg = msg


def enc(v: Any, out: bytearray) -> None:
    if isinstance(v, bool):
        out += b"b1" if v else b"b0"
    elif isinstance(v, int):
        out += b"i%d;" % v
    elif v is None:
        out += b"n"
    elif isinstance(v, str):
        b = v.encode("utf-8", "surrogatepass")
        out += b"s%d:" % len(b)
        out += b
    elif isinstance(v, Rec):
        out += b"r%d:" % len(v.fields)
        for f in v.fields:
            enc(f, out)
    elif isinstance(v, (list, tuple)):
        out += b"l%d:" % len(v)
        for x in v:
            enc(x, out)
    else:
        raise TypeError(f"cannot encode {type(v).__name__}")


def encode_call(fn: Callable[[str], Any], text: str) -> bytes:
    out = bytearray()
    try:
        v = fn(text)
    except Err as e:
        out += b"e%s:" % e.kind.encode()
        enc(e.msg, out)
        return bytes(out)
    enc(v, out)
    return bytes(out)


def load_corpus(path: str) -> list[str]:
    with open(path, encoding="ascii") as f:
        return [bytes.fromhex(line.strip()).decode("utf-8") for line in f]


def inp(i: int, corpus: list[str]) -> str:
    if i < NSCALAR:
        return chr(i if i < 0xD800 else i + 0x800)
    return corpus[i - NSCALAR]


def surrogate_check(cases: dict[str, Callable[[str], Any]], n: int, seed: int) -> None:
    """`surr N SEED`: the malformed-Unicode contract (THREAT_MODEL.md, #469), relationally.

    For N random strings mixing lone surrogates, well-formed pairs written as two code
    units, and ordinary text, every case must give the same answer on `s` as on
    `scrub(s)`, where `scrub` recombines pairs and turns each lone surrogate into one
    U+FFFD. (That the binding agrees with the core on well-formed text is the `crc`
    sweep's job; this checks only the boundary.) Prints one line per case.
    """
    import random

    rng = random.Random(seed)
    units = [
        lambda: chr(rng.randint(0xD800, 0xDBFF)),
        lambda: chr(rng.randint(0xDC00, 0xDFFF)),
        lambda: chr(rng.randint(0x61, 0x7A)),
        lambda: " ",
        lambda: chr(rng.choice([0xE9, 0x430, 0x5D0, 0x301, 0x200B, 0x202E])),
        lambda: chr(rng.randint(0x1F600, 0x1F64F)),
    ]

    def scrub(s: str) -> str:
        return s.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")

    strings = []
    for _ in range(n):
        s = "".join(rng.choice(units)() for _ in range(rng.randint(1, 12)))
        # Split some astral characters into two code units, so pairs arrive unjoined.
        if rng.random() < 0.5:
            s = "".join(
                chr(0xD800 + ((ord(c) - 0x10000) >> 10))
                + chr(0xDC00 + ((ord(c) - 0x10000) & 0x3FF))
                if ord(c) > 0xFFFF
                else c
                for c in s
            )
        strings.append(s)
    for case, fn in cases.items():
        bad = [s for s in strings if encode_call(fn, s) != encode_call(fn, scrub(s))]
        ex = ascii(bad[0]) if bad else ""
        print(f"{case}\t{len(strings)}\t{len(bad)}\t{ex}")


def main(
    cases: dict[str, Callable[[str], Any]], skip: Callable[[str], bool] = lambda t: False
) -> None:
    """`crc CORPUS CASES` | `dump CORPUS CASE FROM TO` | `list`.

    `skip(text)` marks an input the binding cannot express (the C ABI cannot carry
    U+0000); a skipped input is encoded as `x` and the driver excludes it.
    """
    mode = sys.argv[1]
    out = sys.stdout
    if mode == "list":
        print(",".join(cases))
        return
    if mode == "surr":
        surrogate_check(cases, int(sys.argv[2]), int(sys.argv[3]))
        return
    corpus = load_corpus(sys.argv[2])
    total = NSCALAR + len(corpus)

    # Harness self-test: HARNESS_PERTURB=i corrupts the record for input i, and the
    # driver must then report exactly that one input as differing.
    perturb = int(os.environ.get("HARNESS_PERTURB", "-1"))

    def one(case: str, t: str, i: int = -2) -> bytes:
        rec = b"x" if skip(t) else encode_call(cases[case], t)
        return rec + b"!" if i == perturb else rec

    if mode == "crc":
        for case in sys.argv[3].split(","):
            if case not in cases:
                continue
            for block in range((total + BLOCK - 1) // BLOCK):
                lo, hi = block * BLOCK, min((block + 1) * BLOCK, total)
                crc = 0
                for i in range(lo, hi):
                    crc = zlib.crc32(one(case, inp(i, corpus), i), crc)
                out.write(f"{case}\t{block}\t{crc:08x}\t{hi - lo}\n")
            out.flush()
    elif mode == "dump":
        case, lo, hi = sys.argv[3], int(sys.argv[4]), min(int(sys.argv[5]), total)
        for i in range(lo, hi):
            out.write(f"{i}\t{one(case, inp(i, corpus), i).hex()}\n")
    else:
        raise SystemExit(f"unknown mode {mode}")
