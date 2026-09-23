"""Premises for `context=True` (Arabic / Persian / Hebrew dictionary engine).

The context dictionaries are not committed (built from a Kaggle corpus by
`scripts/bootstrap_dicts.sh`), so this script writes a *minimal valid*
dictionary in the documented `TRLD` v1 format (see `src/context.rs::build`)
into a temporary directory and points `DISARM_DICT_DIR` at it. The dictionary
content is irrelevant to the findings: every word the dictionary does not know
falls back to context-free transliteration, and the defect found here is in
how *non-word* spans are handled, which never consults the dictionary.

Checks, for lang in {ar, fa, he} x errors in {ignore, replace, preserve} x
scheme in {default, strict_iso9, gost7034}:
  I1  ASCII passthrough (all 128 ASCII chars + random ASCII strings)
  I2  ASCII output under errors='ignore'
  I3  f(f(s)) == f(s)
  I7  len(f(s)) <= 5*bytes(s) + chars(s)
  H   f(a+b) == f(a)+f(b)
over: every BMP scalar on its own, and every BMP scalar next to an Arabic/Hebrew
word.

Run:  python3 context_dict.py [--json out.json]
"""

from __future__ import annotations

import argparse
import os
import random
import struct
import tempfile


def u16(n: int) -> bytes:
    return struct.pack("<H", n)


def u32(n: int) -> bytes:
    return struct.pack("<I", n)


def s16(s: str) -> bytes:
    b = s.encode("utf-8")
    return u16(len(b)) + b


def build_dict(unigrams: dict[str, str]) -> bytes:
    """TRLD v1: header(24) | unigrams | bigrams (none)."""
    body = b""
    for skel, form in sorted(unigrams.items()):
        body += s16(skel) + u16(1) + s16(form) + u32(1)
    uni_off = 24
    bi_off = 24 + len(body)
    header = b"TRLD" + u32(1) + u32(len(unigrams)) + u32(0) + u32(uni_off) + u32(bi_off)
    return header + body


def install_dicts() -> str:
    d = tempfile.mkdtemp(prefix="disarm-ctx-")
    # One real-looking entry each (skeleton -> vocalised form); content is incidental.
    with open(os.path.join(d, "arabic_dict.bin"), "wb") as fh:
        fh.write(build_dict({"كتب": "كَتَبَ"}))
    with open(os.path.join(d, "persian_dict.bin"), "wb") as fh:
        fh.write(build_dict({"سلام": "سَلام"}))
    with open(os.path.join(d, "hebrew_dict.bin"), "wb") as fh:
        fh.write(build_dict({"שלום": "שָׁלוֹם"}))
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args()

    os.environ["DISARM_DICT_DIR"] = install_dicts()
    # Import only after the env var is set: dictionaries load lazily, once.
    from common import Opts, Tally, all_scalars, dump, i7_bound

    tallies = {k: Tally(keep=4) for k in ("I1", "I2", "I3", "I7", "H")}
    words = {"ar": "كتب", "fa": "سلام", "he": "שלום"}
    rng = random.Random(3)
    ascii_strings = [chr(i) for i in range(128)] + [
        "".join(chr(rng.randrange(128)) for _ in range(rng.randrange(1, 40))) for _ in range(2000)
    ]
    bmp = list(all_scalars(0x80, 0xFFFF))

    for lang in ("ar", "fa", "he"):
        for errors in ("ignore", "replace", "preserve"):
            for iso9, gost in ((False, False), (True, False), (False, True)):
                o = Opts(lang, errors, iso9, gost, context=True)
                lab = o.label()
                for s in ascii_strings:
                    r = o.f(s)
                    if r == s:
                        tallies["I1"].ok()
                    else:
                        tallies["I1"].fail(lab, {"input": s, "f(s)": r, "call": o.call_repr(s)})
                w = words[lang]
                fw = o.f(w)
                for c in bmp:
                    for s in (c, w + " " + c, c + w):
                        r = o.f(s)
                        if errors == "ignore":
                            if r.isascii():
                                tallies["I2"].ok()
                            else:
                                tallies["I2"].fail(
                                    lab, {"input": s, "f(s)": r, "call": o.call_repr(s)}
                                )
                        rr = o.f(r)
                        if rr == r:
                            tallies["I3"].ok()
                        else:
                            tallies["I3"].fail(
                                lab, {"input": s, "f(s)": r, "f(f(s))": rr, "call": o.call_repr(s)}
                            )
                        if errors == "ignore":
                            if len(r) <= i7_bound(s):
                                tallies["I7"].ok()
                            else:
                                tallies["I7"].fail(
                                    lab, {"input": s, "f(s)": r, "bound": i7_bound(s)}
                                )
                    fc = o.f(c)
                    r = o.f(c + w)
                    if r == fc + fw:
                        tallies["H"].ok()
                    else:
                        tallies["H"].fail(lab, {"input": c + w, "f(s)": r, "concat f(c)": fc + fw})

    res = {k: v.to_json() for k, v in tallies.items()}
    for k, v in res.items():
        print(f"{k}: {v['checked']:,} checked, {sum(v['failures'].values()):,} failures")
        for lab, n in sorted(v["failures"].items()):
            ex = v["examples"][lab][0]
            print(f"   {n:>8,d}  {lab:45s} e.g. {ex['input']!a} -> {ex['f(s)']!a}")
    if args.json:
        dump(res, args.json)


if __name__ == "__main__":
    main()
