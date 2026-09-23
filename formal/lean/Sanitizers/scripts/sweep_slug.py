#!/usr/bin/env python3
"""Direct sweep of `slugify`, `Slugifier` and `UniqueSlugifier` against their postconditions.

    python3 scripts/sweep_slug.py [--scalars] [--params] [--unique]

No model involved. Non-ASCII test data is written as escapes only.

  S1 charset: every token is [a-z0-9]+ on the default path; on allow_unicode every
     character is L*/N*/M* or ZWJ/ZWNJ, and a joiner never starts or ends a token
  S2 separators: no leading or trailing separator, no empty token (a doubled
     separator), and no trailing *partial* multi-character separator
  S3 byte length <= max_length (when max_length > 0)
  S4 idempotent: slugify(slugify(x)) == slugify(x) with the same arguments
  S5 lowercase=True leaves nothing that lowercases differently
  S6 no token of the output is a stopword (docs: "case-insensitive")
  S7 at most two combining marks per base (allow_unicode, NFD count)
"""

from __future__ import annotations

import argparse
import collections
import random
import sys
import unicodedata

import disarm

JOINERS = {"\u200c", "\u200d"}


def tokens(out: str, sep: str) -> list[str]:
    return out.split(sep) if sep else [out]


def violations(out: str, kw: dict) -> list[str]:
    v: list[str] = []
    sep = kw.get("separator", "-")
    au = kw.get("allow_unicode", False)
    if out == "":
        return v
    if sep:
        toks = tokens(out, sep)
        if any(t == "" for t in toks):
            v.append("S2")
        # a trailing proper prefix of a multi-character separator
        for k in range(1, len(sep)):
            if out.endswith(sep[:k]) and not sep[:k].isalnum():
                v.append("S2-partial")
                break
    else:
        toks = [out]
    for t in toks:
        for i, c in enumerate(t):
            if au:
                cat = unicodedata.category(c)
                # `Cn` here means unassigned in *Python's* Unicode database, which is older
                # than the Rust core's: those are letters the core knows and Python does not.
                ok = cat[0] in "LNM" or cat == "Cn" or c in JOINERS
                if c in JOINERS and (i == 0 or i == len(t) - 1):
                    ok = False
            else:
                ok = c.isascii() and (c.isalnum())
            if not ok:
                v.append("S1")
                break
    ml = kw.get("max_length", 0)
    if ml and len(out.encode()) > ml:
        v.append("S3")
    if kw.get("lowercase", True) and out.lower() != out:
        v.append("S5")
    # S6 only where it is claimed: no truncation (which can cut a word down to a stopword,
    # as python-slugify's does), a non-empty separator, and with save_order only the ends.
    sw = {w.lower() for w in kw.get("stopwords", ())}
    if sw and sep and not kw.get("max_length", 0):
        ends = [toks[0], toks[-1]] if kw.get("save_order") else toks
        if any(t.lower() in sw for t in ends):
            v.append("S6")
    if au:
        run = 0
        for c in unicodedata.normalize("NFD", out):
            if unicodedata.combining(c) or unicodedata.category(c)[0] == "M":
                run += 1
                if run > 2:
                    v.append("S7")
                    break
            else:
                run = 0
    return v


class Tally:
    def __init__(self) -> None:
        self.n = 0
        self.bad: collections.Counter = collections.Counter()
        self.first: dict = {}

    def add(self, p: str, witness: tuple) -> None:
        self.bad[p] += 1
        prev = self.first.get(p)
        if prev is None or len(repr(witness)) < len(repr(prev)):
            self.first[p] = witness

    def check(self, text: str, **kw) -> None:
        self.n += 1
        out = disarm.slugify(text, **kw)
        v = violations(out, kw)
        again = disarm.slugify(out, **kw)
        if again != out:
            v.append("S4")
        for p in v:
            self.add(p, (text, kw, out, again))

    def report(self, title: str) -> None:
        print(f"== {title}: {self.n} calls")
        if not self.bad:
            print("   all postconditions hold")
        for p in sorted(self.bad):
            print(f"   {p}: {self.bad[p]} violations; shortest: {self.first[p]!r}")


def scalars() -> None:
    for kw in ({}, {"allow_unicode": True}, {"allow_unicode": True, "separator": ""}):
        t = Tally()
        for cp in range(0x110000):
            if 0xD800 <= cp <= 0xDFFF:
                continue
            c = chr(cp)
            for text in (c, "a" + c + "b", "A" + c, c + c + "x", "a" + c + "\u0301"):
                t.check(text, **kw)
        t.report(f"every scalar alone and embedded, {kw}")


def params(n: int, seed: int) -> None:
    rng = random.Random(seed)
    alpha = list("aB1 -_.!") + ["\u00e9", "\u200d", "\u0301", "\u0915", "\u094d", "&amp;"]
    t = Tally()
    for _ in range(n):
        text = "".join(rng.choice(alpha) for _ in range(rng.randint(0, 14)))
        kw = dict(
            # separators made of word characters (`"ab"`) are left out: they make the
            # separator indistinguishable from content, and nothing is claimed for them
            separator=rng.choice(["-", "_", "--", "-_", "", ".", "\u00b7"]),
            max_length=rng.choice([0, 1, 2, 3, 4, 5, 6, 7, 9, 12]),
            word_boundary=rng.random() < 0.5,
            save_order=rng.random() < 0.5,
            stopwords=rng.choice([(), ("a",), ("the", "B"), ("b1",)]),
            allow_unicode=rng.random() < 0.3,
            lowercase=rng.random() < 0.8,
        )
        t.check(text, **kw)
    t.report(f"{n} random inputs x random parameters (seed {seed})")


def unique() -> None:
    """UniqueSlugifier: returned values pairwise distinct, and each satisfies S2/S3."""
    t = Tally()
    inputs = ["ab cd", "ab cd", "ab cd", "ab", "ab", "ab-1", "!!!", "!!!", "x", "x", "a b c d e"]
    for ml in range(0, 9):
        for sep in ("-", "--", "_"):
            for au in (False, True):
                kw = dict(max_length=ml, separator=sep, allow_unicode=au)
                try:
                    u = disarm.UniqueSlugifier(**kw)
                except Exception:
                    continue
                got = []
                for text in inputs:
                    t.n += 1
                    try:
                        out = u(text)
                    except Exception as e:  # documented error paths
                        t.add("U-error:" + type(e).__name__, (text, kw, str(e)[:60]))
                        continue
                    if out in got:
                        t.add("U-dup", (text, kw, out, got))
                    got.append(out)
                    for p in violations(out, kw):
                        t.add("U-" + p, (inputs[: len(got)], kw, got))
    t.report("UniqueSlugifier sequences")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scalars", action="store_true")
    ap.add_argument("--params", action="store_true")
    ap.add_argument("--unique", action="store_true")
    ap.add_argument("--n", type=int, default=300_000)
    ap.add_argument("--seed", type=int, default=1016)
    a = ap.parse_args()
    run_all = not (a.scalars or a.params or a.unique)
    if a.unique or run_all:
        unique()
    if a.params or run_all:
        params(a.n, a.seed)
    if a.scalars or run_all:
        scalars()
    return 0


if __name__ == "__main__":
    sys.exit(main())
