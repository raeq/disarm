#!/usr/bin/env python3
"""Every Unicode scalar against each detector/cleaner pair the documentation ties together.

    python3 scripts/sweep_cleaners.py [--jobs N]

For each scalar `c` (surrogates excluded) and each context `c`, `pay<c>pal`, `1<c>2`:

* census: `has_bidi_control(s)` against `strip_bidi(s) != s`;
* `has_anomalies(s)` against `inspect_anomalies(s).anomalous`;
* `is_canonical(s)` against `canonicalize(s) == s`;
* the doc's one-way claim (`docs/api/predicates.md`): `has_anomalies(c)` implies
  `canonicalize(c) != c`;
* cleaner soundness: a cleaner that deletes `c` from `pay<c>pal` implies
  `has_anomalies("pay<c>pal")`, for `strip_zero_width_chars`, `strip_tags`,
  `strip_control_chars` and `canonicalize` (deleting exactly `c`).

Prints each violated pair with the code points, grouped into ranges.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from collections import defaultdict
from multiprocessing import Pool

import disarm


def pua(cp: int) -> bool:
    return 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0xFFFFD or 0x100000 <= cp <= 0x10FFFD


def check(cp: int):
    out = []
    c = chr(cp)
    word = "pay" + c + "pal"
    for s in (c, word, "1" + c + "2"):
        if disarm.has_bidi_control(s) != (disarm.strip_bidi(s) != s):
            out.append(("census: has_bidi_control != (strip_bidi changes)", cp))
        if disarm.has_anomalies(s) != disarm.inspect_anomalies(s).anomalous:
            out.append(("has_anomalies != inspect_anomalies.anomalous", cp))
        if disarm.is_canonical(s) != (disarm.canonicalize(s) == s):
            out.append(("is_canonical != (canonicalize is identity)", cp))
    if disarm.has_anomalies(c) and disarm.canonicalize(c) == c:
        out.append(("flagged and already canonical (doc: 0)", cp))
    if c not in "paypal" and not disarm.has_anomalies(word):
        for name, f in (
            ("strip_zero_width_chars", disarm.strip_zero_width_chars),
            ("strip_tags", disarm.strip_tags),
            ("strip_control_chars", disarm.strip_control_chars),
            ("canonicalize", disarm.canonicalize),
        ):
            if f(word) == "paypal":
                out.append(
                    (
                        f"{name} deletes it from a word, detector silent"
                        + (" [PUA]" if pua(cp) else ""),
                        cp,
                    )
                )
    return out


def ranges(cps):
    cps = sorted(set(cps))
    out, start, prev = [], None, None
    for x in cps:
        if prev is not None and x == prev + 1:
            prev = x
            continue
        if start is not None:
            out.append((start, prev))
        start = prev = x
    if start is not None:
        out.append((start, prev))
    return ", ".join(f"U+{a:04X}" if a == b else f"U+{a:04X}-{b:04X}" for a, b in out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    cps = [cp for cp in range(0x110000) if not 0xD800 <= cp <= 0xDFFF]
    with Pool(args.jobs) as pool:
        results = pool.map(check, cps, chunksize=4000)
    by = defaultdict(list)
    for r in results:
        for name, cp in r:
            by[name].append(cp)
    print(f"{len(cps)} scalars")
    for name, v in sorted(by.items()):
        cats = sorted({unicodedata.category(chr(cp)) for cp in v})
        shown = ranges(v) if len(v) < 2000 else f"{len(v)} code points"
        print(f"{name}: {len(set(v))} code points {cats}\n    {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
