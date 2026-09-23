"""Finding 1: `skeleton_key` is not a fixed point, and misses a confusable pair.

Model: `Findings.skeleton_once`, `skeleton_twice`, `skeleton_misses_pair`, `skeleton_cgj`.
"""

from __future__ import annotations

import functools

from common import show, w

import disarm

for pol in ("numeric", "tr39", "preserve"):
    f = functools.partial(disarm.skeleton_key, digit_policy=pol)
    show(f"skeleton_key[{pol}] U+03B0", w(0x3B0), f)
    show(f"skeleton_key[{pol}] yen + acute", w(0xA5, 0x301), f)
    show(f"skeleton_key[{pol}] e + CGJ + acute", w(0x65, 0x34F, 0x301), f)
    show(f"skeleton_key[{pol}] I-dot + U+20D2", w(0x130, 0x20D2), f)

print()
yen = disarm.skeleton_key(w(0xA5, 0x301))
cap = disarm.skeleton_key(w(0xDD))
print("yen + acute keys to", ascii(yen), "; Y-acute keys to", ascii(cap), "; collide:", yen == cap)
print("output is NFC:", disarm.is_normalized(yen, form="NFC"))
