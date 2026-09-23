#!/usr/bin/env python3
"""F2: under digit_policy="preserve", normalize_confusables returns text that
is_confusable flags, against "its output is never itself confusable".

Checks.lean F2_preserve_incomplete: the one-character witness DEVANAGARI DIGIT ZERO.
Exits 0 when the failure reproduces.
"""

import disarm

out = disarm.normalize_confusables("\u0966", digit_policy="preserve")
print("normalize_confusables('\\u0966', digit_policy='preserve') =", ascii(out))
print("is_confusable(that)                                      =", disarm.is_confusable(out))
count = sum(
    1
    for cp in range(0x110000)
    if not 0xD800 <= cp <= 0xDFFF
    and disarm.is_confusable(disarm.normalize_confusables(chr(cp), digit_policy="preserve"))
)
print("single code points whose preserve-fold is still confusable (latin):", count)
raise SystemExit(0 if disarm.is_confusable(out) else 1)
