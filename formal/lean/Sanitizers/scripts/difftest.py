#!/usr/bin/env python3
"""Differential test: the Lean models against the real library.

    python3 scripts/difftest.py [--only F|S|U|L|E|D] [--exhaustive N] [--random N] [--seed S]

Needs the model's driver built (`lake build difftest` in `formal/lean/Sanitizers`) and an
importable `disarm`. Each model is fed the same cases as the library, through the public
Python surface, and the outputs are compared as strings. Exit status is 0 only when every
comparison agrees.

Model tags (one per line of the driver protocol, see `Main.lean`):

  F  sanitize_filename            S  slugify (ASCII path)
  U  UniqueSlugifier sequences    L  strip_log_injection
  E  escape_html / percent_encode D  edit_distance

The exhaustive alphabets are the ones `Sanitizers/Bounded.lean` quantifies over, so a
bounded theorem about the *current* model is also a statement about the library on those
words. Non-ASCII test data is written as escapes only.
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

PLAT = {"u": "universal", "w": "windows", "p": "posix"}


def enc(s: str) -> str:
    return ".".join(str(ord(c)) for c in s)


def dec(s: str) -> str:
    return (
        "".join(chr(int(t)) if t.isdecimal() else "<" + t + ">" for t in s.split(".")) if s else ""
    )


def words(alpha, n):
    for k in range(n + 1):
        for w in itertools.product(alpha, repeat=k):
            yield "".join(w)


class Runner:
    """Feeds cases to the Lean driver in chunks and compares with the library."""

    def __init__(self) -> None:
        self.total = 0
        self.agree = 0
        self.fix_changed = 0
        self.mismatches: list = []
        self.batch: list = []

    def add(self, line: str, expected: str, label) -> None:
        self.batch.append((line, expected, label))
        if len(self.batch) >= 100_000:
            self.flush()

    def flush(self) -> None:
        if not self.batch:
            return
        inp = "".join(line + "\n" for line, _, _ in self.batch)
        res = subprocess.run([str(EXE)], input=inp, capture_output=True, text=True, check=True)
        outs = res.stdout.split("\n")
        for (line, expected, label), out in zip(self.batch, outs[: len(self.batch)], strict=True):
            self.total += 1
            cur, _, fixed = out.partition("\t")
            if cur.startswith("ERR"):
                raise SystemExit(f"driver error {cur} on {line!r}")
            if cur == expected:
                self.agree += 1
            else:
                if len(self.mismatches) < 20:
                    self.mismatches.append(
                        (
                            label,
                            ascii(dec(cur)) if not cur.startswith("#") else cur,
                            ascii(dec(expected)) if not expected.startswith("#") else expected,
                        )
                    )
            if fixed != cur:
                self.fix_changed += 1
        self.batch = []


# ---------------------------------------------------------------- F: sanitize_filename

F_ALPHA = [".", " ", "/", "*", "_", "c", "o", "n", "x"]
F_SEPS = ["_", "", "-", " "]
F_MAX = [0, 1, 2, 3, 4, 5, 6, 8]
F_RAND_ALPHA = list('abcCONnulAUX.. //\\:*?"<>|_-%$1') + [
    "\t",
    "\x00",
    "\x01",
    "\x1f",
    "\x7f",
    "\n",
    "\r",
    "\x0b",
]


def f_case(r: Runner, text: str, sep: str, ml: int, pl: str, pe: bool) -> None:
    expected = disarm.sanitize_filename(
        text, separator=sep, max_length=ml, platform=PLAT[pl], preserve_extension=pe
    )
    line = "\t".join(["F", enc(text), enc(sep), str(ml), pl, "1" if pe else "0"])
    r.add(line, enc(expected), ("F", text, sep, ml, pl, pe))


def run_f(r: Runner, n_exh: int, n_rand: int, rng: random.Random) -> None:
    for w in words(F_ALPHA, n_exh):
        for sep, ml, pl, pe in itertools.product(F_SEPS, F_MAX, "up", (False, True)):
            f_case(r, w, sep, ml, pl, pe)
    for _ in range(n_rand):
        w = "".join(rng.choice(F_RAND_ALPHA) for _ in range(rng.randint(0, 16)))
        f_case(
            r,
            w,
            rng.choice(F_SEPS + ["--", ".", "ab"]),
            rng.choice([0, 1, 2, 3, 4, 5, 7, 9, 12, 20]),
            rng.choice("uwp"),
            rng.random() < 0.5,
        )


# ---------------------------------------------------------------- S: slugify (ASCII path)

S_ALPHA = ["a", "B", "1", " ", "-", "!"]
S_SEPS = ["-", "", "--", "-_", "."]
S_STOPS = [(), ("a",), ("A", "b1"), ("b",)]
S_RAND_ALPHA = list("abcABC019 -_.!?/#'\"()[]") + ["\t", "\x7f"]


def s_line(text, sep, ml, wb, so, lc, stops) -> str:
    return "\t".join(
        [
            "S",
            enc(text),
            enc(sep),
            str(ml),
            "1" if wb else "0",
            "1" if so else "0",
            "1" if lc else "0",
            ",".join(enc(w) for w in stops),
        ]
    )


def s_case(r: Runner, text, sep, ml, wb, so, lc, stops) -> None:
    expected = disarm.slugify(
        text,
        separator=sep,
        max_length=ml,
        word_boundary=wb,
        save_order=so,
        lowercase=lc,
        stopwords=list(stops),
    )
    r.add(
        s_line(text, sep, ml, wb, so, lc, stops),
        enc(expected),
        ("S", text, sep, ml, wb, so, lc, stops),
    )


def run_s(r: Runner, n_exh: int, n_rand: int, rng: random.Random) -> None:
    for w in words(S_ALPHA, n_exh):
        for sep, ml, wb, stops in itertools.product(
            S_SEPS, (0, 1, 2, 3, 4, 5), (False, True), S_STOPS
        ):
            s_case(r, w, sep, ml, wb, rng.random() < 0.5, rng.random() < 0.8, stops)
    for _ in range(n_rand):
        w = "".join(rng.choice(S_RAND_ALPHA) for _ in range(rng.randint(0, 20)))
        stops = rng.choice(S_STOPS + [("the", "of"), ("ab", "C")])
        s_case(
            r,
            w,
            rng.choice(S_SEPS + ["_", "ab", "--_"]),
            rng.choice([0, 1, 2, 3, 4, 5, 6, 8, 10, 15]),
            rng.random() < 0.5,
            rng.random() < 0.5,
            rng.random() < 0.8,
            stops,
        )


# ---------------------------------------------------------------- U: UniqueSlugifier

U_TEXTS = ["ab cd", "ab", "ab-1", "!!!", "x", "a b c", "AB CD", "ab c", "abcdef"]


def u_case(r: Runner, texts, sep, ml, wb, so, lc, stops) -> None:
    u = disarm.UniqueSlugifier(
        separator=sep,
        max_length=ml,
        word_boundary=wb,
        save_order=so,
        lowercase=lc,
        stopwords=list(stops),
    )
    out = []
    for t in texts:
        try:
            out.append(enc(u(t)))
        except disarm.DisarmError as e:
            msg = str(e)
            out.append(
                "#M" if "too small" in msg else "#A" if "attempt" in msg.lower() else "#?" + msg
            )
    line = "\t".join(
        [
            "U",
            enc(sep),
            str(ml),
            "1" if wb else "0",
            "1" if so else "0",
            "1" if lc else "0",
            ",".join(enc(w) for w in stops),
            ",".join(enc(t) for t in texts),
        ]
    )
    r.add(line, ",".join(out), ("U", texts, sep, ml, wb, so, lc, stops))


def run_u(r: Runner, n_exh: int, n_rand: int, rng: random.Random) -> None:
    for _ in range(max(n_rand // 10, 1000)):
        texts = [rng.choice(U_TEXTS) for _ in range(rng.randint(1, 12))]
        u_case(
            r,
            texts,
            rng.choice(["-", "--", "_", "-_"]),
            rng.choice(range(0, 10)),
            rng.random() < 0.5,
            rng.random() < 0.5,
            rng.random() < 0.8,
            rng.choice([(), ("ab",), ("x",)]),
        )
    # one long run of a single base, across the counter's digit boundaries
    for ml in (0, 2, 3, 4, 5):
        u_case(r, ["ab"] * 120, "-", ml, False, False, True, ())


# ---------------------------------------------------------------- L, H, P, D

L_ALPHA = [
    "a",
    "\t",
    "\r",
    "\n",
    "\x00",
    "\x1b",
    "\x7f",
    "\x85",
    "\x9b",
    "\u2028",
    "\u2029",
    "\u202e",
    "\u200b",
    "\u00e9",
]


def run_l(r: Runner, n_exh: int, n_rand: int, rng: random.Random) -> None:
    for w in words(L_ALPHA, min(n_exh, 4)):
        for rep, kt in itertools.product(["\ufffd", "", "?", "ab"], (False, True)):
            exp = disarm.strip_log_injection(w, replacement=rep, keep_tab=kt)
            r.add(
                "\t".join(["L", enc(w), enc(rep), "1" if kt else "0"]), enc(exp), ("L", w, rep, kt)
            )


E_ALPHA = ["a", "&", "<", ">", '"', "'", " ", "+", "%", "/", "~", "\u00e9", "\U0001f600", "\x00"]


def run_e(r: Runner, n_exh: int, n_rand: int, rng: random.Random) -> None:
    for w in words(E_ALPHA, min(n_exh, 4)):
        r.add("\t".join(["H", enc(w)]), enc(disarm.escape_html(w)), ("H", w))
        for comp in ("path", "segment", "query", "form"):
            r.add(
                "\t".join(["P", comp, enc(w)]),
                enc(disarm.percent_encode(w, component=comp)),
                ("P", comp, w),
            )
    for _ in range(n_rand // 4):
        w = "".join(chr(rng.randint(0, 0x2FF)) for _ in range(rng.randint(0, 12)))
        r.add("\t".join(["H", enc(w)]), enc(disarm.escape_html(w)), ("H", w))
        comp = rng.choice(("path", "segment", "query", "form"))
        r.add(
            "\t".join(["P", comp, enc(w)]),
            enc(disarm.percent_encode(w, component=comp)),
            ("P", comp, w),
        )


D_ALPHA = ["a", "b", "\u00e9", "\u0301"]


def run_d(r: Runner, n_exh: int, n_rand: int, rng: random.Random) -> None:
    ws = list(words(D_ALPHA, min(n_exh, 4)))
    for a in ws:
        for b in ws[:: max(1, len(ws) // 60)]:
            r.add("\t".join(["D", enc(a), enc(b)]), str(disarm.edit_distance(a, b)), ("D", a, b))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--exhaustive", type=int, default=5)
    ap.add_argument("--random", type=int, default=200_000)
    ap.add_argument("--seed", type=int, default=1016)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    tags = a.only or "FSULED"
    ok = True
    for tag, fn in (
        ("F", run_f),
        ("S", run_s),
        ("U", run_u),
        ("L", run_l),
        ("E", run_e),
        ("D", run_d),
    ):
        if tag not in tags:
            continue
        r = Runner()
        fn(r, a.exhaustive, a.random, rng)
        r.flush()
        print(
            f"{tag}: {r.agree} of {r.total} agree; the fixed model differs from the "
            f"current one on {r.fix_changed}"
        )
        for m in r.mismatches:
            print("   MISMATCH", m)
        ok &= r.agree == r.total
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
