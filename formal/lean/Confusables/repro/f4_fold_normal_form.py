#!/usr/bin/env python3
"""F4: normalize_confusables is not invariant to the input's normal form.

compose-at-lookup (compose.rs:179) anchors a cluster only on a following combining
mark, so a starter + starter composition (Kirat Rai, Unicode 16) is left decomposed.
The fold of NFC(x) and of NFD(x) then differ, against api/safety.rs:106-110. It is the
only such class in Unicode 17 (probe `starters`). Checks.lean F4_fold_nf.
Exits 0 when the failure reproduces.
"""

import disarm

bad = []
for cp in (0x16D68, 0x16D69, 0x16D6A):
    c = chr(cp)
    d = disarm.normalize(c, form="NFD")
    a, b = disarm.normalize_confusables(c), disarm.normalize_confusables(d)
    print(f"U+{cp:04X}: fold(NFC) = {ascii(a)}   fold(NFD) = {ascii(b)}")
    bad.append(a != b)
raise SystemExit(0 if all(bad) else 1)
