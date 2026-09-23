"""Direct string-level checks of I1, I2, I3 and I7 under every option profile.

Unlike `tests/exhaustive_transliterate.rs` (default options only, one code point
at a time), this sweeps
  * every Unicode scalar (U+0000..U+10FFFF) under the core profiles
    (lang in {None, 'auto'} x scheme in {default, strict_iso9, gost7034}
     x tones in {False, True} x errors in {ignore, replace, preserve}),
  * every BMP scalar under each of the 83 built-in `lang=` profiles (x tones),
  * random multi-character strings (length 2..12, mixed scripts, with
    combining marks, jamo and viramas over-represented) under every profile,
and records
  I1  ASCII in  -> output identical
  I2  errors='ignore' -> output ASCII
  I3  f(f(s)) == f(s)   (for every errors mode; the docs state it for 'ignore')
  I7  len(f(s)) <= 5*bytes(s) + chars(s)   (for errors='ignore'; the audit ran with the
      old bound, 4*bytes, and found U+337F over it: see the README, F3)
  NF  f(s) == f(NFC(s)) == f(NFD(s))   (the #477 normal-form-invariance claim that
      the compose-at-lookup boundary is meant to guarantee; a side premise)

Run:  python3 invariants.py [--quick] [--json out.json]
"""

from __future__ import annotations

import argparse
import random
import time
import unicodedata

from common import Opts, Tally, all_scalars, block, dump, i7_bound, langs

ERRORS = ("ignore", "replace", "preserve")


def core_profiles(errors_modes=ERRORS) -> list[Opts]:
    out = []
    for e in errors_modes:
        for lg in (None, "auto"):
            for iso, gost in ((False, False), (True, False), (False, True)):
                for tones in (False, True):
                    out.append(Opts(lg, e, iso, gost, tones))
    return out


def lang_profiles() -> list[Opts]:
    return [Opts(lg, "ignore", tones=t) for lg in langs() for t in (False, True)]


def string_pool(n: int, seed: int = 11) -> list[str]:
    rng = random.Random(seed)
    bmp = block(0x80, 0xFFFF)
    smp = [c for c in block(0x10000, 0x1FFFF)]
    marks = (
        block(0x0300, 0x036F)
        + block(0x0591, 0x05C7)
        + block(0x064B, 0x065F)
        + block(0x3099, 0x309A)
    )
    jamo = block(0x1100, 0x11FF)
    indic = block(0x0900, 0x0DFF)
    cjk = block(0x4E00, 0x9FFF) + block(0xF900, 0xFAFF)
    kana = block(0x3040, 0x30FF)
    ascii_ = [chr(c) for c in range(0x20, 0x7F)]
    buckets = [bmp, bmp, smp, marks, jamo, indic, cjk, kana, ascii_]
    out = []
    for _ in range(n):
        k = rng.randrange(2, 13)
        out.append("".join(rng.choice(rng.choice(buckets)) for _ in range(k)))
    return out


class Checks:
    def __init__(self) -> None:
        self.t = {k: Tally(keep=4) for k in ("I1", "I2", "I3", "I7", "NF")}
        self.i7_worst: tuple[int, str, str] = (-(10**9), "", "")

    def run(self, o: Opts, s: str, nf: bool = True) -> None:
        r = o.f(s)
        lab = o.label()
        if s.isascii():
            if r == s:
                self.t["I1"].ok()
            else:
                self.t["I1"].fail(lab, {"input": s, "f(s)": r, "call": o.call_repr(s)})
        if o.errors == "ignore":
            if r.isascii():
                self.t["I2"].ok()
            else:
                self.t["I2"].fail(lab, {"input": s, "f(s)": r, "call": o.call_repr(s)})
            slack = len(r) - i7_bound(s)
            if slack > self.i7_worst[0]:
                self.i7_worst = (slack, s, r)
            if slack <= 0:
                self.t["I7"].ok()
            else:
                self.t["I7"].fail(lab, {"input": s, "f(s)": r, "bound": i7_bound(s)})
        rr = o.f(r)
        if rr == r:
            self.t["I3"].ok()
        else:
            self.t["I3"].fail(lab, {"input": s, "f(s)": r, "f(f(s))": rr, "call": o.call_repr(s)})
        if nf:
            for form in ("NFC", "NFD"):
                s2 = unicodedata.normalize(form, s)
                if s2 != s:
                    r2 = o.f(s2)
                    if r2 == r:
                        self.t["NF"].ok()
                    else:
                        self.t["NF"].fail(
                            f"{lab} | {form}",
                            {"input": s, "f(s)": r, f"f({form}(s))": r2, "call": o.call_repr(s)},
                        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    ck = Checks()

    t0 = time.time()
    hi = 0xFFFF if a.quick else 0x10FFFF
    scalars = list(all_scalars(0, hi))
    for o in core_profiles():
        for c in scalars:
            ck.run(o, c)
    print(f"core profiles x {len(scalars):,} scalars: {time.time() - t0:.0f}s", flush=True)

    t0 = time.time()
    bmp = list(all_scalars(0, 0xFFFF))
    for o in lang_profiles():
        for c in bmp:
            ck.run(o, c, nf=False)
    print(
        f"{len(lang_profiles())} lang profiles x {len(bmp):,} BMP scalars: {time.time() - t0:.0f}s",
        flush=True,
    )

    t0 = time.time()
    pool = string_pool(2_000 if a.quick else 20_000)
    for o in core_profiles() + lang_profiles():
        for s in pool:
            ck.run(o, s)
    print(
        f"{len(core_profiles()) + len(lang_profiles())} profiles x {len(pool):,} random strings: {time.time() - t0:.0f}s",
        flush=True,
    )

    res = {k: v.to_json() for k, v in ck.t.items()}
    res["I7_worst_slack"] = {
        "slack": ck.i7_worst[0],
        "input": ck.i7_worst[1],
        "f(s)": ck.i7_worst[2],
    }
    for k in ("I1", "I2", "I3", "I7", "NF"):
        v = res[k]
        print(f"\n{k}: {v['checked']:,} checked, {sum(v['failures'].values()):,} failures")
        agg: dict[str, int] = {}
        for lab, n in v["failures"].items():
            agg[lab] = agg.get(lab, 0) + n
        for lab, n in sorted(agg.items(), key=lambda kv: -kv[1])[:25]:
            ex = v["examples"][lab][0]
            print(f"   {n:>9,d}  {lab:50s} e.g. {ex['input']!a} -> {ex['f(s)']!a}")
    print("\nI7 worst slack (len(f(s)) - bound, <=0 means within bound):", res["I7_worst_slack"])
    if a.json:
        dump(res, a.json)


if __name__ == "__main__":
    main()
