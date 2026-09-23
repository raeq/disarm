#!/usr/bin/env python3
"""Random strings through every detector.

    python3 scripts/fuzz.py [SEED] [N]

Checks, over N random strings from a 61-character alphabet of the classes the detectors
branch on (a small lexicon is passed, so `leet` and `segmentation` run too):

* no detector function raises (a Rust panic surfaces as an exception);
* `has_anomalies` agrees with `inspect_anomalies(...).anomalous`;
* locality: `has_anomalies(a + sep + b) == has_anomalies(a) or has_anomalies(b)` for a
  space and a line feed, on pairs with no `CR` (the proved cases, `Props.lean`).

The README's run is `python3 scripts/fuzz.py 11 1000000`.
"""

import random
import sys

import disarm

rnd = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
ALPHA = list("ae1 .-@$|!0") + [
    chr(c)
    for c in (
        0x00E9,
        0x0301,
        0x0302,
        0x05D0,
        0x0430,
        0x03BF,
        0x200B,
        0x200C,
        0x200D,
        0x2060,
        0xFEFF,
        0x00AD,
        0x034F,
        0xFE0F,
        0xFE01,
        0xE0100,
        0xE0061,
        0xE0067,
        0xE0062,
        0xE0073,
        0xE0063,
        0xE0074,
        0xE007F,
        0x1F3F4,
        0xE000,
        0x202E,
        0x2067,
        0x202B,
        0x200F,
        0x200E,
        0x061C,
        0x0007,
        0x0008,
        0x000D,
        0x000A,
        0x0085,
        0x2028,
        0x00A0,
        0x200A,
        0x0663,
        0xFF41,
        0x0251,
        0x20DD,
        0x0488,
        0x206A,
        0x3164,
        0x1D173,
        0x2236,
        0x00BD,
        0x0385,
    )
]
LEX = {"free", "admin", "paypal", "ignore", "login", "password", "iogin"}


def rs(n):
    return "".join(rnd.choice(ALPHA) for _ in range(n))


bad = {"has_vs_inspect": 0, "locality": 0, "panic": 0}
pairs = 0
ex = {}
fns = [
    disarm.detect_scripts,
    disarm.is_mixed_script,
    disarm.has_bidi_conflict,
    disarm.has_bidi_control,
    disarm.decode_smuggled,
    disarm.is_confusable,
    disarm.canonicalize,
    disarm.is_canonical,
    disarm.is_zalgo,
    lambda s: disarm.is_mixed_script(s, per_word=True),
    lambda s: disarm.has_bidi_conflict(s, per_word=True),
    disarm.is_suspicious_hostname,
    disarm.find_confusables,
]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 100000
for _ in range(N):
    s = rs(rnd.randint(0, 14))
    try:
        h = disarm.has_anomalies(s, LEX)
        r = disarm.inspect_anomalies(s, LEX)
        for f in fns:
            f(s)
    except BaseException as e:  # noqa: BLE001 - a panic is what is being looked for
        bad["panic"] += 1
        ex.setdefault("panic", (s, repr(e)))
        continue
    if h != r.anomalous:
        bad["has_vs_inspect"] += 1
        ex.setdefault("has_vs_inspect", s)
    a, b = rs(rnd.randint(0, 7)), rs(rnd.randint(0, 7))
    if "\r" in a + b:
        continue
    pairs += 1
    for sep in (" ", "\n"):
        joined = disarm.has_anomalies(a + sep + b, LEX)
        if joined != (disarm.has_anomalies(a, LEX) or disarm.has_anomalies(b, LEX)):
            bad["locality"] += 1
            ex.setdefault("locality", (a, sep, b))
print(f"{N} strings, {pairs} CR-free pairs:", bad)
print(ascii(ex))
