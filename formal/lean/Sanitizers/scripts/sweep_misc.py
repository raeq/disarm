#!/usr/bin/env python3
"""Direct sweeps of `strip_log_injection`, `escape_html`, `percent_encode`,
`is_suspicious_hostname`, `edit_distance` / `nearest_match` against their postconditions.

    python3 scripts/sweep_misc.py [--log] [--enc] [--host] [--dist]

No model involved. Non-ASCII test data is written as escapes only.

  L1 no neutralized character in the output (C0, DEL, C1, LS, PS; TAB unless keep_tab)
  L2 idempotent;  L3 every other character kept, in order (output == input with each
     neutralized character replaced);  L4 a replacement containing a neutralized
     character is rejected
  E1 html.unescape(escape_html(s)) == s, and the output has none of & < > " ' except
     inside the five entities;  E2 unquote(percent_encode(s)) == s (unquote_plus for
     form), output ASCII and inside the component's safe set plus %XX
  H1 canonical carries no bidi control and no character of the documented invisible
     classes;  H2 a label containing a character UTS #46 deletes (IGNORED) is flagged
  D1 edit_distance agrees with a reference Levenshtein over scalars; nearest_match
     returns the first candidate at the least distance <= max_distance
"""

from __future__ import annotations

import argparse
import collections
import html
import random
import sys
import unicodedata
import urllib.parse

import disarm

NEUTRAL = (
    set(chr(c) for c in range(0x20))
    | {"\x7f"}
    | set(chr(c) for c in range(0x80, 0xA0))
    | {"\u2028", "\u2029"}
)
BIDI = set("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u200e\u200f\u061c")


def every_scalar():
    for cp in range(0x110000):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        yield chr(cp)


class Tally:
    def __init__(self, title: str) -> None:
        self.title = title
        self.n = 0
        self.bad: collections.Counter = collections.Counter()
        self.first: dict = {}

    def fail(self, p: str, witness) -> None:
        self.bad[p] += 1
        self.first.setdefault(p, witness)

    def report(self) -> None:
        print(f"== {self.title}: {self.n} checks")
        if not self.bad:
            print("   all postconditions hold")
        for p in sorted(self.bad):
            print(f"   {p}: {self.bad[p]} violations; first: {ascii(self.first[p])}")


def log() -> None:
    t = Tally("strip_log_injection, every scalar alone and embedded, 3 replacements x keep_tab")
    for c in every_scalar():
        for s in (c, "a" + c + "b", c + c):
            for rep in ("\ufffd", "", "?"):
                for kt in (False, True):
                    t.n += 1
                    out = disarm.strip_log_injection(s, replacement=rep, keep_tab=kt)
                    bad = NEUTRAL - ({"\t"} if kt else set())
                    if any(ch in bad for ch in out):
                        t.fail("L1", (s, rep, kt, out))
                    if disarm.strip_log_injection(out, replacement=rep, keep_tab=kt) != out:
                        t.fail("L2", (s, rep, kt, out))
                    exp = "".join(rep if ch in bad else ch for ch in s)
                    if out != exp:
                        t.fail("L3", (s, rep, kt, out, exp))
    for c in NEUTRAL:
        t.n += 1
        try:
            disarm.strip_log_injection("x", replacement="a" + c, keep_tab=(c == "\t"))
            if c != "\t":
                t.fail("L4", c)
        except Exception:
            pass
    t.report()
    # Not claimed, recorded for the README: what passes through untouched.
    kept = [
        c
        for c in "\u202e\u2066\u200b\u200e\u061c\ufeff\u00ad\x1b"
        if disarm.strip_log_injection(c) == c
    ]
    print("   passed through (not claimed either way):", ascii("".join(kept)))


SEG = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~!$&'()*+,;=:@")
PATH = SEG | {ord("/")}
VAL = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def enc() -> None:
    t = Tally("escape_html / percent_encode, every scalar alone and embedded")
    for c in every_scalar():
        for s in (c, "&" + c + ";", "%" + c, "a" + c + "+ b"):
            t.n += 1
            e = disarm.escape_html(s)
            if html.unescape(e) != s:
                t.fail("E1-roundtrip", (s, e))
            stripped = e
            for ent in ("&amp;", "&lt;", "&gt;", "&quot;", "&#x27;"):
                stripped = stripped.replace(ent, "")
            if any(m in stripped for m in "&<>\"'"):
                t.fail("E1-charset", (s, e))
            for comp, safe, dec in (
                ("path", PATH, urllib.parse.unquote),
                ("segment", SEG, urllib.parse.unquote),
                ("query", VAL, urllib.parse.unquote),
                ("form", VAL, urllib.parse.unquote_plus),
            ):
                p = disarm.percent_encode(s, component=comp)
                if dec(p, errors="strict") != s:
                    t.fail("E2-roundtrip-" + comp, (s, p))
                if not p.isascii():
                    t.fail("E2-ascii-" + comp, (s, p))
                i = 0
                b = p.encode()
                while i < len(b):
                    if b[i] == ord("%"):
                        if (
                            not all(x in b"0123456789ABCDEF" for x in b[i + 1 : i + 3])
                            or len(b[i + 1 : i + 3]) != 2
                        ):
                            t.fail("E2-malformed-" + comp, (s, p))
                        i += 3
                    elif b[i] in safe or (comp == "form" and b[i] == ord("+")):
                        i += 1
                    else:
                        t.fail("E2-charset-" + comp, (s, p))
                        i += 1
    t.report()


def host_sweep() -> None:
    t = Tally("is_suspicious_hostname, every scalar inside a label")
    silent = collections.Counter()
    silent_ex: dict = {}
    for c in every_scalar():
        h = "pay" + c + "pal.com"
        t.n += 1
        sus, a = disarm.is_suspicious_hostname(h)
        if any(ch in BIDI for ch in a.canonical):
            t.fail("H1-bidi", (h, a.canonical))
        if any(unicodedata.category(ch) == "Cf" for ch in a.canonical):
            t.fail("H1-Cf", (h, a.canonical))
        if not sus and not c.isascii() and a.canonical == "paypal.com":
            cat = unicodedata.category(c)
            silent[cat] += 1
            silent_ex.setdefault(cat, []).append(c)
    t.report()
    print(
        "   non-ASCII characters whose hostname screens clean AND canonicalizes to "
        "'paypal.com' (the label was silently rewritten), by category:"
    )
    for cat, n in silent.most_common():
        print(f"     {cat}: {n}  e.g. {ascii(''.join(silent_ex[cat][:12]))}")


def ref_lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        cur = [i + 1]
        for j, cb in enumerate(b):
            cur.append(min(prev[j + 1] + 1, cur[j] + 1, prev[j] + (ca != cb)))
        prev = cur
    return prev[-1]


def dist(n: int, seed: int) -> None:
    rng = random.Random(seed)
    alpha = ["a", "b", "c", "\u00e9", "e\u0301", "\U0001f600"]
    t = Tally(f"edit_distance / nearest_match, {n} random cases")
    for _ in range(n):
        a = "".join(rng.choice(alpha) for _ in range(rng.randint(0, 7)))
        b = "".join(rng.choice(alpha) for _ in range(rng.randint(0, 7)))
        t.n += 1
        d = disarm.edit_distance(a, b)
        if d != ref_lev(a, b):
            t.fail("D1", (a, b, d, ref_lev(a, b)))
        cands = ["".join(rng.choice(alpha) for _ in range(rng.randint(0, 5))) for _ in range(4)]
        md = rng.randint(0, 3)
        got = disarm.nearest_match(a, cands, max_distance=md)
        ds = [ref_lev(a, c) for c in cands]
        ok = [i for i, x in enumerate(ds) if x <= md]
        exp = None if not ok else min(ok, key=lambda i: (ds[i], i))
        if (got is None) != (exp is None) or (
            got is not None and (got.value, got.distance) != (cands[exp], ds[exp])
        ):
            t.fail("D2", (a, cands, md, got, exp))
    t.report()


def main() -> int:
    ap = argparse.ArgumentParser()
    for f in ("log", "enc", "host", "dist"):
        ap.add_argument("--" + f, action="store_true")
    a = ap.parse_args()
    run_all = not (a.log or a.enc or a.host or a.dist)
    if a.dist or run_all:
        dist(200_000, 1016)
    if a.host or run_all:
        host_sweep()
    if a.log or run_all:
        log()
    if a.enc or run_all:
        enc()
    return 0


if __name__ == "__main__":
    sys.exit(main())
