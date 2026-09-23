#!/usr/bin/env python3
"""Direct sweep of `sanitize_filename` against its security postconditions.

    python3 scripts/sweep_filename.py [--scalars] [--reserved] [--lengths]

No model involved: every check here is run on the built library. Non-ASCII test data is
written as escapes only.

Postconditions checked (P1-P9, named in README.md):

  P1 non-empty                    P6 no leading dot/space, no trailing dot/space
  P2 not "." or ".."              P7 byte length <= max_length (when max_length > 0)
  P3 no platform-illegal char     P8 Windows modes: not a reserved device name
  P4 no control character (Cc)       (stem before the first dot, after Windows' own
  P5 no Cf character                  trailing dot/space strip; any case; COM/LPT with
                                      superscript digits 1-3 as Microsoft lists them)
  P9 idempotent: f(f(x)) == f(x) with the same arguments
"""

from __future__ import annotations

import argparse
import collections
import itertools
import sys
import unicodedata

import disarm

UNIVERSAL_ILLEGAL = set('/\\:*?"<>|\x00')
POSIX_ILLEGAL = set("/\x00")
RESERVED = (
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{i}" for i in range(10)]
    + [f"LPT{i}" for i in range(10)]
    + ["CLOCK$", "KEYBD$", "SCREEN$"]
)
# Microsoft's naming-a-file page also lists COM and LPT followed by superscript 1-3.
SUPERSCRIPTS = ["\u00b9", "\u00b2", "\u00b3"]
RESERVED_WIN = set(RESERVED) | {p + s for p in ("COM", "LPT") for s in SUPERSCRIPTS}


def windows_stem(name: str) -> str:
    """What Windows compares against the device list: trailing dots/spaces of the whole
    name are dropped by Win32 path normalisation, then the part before the first dot,
    with its own trailing spaces dropped (RtlIsDosDeviceName_U)."""
    n = name.rstrip(". ")
    return n.split(".", 1)[0].rstrip(" ")


def violations(out: str, *, platform: str, max_length: int) -> list[str]:
    v = []
    if out == "":
        v.append("P1")
    if out in (".", ".."):
        v.append("P2")
    illegal = POSIX_ILLEGAL if platform == "posix" else UNIVERSAL_ILLEGAL
    if any(c in illegal for c in out):
        v.append("P3")
    if any(unicodedata.category(c) == "Cc" for c in out):
        v.append("P4")
    if any(unicodedata.category(c) == "Cf" for c in out):
        v.append("P5")
    if out[:1] in (".", " ") or out[-1:] in (".", " "):
        v.append("P6")
    if max_length > 0 and len(out.encode("utf-8")) > max_length:
        v.append("P7")
    if platform != "posix" and windows_stem(out).upper() in RESERVED_WIN:
        v.append("P8")
    return v


class Tally:
    def __init__(self) -> None:
        self.n = 0
        self.bad: dict[str, int] = collections.Counter()
        self.first: dict[str, tuple] = {}

    def check(self, text: str, **kw) -> None:
        self.n += 1
        out = disarm.sanitize_filename(text, **kw)
        v = violations(
            out, platform=kw.get("platform", "universal"), max_length=kw.get("max_length", 255)
        )
        again = disarm.sanitize_filename(out, **kw)
        if again != out:
            v.append("P9")
        for p in v:
            self.bad[p] += 1
            # keep the shortest witness per property
            prev = self.first.get(p)
            if prev is None or len(text) < len(prev[0]):
                self.first[p] = (text, kw, out, again)

    def report(self, title: str) -> None:
        print(f"== {title}: {self.n} calls")
        if not self.bad:
            print("   all postconditions hold")
        for p in sorted(self.bad):
            text, kw, out, again = self.first[p]
            print(
                f"   {p}: {self.bad[p]} violations; shortest: "
                f"sanitize_filename({text!r}, **{kw!r}) -> {out!r} (again -> {again!r})"
            )


def scalars() -> None:
    for platform in ("universal", "windows", "posix"):
        t = Tally()
        for cp in range(0x110000):
            if 0xD800 <= cp <= 0xDFFF:
                continue
            c = chr(cp)
            for text in (c, "a" + c + "b.txt", c + ".con", "CON" + c, "x" + c + c + "y"):
                t.check(text, platform=platform)
        t.report(f"every scalar alone and embedded, platform={platform}")


def reserved() -> None:
    t = Tally()
    names = sorted(RESERVED_WIN) + ["CONIN$", "CONOUT$"]
    exts = ["", ".txt", ".tar.gz", ".", ".con"]
    trails = ["", ".", " ", "..", " .", ". "]
    prefixes = ["", "*", "_", " ", ".", "/", "a/", "?"]
    seps = ["_", "-", "", " "]
    for name in names:
        for cased in {name.upper(), name.lower(), name[:1].lower() + name[1:]}:
            for ext, trail, pre in itertools.product(exts, trails, prefixes):
                for text in (pre + cased + trail + ext, pre + "." + cased + trail):
                    for sep in seps:
                        for ml in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 255):
                            for pe in (True, False):
                                for platform in ("universal", "windows"):
                                    t.check(
                                        text,
                                        separator=sep,
                                        max_length=ml,
                                        preserve_extension=pe,
                                        platform=platform,
                                    )
    t.report("reserved name x case x extension x trailing x prefix x separator x max_length")


def lengths() -> None:
    t = Tally()
    stems = ["abcdefgh", "ab_cd_ef", "a.bcd.ef", "ab cd ef", "a..b..c", "CONtest", "a*b*c*d"]
    exts = ["", ".txt", ".t", ".longext", "."]
    for stem, ext in itertools.product(stems, exts):
        text = stem + ext
        for ml in range(0, len(text) + 3):
            for pe in (True, False):
                for sep in ("_", "-", ""):
                    for platform in ("universal", "posix"):
                        t.check(
                            text,
                            separator=sep,
                            max_length=ml,
                            preserve_extension=pe,
                            platform=platform,
                        )
    t.report("every max_length boundary")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scalars", action="store_true")
    ap.add_argument("--reserved", action="store_true")
    ap.add_argument("--lengths", action="store_true")
    a = ap.parse_args()
    run_all = not (a.scalars or a.reserved or a.lengths)
    if a.lengths or run_all:
        lengths()
    if a.reserved or run_all:
        reserved()
    if a.scalars or run_all:
        scalars()
    return 0


if __name__ == "__main__":
    sys.exit(main())
