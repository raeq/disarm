#!/usr/bin/env python3
"""F3: the #458 fast-path guard skips a canonical composition NFKC performs.

KIRAT RAI VOWEL SIGN E (U+16D67, Unicode 16) is a starter that composes with the starter
before it: U+16D67 U+16D67 is the NFD of U+16D68. The guard (presets.rs:780) exempts
only conjoining jamo from its per-character NFKC test, so under the default policy the
presets return the input unnormalized, while any other digit_policy (which bypasses the
guard) composes it. Checks.lean F3_guard / F3_nf / F3_policy.
Exits 0 when the failure reproduces.
"""

import disarm

nfd = "\U00016d67\U00016d67"
nfc = disarm.normalize(nfd, form="NFC")
print("NFC of U+16D67 U+16D67 =", ascii(nfc))
ok = []
for name in ("skeleton_key", "canonicalize", "canonicalize_strict"):
    f = getattr(disarm, name)
    a, b, c = f(nfd), f(nfd, digit_policy="tr39"), f(nfc)
    print(
        f"{name}(nfd) = {ascii(a)}   {name}(nfd, digit_policy='tr39') = {ascii(b)}   {name}(nfc) = {ascii(c)}"
    )
    ok.append(a != b and a != c)
print("reproduced:", ok)
raise SystemExit(0 if all(ok) else 1)
